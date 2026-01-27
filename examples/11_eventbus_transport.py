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
# File: 11_eventbus_transport.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Example demonstrating ProcessHub with EventBus (RabbitMQ) transport.
#   Shows how to use RabbitMQ instead of ZMQ for message passing.
#   Includes WebView dashboard for real-time monitoring.
#
# Prerequisites:
#   1. RabbitMQ server running (default: localhost:5672)
#   2. EventBusClient package installed
#   3. FastAPI installed (for WebView): pip install fastapi uvicorn
#
# Usage:
#   1. Start RabbitMQ: docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:management
#   2. Run server: python 11_eventbus_transport.py server
#   3. Run client: python 11_eventbus_transport.py client
#   4. Open browser: http://localhost:2507
#
# *******************************************************************************
"""
EventBus Transport Example with WebView Dashboard.

This example demonstrates how to:
1. Create a ProcessHubServer using EventBusTransport (RabbitMQ)
2. Create a ProcessHubClient using EventBusTransport
3. Exchange messages via RabbitMQ instead of ZMQ
4. Monitor processes via WebView dashboard

Prerequisites:
    - RabbitMQ server running (docker run -d -p 5672:5672 rabbitmq:management)
    - EventBusClient package installed
    - FastAPI installed (pip install fastapi uvicorn)

The EventBus transport provides:
- Topic-based routing via RabbitMQ exchanges
- Automatic reconnection on connection loss
- JSON or Pickle serialization
- Compatible with existing ProcessHub protocol

WebView dashboard provides:
- Real-time process monitoring at http://localhost:2507
- REST API at http://localhost:2507/api/state
- Swagger docs at http://localhost:2507/docs
"""

import logging
import sys
import time
from pathlib import Path

# Add ProcessHub to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from ProcessHub.transport import HAS_EVENTBUS

if not HAS_EVENTBUS:
    print("ERROR: EventBusClient is required for this example.")
    print("Install from: https://github.com/test-fullautomation/python-rabbitmq-messagebus")
    sys.exit(1)

from ProcessHub.transport import EventBusTransport, EventBusConfig
from ProcessHub.runtime import ProcessHubServer, ProcessHubClient, ClientEvent
from ProcessHub.process import SimpleExecutor

# Check for WebView availability (requires fastapi)
try:
    from ProcessHub.ui import WebView
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False
    WebView = None  # type: ignore

