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
# File: 06_testing_with_inmemory.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Example demonstrating how to use InMemoryTransport for testing.
#   Shows how to write unit tests for process hub without requiring
#   actual ZMQ connections.
#
# Usage:
#   python 06_testing_with_inmemory.py
#
# *******************************************************************************
"""
Testing with InMemoryTransport Example.

This example demonstrates how to:
1. Use InMemoryTransport for synchronous testing
2. Inspect sent messages without network overhead
3. Mock process executors for deterministic tests
4. Test core hub logic in isolation

InMemoryTransport is ideal for:
- Unit tests that don't need real network
- Fast integration tests
- Debugging message flows
- Testing without ZMQ dependency
"""

import logging
import sys
from pathlib import Path
from typing import Optional

# Add ProcessHub to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from ProcessHub.transport import InMemoryTransport
from ProcessHub.core import ProcessHubCore, ProcessRegistry
from ProcessHub.core.models import ProcessState
from ProcessHub.process import ProcessExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MockExecutor(ProcessExecutor):
    """
    Mock executor for testing.

    Records all operations without actually starting processes.
    Useful for testing the hub logic in isolation.
    """

    def __init__(self, should_succeed: bool = True):
        """
        Initialize mock executor.

        **Arguments:**

        * ``should_succeed``

          / *Condition*: optional / *Type*: bool / *Default*: True /

          Whether start/stop operations should succeed.
        """
        self.should_succeed = should_succeed
        self.started_processes: dict[str, dict] = {}
        self.stopped_processes: list[str] = []
        self.next_pid = 1000

    def start(
        self, name: str, config: dict
    ) -> tuple[bool, str, Optional[int]]:
        """Mock start - records the operation."""
        if self.should_succeed:
            pid = self.next_pid
            self.next_pid += 1
            self.started_processes[name] = {
                "config": config,
                "pid": pid,
            }
            logger.info("[MockExecutor] Started '%s' with PID %d", name, pid)
            return True, f"Started {name}", pid
        else:
            logger.info("[MockExecutor] Failed to start '%s'", name)
            return False, "Mock failure", None

    def stop(self, name: str, force: bool = False) -> bool:
        """Mock stop - records the operation."""
        if name in self.started_processes:
            del self.started_processes[name]
        self.stopped_processes.append(name)
        logger.info("[MockExecutor] Stopped '%s'", name)
        return True

    def is_running(self, name: str) -> bool:
        """Check if mock process is running."""
        return name in self.started_processes

    def get_pid(self, name: str) -> Optional[int]:
        """Get mock PID."""
        if name in self.started_processes:
            return self.started_processes[name]["pid"]
        return None


def demo_basic_inmemory():
    """Demonstrate basic InMemoryTransport usage."""
    logger.info("=" * 60)
    logger.info("Basic InMemoryTransport Usage")
    logger.info("=" * 60)

    transport = InMemoryTransport()

    # Register a handler
    received_messages = []

    def handler(message):
        received_messages.append(message)
        logger.info("Received: %s", message)

    transport.register_handler("TEST_TOPIC", handler)
    transport.start()

    # Send messages
    transport.send("TEST_TOPIC", {"action": "test", "data": "hello"})
    transport.send("TEST_TOPIC", {"action": "test", "data": "world"})

    # Messages are delivered synchronously
    logger.info("Received %d messages", len(received_messages))
    assert len(received_messages) == 2

    # Inspect sent messages (test helper)
    all_messages = transport.get_sent_messages()
    logger.info("Total sent messages: %d", len(all_messages))

    # Filter by topic
    test_messages = transport.get_sent_messages("TEST_TOPIC")
    logger.info("TEST_TOPIC messages: %d", len(test_messages))

    transport.stop()
    logger.info("")


