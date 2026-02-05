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
# File: models.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Data models for Process Hub - normalized representations and protocol schema.
#   This module implements:
#   - 3.4: Normalized process representation (ProcessState enum, ProcessInfo dataclass)
#   - 3.5: Protocol schema (typed message dataclasses with versioning)
#   - 3.2: Immutable snapshots for UI (frozen dataclasses)
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Data models for Process Hub - normalized representations and protocol schema.

This module implements:

- 3.4: Normalized process representation (ProcessState enum, ProcessInfo dataclass)

- 3.5: Protocol schema (typed message dataclasses with versioning)

- 3.2: Immutable snapshots for UI (frozen dataclasses)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Set


# ============================================================================
# 3.4: Normalized Process Representation
# ============================================================================


class ProcessState(Enum):
    """
ProcessState: Explicit process lifecycle states.

Replaces the inconsistent status field that was:

- Initialized as string "None"

- Then set to boolean True/False

Now all states are explicit enum values.
    """

    REGISTERED = "registered"  # In config, not started
    STARTING = "starting"  # Subprocess created, waiting for confirmation
    RUNNING = "running"  # Confirmed running
    STOPPING = "stopping"  # Stop requested
    STOPPED = "stopped"  # Process exited normally
    DEAD = "dead"  # Was running, now killed unexpectedly
    FAILED = "failed"  # Start/restart failed


@dataclass
class ProcessInfo:
    """
ProcessInfo: Normalized process representation.

Replaces the dict-based shared_info with explicit fields:

- name: process identifier (was dict key)

- state: ProcessState enum (was "status": "None"/True/False)

- pid: process ID (was "pid": 0)

- requesters: set of panel IDs (was "requester": list)

- error_message: failure reason (new field)

- metadata: extensible data (new field)
    """

    name: str
    state: ProcessState = ProcessState.REGISTERED
    pid: Optional[int] = None
    requesters: Set[str] = field(default_factory=set)
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_requester(self, requester_id: str) -> None:
        """
Add a requester to this process.

**Arguments:**

* ``requester_id``

  / *Condition*: required / *Type*: str /

  The panel ID of the requester to add.
        """
        if requester_id:
            self.requesters.add(requester_id)

    def remove_requester(self, requester_id: str) -> bool:
        """
Remove requester from process.

**Arguments:**

* ``requester_id``

  / *Condition*: required / *Type*: str /

  The panel ID of the requester to remove.

**Returns:**

  / *Type*: bool /

  True if no requesters remain (process can be stopped), False otherwise.
        """
        self.requesters.discard(requester_id)
        return len(self.requesters) == 0

    def is_active(self) -> bool:
        """
Check if process is in an active state (STARTING or RUNNING).

**Returns:**

  / *Type*: bool /

  True if the process is starting or running, False otherwise.
        """
        return self.state in (ProcessState.STARTING, ProcessState.RUNNING)

    def to_dict(self) -> dict:
        """
Convert to dict for backward compatibility / UI.

Maintains similar structure to old shared_info format.

**Returns:**

  / *Type*: dict /

  A dictionary with keys: pid, requester, status, error.
        """
        return {
            "pid": self.pid or 0,
            "requester": list(self.requesters),
            "status": self.state.value,
            "error": self.error_message,
        }


# ============================================================================
# 3.5: Protocol Schema
# ============================================================================

PROTOCOL_VERSION = "1.0"


@dataclass
class MessageBase:
    """
MessageBase: Base class for all protocol messages.

Adds:

- version: for protocol evolution

- timestamp: for debugging/ordering

- request_id: for request/response correlation
    """

    version: str = PROTOCOL_VERSION
    timestamp: float = field(default_factory=time.time)
    request_id: Optional[str] = None


# --- Connection Messages ---


@dataclass
class RegisterConnectionRequest(MessageBase):
    """
RegisterConnectionRequest: Client -> Server message to register a panel connection.
    """

    panel_id: str = ""
    session_id: str = ""


@dataclass
class RegisterConnectionResponse(MessageBase):
    """
RegisterConnectionResponse: Server -> Client message with registration result.
    """

    panel_id: str = ""
    success: bool = True
    message: str = ""


@dataclass
class UnregisterConnectionRequest(MessageBase):
    """
UnregisterConnectionRequest: Client -> Server message to unregister a panel connection.
    """

    panel_id: str = ""


@dataclass
class UnregisterConnectionResponse(MessageBase):
    """
UnregisterConnectionResponse: Server -> Client message with unregistration result.
    """

    panel_id: str = ""
    message: str = ""


