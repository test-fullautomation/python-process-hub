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
# File: __init__.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Core business logic package - no I/O dependencies.
#   Contains pure business logic for process hub.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Core business logic - no I/O dependencies.

This module contains the pure business logic for process hub:

- Models: Data structures and protocol messages

- ProcessRegistry: Thread-safe process state management

- RestartStateMachine: Explicit restart state machine

- ProcessHubCore: Core hub logic (handles all business operations)
"""

from .models import (
    PROTOCOL_VERSION,
    ConnectionInfoRequest,
    ConnectionInfoResponse,
    ConnectionSnapshot,
    HubStateSnapshot,
    MessageBase,
    ProcessInfo,
    ProcessRestartDone,
    ProcessRestartNotify,
    ProcessRestartReady,
    ProcessSnapshot,
    ProcessStartRequest,
    ProcessStartResponse,
    ProcessState,
    ProcessStopRequest,
    ProcessStopResponse,
    RegisterConnectionRequest,
    RegisterConnectionResponse,
    UnregisterConnectionRequest,
    UnregisterConnectionResponse,
)
from .process_registry import ProcessRegistry
from .restart_state import RestartContext, RestartState, RestartStateMachine
from .hub_core import MessageType, OutgoingMessage, ProcessHubCore

__all__ = [
    # Version
    "PROTOCOL_VERSION",
    # Process models
    "ProcessState",
    "ProcessInfo",
    "ProcessSnapshot",
    "ConnectionSnapshot",
    "HubStateSnapshot",
    # Protocol messages
    "MessageBase",
    "RegisterConnectionRequest",
    "RegisterConnectionResponse",
    "UnregisterConnectionRequest",
    "UnregisterConnectionResponse",
    "ConnectionInfoRequest",
    "ConnectionInfoResponse",
    "ProcessStartRequest",
    "ProcessStartResponse",
    "ProcessStopRequest",
    "ProcessStopResponse",
    "ProcessRestartNotify",
    "ProcessRestartReady",
    "ProcessRestartDone",
    # Restart
    "RestartState",
    "RestartContext",
    "RestartStateMachine",
    # Registry
    "ProcessRegistry",
    # Core
    "MessageType",
    "OutgoingMessage",
    "ProcessHubCore",
]
