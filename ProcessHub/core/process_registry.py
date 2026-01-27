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
# File: process_registry.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Process registry - centralized process state with explicit concurrency.
#   This module implements improvement 3.2: Single lock protects all process state.
#   get_snapshot() returns immutable copy for UI.
#
# Original author:
#   Nguyen Tan Phat (MS/EMC51)
#
# Original file:
#   ta-framework-tsb/ta_framework/project/process_hub/process_manager.py
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Process registry - centralized process state with explicit concurrency.

This module implements improvement 3.2:

- Single lock protects all process state

- get_snapshot() returns immutable copy for UI

- Clear documentation of what data is protected

Replaces the scattered state in ProcessManager:

- self.process_map

- self.process_requester

- self.shared_info

- self.shared_info_lock
"""

from __future__ import annotations

import threading
from typing import Iterator, Optional

from .models import ProcessInfo, ProcessSnapshot, ProcessState


class ProcessRegistry:
    """
ProcessRegistry: Thread-safe process registry.

Concurrency model (3.2):

- Single _lock protects all process state

- All public methods acquire lock

- get_snapshot() returns immutable data for UI (no external locking needed)

Usage:

    registry = ProcessRegistry()

    # Register process

    registry.register("my_process", requester="panel_1")

    # Update state

    registry.update_state("my_process", ProcessState.RUNNING, pid=1234)

    # Get snapshot for UI (no locks needed by caller)

    snapshot = registry.get_snapshot()

    # Remove requester

    if registry.unregister("my_process", "panel_1"):

        # No more requesters, can stop process

        pass
    """

    def __init__(self):
        """
Initialize the ProcessRegistry.

Creates an empty registry with a thread lock for safe concurrent access.
        """
        self._processes: dict[str, ProcessInfo] = {}
        self._lock = threading.Lock()

    # ========================================================================
    # Thread-safe accessors
    # ========================================================================

    def get(self, name: str) -> Optional[ProcessInfo]:
        """
Get process info.

Returns a copy to prevent external mutation.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The name of the process to retrieve.

**Returns:**

  / *Type*: Optional[ProcessInfo] /

  A copy of the ProcessInfo, or None if not found.
        """
        with self._lock:
            proc = self._processes.get(name)
            if proc is None:
                return None
            # Return a copy to prevent external mutation
            return ProcessInfo(
                name=proc.name,
                state=proc.state,
                pid=proc.pid,
                requesters=proc.requesters.copy(),
                error_message=proc.error_message,
                metadata=proc.metadata.copy(),
            )

    def exists(self, name: str) -> bool:
        """
Check if process is registered.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The name of the process to check.

**Returns:**

  / *Type*: bool /

  True if the process exists in the registry, False otherwise.
        """
        with self._lock:
            return name in self._processes

    def get_all_names(self) -> list[str]:
        """
Get all registered process names.

**Returns:**

  / *Type*: list[str] /

  List of all registered process names.
        """
        with self._lock:
            return list(self._processes.keys())

    def get_snapshot(self) -> tuple[ProcessSnapshot, ...]:
        """
Get immutable snapshot of all processes.

Returns frozen dataclass instances for UI path. No locks needed by caller - snapshot is immutable.

This replaces:

    with shared_info_lock:
    
        proc_data = copy.deepcopy(proc_info)

**Returns:**

  / *Type*: tuple[ProcessSnapshot, ...] /

  Tuple of immutable ProcessSnapshot objects.
        """
        with self._lock:
            return tuple(
                ProcessSnapshot(
                    name=p.name,
                    state=p.state,
                    pid=p.pid or 0,
                    requesters=tuple(p.requesters),
                )
                for p in self._processes.values()
            )

    def get_requesters(self, name: str) -> list[str]:
        """
Get requester list for a process.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The name of the process.

**Returns:**

  / *Type*: list[str] /

  List of panel IDs that requested this process.
        """
        with self._lock:
            proc = self._processes.get(name)
            return list(proc.requesters) if proc else []

    def get_state(self, name: str) -> Optional[ProcessState]:
        """
Get process state.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The name of the process.

**Returns:**

  / *Type*: Optional[ProcessState] /

  The process state, or None if process not found.
        """
        with self._lock:
            proc = self._processes.get(name)
            return proc.state if proc else None

    # ========================================================================
    # State mutations (all under lock)
    # ========================================================================

    def register(self, name: str, requester: Optional[str] = None) -> bool:
        """
Register a process (or add requester if exists).

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The name of the process to register.