from ProcessHub.ui import NullView

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_server():
    """Run the ProcessHub server with EventBus transport and WebView dashboard."""
    logger.info("Starting ProcessHub Server with EventBus transport...")

    # Create EventBus transport configuration
    config = EventBusConfig(
        host="localhost",
        port=5672,
        exchange_name="process_hub",
        routing_key_prefix="processhub",
        serializer="PickleSerializer",
        auto_reconnect=True,
    )

    # Create transport
    transport = EventBusTransport(config=config)

    # Create executor
    executor = SimpleExecutor(stop_timeout=5.0)

    # Define process configurations
    python_exe = sys.executable
    process_config = {
        "worker_1": {
            "script": python_exe,
            "args": ["-c", "import time; print('Worker 1 running'); time.sleep(3600)"],
            "wait_time": 1.0,
            "process_name": "worker_1",
            "enable": True,
            "description": "Worker 1 - Example background worker",
            "mandatory": False,
            "central_log": False,
            "warning_on_deselect": "",
        },
        "worker_2": {
            "script": python_exe,
            "args": ["-c", "import time; print('Worker 2 running'); time.sleep(3600)"],
            "wait_time": 1.0,
            "process_name": "worker_2",
            "enable": True,
            "description": "Worker 2 - Example background worker",
            "mandatory": False,
            "central_log": False,
            "warning_on_deselect": "",
        },
        "worker_3": {
            "script": python_exe,
            "args": ["-c", "import time; print('Worker 3 running'); time.sleep(3600)"],
            "wait_time": 1.0,
            "process_name": "worker_3",
            "enable": True,
            "description": "Worker 3 - Example background worker",
            "mandatory": True,
            "central_log": True,
            "warning_on_deselect": "Worker 3 is required for full functionality",
        },
    }

    # =========================================================================
    # Define admin callbacks for process control
    # =========================================================================

    # Holder for server reference (used by admin callbacks)
    server_holder = [None]

    def on_process_start(process_names: list[str]) -> dict[str, bool]:
        """Admin callback to start processes."""
        server = server_holder[0]
        results = {}

        for name in process_names:
            cfg = process_config.get(name, {})
            if not cfg:
                logger.warning("No config found for process: %s", name)
                results[name] = False
                continue

            logger.info("Admin starting process: %s", name)
            success, msg, pid = executor.start(name, cfg)
            results[name] = success

            if success and server and pid:
                server.register_admin_process(name, pid)
                logger.info("Process %s started with PID %s", name, pid)
            elif not success:
                logger.error("Failed to start %s: %s", name, msg)

        return results

    def on_process_stop(process_names: list[str], force: bool) -> dict[str, bool]:
        """Admin callback to stop processes."""
        server = server_holder[0]
        results = {}

        for name in process_names:
            logger.info("Admin stopping process: %s (force=%s)", name, force)
            success, msg = executor.stop(name, force=force)
            results[name] = success

            if success and server:
                server.unregister_admin_process(name)
                logger.info("Process %s stopped", name)
            elif not success:
                logger.error("Failed to stop %s: %s", name, msg)

        return results

    def get_available_processes() -> list[str]:
        """Return list of available process names."""
        return list(process_config.keys())

    def get_process_config() -> dict[str, dict]:
        """Return all process configurations."""
        return process_config.copy()

    def add_process_config(name: str, cfg: dict) -> tuple[bool, str]:
        """Add a new process configuration."""
        if name in process_config:
            return False, f"Process '{name}' already exists"
        if not cfg.get("script"):
            return False, "Script path is required"

        process_config[name] = cfg
        logger.info("Added process config: %s", name)
        return True, f"Configuration '{name}' added successfully"

    def update_process_config(name: str, cfg: dict) -> tuple[bool, str]:
        """Update an existing process configuration."""
        if name not in process_config:
            return False, f"Process '{name}' not found"
        if not cfg.get("script"):
            return False, "Script path is required"

        process_config[name] = cfg
        logger.info("Updated process config: %s", name)
        return True, f"Configuration '{name}' updated successfully"

    def remove_process_config(name: str) -> tuple[bool, str]:
        """Remove a process configuration."""
        if name not in process_config:
            return False, f"Process '{name}' not found"
        if executor.is_running(name):
            return False, f"Cannot remove '{name}': process is running"

        del process_config[name]
        logger.info("Removed process config: %s", name)
        return True, f"Configuration '{name}' removed successfully"

    def reset_hub() -> tuple[bool, str]:
        """Reset the hub by removing all connections and stopping all processes."""
        server = server_holder[0]
        if server is None:
            return False, "Server not initialized"
        try:
            return server.reset()
        except Exception as e:
            logger.exception("Error resetting hub")
            return False, f"Error resetting hub: {str(e)}"

    # =========================================================================
    # Create view with admin callbacks
    # =========================================================================

    web_host = "127.0.0.1"
    web_port = 2508
    if HAS_WEBVIEW:
        view = WebView(
            host=web_host,
            port=web_port,
            title="ProcessHub - EventBus Transport",
            on_process_start=on_process_start,
            on_process_stop=on_process_stop,
            get_available_processes=get_available_processes,
            get_process_config=get_process_config,
            add_process_config=add_process_config,
            update_process_config=update_process_config,
            remove_process_config=remove_process_config,
            reset_hub=reset_hub,
        )
        # Start the web view server
        view.start()
    else:
        view = NullView()
        logger.warning("WebView not available. Install fastapi uvicorn for dashboard.")

    # Create server
    server = ProcessHubServer(
        transport=transport,
        executor=executor,
        view=view,
        process_config=process_config,
        refresh_interval=1.0,
    )

    # Set server reference for admin callbacks
    server_holder[0] = server

    print()
    print("=" * 60)
    print("  ProcessHub Server (EventBus/RabbitMQ Transport)")
    print("=" * 60)
    print()
    print(f"  RabbitMQ: {config.host}:{config.port}")
    print(f"  Exchange: {config.exchange_name}")
    print(f"  Routing Key Prefix: {config.routing_key_prefix}")
    print()
    if HAS_WEBVIEW:
        print(f"  Web Dashboard: http://{web_host}:{web_port}")
        print(f"  API Docs:      http://{web_host}:{web_port}/docs")
        print(f"  Admin API:     ENABLED")
        print()
    print("  Available processes:")
    for name in process_config:
        print(f"    - {name}")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    print()

    try:
        server.run()
    except KeyboardInterrupt:
        pass

    # Stop the web view
    if HAS_WEBVIEW:
        view.stop()

    logger.info("Server stopped")


