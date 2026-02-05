# **************************************************************************************************************
#
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
#
# **************************************************************************************************************
#
# process_helpers.py
#
# Nguyen Huynh Tri Cuong (MS/EMC51)
#
# Test utilities for ProcessHub component tests.
#
# 05.02.2026
#
# --------------------------------------------------------------------------------------------------------------

"""
Test utilities for ProcessHub component tests.

Provides a MockExecutor and helper functions to create a ProcessHubCore
instance for testing without requiring actual process execution or transport.
"""

import os
import sys

# Add the project root to path so we can import ProcessHub
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from ProcessHub.core.hub_core import ProcessHubCore
from ProcessHub.core.models import (
    RegisterConnectionRequest,
    UnregisterConnectionRequest,
    ProcessStartRequest,
    ProcessStopRequest,
)

# --------------------------------------------------------------------------------------------------------------

class MockExecutor:
    """
    Mock process executor for testing.

    Simulates process start/stop/health without real OS processes.
    """

    def __init__(self):
        self._running = {}    # name -> pid
        self._next_pid = 1000
        self._fail_start = set()  # process names that should fail to start
        self._fail_stop = set()   # process names that should fail to stop

    def set_fail_start(self, names):
        """Configure process names that will fail to start."""
        self._fail_start = set(names)

    def set_fail_stop(self, names):
        """Configure process names that will fail to stop."""
        self._fail_stop = set(names)

    def kill_process(self, name):
        """Simulate a process being killed externally."""
        if name in self._running:
            del self._running[name]

    def start(self, name):
        """Start a mock process. Returns (success, message, pid)."""
        if name in self._fail_start:
            return (False, f"Failed to start {name}", None)
        pid = self._next_pid
        self._next_pid += 1
        self._running[name] = pid
        return (True, f"Started {name}", pid)

    def stop(self, name, force=False):
        """Stop a mock process. Returns success."""
        if name in self._fail_stop:
            return False
        if name in self._running:
            del self._running[name]
        return True

    def check_health(self, names):
        """Check which processes are dead. Returns list of dead names."""
        dead = []
        for name in names:
            if name not in self._running:
                dead.append(name)
        return dead


def create_test_core(executor=None):
    """
    Create a ProcessHubCore with a MockExecutor for testing.

    Returns: (core, executor)
    """
    if executor is None:
        executor = MockExecutor()

    core = ProcessHubCore(
        process_starter=executor.start,
        process_stopper=executor.stop,
        health_checker=executor.check_health,
        restart_timeout=10.0,
        restart_max_retries=3,
    )
    return core, executor


def register_panel(core, panel_id, session_id="test_session"):
    """Helper: register a panel and return the response messages."""
    req = RegisterConnectionRequest(panel_id=panel_id, session_id=session_id)
    return core.handle_register(req)


def start_processes(core, panel_id, process_list):
    """Helper: start processes and return the response messages."""
    req = ProcessStartRequest(panel_id=panel_id, process_list=process_list)
    return core.handle_start_request(req)


def stop_processes(core, panel_id, process_list, force=False):
    """Helper: stop processes and return the response messages."""
    req = ProcessStopRequest(panel_id=panel_id, process_list=process_list, force=force)
    return core.handle_stop_request(req)


def unregister_panel(core, panel_id):
    """Helper: unregister a panel and return the response messages."""
    req = UnregisterConnectionRequest(panel_id=panel_id)
    return core.handle_unregister(req)

# --------------------------------------------------------------------------------------------------------------
