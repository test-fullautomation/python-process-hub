#  Copyright 2020-2026 Robert Bosch GmbH
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# *******************************************************************************
#
# File: hub_core.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   ProcessHubCore - pure business logic, no I/O.
#   This module implements improvement 3.1: Separate core logic vs. runtime.
#   Owns ProcessRegistry, ConnectionRegistry, RestartStateMachine.
#   Exposes handle_message() -> returns outgoing messages.
#   Has no direct knowledge of ZMQ, no TUI.
#
# Original author:
#   Nguyen Tan Phat (MS/EMC51)
#
# Original file:
#   ta-framework-tsb/ta_framework/project/process_hub/process_hub_server.py
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
ProcessHubCore - pure business logic, no I/O.

This module implements improvement 3.1:

- Separate core logic vs. runtime

- Owns ProcessRegistry, ConnectionRegistry, RestartStateMachine

- Exposes handle_message() -> returns outgoing messages

- Has no direct knowledge of ZMQ, no TUI

Benefits:

- Immediately improves testability

- Makes it possible to embed Process Hub inside other processes/transports
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Protocol

from .models import (
    ConnectionInfoRequest,
    ConnectionInfoResponse,
    ConnectionSnapshot,
    HubStateSnapshot,
    MessageBase,
    ProcessRestartDone,
    ProcessRestartNotify,
    ProcessRestartReady,
    ProcessStartRequest,
    ProcessStartResponse,
    ProcessState,
    ProcessStopRequest,
    ProcessStopResponse,
    RegisterConnectionRequest,
    RegisterConnectionResponse,
    ServerShutdownNotify,
    UnregisterConnectionRequest,
    UnregisterConnectionResponse,
)
from .process_registry import ProcessRegistry
from .restart_state import RestartState, RestartStateMachine

logger = logging.getLogger(__name__)


# ============================================================================
# Types
# ============================================================================


class MessageType(Enum):
    """
MessageType: Outgoing message types for transport routing.
    """

    REGISTER_RESPONSE = "REGISTER_CONNECTION_RESPONSE"
    UNREGISTER_RESPONSE = "UNREGISTER_CONNECTION_RESPONSE"
    CONNECTION_INFO_RESPONSE = "CONNECTION_INFO_RESPONSE"
    START_RESPONSE = "PROCESS_START_RESPONSE"
    STOP_RESPONSE = "PROCESS_STOP_RESPONSE"
    RESTART_NOTIFY = "PROCESS_RESTART_NOTIFY"
    RESTART_DONE = "PROCESS_RESTART_DONE"
    SHUTDOWN_NOTIFY = "SERVER_SHUTDOWN_NOTIFY"


@dataclass
class OutgoingMessage:
    """
OutgoingMessage: Wrapper for outgoing messages.

Used by runtime to route messages to transport layer.
    """

    msg_type: MessageType
    payload: MessageBase
    target_panel: Optional[str] = None  # None = broadcast to topic


class ProcessExecutorProtocol(Protocol):
    """
ProcessExecutorProtocol: Protocol for process executor callbacks.
    """

    def start_process(self, name: str) -> tuple[bool, str, Optional[int]]:
        """
Start a process.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The name of the process to start.

**Returns:**

  / *Type*: tuple[bool, str, Optional[int]] /

  A tuple of (success, message, pid).
        """
        ...

    def stop_process(self, name: str, force: bool = False) -> bool:
        """
Stop a process.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The name of the process to stop.

* ``force``

  / *Condition*: optional / *Type*: bool / *Default*: False /

  If True, force stop the process without graceful shutdown.

**Returns:**

  / *Type*: bool /

  True if the process was stopped successfully, False otherwise.
        """
        ...

    def is_running(self, name: str) -> bool:
        """
Check if process is running.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The name of the process to check.

**Returns:**

  / *Type*: bool /

  True if the process is running, False otherwise.
        """
        ...


# ============================================================================
# Connection Info
# ============================================================================


@dataclass
class ConnectionInfo:
    """
ConnectionInfo: Connection metadata for a panel.
    """

    panel_id: str
    session_id: str
    session_panel_ids: list[str] = field(default_factory=list)
    connected_at: float = field(default_factory=time.time)


# ============================================================================
# ProcessHubCore
# ============================================================================