* ``requester``

  / *Condition*: optional / *Type*: Optional[str] / *Default*: None /

  Panel ID requesting this process.

**Returns:**

  / *Type*: bool /

  True if newly registered, False if already existed.
        """
        with self._lock:
            if name in self._processes:
                if requester:
                    self._processes[name].add_requester(requester)
                return False

            proc = ProcessInfo(name=name, state=ProcessState.REGISTERED)
            if requester:
                proc.add_requester(requester)
            self._processes[name] = proc
            return True

    def unregister(self, name: str, requester: Optional[str] = None) -> bool:
        """
Remove requester from process.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The name of the process.

* ``requester``

  / *Condition*: optional / *Type*: Optional[str] / *Default*: None /

  Panel ID to remove from requesters.

**Returns:**

  / *Type*: bool /

  True if process has no more requesters (can be stopped).
        """
        with self._lock:
            proc = self._processes.get(name)
            if proc is None:
                return False

            if requester:
                return proc.remove_requester(requester)
            return len(proc.requesters) == 0

    def remove(self, name: str) -> bool:
        """
Completely remove process from registry.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The name of the process to remove.

**Returns:**

  / *Type*: bool /

  True if process was removed, False if not found.
        """
        with self._lock:
            if name in self._processes:
                del self._processes[name]
                return True
            return False

    def update_state(
        self,
        name: str,
        state: ProcessState,
        pid: Optional[int] = None,
        error: Optional[str] = None,
    ) -> bool:
        """
Update process state.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The name of the process to update.

* ``state``

  / *Condition*: required / *Type*: ProcessState /

  The new state to set.

* ``pid``

  / *Condition*: optional / *Type*: Optional[int] / *Default*: None /

  Process ID to set (if provided).

* ``error``

  / *Condition*: optional / *Type*: Optional[str] / *Default*: None /

  Error message (for FAILED state).

**Returns:**

  / *Type*: bool /

  True if process found and updated.
        """
        with self._lock:
            proc = self._processes.get(name)
            if proc is None:
                return False

            proc.state = state
            if pid is not None:
                proc.pid = pid
            if error is not None:
                proc.error_message = error
            return True

    def update_pid(self, name: str, pid: int) -> bool:
        """
Update process PID.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The name of the process.

* ``pid``

  / *Condition*: required / *Type*: int /

  The new process ID.

**Returns:**

  / *Type*: bool /

  True if process found and updated.
        """
        with self._lock:
            proc = self._processes.get(name)
            if proc is None:
                return False
            proc.pid = pid
            return True

    def remove_requester_from_all(self, requester: str) -> list[str]:
        """
Remove requester from all processes.

Used when a panel disconnects.

**Arguments:**

* ``requester``

  / *Condition*: required / *Type*: str /

  The panel ID to remove from all processes.

**Returns:**

  / *Type*: list[str] /

  List of process names that now have no requesters (can be stopped).
        """
        orphaned = []
        with self._lock:
            for name, proc in self._processes.items():
                if proc.remove_requester(requester):
                    orphaned.append(name)
        return orphaned

    # ========================================================================
    # Health check support
    # ========================================================================

    def get_active_processes(self) -> list[str]:
        """
Get names of processes in RUNNING state.

**Returns:**

  / *Type*: list[str] /

  List of process names that are currently running.
        """
        with self._lock:
            return [
                name
                for name, proc in self._processes.items()
                if proc.state == ProcessState.RUNNING
            ]

    def mark_dead(self, names: list[str]) -> None:
        """
Mark processes as DEAD.

Called after health check detects dead processes.

**Arguments:**

* ``names``

  / *Condition*: required / *Type*: list[str] /

  List of process names to mark as dead.
        """
        with self._lock:
            for name in names:
                proc = self._processes.get(name)
                if proc and proc.state == ProcessState.RUNNING:
                    proc.state = ProcessState.DEAD

    def clear_all(self) -> None:
        """
Clear all processes (for shutdown).
        """
        with self._lock:
            self._processes.clear()

    # ========================================================================
    # Iteration support
    # ========================================================================

    def __len__(self) -> int:
        """
Get number of registered processes.

**Returns:**

  / *Type*: int /

  Number of processes in the registry.
        """
        with self._lock:
            return len(self._processes)

    def __contains__(self, name: str) -> bool:
        """
Check if process name is in registry.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  The process name to check.

**Returns:**

  / *Type*: bool /

  True if the process is registered.
        """
        with self._lock:
            return name in self._processes
