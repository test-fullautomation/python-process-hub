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
# File: 07_snapshot_and_views.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Example demonstrating HubStateSnapshot and ConsoleView usage.
#   Shows how to:
#   - Create immutable state snapshots for thread-safe UI rendering
#   - Use ConsoleView to display hub state in terminal
#   - Create custom views by extending HubViewBase
#
# Usage:
#   python 07_snapshot_and_views.py
#
# *******************************************************************************
"""
Snapshot and Views Example.

This example demonstrates:

1. Creating HubStateSnapshot manually for testing/simulation

2. Using ConsoleView to render state to terminal

3. Creating a custom view (JSON export view)

4. Benefits of immutable snapshots for thread-safe UI


Key concepts:

- HubStateSnapshot: Frozen dataclass containing connection and process state

- ConsoleView: ASCII table renderer for terminal display

- HubViewBase: Abstract base for custom view implementations
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

# Add ProcessHub to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from ProcessHub.core.models import (
    HubStateSnapshot,
    ConnectionSnapshot,
    ProcessSnapshot,
    ProcessState,
)
from ProcessHub.ui import ConsoleView, NullView
from ProcessHub.ui.base import HubViewBase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_sample_snapshot(
    num_connections: int = 2,
    num_processes: int = 3,
    include_dead: bool = False,
) -> HubStateSnapshot:
    """
Create a sample HubStateSnapshot for demonstration.

**Arguments:**

* ``num_connections``

  / *Condition*: optional / *Type*: int / *Default*: 2 /

  Number of connections to create.

* ``num_processes``

  / *Condition*: optional / *Type*: int / *Default*: 3 /

  Number of processes to create.

* ``include_dead``

  / *Condition*: optional / *Type*: bool / *Default*: False /

  Whether to include a dead process.

**Returns:**

/ *Type*: HubStateSnapshot /

Sample snapshot with connections and processes.
    """
    # Create connection snapshots
    connections = []
    session_panels = tuple(f"panel_{i}" for i in range(num_connections))

    for i in range(num_connections):
        connections.append(
            ConnectionSnapshot(
                panel_id=f"panel_{i}",
                session_id="session_abc123",
                session_panel_ids=session_panels,
            )
        )

    # Create process snapshots
    processes = []
    states = [ProcessState.RUNNING, ProcessState.STARTING, ProcessState.STOPPED]

    for i in range(num_processes):
        state = states[i % len(states)]
        if include_dead and i == 0:
            state = ProcessState.DEAD

        processes.append(
            ProcessSnapshot(
                name=f"process_{i}",
                state=state,
                pid=1000 + i if state == ProcessState.RUNNING else 0,
                requesters=tuple(f"panel_{j}" for j in range(min(i + 1, num_connections))),
            )
        )

    # Create killed processes list if we have dead ones
    killed = tuple(p.name for p in processes if p.state == ProcessState.DEAD)

    return HubStateSnapshot(
        connections=tuple(connections),
        processes=tuple(processes),
        killed_processes=killed,
        pending_panels=tuple(f"panel_{i}" for i in range(num_connections)) if killed else (),
        restart_state="AWAITING_ACK" if killed else "IDLE",
    )


def demo_snapshot_basics():
    """
Demonstrate basic snapshot creation and access.
    """
    logger.info("=" * 60)
    logger.info("HubStateSnapshot Basics")
    logger.info("=" * 60)

    # Create a sample snapshot
    snapshot = create_sample_snapshot(num_connections=2, num_processes=3)

    # Snapshots are immutable (frozen dataclass)
    logger.info("Snapshot is immutable: %s", snapshot.__class__.__dataclass_fields__)

    # Access connections
    logger.info("\nConnections (%d):", len(snapshot.connections))
    for conn in snapshot.connections:
        logger.info("  Panel: %s, Session: %s", conn.panel_id, conn.session_id)
        logger.info("    Session panels: %s", conn.session_panel_ids)

    # Access processes
    logger.info("\nProcesses (%d):", len(snapshot.processes))
    for proc in snapshot.processes:
        logger.info("  %s: state=%s, pid=%d, requesters=%s",
                    proc.name, proc.state.value, proc.pid, proc.requesters)

    # Restart state
    logger.info("\nRestart state: %s", snapshot.restart_state)
    logger.info("Killed processes: %s", snapshot.killed_processes)
    logger.info("Pending panels: %s", snapshot.pending_panels)

    # Try to modify - will fail
    logger.info("\nTrying to modify snapshot (should fail)...")
    try:
        snapshot.restart_state = "MODIFIED"  # type: ignore
    except Exception as e:
        logger.info("  Correctly raised: %s", type(e).__name__)

    logger.info("")


def demo_console_view():
    """
