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
# File: 04_restart_coordination.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Example demonstrating the coordinated restart flow.
#   Shows how the server detects dead processes and coordinates
#   restart with all connected clients.
#
# Usage:
#   1. First start the server: python 01_basic_server.py
#   2. Then run this example: python 04_restart_coordination.py
#
# *******************************************************************************
"""
Coordinated Restart Example.

This example demonstrates the restart coordination flow:

1. Server detects a process has died (health check)
2. Server enters restart state machine:
   - IDLE -> DETECTING -> NOTIFYING -> AWAITING_ACK -> RESTARTING -> DONE
3. Server notifies all connected clients about dead processes
4. Clients acknowledge they're ready for restart
5. Server restarts the processes
6. Server notifies clients of restart completion

The state machine ensures:
- All clients are aware of the restart
- Clients can prepare (save state, pause operations)
- Restart happens in a coordinated manner
- Timeout handling if clients don't respond
"""

import logging
import sys
import time
from pathlib import Path

# Add ProcessHub to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from ProcessHub.runtime import ProcessHubClient
from ProcessHub.transport import ZmqTransport

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RestartAwareClient:
    """
    Client that properly handles restart notifications.

    Demonstrates best practices for handling process restarts:
    1. Receive kill notification
    2. Save any necessary state
    3. Acknowledge readiness for restart
    4. Wait for restart completion
    5. Resume operations
    """

    def __init__(self, panel_id: str, session_id: str = "default_session"):
        """
        Initialize restart-aware client.

        **Arguments:**

        * ``panel_id``

          / *Condition*: required / *Type*: str /

          Unique identifier for this panel.

        * ``session_id``

          / *Condition*: optional / *Type*: str / *Default*: "default_session" /

          Session identifier for grouping panels.
        """
        self.panel_id = panel_id
        self.session_id = session_id
        self.transport = ZmqTransport(
            start_broker=False,
            xpub_port=5555,
            xsub_port=5556,
        )
        self.client = ProcessHubClient(
            transport=self.transport,
            panel_id=panel_id,
            default_timeout=30.0,
        )

        # State tracking
        self.is_restarting = False
        self.killed_processes: list[str] = []

        self._setup_callbacks()

    def _setup_callbacks(self) -> None:
        """Set up callback handlers with restart handling."""

        def on_registered(data: dict) -> None:
            """Handle registration confirmation."""
            logger.info("[%s] Registered with server", self.panel_id)

        def on_started(data: dict) -> None:
            """Handle process start response."""
            if data.get("success"):
                logger.info("[%s] Processes started successfully", self.panel_id)
            else:
                logger.error(
                    "[%s] Failed to start: %s",
                    self.panel_id,
                    data.get("error_message")
                )

        def on_process_killed(killed_processes: list) -> None:
            """
            Handle kill notification from server.

            This is the key callback for restart coordination.
            When received, the client should:
            1. Save any state that needs to be preserved
            2. Pause operations that depend on the dead processes
            3. Acknowledge readiness for restart
            """
            logger.warning(
                "[%s] Received KILL notification for: %s",
                self.panel_id,
                killed_processes
            )

            self.is_restarting = True
            self.killed_processes = killed_processes

            # Step 1: Save state (simulated)
            logger.info("[%s] Saving application state...", self.panel_id)
            time.sleep(0.5)  # Simulate state saving

            # Step 2: Pause dependent operations
            logger.info("[%s] Pausing operations...", self.panel_id)

            # Step 3: Acknowledge readiness
            logger.info("[%s] Sending restart acknowledgment...", self.panel_id)
            self.client.notify_restart_ready()

        def on_process_restarted(data: dict) -> None:
            """
            Handle restart completion notification.

            When received, the client should:
            1. Verify processes are running
            2. Restore any saved state
            3. Resume operations
            """
            if data.get("success"):
                logger.info(
                    "[%s] Restart completed successfully!",
                    self.panel_id
                )

                # Resume operations
                logger.info("[%s] Resuming operations...", self.panel_id)
                self.is_restarting = False
                self.killed_processes = []

            else:
                logger.error(
                    "[%s] Restart FAILED! Failed processes: %s",
                    self.panel_id,
                    data.get("failed_processes")
                )
                # Handle restart failure - maybe notify user, retry, etc.

        def on_restart_failed(data: dict) -> None:
            """Handle restart failure (timeout, etc.)."""
            logger.error(
                "[%s] Restart failed: %s",
                self.panel_id,
                data
            )
            self.is_restarting = False

        # Connect callbacks using client's built-in controller
        self.client.controller.connect("connection_registered", on_registered)
        self.client.controller.connect("process_started", on_started)
        self.client.controller.connect("process_killed", on_process_killed)
        self.client.controller.connect("process_restarted", on_process_restarted)
        self.client.controller.connect("restart_failed", on_restart_failed)

    def connect(self) -> None:
        """Connect to server."""
        logger.info("[%s] Connecting to server...", self.panel_id)
        self.client.start()
        self.client.register_connection(session_id=self.session_id)

        # Wait for registration to complete
        if not self.client.wait_for_registration(timeout=5.0):
            logger.error("[%s] Failed to register! Is server running?", self.panel_id)
            raise RuntimeError(f"Failed to register panel {self.panel_id}")

        logger.info("[%s] Connected and registered", self.panel_id)

    def request_processes(self, processes: list[str]) -> None:
        """Request processes."""
        logger.info("[%s] Requesting processes: %s", self.panel_id, processes)
        self.client.request_process_start(processes)

    def disconnect(self) -> None:
        """Disconnect from server."""
        logger.info("[%s] Disconnecting...", self.panel_id)
        if self.client.is_registered:
            self.client.unregister_connection()
            time.sleep(0.3)
        self.client.stop()


def main():
    """Run the restart coordination example."""
    logger.info("=" * 60)
    logger.info("Restart Coordination Example")
    logger.info("=" * 60)
    logger.info("")
    logger.info("This example demonstrates coordinated restart handling.")
    logger.info("To trigger a restart, you need to manually kill a process")
    logger.info("that the client has requested.")
    logger.info("")
    logger.info("Steps:")
    logger.info("1. Client connects and requests processes")
    logger.info("2. Find the PID of 'worker_1' in the server console")
    logger.info("3. Kill that process (e.g., 'taskkill /PID <pid>' on Windows)")
    logger.info("4. Watch the restart coordination happen")
    logger.info("")
    logger.info("=" * 60)

    client = RestartAwareClient("restart_demo_panel", session_id="restart_demo")

    try:
        # Connect to server
        client.connect()
        time.sleep(1)

        # Request some processes
        client.request_processes(["worker_1", "worker_2"])
        time.sleep(2)

        logger.info("")
        logger.info("=" * 60)
        logger.info("Processes started. Now kill 'worker_1' to trigger restart.")
        logger.info("The client will automatically handle the restart flow.")
        logger.info("=" * 60)
        logger.info("")

        # Main loop - wait for restart or user interrupt
        # Note: Messages are handled automatically via callbacks
        logger.info("Waiting for events (Ctrl+C to exit)...")
        while True:
            if client.is_restarting:
                logger.info("[Status] Restart in progress...")

            time.sleep(1.0)

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")

    finally:
        client.disconnect()
        logger.info("Example complete")


if __name__ == "__main__":
    main()