@dataclass
class ConnectionInfoRequest(MessageBase):
    """
ConnectionInfoRequest: Client -> Server message to request connection info.
    """

    panel_id: str = ""


@dataclass
class ConnectionInfoResponse(MessageBase):
    """
ConnectionInfoResponse: Server -> Client message with connection info.
    """

    panel_id: str = ""
    connections: dict = field(default_factory=dict)


# --- Process Control Messages ---


@dataclass
class ProcessStartRequest(MessageBase):
    """
ProcessStartRequest: Client -> Server message to start process(es).

Fields:
- panel_id: requesting panel

- process_list: processes to start

- timeout_per_process: max time to wait per process
    """

    panel_id: str = ""
    process_list: list[str] = field(default_factory=list)
    timeout_per_process: float = 20.0


@dataclass
class ProcessStartResponse(MessageBase):
    """
ProcessStartResponse: Server -> Client message with start result.

Replaces old format:

    {"panel_id": ..., "status": bool, "failed_proc": [], "failed_msg": ""}

With explicit fields and consistent naming.
    """

    panel_id: str = ""
    success: bool = True
    failed_processes: list[str] = field(default_factory=list)
    error_message: str = ""


@dataclass
class ProcessStopRequest(MessageBase):
    """
ProcessStopRequest: Client -> Server message to stop process(es).
    """

    panel_id: str = ""
    process_list: list[str] = field(default_factory=list)
    force: bool = False


@dataclass
class ProcessStopResponse(MessageBase):
    """
ProcessStopResponse: Server -> Client message with stop result.

Provides detailed feedback on what happened to each process:

* ``stopped`` - processes that were actually terminated
* ``still_in_use`` - processes where only the requester was removed
  (other clients still need them)
* ``failed`` - processes that failed to stop
    """

    panel_id: str = ""
    success: bool = True
    message: str = ""
    stopped: list[str] = field(default_factory=list)
    still_in_use: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


# --- Restart Coordination Messages ---


@dataclass
class ProcessRestartNotify(MessageBase):
    """
ProcessRestartNotify: Server -> Client message indicating process(es) died and restart is needed.

Sent to all affected panels when health check detects dead processes.
    """

    panel_id: str = ""
    killed_processes: list[str] = field(default_factory=list)


@dataclass
class ProcessRestartReady(MessageBase):
    """
ProcessRestartReady: Client -> Server message indicating panel is ready for restart.

Sent by client after receiving ProcessRestartNotify and completing any necessary cleanup.
    """

    panel_id: str = ""


@dataclass
class ProcessRestartDone(MessageBase):
    """
ProcessRestartDone: Server -> Client message indicating restart completed.

Sent to all affected panels after restart sequence completes.
    """

    panel_id: str = ""
    success: bool = True
    failed_processes: list[str] = field(default_factory=list)


# --- Server Lifecycle Messages ---


@dataclass
class ServerShutdownNotify(MessageBase):
    """
ServerShutdownNotify: Server -> Client message indicating server is shutting down or resetting.

Sent to all connected panels before server shutdown or reset.
Clients should handle this by cleaning up their state and potentially reconnecting.
    """

    panel_id: str = ""
    reason: str = "shutdown"  # "shutdown" or "reset"
    message: str = ""


# ============================================================================
# 3.2: Immutable State Snapshots for UI
# ============================================================================


@dataclass(frozen=True)
class ConnectionSnapshot:
    """
ConnectionSnapshot: Immutable snapshot of a connection.

Used by UI to display connection state without holding locks.
    """

    panel_id: str
    session_id: str
    session_panel_ids: tuple[str, ...]
    connected_at: Optional[float] = None


@dataclass(frozen=True)
class ProcessSnapshot:
    """
ProcessSnapshot: Immutable snapshot of a process.

Used by UI to display process state without holding locks.
    """

    name: str
    state: ProcessState
    pid: int
    requesters: tuple[str, ...]


@dataclass(frozen=True)
class HubStateSnapshot:
    """
HubStateSnapshot: Immutable snapshot of hub state for UI.

Benefits:

- Core updates internal mutable state

- get_state() returns a fresh snapshot (copy)

- UI can read snapshot without locks

- No race conditions between UI and core

This replaces the pattern of:

    with shared_info_lock:

        proc_data = copy.deepcopy(proc_info)

        con_data = copy.deepcopy(self.connections)
    """

    connections: tuple[ConnectionSnapshot, ...]
    processes: tuple[ProcessSnapshot, ...]
    killed_processes: tuple[str, ...]
    pending_panels: tuple[str, ...]
    restart_state: str  # RestartState enum value