Demonstrate ConsoleView rendering.
    """
    logger.info("=" * 60)
    logger.info("ConsoleView Rendering")
    logger.info("=" * 60)
    logger.info("")
    logger.info("ConsoleView renders hub state as ASCII tables.")
    logger.info("Below is an example render (without screen clear):")
    logger.info("")

    # Create view without screen clearing for demo
    view = ConsoleView(clear_screen=False)

    # Create sample snapshot
    snapshot = create_sample_snapshot(num_connections=3, num_processes=4)

    # Render it
    view.render(snapshot)

    logger.info("")


def demo_console_view_with_restart():
    """
Demonstrate ConsoleView during restart scenario.
    """
    logger.info("=" * 60)
    logger.info("ConsoleView During Restart")
    logger.info("=" * 60)
    logger.info("")
    logger.info("When processes die, ConsoleView shows restart info:")
    logger.info("")

    view = ConsoleView(clear_screen=False)

    # Create snapshot with dead process
    snapshot = create_sample_snapshot(
        num_connections=2,
        num_processes=3,
        include_dead=True
    )

    view.render(snapshot)

    logger.info("")


class JsonExportView(HubViewBase):
    """
Custom view that exports state as JSON.

Demonstrates how to create custom views by extending HubViewBase.

Useful for:

- REST API endpoints

- Log aggregation

- External monitoring systems
    """

    def __init__(self, output_file: Optional[str] = None):
        """
Initialize JSON export view.

**Arguments:**

* ``output_file``

  / *Condition*: optional / *Type*: str / *Default*: None /

  File path to write JSON. If None, prints to stdout.
        """
        self._output_file = output_file
        self._last_json: Optional[str] = None

    def render(self, snapshot: HubStateSnapshot) -> None:
        """
Render snapshot as JSON.
        """
        data = {
            "timestamp": time.time(),
            "restart_state": snapshot.restart_state,
            "connections": [
                {
                    "panel_id": c.panel_id,
                    "session_id": c.session_id,
                    "session_panels": list(c.session_panel_ids),
                }
                for c in snapshot.connections
            ],
            "processes": [
                {
                    "name": p.name,
                    "state": p.state.value,
                    "pid": p.pid,
                    "requesters": list(p.requesters),
                }
                for p in snapshot.processes
            ],
            "killed_processes": list(snapshot.killed_processes),
            "pending_panels": list(snapshot.pending_panels),
        }

        self._last_json = json.dumps(data, indent=2)

        if self._output_file:
            with open(self._output_file, "w") as f:
                f.write(self._last_json)
        else:
            print(self._last_json)

    def get_last_json(self) -> Optional[str]:
        """Get the last rendered JSON string."""
        return self._last_json


class MetricsView(HubViewBase):
    """
Custom view that tracks metrics over time.

Demonstrates stateful view that accumulates data across renders.
    """

    def __init__(self):
        """
Initialize metrics view.
        """
        self.render_count = 0
        self.max_connections = 0
        self.max_processes = 0
        self.dead_process_events = 0

    def render(self, snapshot: HubStateSnapshot) -> None:
        """
Update metrics from snapshot.
        """
        self.render_count += 1
        self.max_connections = max(self.max_connections, len(snapshot.connections))
        self.max_processes = max(self.max_processes, len(snapshot.processes))

        if snapshot.killed_processes:
            self.dead_process_events += 1

    def get_metrics(self) -> dict:
        """
Get accumulated metrics.
        """
        return {
            "render_count": self.render_count,
            "max_connections": self.max_connections,
            "max_processes": self.max_processes,
            "dead_process_events": self.dead_process_events,
        }


def demo_custom_views():
    """
