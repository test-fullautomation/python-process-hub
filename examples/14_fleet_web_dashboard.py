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
# File: 14_fleet_web_dashboard.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / February 2026.
#
# Description:
#   Example demonstrating Fleet Orchestrator with web dashboard.
#   Shows how to deploy a fleet with EventBus (RabbitMQ) transport
#   and a web-based fleet monitoring dashboard.
#
# Prerequisites:
#   1. RabbitMQ server running (default: localhost:5672)
#   2. EventBusClient package installed
#   3. FastAPI installed: pip install fastapi uvicorn
#
# Usage:
#   1. Start RabbitMQ:
#      docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:management
#
#   2. Run orchestrator with dashboard:
#      python 14_fleet_web_dashboard.py orchestrator
#
#   3. Run hub agent (on each test machine):
#      python 14_fleet_web_dashboard.py agent --hub-id=bench-1 --hub-name="HIL Bench 1"
#
#   4. Open fleet dashboard:
#      http://localhost:2510
#
# *******************************************************************************
"""
Fleet Web Dashboard Example.

This example demonstrates a production-like fleet deployment:
1. FleetOrchestrator with REST API and web dashboard
2. HubAgents on separate machines using EventBus (RabbitMQ) transport
3. Real-time fleet monitoring via browser

Architecture:
    ┌─────────────────────────────────┐
    │   Orchestrator Machine          │
    │   - FleetOrchestrator           │
    │   - FleetWebAPI (port 2510)     │
    └──────────────┬──────────────────┘
                   │ RabbitMQ (fleet.* topics)
         ┌─────────┴─────────┐
         │                   │
    ┌────▼─────┐       ┌────▼─────┐
    │ Machine 1│       │ Machine 2│
    │ HubAgent │       │ HubAgent │
    │ + Server │       │ + Server │
    └──────────┘       └──────────┘

REST API endpoints:
    GET  /api/fleet/status              Fleet-wide status
    GET  /api/fleet/hubs                List all hubs
    GET  /api/fleet/hubs/{hub_id}       Single hub details
    POST /api/fleet/hubs/{hub_id}/start Start processes on hub
    POST /api/fleet/hubs/{hub_id}/stop  Stop processes on hub
    POST /api/fleet/hubs/{hub_id}/reset Reset hub
"""

import argparse
import logging
import platform
import sys
import time
from pathlib import Path

# Add ProcessHub to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from ProcessHub.transport import HAS_EVENTBUS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_orchestrator(args):
    """Run the FleetOrchestrator with web dashboard."""
    if not HAS_EVENTBUS:
        print("ERROR: EventBusClient is required for this example.")
        print("Install from: https://github.com/test-fullautomation/python-rabbitmq-messagebus")
        sys.exit(1)

    from ProcessHub.transport import EventBusTransport, EventBusConfig
    from ProcessHub.fleet import FleetOrchestrator

    # Check for FleetWebAPI availability
    try:
        from ProcessHub.fleet.web_api import FleetWebAPI
        HAS_WEB_API = True
    except ImportError:
        HAS_WEB_API = False

    # Create EventBus transport for fleet communication
    config = EventBusConfig(
        host=args.rabbitmq_host,
        port=args.rabbitmq_port,
        exchange_name="process_hub_fleet",
        routing_key_prefix="fleet",
        serializer="PickleSerializer",
        auto_reconnect=True,
    )

    fleet_transport = EventBusTransport(config=config)

    # Create orchestrator
    orchestrator = FleetOrchestrator(
        transport=fleet_transport,
        health_timeout=args.health_timeout,
        tick_interval=5.0,
    )
    orchestrator.start()

    # Start web dashboard (optional)
    web_api = None
    if HAS_WEB_API:
        web_api = FleetWebAPI(
            orchestrator=orchestrator,
            host=args.web_host,
            port=args.web_port,
        )
        web_api.start()

    print()
    print("=" * 60)
    print("  Fleet Orchestrator + Web Dashboard")
    print("=" * 60)
    print()
    print(f"  RabbitMQ:        {args.rabbitmq_host}:{args.rabbitmq_port}")
    print(f"  Health timeout:  {args.health_timeout}s")
    print()
    if HAS_WEB_API:
        print(f"  Fleet Dashboard: http://{args.web_host}:{args.web_port}")
        print(f"  REST API:        http://{args.web_host}:{args.web_port}/api/fleet/status")
        print(f"  API Docs:        http://{args.web_host}:{args.web_port}/docs")
    else:
        print("  Web dashboard not available. Install: pip install fastapi uvicorn")
    print()
    print("  Waiting for hub agents to connect...")
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    print()

    try:
        while True:
            orchestrator.tick()

            # Log fleet status periodically
            snapshot = orchestrator.get_fleet_snapshot()
            if snapshot.total_hubs > 0:
                logger.info(
                    "Fleet: %d hubs (%d online), %d processes",
                    snapshot.total_hubs,
                    snapshot.online_hubs,
                    snapshot.total_processes,
                )

            time.sleep(5)
    except KeyboardInterrupt:
        pass

    print()
    print("Shutting down...")

    if web_api:
        web_api.stop()
    orchestrator.stop()

    print("Fleet orchestrator stopped.")


