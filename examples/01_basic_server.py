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
# File: 01_basic_server.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Basic example of running a Process Hub Server.
#   Demonstrates how to start a server that listens for client connections
#   and manages process lifecycle.
#
# Usage:
#   python 01_basic_server.py
#
# *******************************************************************************
"""
Basic Process Hub Server Example.

This example demonstrates how to:
1. Create a ProcessHubServer with ZMQ transport
2. Configure process definitions
3. Run the server main loop
4. Handle graceful shutdown

The server will:
- Listen for client connections on ZMQ ports
- Accept process start/stop requests
- Monitor process health
- Coordinate process restarts
"""

import logging
import sys
from pathlib import Path

# Add ProcessHub to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from ProcessHub.runtime import ProcessHubServer
from ProcessHub.transport import ZmqTransport
from ProcessHub.ui import ConsoleView
from ProcessHub.process import SimpleExecutor

# Configure logging - use DEBUG to see message flow
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Reduce noise from some loggers
logging.getLogger("asyncio").setLevel(logging.WARNING)


def create_server() -> ProcessHubServer:
    """
    Create and configure the Process Hub Server.

    **Returns:**

    / *Type*: ProcessHubServer /

    Configured server instance.
    """
    # Create ZMQ transport with broker
    # The server starts the broker, clients connect to it
    transport = ZmqTransport(
        start_broker=True,
        xpub_port=5555,  # Clients subscribe here
        xsub_port=5556,  # Clients publish here
    )

    # Create a simple executor for process management
    executor = SimpleExecutor(stop_timeout=5.0)

    # Create console view for TUI display
    # Set clear_screen=False to see debug logs
    view = ConsoleView(clear_screen=True)

    # Define process configurations
    # In production, load these from a JSON file
    # Use sys.executable to get the current Python interpreter path
    python_exe = sys.executable

    process_config = {
        "example_process": {
            "script": python_exe,
            "args": ["-c", "import time; print('example_process running'); time.sleep(3600)"],
            "wait_time": 1.0,
            "process_name": "example_process",
        },
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

    # Create server
    server = ProcessHubServer(
        transport=transport,
        executor=executor,
        view=view,
        process_config=process_config,
        refresh_interval=0.5,  # Main loop refresh rate
        restart_timeout=30.0,  # Timeout for restart coordination
    )

    return server


def main():
    """Run the Process Hub Server."""
    logger.info("Starting Process Hub Server...")

    server = create_server()

    # Note: server.run() handles signal handlers internally
    # No need for extra signal handlers here

    logger.info("Server listening on ports 5555 (XPUB) and 5556 (XSUB)")
    logger.info("Press Ctrl+C to stop")

    # Run the server (blocks until Ctrl+C or stop() is called)
    # The run() method handles cleanup automatically
    server.run()

    logger.info("Server stopped")


if __name__ == "__main__":
    main()
