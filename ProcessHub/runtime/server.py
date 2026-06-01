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
# File: server.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   ProcessHubServer - thin runtime wrapper around ProcessHubCore.
#   This module implements improvement 3.1: ZmqHubServer = small adapter.
#   Server only handles: transport wiring, main loop, lifecycle.
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
ProcessHubServer - thin runtime wrapper around ProcessHubCore.

This module implements improvement 3.1:

- ZmqHubServer = small adapter: recv ZMQ -> call core.handle_message -> send ZMQ

- All business logic is in ProcessHubCore

- Server only handles: transport wiring, main loop, lifecycle

Benefits:

- Clean separation of concerns

- Core can be tested without transport

- Easy to swap transports (ZMQ, HTTP, in-memory)
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from dataclasses import asdict
from enum import Enum
from typing import Any, Callable, Optional, Protocol

from ..core.hub_core import MessageType, OutgoingMessage, ProcessHubCore
from ..core.models import (
    ConnectionInfoRequest,
    MessageBase,
    ProcessRestartReady,
    ProcessStartRequest,
    ProcessStopRequest,
    RegisterConnectionRequest,
    UnregisterConnectionRequest,
)
from ..transport.base import TransportBase
from ..ui.base import HubView
from ..ui.null_view import NullView

logger = logging.getLogger(__name__)


# ============================================================================
# Topic Constants
# ============================================================================


class Topics(str, Enum):
    """
Message topics for process hub protocol.

These match the original ProcessEventTopic values for compatibility.
    """

    # Connection management
    REGISTER_REQUEST = "REGISTER_CONNECTION_REQUEST"
    REGISTER_RESPONSE = "REGISTER_CONNECTION_RESPONSE"
    UNREGISTER_REQUEST = "UNREGISTER_CONNECTION_REQUEST"
    UNREGISTER_RESPONSE = "UNREGISTER_CONNECTION_RESPONSE"
    CONNECTION_INFO_REQUEST = "CONNECTION_INFO_REQUEST"
    CONNECTION_INFO_RESPONSE = "CONNECTION_INFO_RESPONSE"

    # Process control
    START_REQUEST = "PROCESS_START_REQUEST"
    START_RESPONSE = "PROCESS_START_RESPONSE"
    STOP_REQUEST = "PROCESS_STOP_REQUEST"
    STOP_RESPONSE = "PROCESS_STOP_RESPONSE"

    # Restart coordination
    RESTART_NOTIFY = "PROCESS_RESTART_NOTIFY"
    RESTART_READY = "PROCESS_RESTART_READY"
    RESTART_DONE = "PROCESS_RESTART_DONE"

    # Server lifecycle
    SHUTDOWN_NOTIFY = "SERVER_SHUTDOWN_NOTIFY"


# Map MessageType to Topic for outgoing messages
MESSAGE_TYPE_TO_TOPIC = {
    MessageType.REGISTER_RESPONSE: Topics.REGISTER_RESPONSE,
    MessageType.UNREGISTER_RESPONSE: Topics.UNREGISTER_RESPONSE,
    MessageType.CONNECTION_INFO_RESPONSE: Topics.CONNECTION_INFO_RESPONSE,
    MessageType.START_RESPONSE: Topics.START_RESPONSE,
    MessageType.STOP_RESPONSE: Topics.STOP_RESPONSE,
    MessageType.RESTART_NOTIFY: Topics.RESTART_NOTIFY,
    MessageType.RESTART_DONE: Topics.RESTART_DONE,
    MessageType.SHUTDOWN_NOTIFY: Topics.SHUTDOWN_NOTIFY,
}


# ============================================================================
# Process Executor Protocol
# ============================================================================


class ProcessExecutor(Protocol):
    """
Protocol for process executor implementations.
   """

    def start(self, name: str, config: dict) -> tuple[bool, str, Optional[int]]:
        """
Start a process. Returns (success, message, pid).
        """
        ...

    def stop(self, name: str, force: bool = False) -> bool:
        """
Stop a process.
        """
        ...

    def is_running(self, name: str) -> bool:
        """
Check if process is running.
        """
        ...


