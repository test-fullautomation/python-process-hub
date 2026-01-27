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
# File: 02_basic_client.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Basic example of a Process Hub Client.
#   Demonstrates how to connect to a server, request processes,
#   and handle server responses.
#
# Usage:
#   1. First start the server: python 01_basic_server.py
#   2. Then run this client: python 02_basic_client.py
#
# *******************************************************************************
"""
Basic Process Hub Client Example.

This example demonstrates how to:
1. Create a ProcessHubClient with ZMQ transport
2. Connect to the server
3. Request process start/stop
4. Handle server responses via callbacks
5. Gracefully disconnect

The client will:
- Connect to the Process Hub Server
- Register itself with a panel ID
- Request processes to be started
- Receive notifications about process state
"""

import logging
import sys
import time
from pathlib import Path

# Add ProcessHub to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from ProcessHub.runtime import ProcessHubClient, ClientController
from ProcessHub.transport import ZmqTransport

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_client(panel_id: str) -> ProcessHubClient:
    """
    Create and configure a Process Hub Client.

    **Arguments:**

    * ``panel_id``

      / *Condition*: required / *Type*: str /

      Unique identifier for this client/panel.

    **Returns:**

    / *Type*: ProcessHubClient /

    Configured client instance.
    """
    # Create ZMQ transport (client mode - no broker)
    transport = ZmqTransport(
        start_broker=False,  # Client doesn't start broker
        xpub_port=5555,
        xsub_port=5556,
    )

    # Create client (controller is created internally)
    client = ProcessHubClient(
        transport=transport,
        panel_id=panel_id,
        default_timeout=30.0,
    )

    return client


def setup_callbacks(controller: ClientController) -> None:
    """
    Set up callback handlers for server responses.

    **Arguments:**

    * ``controller``

      / *Condition*: required / *Type*: ClientController /

      The client controller to configure.
    """
    def on_registered(data: dict) -> None:
        """Called when registration is confirmed."""
        logger.info("Registration confirmed: %s", data)

    def on_process_started(data: dict) -> None:
        """Called when processes are started."""
        if data.get("success"):
            logger.info("Processes started successfully!")
        else:
            logger.error(
                "Failed to start processes: %s",
                data.get("error_message", "Unknown error")
            )
            if data.get("failed_processes"):
                logger.error("Failed processes: %s", data["failed_processes"])

    def on_process_stopped(data: dict) -> None:
        """Called when processes are stopped."""
        logger.info("Processes stopped: %s", data)

    def on_process_killed(killed_processes: list) -> None:
        """Called when server detects dead processes."""
        logger.warning("Server detected dead processes: %s", killed_processes)
        logger.info("Server will coordinate restart...")

    def on_process_restarted(data: dict) -> None:
        """Called when restart is complete."""
        if data.get("success"):
            logger.info("Processes restarted successfully!")
        else:
            logger.error("Restart failed: %s", data.get("failed_processes"))

    def on_timeout(message: str) -> None:
        """Called on server timeout."""
        logger.error("Server timeout: %s", message)

    # Connect callbacks
    controller.connect("connection_registered", on_registered)
    controller.connect("process_started", on_process_started)
    controller.connect("process_stopped", on_process_stopped)
    controller.connect("process_killed", on_process_killed)
    controller.connect("process_restarted", on_process_restarted)
    controller.connect("server_timeout", on_timeout)


def main():
    """Run the Process Hub Client example."""
    panel_id = "example_panel_01"
    session_id = "example_session"

    logger.info("Creating client with panel ID: %s", panel_id)
    client = create_client(panel_id)

    # Set up callbacks using client's built-in controller
    setup_callbacks(client.controller)

    try:
        # Start the client (connects transport)
        logger.info("Starting client...")
        client.start()

        # Register with server (must provide session_id)
        logger.info("Registering with server (session=%s)...", session_id)
        client.register_connection(session_id=session_id)

        # Wait for registration to complete (blocking)
        logger.info("Waiting for registration confirmation...")
        if not client.wait_for_registration(timeout=5.0):
            logger.error("Failed to register with server!")
            logger.error("Make sure the server is running: python 01_basic_server.py")
            return

        logger.info("Registration successful!")

        # Request processes to start
        processes_to_start = ["example_process", "worker_1"]
        logger.info("Requesting processes: %s", processes_to_start)
        client.request_process_start(processes_to_start)

        # Wait for response (callbacks will be invoked)
        logger.info("Waiting for responses (callbacks handle messages)...")
        time.sleep(5)

        # Request to stop processes
        logger.info("Requesting process stop...")
        client.request_process_stop(processes_to_start)

        # Wait for stop confirmation
        time.sleep(2)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    except RuntimeError as e:
        logger.error("Runtime error: %s", e)

    finally:
        # Unregister and disconnect
        if client.is_registered:
            logger.info("Unregistering from server...")
            client.unregister_connection()
            time.sleep(0.5)

        logger.info("Stopping client...")
        client.stop()
        logger.info("Client stopped")


if __name__ == "__main__":
    main()
