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
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / February 2026.
#
# Description:
#   Fleet protocol messages and immutable state snapshots.
#   Messages extend MessageBase for protocol versioning.
#   Snapshots use frozen dataclasses with tuples for thread-safe fleet queries.
#
# History:
#
# 06.02.2026 / V 1.1.0 / Nguyen Huynh Tri Cuong
# - Initial fleet orchestrator implementation
#
# *******************************************************************************
"""
Fleet protocol messages and immutable state snapshots.

Messages:
- HubAnnounce: Hub agent heartbeat / registration
- HubRegistered: Orchestrator acknowledgement
- HubDeregistered: Hub removal notification
- HubStatusReport: Periodic status from hub agent
- FleetCommand: Command from orchestrator to hub agent
- FleetCommandResult: Result from hub agent to orchestrator

Snapshots (frozen):
- HubSnapshot: Immutable view of a single hub
- FleetStateSnapshot: Immutable view of the entire fleet
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from ..core.models import MessageBase


# ============================================================================
# Fleet Protocol Messages
# ============================================================================


@dataclass
class HubAnnounce(MessageBase):
    """
HubAnnounce: Hub agent heartbeat and registration message.

Sent periodically by each HubAgent to announce its presence.
The orchestrator uses this for hub discovery and liveness detection.
    """

    hub_id: str = ""
    hub_name: str = ""
    host: str = ""
    capabilities: list[str] = field(default_factory=list)


@dataclass
class HubRegistered(MessageBase):
    """
HubRegistered: Orchestrator -> HubAgent registration acknowledgement.

Sent by the orchestrator after successfully registering a hub.
    """

    hub_id: str = ""
    success: bool = True
    message: str = ""
    fleet_id: str = ""


@dataclass
class HubDeregistered(MessageBase):
    """
HubDeregistered: Hub removal notification.

Sent when a hub is deregistered (graceful shutdown or timeout).
    """

    hub_id: str = ""
    reason: str = ""


@dataclass
class HubStatusReport(MessageBase):
    """
HubStatusReport: Periodic status from hub agent.

Sent by HubAgent with current server state from server.core.get_state_snapshot().
    """

    hub_id: str = ""
    process_count: int = 0
    connection_count: int = 0
    processes: list[str] = field(default_factory=list)
    connections: list[str] = field(default_factory=list)
    restart_state: str = ""


@dataclass
class FleetCommand(MessageBase):
    """
FleetCommand: Command from orchestrator/client to hub agent.

Supported actions:
- start_process: params = {"process_list": [...], "panel_id": "fleet"}
- stop_process:  params = {"process_list": [...], "panel_id": "fleet"}
- reset:         params = {}
- get_status:    params = {}
    """

    command_id: str = ""
    hub_id: str = ""
    action: str = ""
    params: dict = field(default_factory=dict)


@dataclass
class FleetCommandResult(MessageBase):
    """
FleetCommandResult: Result from hub agent back to orchestrator.

Contains the command_id for correlation with the original FleetCommand.
    """

    command_id: str = ""
    hub_id: str = ""
    success: bool = True
    message: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class FleetStatusRequest(MessageBase):
    """
FleetStatusRequest: Request for fleet-wide status.

Sent by FleetClient to request a FleetStatusResponse from the orchestrator.
    """

    requester_id: str = ""


@dataclass
class FleetStatusResponse(MessageBase):
    """
FleetStatusResponse: Fleet-wide status from orchestrator.

Contains serialized fleet state for the requesting client.
    """

    total_hubs: int = 0
    online_hubs: int = 0
    total_processes: int = 0
    hubs: list[dict] = field(default_factory=list)


# ============================================================================
# Immutable Fleet State Snapshots
# ============================================================================


@dataclass(frozen=True)
class HubSnapshot:
    """
HubSnapshot: Immutable snapshot of a single hub's state.

Used by FleetWebAPI, FleetClient, and orchestrator for thread-safe
fleet state queries without holding locks.
    """

    hub_id: str
    hub_name: str
    host: str
    status: str
    process_count: int
    connection_count: int
    processes: tuple[str, ...]
    connections: tuple[str, ...]
    last_seen: float
    version: str = ""


@dataclass(frozen=True)
class FleetStateSnapshot:
    """
FleetStateSnapshot: Immutable snapshot of the entire fleet.

Returned by FleetOrchestrator.get_fleet_snapshot() and
HubRegistry.get_snapshot().
    """

    hubs: tuple[HubSnapshot, ...]
    total_hubs: int
    online_hubs: int
    total_processes: int
    timestamp: float = field(default_factory=time.time)
