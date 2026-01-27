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
# File: 03_multi_client.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Multi-client example demonstrating shared process management.
#   Shows how multiple clients can request the same processes,
#   and how reference counting works.
#
# Usage:
#   1. First start the server: python 01_basic_server.py
#   2. Then run this example: python 03_multi_client.py
#
# *******************************************************************************
"""
Multi-Client Process Hub Example.

This example demonstrates:
1. Multiple clients connecting to the same server
2. Shared process ownership (reference counting)
3. Process lifecycle with multiple requesters
4. Proper cleanup when clients disconnect

Key concept - Reference Counting:
- When Panel A requests "worker_1", it starts
- When Panel B also requests "worker_1", it's already running (shared)
- When Panel A disconnects, "worker_1" keeps running (Panel B still needs it)
- When Panel B disconnects, "worker_1" finally stops (no more requesters)
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


class PanelClient:
    """
    Wrapper class representing a panel/client.

    Encapsulates the client and panel-specific logic.
    """

    def __init__(self, panel_id: str, session_id: str = "default_session"):
        """
        Initialize panel client.

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
        self._setup_callbacks()

    def _setup_callbacks(self) -> None:
        """Set up callback handlers."""
        def on_registered(data: dict) -> None:
            logger.info("[%s] Registered with server!", self.panel_id)

        def on_started(data: dict) -> None:
            if data.get("success"):
                logger.info("[%s] Processes started!", self.panel_id)
            else:
                logger.error("[%s] Start failed: %s", self.panel_id, data)

        def on_stopped(data: dict) -> None:
            logger.info("[%s] Processes stopped: %s", self.panel_id, data)

        def on_killed(killed: list) -> None:
            logger.warning("[%s] Detected killed processes: %s", self.panel_id, killed)

        # Use client's built-in controller
        self.client.controller.connect("connection_registered", on_registered)
        self.client.controller.connect("process_started", on_started)
        self.client.controller.connect("process_stopped", on_stopped)
        self.client.controller.connect("process_killed", on_killed)

    def connect(self) -> None:
        """Connect to server and register."""
        logger.info("[%s] Connecting...", self.panel_id)
        self.client.start()
        self.client.register_connection(session_id=self.session_id)

        # Wait for registration to complete
        if not self.client.wait_for_registration(timeout=5.0):
            logger.error("[%s] Failed to register! Is server running?", self.panel_id)
            raise RuntimeError(f"Failed to register panel {self.panel_id}")

    def request_processes(self, processes: list[str]) -> None:
        """Request processes to start."""
        logger.info("[%s] Requesting: %s", self.panel_id, processes)
        self.client.request_process_start(processes)

    def release_processes(self, processes: list[str]) -> None:
        """Release processes (may stop if no other requesters)."""
        logger.info("[%s] Releasing: %s", self.panel_id, processes)
        self.client.request_process_stop(processes)

    def disconnect(self) -> None:
        """Unregister and disconnect."""
        logger.info("[%s] Disconnecting...", self.panel_id)
        if self.client.is_registered:
            self.client.unregister_connection()
            time.sleep(0.3)
        self.client.stop()


def main():
    """Run the multi-client example."""
    logger.info("=" * 60)
    logger.info("Multi-Client Process Hub Example")
    logger.info("=" * 60)

    # Create two panel clients (same session for shared processes)
    panel_a = PanelClient("panel_A", session_id="shared_session")
    panel_b = PanelClient("panel_B", session_id="shared_session")

    try:
        # Both panels connect
        logger.info("\n--- Phase 1: Both panels connect ---")
        panel_a.connect()
        panel_b.connect()
        time.sleep(1)

        # Panel A requests worker_1 and worker_2
        logger.info("\n--- Phase 2: Panel A requests worker_1, worker_2 ---")
        panel_a.request_processes(["worker_1", "worker_2"])
        time.sleep(2)

        # Panel B also requests worker_1 (shared) and example_process (new)
        logger.info("\n--- Phase 3: Panel B requests worker_1 (shared), example_process ---")
        panel_b.request_processes(["worker_1", "example_process"])
        time.sleep(2)

        # Now worker_1 has 2 requesters: panel_A and panel_B
        logger.info("\n--- Current state ---")
        logger.info("worker_1: owned by [panel_A, panel_B]")
        logger.info("worker_2: owned by [panel_A]")
        logger.info("example_process: owned by [panel_B]")
        time.sleep(2)

        # Panel A disconnects - worker_1 should keep running (panel_B needs it)
        # worker_2 should stop (no more requesters)
        logger.info("\n--- Phase 4: Panel A disconnects ---")
        logger.info("Expected: worker_2 stops, worker_1 keeps running")
        panel_a.disconnect()
        time.sleep(2)

        logger.info("\n--- After Panel A disconnect ---")
        logger.info("worker_1: owned by [panel_B] - still running")
        logger.info("worker_2: no owners - stopped")
        logger.info("example_process: owned by [panel_B] - still running")
        time.sleep(2)

        # Panel B disconnects - all remaining processes should stop
        logger.info("\n--- Phase 5: Panel B disconnects ---")
        logger.info("Expected: worker_1 and example_process stop")
        panel_b.disconnect()
        time.sleep(2)

        logger.info("\n--- Final state ---")
        logger.info("All processes stopped (no requesters)")

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        panel_a.disconnect()
        panel_b.disconnect()

    logger.info("\n" + "=" * 60)
    logger.info("Example complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
