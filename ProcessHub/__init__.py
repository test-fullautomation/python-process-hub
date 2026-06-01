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
#   Python Process Hub - Process lifecycle management with ZMQ-based coordination.
#   Manages process lifecycle (start, stop, restart), coordinates restarts across
#   multiple clients, provides health monitoring and automatic recovery.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# 06.02.2026 / V 1.1.0 / Nguyen Huynh Tri Cuong
# - Added fleet orchestrator overlay for multi-hub coordination
# - New package: ProcessHub.fleet (orchestrator, hub_agent, fleet_client,
#   hub_registry, models, topics, web_api)
# - Optional fleet imports with HAS_FLEET flag
#
# *******************************************************************************
"""
Python Process Hub - Process lifecycle management with ZMQ-based coordination.

This package provides a robust process management hub that:

- Manages process lifecycle (start, stop, restart)

- Coordinates restarts across multiple clients

- Provides health monitoring and automatic recovery

- Supports pluggable transports (ZMQ, in-memory for testing)

Example usage (Server):

    from ProcessHub import ProcessHubServer

    from ProcessHub.transport import InMemoryTransport

    from ProcessHub.ui import ConsoleView

    from ProcessHub.process import SimpleExecutor

    transport = InMemoryTransport()

    view = ConsoleView()

    executor = SimpleExecutor()


    server = ProcessHubServer(

        transport=transport,

        view=view,

        executor=executor,

    )

    server.run()

Example usage (Client):

    from ProcessHub import ProcessHubClient

    from ProcessHub.transport import InMemoryTransport

    transport = InMemoryTransport()

    client = ProcessHubClient(transport=transport, panel_id="my_panel")

    client.start()

    client.register_connection(session_id="my_session")

    client.request_process_start(["my_process"])
"""

# Version info
from .version import VERSION, VERSION_DATE
__version__ = VERSION
__version_date__ = VERSION_DATE

# Core models
from .core.models import (
    ProcessState,
    ProcessInfo,
    HubStateSnapshot,
    ProcessSnapshot,
    ConnectionSnapshot,
    ServerShutdownNotify,
    PROTOCOL_VERSION,
)

# Core logic
from .core.restart_state import RestartState, RestartStateMachine
from .core.process_registry import ProcessRegistry
from .core.hub_core import ProcessHubCore, MessageType, OutgoingMessage

# Runtime
from .runtime.server import ProcessHubServer, Topics
from .runtime.client import ProcessHubClient
from .runtime.client_controller import ClientController, ClientEvent

# Process execution
from .process.executor import ProcessExecutor, SimpleExecutor, MockExecutor

# Logging integration (optional)
from .logging.integration import (
    LoggingIntegration,
    LoggingServerType,
    LoggingConfig,
    LoggingAwareExecutor,
)

# Fleet orchestrator (optional overlay)
try:
    from .fleet import FleetOrchestrator, HubAgent, FleetClient, FleetTopics
    HAS_FLEET = True
except ImportError:
    HAS_FLEET = False
    FleetOrchestrator = None  # type: ignore
    HubAgent = None  # type: ignore
    FleetClient = None  # type: ignore
    FleetTopics = None  # type: ignore

__all__ = [
    # Version
    "__version__",
    "PROTOCOL_VERSION",
    # Core models
    "ProcessState",
    "ProcessInfo",
    "HubStateSnapshot",
    "ProcessSnapshot",
    "ConnectionSnapshot",
    "ServerShutdownNotify",
    # Restart
    "RestartState",
    "RestartStateMachine",
    # Registry
    "ProcessRegistry",
    # Core
    "ProcessHubCore",
    "MessageType",
    "OutgoingMessage",
    # Runtime
    "ProcessHubServer",
    "ProcessHubClient",
    "ClientController",
    "ClientEvent",
    "Topics",
    # Process execution
    "ProcessExecutor",
    "SimpleExecutor",
    "MockExecutor",
    # Logging integration
    "LoggingIntegration",
    "LoggingServerType",
    "LoggingConfig",
    "LoggingAwareExecutor",
    # Fleet orchestrator (optional)
    "FleetOrchestrator",
    "HubAgent",
    "FleetClient",
    "FleetTopics",
    "HAS_FLEET",
]