class ProcessHubCore:
    """
ProcessHubCore: Core hub logic - testable without I/O.

This class contains all business logic for process management:

- Connection registration/unregistration

- Process start/stop requests

- Restart coordination

- Health check detection

It does NOT know about:
- ZMQ or any transport

- TUI or any display

- File I/O or logging configuration

Usage:

    # Create with executor callbacks

    core = ProcessHubCore(

        process_starter=my_start_func,

        process_stopper=my_stop_func,

        health_checker=my_health_func,
    )

    # Handle incoming message

    outgoing = core.handle_register(request)

    for msg in outgoing:

        transport.send(msg.msg_type.value, msg.payload)

    # Periodic tick (health check)

    outgoing = core.tick()

    for msg in outgoing:

        transport.send(msg.msg_type.value, msg.payload)

    # Get state for UI

    snapshot = core.get_state_snapshot()
    """

    def __init__(
        self,
        process_starter: Callable[[str], tuple[bool, str, Optional[int]]],
        process_stopper: Callable[[str, bool], bool],
        health_checker: Callable[[list[str]], list[str]],
        restart_timeout: float = 300.0,
        restart_max_retries: int = 3,
    ):
        """
Initialize the ProcessHubCore.

**Arguments:**

* ``process_starter``

  / *Condition*: required / *Type*: Callable[[str], tuple[bool, str, Optional[int]]] /

  Callable that starts a process. Takes process name, returns (success, message, pid).

* ``process_stopper``

  / *Condition*: required / *Type*: Callable[[str, bool], bool] /

  Callable that stops a process. Takes (process_name, force), returns success.

* ``health_checker``

  / *Condition*: required / *Type*: Callable[[list[str]], list[str]] /

  Callable that checks process health. Takes list of process names, returns list of dead process names.

* ``restart_timeout``

  / *Condition*: optional / *Type*: float / *Default*: 300.0 /

  Maximum time in seconds for restart coordination before timeout.

* ``restart_max_retries``

  / *Condition*: optional / *Type*: int / *Default*: 3 /

  Maximum restart attempts before giving up.
        """
        self._process_starter = process_starter
        self._process_stopper = process_stopper
        self._health_checker = health_checker

        # Connection state
        self._connections: dict[str, ConnectionInfo] = {}
        self._connection_lock = threading.Lock()

        # Process state
        self._registry = ProcessRegistry()

        # Restart state machine
        self._restart_fsm = RestartStateMachine(
            timeout=restart_timeout,
            max_retries=restart_max_retries,
        )

        # Operation lock - serializes process operations
        # Lock ordering: connection_lock -> operation_lock -> registry._lock
        self._operation_lock = threading.Lock()

    # ========================================================================
    # State Snapshot (3.2: immutable for UI)
    # ========================================================================

    def get_state_snapshot(self) -> HubStateSnapshot:
        """
Get immutable state snapshot for UI.

Returns frozen dataclass - no locks needed by caller. UI can safely read this without synchronization.

**Returns:**

  / *Type*: HubStateSnapshot /

  An immutable snapshot of the current hub state including connections, processes, and restart state.
        """
        # Get connection snapshot
        with self._connection_lock:
            connections = tuple(
                ConnectionSnapshot(
                    panel_id=c.panel_id,
                    session_id=c.session_id,
                    session_panel_ids=tuple(c.session_panel_ids),
                    connected_at=c.connected_at,
                )
                for c in self._connections.values()
            )

        # Get process snapshot
        processes = self._registry.get_snapshot()

        # Get restart snapshot
        restart_snapshot = self._restart_fsm.get_snapshot()

        return HubStateSnapshot(
            connections=connections,
            processes=processes,
            killed_processes=restart_snapshot["killed_processes"],
            pending_panels=restart_snapshot["pending_panels"],
            restart_state=restart_snapshot["state"],
        )

    # ========================================================================
    # Connection Management
    # ========================================================================

    def handle_register(
        self, req: RegisterConnectionRequest
    ) -> list[OutgoingMessage]:
        """
Handle connection registration.

Registers a panel and updates session groupings.

**Arguments:**

* ``req``

  / *Condition*: required / *Type*: RegisterConnectionRequest /

  The registration request containing panel_id and session_id.

**Returns:**

  / *Type*: list[OutgoingMessage] /

  List of outgoing messages to send (registration response).
        """
        with self._connection_lock:
            conn = ConnectionInfo(
                panel_id=req.panel_id,
                session_id=req.session_id,
                session_panel_ids=[req.panel_id],
            )
            self._connections[req.panel_id] = conn

            # Update session panel IDs for all panels in same session
            shared = [
                pid
                for pid, c in self._connections.items()
                if c.session_id == req.session_id
            ]
            for pid in shared:
                self._connections[pid].session_panel_ids = shared.copy()

            logger.info(
                "Registered panel %s with session %s",
                req.panel_id,
                req.session_id,
            )

        return [
            OutgoingMessage(
                msg_type=MessageType.REGISTER_RESPONSE,
                payload=RegisterConnectionResponse(
                    panel_id=req.panel_id,
                    success=True,
                    message=f"Registered panel {req.panel_id}",
                ),
                target_panel=req.panel_id,
            )
        ]

    def handle_unregister(
        self, req: UnregisterConnectionRequest
    ) -> list[OutgoingMessage]:
        """
Handle connection unregistration.

Removes panel and cleans up any orphaned processes.

**Arguments:**

* ``req``

  / *Condition*: required / *Type*: UnregisterConnectionRequest /

  The unregistration request containing panel_id.

**Returns:**

  / *Type*: list[OutgoingMessage] /

  List of outgoing messages to send (unregistration response).
        """
        with self._connection_lock:
            if req.panel_id in self._connections:
                del self._connections[req.panel_id]
                logger.info("Unregistered panel %s", req.panel_id)

        # Remove from all process requesters
        orphaned = self._registry.remove_requester_from_all(req.panel_id)

        # Stop orphaned processes (no more requesters)
        for name in orphaned:
            logger.info("Stopping orphaned process %s", name)
            self._process_stopper(name, force=True)
            self._registry.remove(name)

        return [
            OutgoingMessage(
                msg_type=MessageType.UNREGISTER_RESPONSE,
                payload=UnregisterConnectionResponse(
                    panel_id=req.panel_id,
                    message=f"Unregistered panel {req.panel_id}",
                ),
                target_panel=req.panel_id,
            )
        ]

    def handle_connection_info(
        self, req: ConnectionInfoRequest
    ) -> list[OutgoingMessage]:
        """
Handle connection info request.

**Arguments:**

* ``req``

  / *Condition*: required / *Type*: ConnectionInfoRequest /

  The request containing panel_id.

**Returns:**

  / *Type*: list[OutgoingMessage] /

  List of outgoing messages containing connection information.
        """
        with self._connection_lock:
            conn_dict = {
                pid: {
                    "session_id": c.session_id,
                    "session_panel_ids": c.session_panel_ids,
                }
                for pid, c in self._connections.items()
            }

        return [
            OutgoingMessage(
                msg_type=MessageType.CONNECTION_INFO_RESPONSE,
                payload=ConnectionInfoResponse(
                    panel_id=req.panel_id,
                    connections=conn_dict,
                ),
                target_panel=req.panel_id,
            )
        ]

    def is_registered(self, panel_id: str) -> bool:
        """
Check if panel is registered.

**Arguments:**

* ``panel_id``

  / *Condition*: required / *Type*: str /

  The panel ID to check.

**Returns:**

  / *Type*: bool /

  True if the panel is registered, False otherwise.
        """
        with self._connection_lock:
            return panel_id in self._connections

    # ========================================================================
    # Process Control
    # ========================================================================

    def handle_start_request(
        self, req: ProcessStartRequest
    ) -> list[OutgoingMessage]:
        """
Handle process start request.

Starts requested processes sequentially. On failure, rolls back all started processes.

**Arguments:**

* ``req``

  / *Condition*: required / *Type*: ProcessStartRequest /

  The start request containing panel_id and process_list.

**Returns:**

  / *Type*: list[OutgoingMessage] /

  List of outgoing messages (start response with success/failure info).
        """
        with self._operation_lock:
            failed_procs = []
            error_msg = ""
            started_procs = []

            for proc_name in req.process_list:
                # Register process with requester
                is_new = self._registry.register(proc_name, req.panel_id)
                self._registry.update_state(proc_name, ProcessState.STARTING)

                # Check if already running
                if not is_new and self._registry.get_state(proc_name) == ProcessState.RUNNING:
                    logger.info("Process %s already running", proc_name)
                    continue

                # Execute process
                logger.info("Starting process %s for panel %s", proc_name, req.panel_id)
                success, msg, pid = self._process_starter(proc_name)

                if success:
                    self._registry.update_state(
                        proc_name, ProcessState.RUNNING, pid=pid
                    )
                    started_procs.append(proc_name)
                    logger.info("Started process %s (pid=%s)", proc_name, pid)
                else:
                    self._registry.update_state(
                        proc_name, ProcessState.FAILED, error=msg
                    )
                    failed_procs.append(proc_name)
                    error_msg = msg
                    logger.error("Failed to start process %s: %s", proc_name, msg)
                    break  # Stop on first failure

            # Rollback on failure
            if failed_procs:
                logger.warning("Rolling back %d started processes", len(started_procs))
                for name in started_procs:
                    self._process_stopper(name, force=True)
                    self._registry.update_state(name, ProcessState.STOPPED)

                # Also remove failed process registration
                for name in failed_procs:
                    self._registry.unregister(name, req.panel_id)

            return [
                OutgoingMessage(
                    msg_type=MessageType.START_RESPONSE,
                    payload=ProcessStartResponse(
                        panel_id=req.panel_id,
                        success=len(failed_procs) == 0,
                        failed_processes=failed_procs,
                        error_message=error_msg,
                    ),
                    target_panel=req.panel_id,
                )
            ]

    def handle_stop_request(
        self, req: ProcessStopRequest
    ) -> list[OutgoingMessage]:
        """
Handle process stop request.

Stops processes only if no other panels need them, unless force=True.

**Arguments:**

* ``req``

  / *Condition*: required / *Type*: ProcessStopRequest /

  The stop request containing panel_id, process_list, and force flag.

**Returns:**

  / *Type*: list[OutgoingMessage] /

  List of outgoing messages (stop response).
        """
        with self._operation_lock:
            for proc_name in req.process_list:
                # Check if we can stop (no other requesters)
                can_stop = self._registry.unregister(proc_name, req.panel_id)

                if can_stop or req.force:
                    logger.info("Stopping process %s (force=%s)", proc_name, req.force)
                    self._registry.update_state(proc_name, ProcessState.STOPPING)
                    success = self._process_stopper(proc_name, force=req.force)

                    if success:
                        self._registry.remove(proc_name)
                        logger.info("Stopped process %s", proc_name)
                    else:
                        logger.error("Failed to stop process %s", proc_name)
                else:
                    logger.info(
                        "Process %s still needed by other panels",
                        proc_name,
                    )

            return [
                OutgoingMessage(
                    msg_type=MessageType.STOP_RESPONSE,
                    payload=ProcessStopResponse(
                        panel_id=req.panel_id,
                        success=True,
                        message="Stop request completed",
                    ),
                    target_panel=req.panel_id,
                )
            ]

    # ========================================================================
    # Restart Coordination
    # ========================================================================

    def handle_restart_ready(
        self, req: ProcessRestartReady
    ) -> list[OutgoingMessage]:
        """
Handle panel restart acknowledgment.

When all panels have acknowledged, performs the restart.

**Arguments:**

* ``req``

  / *Condition*: required / *Type*: ProcessRestartReady /

  The restart ready message from a panel.

**Returns:**

  / *Type*: list[OutgoingMessage] /

  List of outgoing messages (restart done notifications if all panels acknowledged).
        """
        logger.info("Panel %s acknowledged restart", req.panel_id)
        success, all_ready = self._restart_fsm.panel_acknowledged(req.panel_id)

        if not success:
            logger.warning(
                "Unexpected restart ready from %s (state=%s)",
                req.panel_id,
                self._restart_fsm.state,
            )
            return []

        if all_ready:
            logger.info("All panels ready, performing restart")
            return self._perform_restart()

        return []

    def _perform_restart(self) -> list[OutgoingMessage]:
        """
Execute restart sequence and notify panels.

Stops all killed processes, then restarts them.

**Returns:**

  / *Type*: list[OutgoingMessage] /

  List of restart done messages to send to affected panels.
        """
        if not self._restart_fsm.begin_restart():
            return []

        killed = self._restart_fsm.killed_processes
        success = True
        failed_procs = []

        with self._operation_lock:
            for name in killed:
                # Stop the dead process
                logger.info("Stopping dead process %s", name)
                self._process_stopper(name, force=True)

                # Restart it
                logger.info("Restarting process %s", name)
                ok, msg, pid = self._process_starter(name)

                if ok:
                    self._registry.update_state(name, ProcessState.RUNNING, pid=pid)
                    logger.info("Restarted process %s (pid=%s)", name, pid)
                else:
                    self._registry.update_state(name, ProcessState.FAILED, error=msg)
                    failed_procs.append(name)
                    success = False
                    logger.error("Failed to restart process %s: %s", name, msg)

        self._restart_fsm.restart_completed(
            success=success,
            error_message=f"Failed: {failed_procs}" if failed_procs else None,
        )

        # Notify all affected panels
        snapshot = self._restart_fsm.get_snapshot()
        messages = []

        for panel_id in snapshot["notified_panels"]:
            messages.append(
                OutgoingMessage(
                    msg_type=MessageType.RESTART_DONE,
                    payload=ProcessRestartDone(
                        panel_id=panel_id,
                        success=success,
                        failed_processes=failed_procs,
                    ),
                    target_panel=panel_id,
                )
            )

        self._restart_fsm.reset_to_idle()
        logger.info("Restart sequence completed (success=%s)", success)

        return messages

    # ========================================================================
    # Periodic Tick (Health Check)
    # ========================================================================

    def tick(self) -> list[OutgoingMessage]:
        """
Periodic tick - run health check, detect killed processes.

Should be called periodically (e.g., every 0.5 seconds). Returns outgoing messages (restart notifications if needed).

**Returns:**

  / *Type*: list[OutgoingMessage] /

  List of outgoing messages. Empty if no dead processes detected, otherwise restart notifications.
        """
        # Check for restart timeout
        if self._restart_fsm.state not in (RestartState.IDLE, RestartState.DONE):
            if self._restart_fsm.check_timeout():
                logger.warning("Restart timed out")
                return self._handle_restart_timeout()
            return []  # Restart in progress, skip health check

        # Health check
        active = self._registry.get_active_processes()
        if not active:
            return []

        dead = self._health_checker(active)
        if not dead:
            return []

        logger.warning("Detected dead processes: %s", dead)

        # Mark as dead in registry
        self._registry.mark_dead(dead)

        # Find affected panels
        affected_panels = set()
        for name in dead:
            requesters = self._registry.get_requesters(name)
            affected_panels.update(requesters)

        if not affected_panels:
            logger.warning("Dead processes have no requesters, skipping restart")
            return []

        logger.info("Notifying panels for restart: %s", affected_panels)

        # Start restart FSM
        if not self._restart_fsm.detect_killed(dead, list(affected_panels)):
            logger.warning("Could not start restart FSM (already in progress?)")
            return []

        # Send notifications
        messages = []
        for panel_id in affected_panels:
            messages.append(
                OutgoingMessage(
                    msg_type=MessageType.RESTART_NOTIFY,
                    payload=ProcessRestartNotify(
                        panel_id=panel_id,
                        killed_processes=dead,
                    ),
                    target_panel=panel_id,
                )
            )

        self._restart_fsm.notifications_sent()
        return messages

    def _handle_restart_timeout(self) -> list[OutgoingMessage]:
        """
Handle restart timeout - notify panels of failure.

**Returns:**

  / *Type*: list[OutgoingMessage] /

  List of restart done messages with success=False.
        """
        snapshot = self._restart_fsm.get_snapshot()
        messages = []

        for panel_id in snapshot["notified_panels"]:
            messages.append(
                OutgoingMessage(
                    msg_type=MessageType.RESTART_DONE,
                    payload=ProcessRestartDone(
                        panel_id=panel_id,
                        success=False,
                        failed_processes=list(snapshot["killed_processes"]),
                    ),
                    target_panel=panel_id,
                )
            )

        self._restart_fsm.reset_to_idle()
        return messages

    # ========================================================================
    # Utilities
    # ========================================================================

    def get_connection_count(self) -> int:
        """
Get number of registered connections.

**Returns:**

  / *Type*: int /

  The number of currently registered panel connections.
        """
        with self._connection_lock:
            return len(self._connections)

    def get_process_count(self) -> int:
        """
Get number of registered processes.

**Returns:**

  / *Type*: int /

  The number of currently registered processes.
        """
        return len(self._registry)

    # ========================================================================
    # Admin Operations
    # ========================================================================

    def register_admin_process(self, name: str, pid: int) -> bool:
        """
Register a process started by admin (not via client request).

This allows processes started via the admin API to appear in the dashboard
and be tracked by the registry.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The process name.

* ``pid``

  / *Condition*: required / *Type*: int /

  The process ID.

**Returns:**

  / *Type*: bool /

  True if registered successfully, False if already exists.
        """
        with self._operation_lock:
            existing = self._registry.get(name)
            if existing and existing.state in (ProcessState.RUNNING, ProcessState.STARTING):
                logger.debug("Process %s already registered (state=%s)", name, existing.state)
                return False

            # Register with special "__admin__" requester
            self._registry.register(name, requester="__admin__")
            self._registry.update_state(name, ProcessState.RUNNING, pid=pid)
            logger.info("Registered admin-started process: %s (pid=%d)", name, pid)
            return True

    def unregister_admin_process(self, name: str) -> bool:
        """
Unregister an admin-started process.

Called when an admin-started process is stopped.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The process name.

**Returns:**

  / *Type*: bool /

  True if unregistered successfully.
        """
        with self._operation_lock:
            existing = self._registry.get(name)
            if not existing:
                return False

            # Remove admin requester
            no_requesters = self._registry.unregister(name, "__admin__")
            if no_requesters:
                self._registry.update_state(name, ProcessState.STOPPED)
            logger.info("Unregistered admin-started process: %s", name)
            return True

    # ========================================================================
    # Reset and Shutdown
    # ========================================================================

    def reset(self) -> tuple[bool, str, list[OutgoingMessage]]:
        """
Reset the hub to a fresh state.

Stops all processes, clears all connections, and resets the restart state machine.
Unlike shutdown(), this does not stop the server - it just clears state.
Returns notification messages to send to clients before they are disconnected.

**Returns:**

  / *Type*: tuple[bool, str, list[OutgoingMessage]] /

  A tuple of (success, message, outgoing_messages) where outgoing_messages
  contains shutdown notifications for all connected clients.
        """
        logger.info("Resetting ProcessHubCore to fresh state")

        stopped_count = 0
        errors = []
        messages = []

        # Collect panel IDs before clearing connections
        with self._connection_lock:
            panel_ids = list(self._connections.keys())
            conn_count = len(panel_ids)

        # Create shutdown notifications for all connected clients
        for panel_id in panel_ids:
            messages.append(
                OutgoingMessage(
                    msg_type=MessageType.SHUTDOWN_NOTIFY,
                    payload=ServerShutdownNotify(
                        panel_id=panel_id,
                        reason="reset",
                        message="Hub is being reset. All connections will be cleared.",
                    ),
                    target_panel=panel_id,
                )
            )

        with self._operation_lock:
            # Stop all processes
            for name in self._registry.get_all_names():
                logger.info("Stopping process %s during reset", name)
                try:
                    if self._process_stopper(name, force=True):
                        stopped_count += 1
                except Exception as e:
                    errors.append(f"{name}: {e}")
                    logger.exception("Error stopping process %s during reset", name)

            # Clear process registry
            self._registry.clear_all()

        # Clear connections
        with self._connection_lock:
            self._connections.clear()

        # Reset restart state machine
        self._restart_fsm.reset_to_idle()

        if errors:
            msg = f"Reset completed with errors. Stopped {stopped_count} processes, cleared {conn_count} connections. Errors: {'; '.join(errors)}"
            logger.warning(msg)
            return True, msg, messages  # Still return success since state was cleared

        msg = f"Hub reset successfully. Stopped {stopped_count} processes, cleared {conn_count} connections."
        logger.info(msg)
        return True, msg, messages

    def shutdown(self) -> list[OutgoingMessage]:
        """
Shutdown the hub.

Stops all processes and clears state. Should be called when the server is shutting down.
Returns notification messages to send to clients before shutdown.

**Returns:**

  / *Type*: list[OutgoingMessage] /

  List of shutdown notifications for all connected clients.
        """
        logger.info("Shutting down ProcessHubCore")

        messages = []

        # Collect panel IDs before clearing connections
        with self._connection_lock:
            panel_ids = list(self._connections.keys())

        # Create shutdown notifications for all connected clients
        for panel_id in panel_ids:
            messages.append(
                OutgoingMessage(
                    msg_type=MessageType.SHUTDOWN_NOTIFY,
                    payload=ServerShutdownNotify(
                        panel_id=panel_id,
                        reason="shutdown",
                        message="Server is shutting down.",
                    ),
                    target_panel=panel_id,
                )
            )

        # Stop all processes
        for name in self._registry.get_all_names():
            logger.info("Stopping process %s", name)
            self._process_stopper(name, force=True)

        # Clear state
        self._registry.clear_all()

        with self._connection_lock:
            self._connections.clear()

        return messages
