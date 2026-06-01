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
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / February 2026.
#
# Description:
#   Fleet orchestrator package - multi-hub coordination overlay.
#   Provides FleetOrchestrator, HubAgent, FleetClient, and supporting models.
#
# History:
#
# 06.02.2026 / V 1.1.0 / Nguyen Huynh Tri Cuong
# - Initial fleet orchestrator implementation
#
# *******************************************************************************
"""
Fleet orchestrator package - multi-hub coordination overlay.

Provides:
- FleetOrchestrator: Central coordinator for multiple hubs
- HubAgent: Sidecar alongside each ProcessHubServer
- FleetClient: External API for CI/CD and CLI
- HubRegistry: Thread-safe hub tracking
- FleetTopics: Message topic enum
- Fleet models: Protocol messages and frozen snapshots

Optional:
- FleetWebAPI: REST dashboard (requires FastAPI)
"""

from .models import (
    FleetCommand,
    FleetCommandResult,
    FleetStateSnapshot,
    FleetStatusRequest,
    FleetStatusResponse,
    HubAnnounce,
    HubDeregistered,
    HubRegistered,
    HubSnapshot,
    HubStatusReport,
)
from .topics import FleetTopics
from .hub_registry import HubRegistry
from .hub_agent import HubAgent
from .orchestrator import FleetOrchestrator
from .fleet_client import FleetClient

# FleetWebAPI is optional (requires FastAPI)
try:
    from .web_api import FleetWebAPI
    HAS_FLEET_WEB = True
except ImportError:
    HAS_FLEET_WEB = False
    FleetWebAPI = None  # type: ignore

__all__ = [
    # Core components
    "FleetOrchestrator",
    "HubAgent",
    "FleetClient",
    "HubRegistry",
    # Topics
    "FleetTopics",
    # Models - Messages
    "HubAnnounce",
    "HubRegistered",
    "HubDeregistered",
    "HubStatusReport",
    "FleetCommand",
    "FleetCommandResult",
    "FleetStatusRequest",
    "FleetStatusResponse",
    # Models - Snapshots
    "HubSnapshot",
    "FleetStateSnapshot",
    # Web API
    "FleetWebAPI",
    "HAS_FLEET_WEB",
]
