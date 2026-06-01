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
# File: 12_fleet_basic.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / February 2026.
#
# Description:
#   Basic Fleet Orchestrator example demonstrating multi-hub coordination.
#   Shows how to set up an orchestrator with two hub agents using
#   InMemoryTransport for local testing.
#
# Usage:
#   python 12_fleet_basic.py
#
# *******************************************************************************
"""
Basic Fleet Orchestrator Example.

This example demonstrates how to:
1. Create a FleetOrchestrator (central coordinator)
2. Create two ProcessHubServers with HubAgents (simulating two PCs)
3. Observe hub discovery and registration
4. Send fleet commands to specific hubs
5. Query fleet-wide status

All components run in a single process using InMemoryTransport.
This is ideal for understanding the fleet architecture before deploying
across real machines with EventBus (RabbitMQ) transport.

For a real multi-machine deployment, replace InMemoryTransport with
EventBusTransport - see example 14_fleet_web_dashboard.py.
"""

import logging
import sys
import time
from pathlib import Path

# Add ProcessHub to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from ProcessHub.transport import InMemoryTransport
from ProcessHub.runtime.server import ProcessHubServer
from ProcessHub.process.executor import MockExecutor
from ProcessHub.ui.null_view import NullView

from ProcessHub.fleet import FleetOrchestrator, HubAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    """Run a basic fleet demonstration."""
    print()
    print("=" * 60)
    print("  Fleet Orchestrator - Basic Example")
    print("=" * 60)
    print()

    # =========================================================================
    # Step 1: Create shared transport (in production, use EventBusTransport)
    # =========================================================================
    # InMemoryTransport allows all components to communicate within one process.
    # In a real deployment, each machine would use its own EventBusTransport
    # connected to a shared RabbitMQ server.

    fleet_transport = InMemoryTransport()
    fleet_transport.start()

    # =========================================================================
    # Step 2: Create two ProcessHubServers (simulating two PCs)
    # =========================================================================
    # Each server has its own LOCAL transport for client communication.
    # The fleet transport is separate - used only by HubAgents.

    local_transport_1 = InMemoryTransport()
    executor_1 = MockExecutor()
    server_1 = ProcessHubServer(
        transport=local_transport_1,
        executor=executor_1,
        view=NullView(),
        process_config={
            "worker_a": {"script": "python", "args": ["-c", "pass"]},
            "worker_b": {"script": "python", "args": ["-c", "pass"]},
        },
    )
    server_1.start()

    local_transport_2 = InMemoryTransport()
    executor_2 = MockExecutor()
    server_2 = ProcessHubServer(
        transport=local_transport_2,
        executor=executor_2,
        view=NullView(),
        process_config={
            "worker_c": {"script": "python", "args": ["-c", "pass"]},
            "worker_d": {"script": "python", "args": ["-c", "pass"]},
        },
    )
    server_2.start()

    print("  [OK] Two ProcessHub servers created")
    print()

    # =========================================================================
    # Step 3: Create FleetOrchestrator (central coordinator)
    # =========================================================================

    orchestrator = FleetOrchestrator(
        transport=fleet_transport,
        health_timeout=30.0,
        tick_interval=5.0,
    )
    orchestrator.start()

    print("  [OK] FleetOrchestrator started")
    print()

    # =========================================================================
    # Step 4: Create HubAgents (sidecars for each server)
    # =========================================================================
    # Each HubAgent sits alongside a ProcessHubServer and:
    # - Sends periodic heartbeats to the orchestrator
    # - Reports server status periodically
    # - Handles fleet commands (start/stop/reset)

    agent_1 = HubAgent(
        server=server_1,
        transport=fleet_transport,
        hub_id="hub-pc1",
        hub_name="Test PC 1",
        heartbeat_interval=5.0,
        status_interval=10.0,
        server_transport=local_transport_1,
    )
    agent_1.start()

    agent_2 = HubAgent(
        server=server_2,
        transport=fleet_transport,
        hub_id="hub-pc2",
        hub_name="Test PC 2",
        heartbeat_interval=5.0,
        status_interval=10.0,
        server_transport=local_transport_2,
    )
    agent_2.start()

    print("  [OK] Two HubAgents started and announced to orchestrator")
    print()

    # =========================================================================
    # Step 5: Query fleet status
    # =========================================================================

    snapshot = orchestrator.get_fleet_snapshot()

    print(f"  Fleet Status:")
    print(f"    Total hubs:    {snapshot.total_hubs}")
    print(f"    Online hubs:   {snapshot.online_hubs}")
    print(f"    Total procs:   {snapshot.total_processes}")
    print()

    for hub in snapshot.hubs:
        print(f"    Hub: {hub.hub_name} ({hub.hub_id})")
        print(f"      Status:     {hub.status}")
        print(f"      Host:       {hub.host}")
        print(f"      Processes:  {hub.process_count}")
        print()

    # =========================================================================
    # Step 6: Send a fleet command (start processes on hub-pc1)
    # =========================================================================

    print("  Sending command: start worker_a on hub-pc1...")
    command_id = orchestrator.send_command(
        hub_id="hub-pc1",
        action="start_process",
        params={"process_list": ["worker_a"], "panel_id": "fleet"},
    )
    print(f"    Command ID: {command_id}")
    print()

    # Give command time to execute
    time.sleep(0.1)

    # Check result - verify process is now running
    snapshot = orchestrator.get_fleet_snapshot()
    for hub in snapshot.hubs:
        if hub.hub_id == "hub-pc1":
            print(f"  Hub PC-1 after command:")
            print(f"    Process count: {hub.process_count}")
            print()

    # =========================================================================
    # Step 7: Cleanup
    # =========================================================================

    print("  Shutting down fleet...")
    agent_1.stop()
    agent_2.stop()
    orchestrator.stop()
    server_1.stop()
    server_2.stop()
    fleet_transport.stop()

    print("  [OK] Fleet shutdown complete")
    print()
    print("=" * 60)
    print("  Next steps:")
    print("  - See 13_fleet_ci_integration.py for CI/CD usage")
    print("  - See 14_fleet_web_dashboard.py for web dashboard")
    print("=" * 60)


if __name__ == "__main__":
    main()
