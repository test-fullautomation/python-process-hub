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
# File: 13_fleet_ci_integration.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / February 2026.
#
# Description:
#   Example demonstrating FleetClient usage in CI/CD pipelines.
#   Shows how to use FleetClient to query fleet status, send commands,
#   and integrate with automated test pipelines.
#
# Prerequisites:
#   For real deployment:
#   1. RabbitMQ server running
#   2. FleetOrchestrator running on central machine
#   3. HubAgents running on each test machine
#
# Usage:
#   python 13_fleet_ci_integration.py
#
# *******************************************************************************
"""
Fleet CI/CD Integration Example.

This example demonstrates how to use FleetClient in CI/CD pipelines:
1. Connect to a running FleetOrchestrator
2. Verify fleet health before running tests
3. Start required processes on target hubs
4. Wait for processes to be ready
5. Run tests (simulated)
6. Stop processes and report results

In a real CI pipeline (Jenkins, GitLab CI, GitHub Actions), you would:
- Import FleetClient and connect to your orchestrator
- Use it to manage test infrastructure before/after test runs

This example uses InMemoryTransport for self-contained demonstration.
For real deployments, replace with EventBusTransport pointing to your
RabbitMQ server.
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

from ProcessHub.fleet import FleetOrchestrator, HubAgent, FleetClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def setup_test_fleet():
    """Set up a test fleet for demonstration purposes.

    In a real CI/CD pipeline, the fleet (orchestrator + hub agents) would
    already be running. You would only use FleetClient to interact with it.
    """
    fleet_transport = InMemoryTransport()
    fleet_transport.start()

    # Create two servers simulating test machines
    servers = []
    agents = []
    for i, hub_config in enumerate([
        {
            "hub_id": "hil-bench-1",
            "hub_name": "HIL Bench 1",
            "processes": {
                "ecu_simulator": {"script": "python", "args": ["-c", "pass"]},
                "can_bridge": {"script": "python", "args": ["-c", "pass"]},
                "trace_recorder": {"script": "python", "args": ["-c", "pass"]},
            },
        },
        {
            "hub_id": "hil-bench-2",
            "hub_name": "HIL Bench 2",
            "processes": {
                "ecu_simulator": {"script": "python", "args": ["-c", "pass"]},
                "can_bridge": {"script": "python", "args": ["-c", "pass"]},
                "log_collector": {"script": "python", "args": ["-c", "pass"]},
            },
        },
    ]):
        local_transport = InMemoryTransport()
        executor = MockExecutor()
        server = ProcessHubServer(
            transport=local_transport,
            executor=executor,
            view=NullView(),
            process_config=hub_config["processes"],
        )
        server.start()
        servers.append(server)

        agent = HubAgent(
            server=server,
            transport=fleet_transport,
            hub_id=hub_config["hub_id"],
            hub_name=hub_config["hub_name"],
            heartbeat_interval=5.0,
            status_interval=10.0,
        )
        agent.start()
        agents.append(agent)

    orchestrator = FleetOrchestrator(
        transport=fleet_transport,
        health_timeout=30.0,
    )
    orchestrator.start()

    return fleet_transport, orchestrator, servers, agents


def teardown_test_fleet(fleet_transport, orchestrator, servers, agents):
    """Tear down the test fleet."""
    for agent in agents:
        agent.stop()
    orchestrator.stop()
    for server in servers:
        server.stop()
    fleet_transport.stop()


def main():
    """Demonstrate CI/CD pipeline integration with FleetClient."""
    print()
    print("=" * 60)
    print("  Fleet CI/CD Integration Example")
    print("=" * 60)
    print()

    # =========================================================================
    # Setup: In real CI, the fleet is already running
    # =========================================================================

    fleet_transport, orchestrator, servers, agents = setup_test_fleet()

    # =========================================================================
    # CI Pipeline Step 1: Connect FleetClient to orchestrator
    # =========================================================================
    # In real CI, connect via EventBusTransport to RabbitMQ:
    #
    #   from ProcessHub.transport import EventBusTransport, EventBusConfig
    #   config = EventBusConfig(host="rabbitmq.company.com", port=5672,
    #                           exchange_name="fleet", routing_key_prefix="fleet")
    #   fleet_transport = EventBusTransport(config=config)
    #   client = FleetClient(transport=fleet_transport)

    client = FleetClient(
        transport=fleet_transport,
        orchestrator=orchestrator,
    )

    print("  Step 1: Connect to fleet orchestrator")
    print("  [OK] FleetClient connected")
    print()

    # =========================================================================
    # CI Pipeline Step 2: Verify fleet health
    # =========================================================================

    print("  Step 2: Verify fleet health")
    snapshot = client.get_fleet_status()

    print(f"    Total hubs:  {snapshot.total_hubs}")
    print(f"    Online hubs: {snapshot.online_hubs}")

    # Abort if not enough hubs are online
    required_hubs = 2
    if snapshot.online_hubs < required_hubs:
        print(f"    [FAIL] Need {required_hubs} online hubs, only {snapshot.online_hubs}")
        print("    Aborting CI pipeline.")
        teardown_test_fleet(fleet_transport, orchestrator, servers, agents)
        return

    print(f"    [OK] {snapshot.online_hubs} hubs online (need {required_hubs})")
    print()

    # List available hubs
    for hub in snapshot.hubs:
        print(f"    {hub.hub_name} ({hub.hub_id}): {hub.status}")

    print()

    # =========================================================================
    # CI Pipeline Step 3: Start required processes
    # =========================================================================

    print("  Step 3: Start test infrastructure processes")

    # Start ECU simulators on both benches
    cmd1 = client.start_processes("hil-bench-1", ["ecu_simulator", "can_bridge"])
    cmd2 = client.start_processes("hil-bench-2", ["ecu_simulator", "can_bridge"])

    print(f"    Started ecu_simulator + can_bridge on hil-bench-1 (cmd: {cmd1})")
    print(f"    Started ecu_simulator + can_bridge on hil-bench-2 (cmd: {cmd2})")

    # Give processes time to start
    time.sleep(0.1)

    # Verify processes are running
    snapshot = client.get_fleet_status()
    for hub in snapshot.hubs:
        print(f"    {hub.hub_name}: {hub.process_count} processes running")

    print("    [OK] Infrastructure ready")
    print()

    # =========================================================================
    # CI Pipeline Step 4: Run tests (simulated)
    # =========================================================================

    print("  Step 4: Run test suite")
    print("    Running test_ecu_communication... PASSED")
    print("    Running test_can_messages...      PASSED")
    print("    Running test_trace_recording...   PASSED")
    print("    [OK] All tests passed")
    print()

    # =========================================================================
    # CI Pipeline Step 5: Cleanup
    # =========================================================================

    print("  Step 5: Cleanup - stop processes")

    client.stop_processes("hil-bench-1", ["ecu_simulator", "can_bridge"])
    client.stop_processes("hil-bench-2", ["ecu_simulator", "can_bridge"])

    time.sleep(0.1)

    print("    [OK] All processes stopped")
    print()

    # =========================================================================
    # CI Pipeline Step 6: Report results
    # =========================================================================

    print("  Step 6: Final fleet status")
    snapshot = client.get_fleet_status()
    print(f"    Online hubs: {snapshot.online_hubs}/{snapshot.total_hubs}")
    print(f"    Running processes: {snapshot.total_processes}")
    print()

    # =========================================================================
    # Teardown (only for this demo)
    # =========================================================================

    teardown_test_fleet(fleet_transport, orchestrator, servers, agents)

    print("=" * 60)
    print("  CI/CD Pipeline Complete")
    print()
    print("  In a real pipeline (Jenkins, GitLab CI, etc.):")
    print("  - FleetClient connects to existing orchestrator via RabbitMQ")
    print("  - No need to set up fleet - it runs as infrastructure")
    print("  - Use FleetClient in pytest fixtures for test setup/teardown")
    print("=" * 60)


if __name__ == "__main__":
    main()