def demo_mock_executor():
    """Demonstrate using MockExecutor for testing."""
    logger.info("=" * 60)
    logger.info("MockExecutor for Testing Process Operations")
    logger.info("=" * 60)

    # Create mock executor that succeeds
    executor = MockExecutor(should_succeed=True)

    # Test starting processes
    logger.info("Starting processes...")
    success, msg, pid = executor.start("process_1", {"script": "test.py"})
    logger.info("  process_1: success=%s, pid=%s", success, pid)

    success, msg, pid = executor.start("process_2", {"script": "test2.py"})
    logger.info("  process_2: success=%s, pid=%s", success, pid)

    # Check running state
    logger.info("\nChecking running state...")
    logger.info("  process_1 running: %s", executor.is_running("process_1"))
    logger.info("  process_2 running: %s", executor.is_running("process_2"))
    logger.info("  process_3 running: %s", executor.is_running("process_3"))

    # Stop a process
    logger.info("\nStopping process_1...")
    executor.stop("process_1")
    logger.info("  process_1 running: %s", executor.is_running("process_1"))

    # Test failing executor
    logger.info("\n--- Testing Failing Executor ---")
    failing_executor = MockExecutor(should_succeed=False)
    success, msg, pid = failing_executor.start("will_fail", {})
    logger.info("  Attempted start: success=%s, msg='%s'", success, msg)

    logger.info("")


def demo_message_inspection():
    """Demonstrate inspecting messages for debugging."""
    logger.info("=" * 60)
    logger.info("Message Inspection for Debugging")
    logger.info("=" * 60)

    transport = InMemoryTransport()

    # Simulate some message flow
    transport.start()
    transport.send("REGISTER", {"panel_id": "panel_1", "session": "sess_1"})
    transport.send("REGISTER", {"panel_id": "panel_2", "session": "sess_2"})
    transport.send("START_REQUEST", {"panel_id": "panel_1", "processes": ["p1"]})
    transport.send("START_RESPONSE", {"success": True})
    transport.send("STOP_REQUEST", {"panel_id": "panel_1", "processes": ["p1"]})

    # Inspect all messages
    logger.info("All messages sent:")
    for topic, message, target in transport.get_sent_messages():
        logger.info("  [%s] %s", topic, message)

    # Count by topic
    logger.info("\nMessage counts by topic:")
    logger.info("  REGISTER: %d", transport.message_count("REGISTER"))
    logger.info("  START_REQUEST: %d", transport.message_count("START_REQUEST"))
    logger.info("  START_RESPONSE: %d", transport.message_count("START_RESPONSE"))
    logger.info("  STOP_REQUEST: %d", transport.message_count("STOP_REQUEST"))

    # Clear and verify
    transport.clear_messages()
    logger.info("\nAfter clear: %d messages", transport.message_count())

    transport.stop()
    logger.info("")


def demo_registry_testing():
    """Demonstrate testing ProcessRegistry directly."""
    logger.info("=" * 60)
    logger.info("ProcessRegistry Unit Testing")
    logger.info("=" * 60)

    registry = ProcessRegistry()

    # Test registration
    logger.info("Testing process registration...")
    is_new = registry.register("process_1", "panel_A")
    logger.info("Registered process_1 for panel_A: is_new=%s", is_new)

    is_new = registry.register("process_1", "panel_B")
    logger.info("Registered process_1 for panel_B: is_new=%s", is_new)

    # Test state updates
    logger.info("\nTesting state updates...")
    registry.update_state("process_1", ProcessState.RUNNING, pid=1234)
    info = registry.get("process_1")
    logger.info("Process state: %s, pid: %s", info.state.value, info.pid)

    # Test requesters
    logger.info("\nTesting requesters...")
    requesters = registry.get_requesters("process_1")
    logger.info("Requesters: %s", requesters)

    # Test unregister
    logger.info("\nTesting unregistration...")
    can_stop = registry.unregister("process_1", "panel_A")
    logger.info("Unregistered panel_A, can_stop=%s", can_stop)

    can_stop = registry.unregister("process_1", "panel_B")
    logger.info("Unregistered panel_B, can_stop=%s", can_stop)

    logger.info("")


def main():
    """Run all InMemoryTransport examples."""
    demo_basic_inmemory()
    demo_mock_executor()
    demo_message_inspection()
    demo_registry_testing()

    logger.info("=" * 60)
    logger.info("All testing examples complete!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Key takeaways:")
    logger.info("1. InMemoryTransport delivers messages synchronously")
    logger.info("2. Use get_sent_messages() to inspect message flow")
    logger.info("3. Test ProcessHubCore directly with mock executor")
    logger.info("4. Test ProcessRegistry for state management logic")


if __name__ == "__main__":
    main()