Demonstrate custom view implementations.
    """
    logger.info("=" * 60)
    logger.info("Custom View Implementations")
    logger.info("=" * 60)
    logger.info("")

    # JSON Export View
    logger.info("1. JsonExportView - exports state as JSON:")
    json_view = JsonExportView()
    snapshot = create_sample_snapshot(num_connections=2, num_processes=2)
    json_view.render(snapshot)

    logger.info("")

    # Metrics View
    logger.info("2. MetricsView - accumulates statistics:")
    metrics_view = MetricsView()

    # Simulate multiple renders
    for i in range(5):
        snapshot = create_sample_snapshot(
            num_connections=i + 1,
            num_processes=i + 2,
            include_dead=(i == 2)  # One snapshot with dead process
        )
        metrics_view.render(snapshot)

    logger.info("Metrics after 5 renders:")
    for key, value in metrics_view.get_metrics().items():
        logger.info("  %s: %s", key, value)

    logger.info("")

    # NullView - does nothing (useful for testing)
    logger.info("3. NullView - no-op view for headless operation:")
    null_view = NullView()
    null_view.render(snapshot)  # Does nothing
    logger.info("  NullView.render() called - no output (as expected)")

    logger.info("")


def demo_thread_safety():
    """
Demonstrate thread-safety benefits of snapshots.
    """
    logger.info("=" * 60)
    logger.info("Thread Safety with Snapshots")
    logger.info("=" * 60)
    logger.info("")

    logger.info("Benefits of immutable snapshots:")
    logger.info("")
    logger.info("1. No locks needed by UI:")
    logger.info("   - Core creates snapshot under its internal lock")
    logger.info("   - Returns frozen copy to UI")
    logger.info("   - UI can read freely without synchronization")
    logger.info("")
    logger.info("2. No race conditions:")
    logger.info("   - Snapshot represents a consistent point-in-time state")
    logger.info("   - Even if core updates, UI sees stable data")
    logger.info("")
    logger.info("3. Safe to pass between threads:")
    logger.info("   - Frozen dataclasses are inherently thread-safe")
    logger.info("   - Can be safely shared without copying")
    logger.info("")

    # Example: Create snapshot, core can continue updating
    snapshot1 = create_sample_snapshot(num_connections=2, num_processes=3)

    # Simulate core updating (creating new snapshot)
    snapshot2 = create_sample_snapshot(num_connections=3, num_processes=4)

    # Original snapshot is unchanged
    logger.info("Snapshot 1 connections: %d", len(snapshot1.connections))
    logger.info("Snapshot 2 connections: %d", len(snapshot2.connections))
    logger.info("(Snapshots are independent - no shared mutable state)")

    logger.info("")


def demo_real_world_usage():
    """
Demonstrate real-world usage pattern.
    """
    logger.info("=" * 60)
    logger.info("Real-World Usage Pattern")
    logger.info("=" * 60)
    logger.info("")

    logger.info("In a real server, the pattern is:")
    logger.info("")
    logger.info("```python")
    logger.info("# Server main loop")
    logger.info("view = ConsoleView()")
    logger.info("")
    logger.info("while running:")
    logger.info("    # Core handles messages, updates internal state")
    logger.info("    core.tick()")
    logger.info("")
    logger.info("    # Get immutable snapshot")
    logger.info("    snapshot = core.get_state_snapshot()")
    logger.info("")
    logger.info("    # Render to UI (no locks held)")
    logger.info("    view.render(snapshot)")
    logger.info("")
    logger.info("    time.sleep(refresh_interval)")
    logger.info("```")
    logger.info("")

    # Simulate the loop
    view = ConsoleView(clear_screen=False)

    logger.info("Simulating 3 render cycles:")
    logger.info("-" * 40)

    for i in range(3):
        logger.info("\n[Cycle %d]", i + 1)
        snapshot = create_sample_snapshot(
            num_connections=i + 1,
            num_processes=2
        )
        # In real code: view.render(snapshot)
        logger.info("  Connections: %d, Processes: %d",
                    len(snapshot.connections), len(snapshot.processes))

    logger.info("")


def main():
    """
Run all snapshot and view examples.
    """
    demo_snapshot_basics()
    demo_console_view()
    demo_console_view_with_restart()
    demo_custom_views()
    demo_thread_safety()
    demo_real_world_usage()

    logger.info("=" * 60)
    logger.info("All snapshot and view examples complete!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Key takeaways:")
    logger.info("1. HubStateSnapshot is immutable (frozen dataclass)")
    logger.info("2. ConsoleView renders state as ASCII tables")
    logger.info("3. Create custom views by extending HubViewBase")
    logger.info("4. Snapshots enable thread-safe UI without locks")


if __name__ == "__main__":
    main()