def run_client():
    """Run a ProcessHub client with EventBus transport."""
    logger.info("Starting ProcessHub Client with EventBus transport...")

    # Create EventBus transport (same config as server)
    config = EventBusConfig(
        host="localhost",
        port=5672,
        exchange_name="process_hub",
        routing_key_prefix="processhub",
        serializer="PickleSerializer",
    )

    transport = EventBusTransport(config=config)

    # Create client
    client = ProcessHubClient(
        transport=transport,
        panel_id="eventbus_client_1",
    )

    # Setup callbacks
    def on_connection_registered(data: dict):
        logger.info("Connected to server! Panel: %s", data.get("panel_id"))

    def on_process_started(data: dict):
        logger.info("Process started: success=%s, failed=%s",
                    data.get("success"), data.get("failed_processes"))

    def on_process_stopped(data: dict):
        logger.info("Process stopped: success=%s, message=%s",
                    data.get("success"), data.get("message"))

    def on_process_killed(killed_processes: list):
        logger.info("Restart notification - killed processes: %s", killed_processes)
        # Acknowledge restart
        client.notify_restart_ready()

    def on_process_restarted(data: dict):
        logger.info("Restart completed: success=%s", data.get("success"))

    def on_server_shutdown(data: dict):
        logger.warning("Server shutdown: reason=%s, message=%s",
                       data.get("reason"), data.get("message"))

    # Register callbacks using ClientEvent enum (recommended - prevents typos)
    client.controller.connect(ClientEvent.CONNECTION_REGISTERED, on_connection_registered)
    client.controller.connect(ClientEvent.PROCESS_STARTED, on_process_started)
    client.controller.connect(ClientEvent.PROCESS_STOPPED, on_process_stopped)
    client.controller.connect(ClientEvent.PROCESS_KILLED, on_process_killed)
    client.controller.connect(ClientEvent.PROCESS_RESTARTED, on_process_restarted)
    client.controller.connect(ClientEvent.SERVER_SHUTDOWN, on_server_shutdown)

    print()
    print("=" * 60)
    print("  ProcessHub Client (EventBus/RabbitMQ Transport)")
    print("=" * 60)
    print()

    # Start client
    client.start()

    # Register with server
    logger.info("Registering with server...")
    client.register_connection(session_id="eventbus_session_1")

    # Wait for registration
    if client.wait_for_registration(timeout=10.0):
        logger.info("Registration successful!")
    else:
        logger.error("Registration timeout")
        client.stop()
        return

    # Request processes
    logger.info("Requesting processes: worker_1, worker_2")
    client.request_process_start(["worker_1", "worker_2"])

    print()
    print("  Client connected and processes requested.")
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    # Graceful shutdown - check if still connected to server
    if client.is_registered:
        # Stop processes
        logger.info("Stopping processes...")
        client.request_process_stop(["worker_1", "worker_2"])
        time.sleep(1)

        # Unregister
        client.unregister_connection()
    else:
        logger.info("Server already disconnected, skipping process stop")

    client.stop()
    logger.info("Client stopped")


def print_usage():
    """Print usage information."""
    print("Usage: python 11_eventbus_transport.py [server|client]")
    print()
    print("Prerequisites:")
    print("  1. RabbitMQ server running:")
    print("     docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:management")
    print()
    print("  2. EventBusClient package installed:")
    print("     git clone https://github.com/test-fullautomation/python-rabbitmq-messagebus.git")
    print("     cd python-rabbitmq-messagebus && pip install -e .")
    print()
    print("  3. FastAPI installed (optional, for WebView dashboard):")
    print("     pip install fastapi uvicorn")
    print()
    print("Commands:")
    print("  server  - Run the ProcessHub server with WebView dashboard")
    print("  client  - Run a ProcessHub client")
    print()
    print("Example:")
    print("  Terminal 1: python 11_eventbus_transport.py server")
    print("  Terminal 2: python 11_eventbus_transport.py client")
    print("  Browser:    http://localhost:2507")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "server":
        run_server()
    elif command == "client":
        run_client()
    else:
        print(f"Unknown command: {command}")
        print()
        print_usage()
        sys.exit(1)