# ============================================================================
# ProcessHubServer
# ============================================================================


class ProcessHubServer:
    """
Process Hub Server - thin runtime wrapper.

Responsibilities:

- Wire transport handlers to core message handlers

- Run main loop (tick + UI refresh)

- Handle shutdown signals

All business logic is in ProcessHubCore.

Usage:

    from ProcessHub.runtime.server import ProcessHubServer
    
    from ProcessHub.transport.zmq_transport import ZmqTransport
    
    from ProcessHub.ui.console_view import ConsoleView

    transport = ZmqTransport(start_broker=True)
    
    view = ConsoleView()

    server = ProcessHubServer(
    
        transport=transport,
        
        view=view,
        
        process_config=my_config,
        
    )
    
    server.run()
    """

    def __init__(
        self,
        transport: TransportBase,
        executor: Optional[ProcessExecutor] = None,
        view: Optional[HubView] = None,
        process_config: Optional[dict[str, dict]] = None,
        refresh_interval: float = 0.5,
        restart_timeout: float = 300.0,
    ):
        """
Initialize the server.

**Arguments:**

* ``transport``

  / *Condition*: required / *Type*: TransportBase /

  Transport implementation (ZMQ, in-memory, etc.).

* ``executor``

  / *Condition*: optional / *Type*: Optional[ProcessExecutor] / *Default*: None /

  Process executor. Uses SimpleExecutor if None.

* ``view``

  / *Condition*: optional / *Type*: Optional[HubView] / *Default*: None /

  UI view for rendering hub state. Uses NullView if None.

* ``process_config``

  / *Condition*: optional / *Type*: Optional[dict[str, dict]] / *Default*: None /

  Process configuration dict mapping process name to config.

* ``refresh_interval``

  / *Condition*: optional / *Type*: float / *Default*: 0.5 /

  Main loop tick interval in seconds.

* ``restart_timeout``

  / *Condition*: optional / *Type*: float / *Default*: 300.0 /

  Max time in seconds for restart coordination.
        """
        self._transport = transport
        self._executor = executor
        self._view = view or NullView()
        self._config = process_config or {}
        self._refresh_interval = refresh_interval
        self._running = False

        # Create core with executor callbacks
        self._core = ProcessHubCore(
            process_starter=self._start_process,
            process_stopper=self._stop_process,
            health_checker=self._check_health,
            restart_timeout=restart_timeout,
        )

        # Register message handlers
        self._register_handlers()

    def _register_handlers(self) -> None:
        """
Register message handlers with transport.
        """
        handlers = {
            Topics.REGISTER_REQUEST: self._on_register_request,
            Topics.UNREGISTER_REQUEST: self._on_unregister_request,
            Topics.CONNECTION_INFO_REQUEST: self._on_connection_info_request,
            Topics.START_REQUEST: self._on_start_request,
            Topics.STOP_REQUEST: self._on_stop_request,
            Topics.RESTART_READY: self._on_restart_ready,
        }

        for topic, handler in handlers.items():
            self._transport.register_handler(topic.value, handler)
            logger.debug("Registered handler for topic: %s", topic.value)

    # ========================================================================
    # Executor Callbacks (called by core)
    # ========================================================================

    def _start_process(self, name: str) -> tuple[bool, str, Optional[int]]:
        """
Start a process using the executor.

This is called by ProcessHubCore when a process needs to be started.
        """
        if self._executor is None:
            logger.warning("No executor configured, cannot start process %s", name)
            return False, "No executor configured", None

        config = self._config.get(name, {})
        logger.debug("Starting process %s with config: %s", name, config)

        try:
            success, msg, pid = self._executor.start(name, config)
            return success, msg, pid
        except Exception as e:
            logger.exception("Error starting process %s", name)
            return False, str(e), None

    def _stop_process(self, name: str, force: bool = False) -> bool:
        """
Stop a process using the executor.

This is called by ProcessHubCore when a process needs to be stopped.
        """
        if self._executor is None:
            logger.warning("No executor configured, cannot stop process %s", name)
            return False

        try:
            return self._executor.stop(name, force)
        except Exception as e:
            logger.exception("Error stopping process %s", name)
            return False

    def _check_health(self, names: list[str]) -> list[str]:
        """
Check which processes are dead.

This is called by ProcessHubCore during tick() for health monitoring.
        """
        if self._executor is None:
            return []

        dead = []
        for name in names:
            try:
                if not self._executor.is_running(name):
                    dead.append(name)
            except Exception as e:
                logger.warning("Error checking health of %s: %s", name, e)
                dead.append(name)  # Assume dead if we can't check

        return dead

    # ========================================================================
    # Message Handlers (transport -> core -> transport)
    # ========================================================================

    def _send_messages(self, messages: list[OutgoingMessage]) -> None:
        """
Send outgoing messages via transport.
        """
        for msg in messages:
            topic = MESSAGE_TYPE_TO_TOPIC.get(msg.msg_type)
            if topic:
                try:
                    payload = self._serialize_message(msg.payload)
                    self._transport.send_async(topic.value, payload)
                    logger.debug("Sent message to topic %s", topic.value)
                except Exception as e:
                    logger.exception("Error sending message to %s", topic.value)

    def _serialize_message(self, message: MessageBase) -> dict:
        """
Serialize a message dataclass to dict.
        """
        if hasattr(message, "__dataclass_fields__"):
            return asdict(message)
        return dict(message)

    def _deserialize_data(self, data: Any) -> dict:
        """
Ensure data is a dict (handle DictMsg wrapper).
        """
        if hasattr(data, "data"):
            # Handle DictMsg wrapper from original implementation
            return data.data
        if isinstance(data, dict):
            return data
        return {"data": data}

    def _on_register_request(self, data: Any) -> None:
        """
Handle register connection request.
        """
        logger.debug("Received register request: %s", data)
        try:
            d = self._deserialize_data(data)
            req = RegisterConnectionRequest(
                panel_id=d.get("panel_id", ""),
                session_id=d.get("session_id", ""),
            )
            logger.info("Processing registration for panel=%s, session=%s",
                       req.panel_id, req.session_id)
            messages = self._core.handle_register(req)
            logger.debug("Sending %d response messages", len(messages))
            self._send_messages(messages)
        except Exception as e:
            logger.exception("Error handling register request")

    def _on_unregister_request(self, data: Any) -> None:
        """
Handle unregister connection request.
        """
        try:
            d = self._deserialize_data(data)
            panel_id = d.get("panel_id", "")

            if not self._core.is_registered(panel_id):
                logger.warning("Unregister request from unknown panel: %s", panel_id)
                return

            req = UnregisterConnectionRequest(panel_id=panel_id)
            messages = self._core.handle_unregister(req)
            self._send_messages(messages)
        except Exception as e:
            logger.exception("Error handling unregister request")

    def _on_connection_info_request(self, data: Any) -> None:
        """
Handle connection info request.
        """
        try:
            d = self._deserialize_data(data)
            panel_id = d.get("panel_id", "")

            if not self._core.is_registered(panel_id):
                logger.warning("Connection info request from unknown panel: %s", panel_id)
                return

            req = ConnectionInfoRequest(panel_id=panel_id)
            messages = self._core.handle_connection_info(req)
            self._send_messages(messages)
        except Exception as e:
            logger.exception("Error handling connection info request")

    def _on_start_request(self, data: Any) -> None:
        """
Handle process start request.
        """
        try:
            d = self._deserialize_data(data)
            panel_id = d.get("panel_id", "")

            if not self._core.is_registered(panel_id):
                logger.warning("Start request from unknown panel: %s", panel_id)
                return

            req = ProcessStartRequest(
                panel_id=panel_id,
                process_list=d.get("process_list", []),
                timeout_per_process=d.get("timeout_per_process", 20.0),
            )
            messages = self._core.handle_start_request(req)
            self._send_messages(messages)
        except Exception as e:
            logger.exception("Error handling start request")

    def _on_stop_request(self, data: Any) -> None:
        """
Handle process stop request.
        """
        try:
            d = self._deserialize_data(data)
            panel_id = d.get("panel_id", "")

            if not self._core.is_registered(panel_id):
                logger.warning("Stop request from unknown panel: %s", panel_id)
                return

            req = ProcessStopRequest(
                panel_id=panel_id,
                process_list=d.get("process_list", []),
                force=d.get("force", False),
            )
            messages = self._core.handle_stop_request(req)
            self._send_messages(messages)
        except Exception as e:
            logger.exception("Error handling stop request")

    def _on_restart_ready(self, data: Any) -> None:
        """
Handle restart ready notification.
        """
        try:
            d = self._deserialize_data(data)
            req = ProcessRestartReady(panel_id=d.get("panel_id", ""))
            messages = self._core.handle_restart_ready(req)
            self._send_messages(messages)
        except Exception as e:
            logger.exception("Error handling restart ready")

    # ========================================================================
    # Lifecycle
    # ========================================================================

    def start(self) -> None:
        """
Start the server (transport only, no main loop).
        """
        logger.info("Starting ProcessHubServer")
        self._transport.start()
        self._running = True
        logger.info("ProcessHubServer started")

    def stop(self) -> None:
        """
Stop the server.

Sends shutdown notifications to all connected clients before stopping.
        """
        if not self._running and not self._transport.is_started:
            return  # Already stopped

        logger.info("Stopping ProcessHubServer")
        self._running = False

        # Shutdown core (stops all processes) and get notification messages
        messages = self._core.shutdown()

        # Send shutdown notifications to clients
        if messages:
            logger.info("Sending shutdown notifications to %d clients", len(messages))
            self._send_messages(messages)

        # Stop transport
        self._transport.stop()
        logger.info("ProcessHubServer stopped")

    def run(self) -> None:
        """
Run the main loop (blocking).

This starts the server, runs the tick/render loop,
and handles shutdown signals.
        """
        # Setup signal handlers
        self._setup_signal_handlers()

        # Start server
        self.start()

        try:
            while self._running:
                # Tick core (health check, restart coordination)
                messages = self._core.tick()
                self._send_messages(messages)

                # Update view
                snapshot = self._core.get_state_snapshot()
                self._view.render(snapshot)

                # Sleep
                time.sleep(self._refresh_interval)

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.exception("Error in main loop")
        finally:
            self.stop()

    def _setup_signal_handlers(self) -> None:
        """
Setup signal handlers for graceful shutdown.
        """
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """
Handle shutdown signals.
        """
        logger.info("Received signal %d, shutting down", signum)
        self._running = False

    # ========================================================================
    # Properties
    # ========================================================================

    def reset(self) -> tuple[bool, str]:
        """
Reset the hub to a fresh state.

Stops all processes, clears all connections, and resets the restart state machine.
The server continues running after reset.
Sends reset notifications to all connected clients before clearing their connections.

**Returns:**

  / *Type*: tuple[bool, str] /

  A tuple of (success, message) indicating result of reset operation.
        """
        logger.info("Resetting ProcessHubServer")

        # Reset core and get notification messages
        success, message, messages = self._core.reset()

        # Send reset notifications to clients
        if messages:
            logger.info("Sending reset notifications to %d clients", len(messages))
            self._send_messages(messages)

        return success, message

    def register_admin_process(self, name: str, pid: int) -> bool:
        """
Register a process started by admin (not via client request).

This allows processes started via the admin API to appear in the dashboard.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The process name.

* ``pid``

  / *Condition*: required / *Type*: int /

  The process ID.

**Returns:**

  / *Type*: bool /

  True if registered successfully.
        """
        return self._core.register_admin_process(name, pid)

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
        return self._core.unregister_admin_process(name)

    @property
    def core(self) -> ProcessHubCore:
        """
Get the core instance (for testing/introspection).
        """
        return self._core

    @property
    def configured_process_names(self) -> list[str]:
        """
Get the list of configured process names.

Returns all process names from the process_config dict,
regardless of whether they are currently running.
        """
        return list(self._config.keys())

    @property
    def process_config(self) -> dict[str, dict]:
        """
Get the full process configuration dict.

Returns the mapping of process name to config dict, containing
fields like script, args, env, wait_time, description, etc.
        """
        return dict(self._config)

    @property
    def is_running(self) -> bool:
        """
Check if server is running.
        """
        return self._running