def run_agent(args):
    """Run a HubAgent alongside a ProcessHubServer."""
    if not HAS_EVENTBUS:
        print("ERROR: EventBusClient is required for this example.")
        print("Install from: https://github.com/test-fullautomation/python-rabbitmq-messagebus")
        sys.exit(1)

    from ProcessHub.transport import EventBusTransport, EventBusConfig
    from ProcessHub.runtime.server import ProcessHubServer
    from ProcessHub.process.executor import SimpleExecutor
    from ProcessHub.ui.null_view import NullView
    from ProcessHub.fleet import HubAgent

    # Create local transport for ProcessHub server
    local_config = EventBusConfig(
        host=args.rabbitmq_host,
        port=args.rabbitmq_port,
        exchange_name="process_hub_local",
        routing_key_prefix="processhub",
        serializer="PickleSerializer",
        auto_reconnect=True,
    )
    local_transport = EventBusTransport(config=local_config)

    # Create fleet transport for hub agent
    fleet_config = EventBusConfig(
        host=args.rabbitmq_host,
        port=args.rabbitmq_port,
        exchange_name="process_hub_fleet",
        routing_key_prefix="fleet",
        serializer="PickleSerializer",
        auto_reconnect=True,
    )
    fleet_transport = EventBusTransport(config=fleet_config)

    # Create process executor and config
    executor = SimpleExecutor(stop_timeout=5.0)
    python_exe = sys.executable
    process_config = {
        "worker_1": {
            "script": python_exe,
            "args": ["-c", "import time; print('Worker 1 running'); time.sleep(3600)"],
            "wait_time": 1.0,
            "process_name": "worker_1",
        },
        "worker_2": {
            "script": python_exe,
            "args": ["-c", "import time; print('Worker 2 running'); time.sleep(3600)"],
            "wait_time": 1.0,
            "process_name": "worker_2",
        },
    }

    # Create ProcessHub server
    server = ProcessHubServer(
        transport=local_transport,
        executor=executor,
        view=NullView(),
        process_config=process_config,
    )
    server.start()

    # Create and start hub agent (sidecar)
    agent = HubAgent(
        server=server,
        transport=fleet_transport,
        hub_id=args.hub_id,
        hub_name=args.hub_name or f"Hub {args.hub_id}",
        heartbeat_interval=args.heartbeat_interval,
        status_interval=args.status_interval,
    )
    agent.start()

    print()
    print("=" * 60)
    print(f"  Hub Agent: {args.hub_name or args.hub_id}")
    print("=" * 60)
    print()
    print(f"  Hub ID:          {args.hub_id}")
    print(f"  Hub Name:        {args.hub_name or args.hub_id}")
    print(f"  Host:            {platform.node()}")
    print(f"  RabbitMQ:        {args.rabbitmq_host}:{args.rabbitmq_port}")
    print(f"  Heartbeat:       every {args.heartbeat_interval}s")
    print(f"  Status report:   every {args.status_interval}s")
    print()
    print("  Available processes:")
    for name in process_config:
        print(f"    - {name}")
    print()
    print("  Agent announced to fleet orchestrator.")
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    print()

    try:
        # Run server main loop (handles tick + health check)
        while True:
            messages = server.core.tick()
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass

    print()
    print("Shutting down...")

    agent.stop()
    server.stop()

    print(f"Hub agent '{args.hub_id}' stopped.")


def main():
    """Parse arguments and run the appropriate component."""
    parser = argparse.ArgumentParser(
        description="Fleet Web Dashboard Example",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run orchestrator with dashboard
  python 14_fleet_web_dashboard.py orchestrator

  # Run hub agent
  python 14_fleet_web_dashboard.py agent --hub-id=bench-1 --hub-name="HIL Bench 1"

  # Run with custom RabbitMQ
  python 14_fleet_web_dashboard.py orchestrator --rabbitmq-host=10.0.0.5
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Component to run")

    # Orchestrator subcommand
    orch_parser = subparsers.add_parser("orchestrator", help="Run fleet orchestrator")
    orch_parser.add_argument("--rabbitmq-host", default="localhost", help="RabbitMQ host")
    orch_parser.add_argument("--rabbitmq-port", type=int, default=5672, help="RabbitMQ port")
    orch_parser.add_argument("--web-host", default="127.0.0.1", help="Web dashboard host")
    orch_parser.add_argument("--web-port", type=int, default=2510, help="Web dashboard port")
    orch_parser.add_argument(
        "--health-timeout", type=float, default=30.0, help="Hub health timeout (seconds)"
    )

    # Agent subcommand
    agent_parser = subparsers.add_parser("agent", help="Run hub agent")
    agent_parser.add_argument("--hub-id", required=True, help="Unique hub identifier")
    agent_parser.add_argument("--hub-name", default="", help="Human-readable hub name")
    agent_parser.add_argument("--rabbitmq-host", default="localhost", help="RabbitMQ host")
    agent_parser.add_argument("--rabbitmq-port", type=int, default=5672, help="RabbitMQ port")
    agent_parser.add_argument(
        "--heartbeat-interval", type=float, default=5.0, help="Heartbeat interval (seconds)"
    )
    agent_parser.add_argument(
        "--status-interval", type=float, default=10.0, help="Status report interval (seconds)"
    )

    args = parser.parse_args()

    if args.command == "orchestrator":
        run_orchestrator(args)
    elif args.command == "agent":
        run_agent(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
