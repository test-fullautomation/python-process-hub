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
# File: manager.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Process Manager - high-level process lifecycle management.
#   Provides unified interface combining process execution, state tracking,
#   and requester management.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Process Manager - high-level process lifecycle management.

This module provides a unified interface for managing processes,
combining the functionality of:

- Process execution (via Executor)

- Process state tracking (via ProcessRegistry from core)

- Requester management (reference counting)

This is the normalized version of the original ProcessManager,
with explicit process states and cleaner separation of concerns.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional

from ..core.models import ProcessInfo, ProcessState
from ..core.process_registry import ProcessRegistry
from .executor import ProcessExecutor, SimpleExecutor, create_executor

logger = logging.getLogger(__name__)


class ProcessManager:
    """
High-level process manager.

Combines process execution with state tracking:

- Manages process lifecycle (register, start, stop)

- Tracks requesters (reference counting)

- Provides health checks

- Thread-safe operations

This is a normalized version of the original ProcessManager:

- Uses ProcessState enum instead of mixed "None"/True/False

- Uses ProcessRegistry for thread-safe state management

- Separates execution logic into Executor

Usage:

    manager = ProcessManager()

    # Register and start
    
    manager.register("my_process", requester="panel_1", config={...})
    
    success, msg = manager.start("my_process")

    # Check status
    
    if manager.is_running("my_process"):
    
        print("Running!")

    # Health check
    
    dead = manager.health_check()

    # Stop (only if no other requesters)
    
    manager.unregister("my_process", requester="panel_1")
    
    manager.stop("my_process")  # Actually stops if no requesters
    """

    def __init__(
        self,
        executor: Optional[ProcessExecutor] = None,
        stop_timeout: float = 5.0,
    ):
        """
Initialize process manager.

**Arguments:**

* ``executor``

  / *Condition*: optional / *Type*: ProcessExecutor / *Default*: None /

  Process executor (creates SimpleExecutor if None).

* ``stop_timeout``

  / *Condition*: optional / *Type*: float / *Default*: 5.0 /

  Timeout for graceful stop (seconds).
        """
        self._executor = executor or SimpleExecutor(stop_timeout=stop_timeout)
        self._registry = ProcessRegistry()
        self._configs: dict[str, dict] = {}
        self._lock = threading.Lock()

    @property
    def executor(self) -> ProcessExecutor:
        """
Get the executor.
        """
        return self._executor

    @property
    def registry(self) -> ProcessRegistry:
        """
Get the registry.
        """
        return self._registry

    # ========================================================================
    # Registration
    # ========================================================================

    def register(
        self,
        name: str,
        requester: Optional[str] = None,
        config: Optional[dict] = None,
    ) -> bool:
        """
Register a process.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  Process name.

* ``requester``

  / *Condition*: optional / *Type*: str / *Default*: None /

  Panel/client ID requesting this process.

* ``config``

  / *Condition*: optional / *Type*: dict / *Default*: None /

  Process configuration (script, args, etc.).

**Returns:**

/ *Type*: bool /

True if newly registered, False if already existed.
        """
        with self._lock:
            # Store config
            if config:
                self._configs[name] = config

            # Register in registry
            is_new = self._registry.register(name, requester)

            if is_new:
                logger.info("Registered process '%s' for requester '%s'", name, requester)
            else:
                logger.debug("Added requester '%s' to process '%s'", requester, name)

            return is_new

    def unregister(
        self,
        name: str,
        requester: Optional[str] = None,
    ) -> bool:
        """
Unregister a requester from a process.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  Process name.

* ``requester``

  / *Condition*: optional / *Type*: str / *Default*: None /

  Panel/client ID to remove.

**Returns:**

/ *Type*: bool /

True if process has no more requesters (can be stopped).
        """
        with self._lock:
            can_stop = self._registry.unregister(name, requester)

            if can_stop:
                logger.info("No more requesters for '%s', can be stopped", name)
            else:
                logger.debug("Removed requester '%s' from '%s'", requester, name)

            return can_stop

    # ========================================================================
    # Lifecycle
    # ========================================================================

    def start(self, name: str) -> tuple[bool, str]:
        """
Start a process.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  Process name (must be registered first).

**Returns:**

/ *Type*: tuple[bool, str] /

Tuple of (success, message).
        """
        with self._lock:
            # Check if registered
            if not self._registry.exists(name):
                return False, f"Process '{name}' not registered"

            # Check if already running
            current_state = self._registry.get_state(name)
            if current_state == ProcessState.RUNNING:
                return True, f"Process '{name}' already running"

            # Get config
            config = self._configs.get(name, {})

            # Update state to STARTING
            self._registry.update_state(name, ProcessState.STARTING)

            # Start process
            success, msg, pid = self._executor.start(name, config)

            if success:
                self._registry.update_state(name, ProcessState.RUNNING, pid=pid)
                logger.info("Started process '%s' (pid=%s)", name, pid)
                return True, msg
            else:
                self._registry.update_state(name, ProcessState.FAILED, error=msg)
                logger.error("Failed to start '%s': %s", name, msg)
                return False, msg

    def stop(self, name: str, force: bool = False) -> bool:
        """
Stop a process.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  Process name.

* ``force``

  / *Condition*: optional / *Type*: bool / *Default*: False /

  Force stop even if requesters exist.

**Returns:**

/ *Type*: bool /

True if stopped successfully.
        """
        with self._lock:
            # Check if can stop (no requesters)
            info = self._registry.get(name)
            if not info:
                return True  # Not registered, nothing to stop

            if not force and info.requesters:
                logger.warning(
                    "Cannot stop '%s': still has requesters %s",
                    name,
                    info.requesters,
                )
                return False

            # Update state
            self._registry.update_state(name, ProcessState.STOPPING)

            # Stop process
            success = self._executor.stop(name, force=force)

            if success:
                self._registry.remove(name)
                self._configs.pop(name, None)
                logger.info("Stopped process '%s'", name)
            else:
                logger.error("Failed to stop '%s'", name)

            return success

    def force_stop_all(self) -> None:
        """
Force stop all processes.
        """
        with self._lock:
            for name in self._registry.get_all_names():
                self._executor.stop(name, force=True)

            self._registry.clear_all()
            self._configs.clear()
            logger.info("Force stopped all processes")

    # ========================================================================
    # Status
    # ========================================================================

    def is_running(self, name: str) -> bool:
        """
Check if a process is running.
        """
        return self._executor.is_running(name)

    def get_state(self, name: str) -> Optional[ProcessState]:
        """
Get process state.
        """
        return self._registry.get_state(name)

    def get_info(self, name: str) -> Optional[ProcessInfo]:
        """
Get process info.
        """
        return self._registry.get(name)

    def get_all_names(self) -> list[str]:
        """
Get all registered process names.
        """
        return self._registry.get_all_names()

    def get_requesters(self, name: str) -> list[str]:
        """
Get requesters for a process.
        """
        return self._registry.get_requesters(name)

    # ========================================================================
    # Health Check
    # ========================================================================

    def health_check(self) -> list[str]:
        """
Check health of all running processes.

Returns:

    List of process names that are dead (were running, now not)
        """
        dead_processes = []

        with self._lock:
            for name in self._registry.get_active_processes():
                if not self._executor.is_running(name):
                    logger.warning("Detected dead process: %s", name)
                    dead_processes.append(name)

            # Mark dead processes
            self._registry.mark_dead(dead_processes)

        return dead_processes

    def remove_requester_from_all(self, requester: str) -> list[str]:
        """
Remove requester from all processes.

**Arguments:**

* ``requester``

  / *Condition*: required / *Type*: str /

  Requester to remove.

**Returns:**

/ *Type*: list[str] /

List of process names that now have no requesters.
        """
        return self._registry.remove_requester_from_all(requester)

    # ========================================================================
    # Shared Info (backward compatibility)
    # ========================================================================

    def get_shared_info(self) -> dict[str, dict]:
        """
Get shared info dict (backward compatibility).

Returns dict in format compatible with original ProcessManager:

    {
        "process_name": {
        
            "pid": 1234,
            
            "requester": ["panel_1", "panel_2"],
            
            "status": True
            
        }
        
    }
        """
        snapshot = self._registry.get_snapshot()
        result = {}

        for proc in snapshot:
            result[proc.name] = {
                "pid": proc.pid,
                "requester": list(proc.requesters),
                "status": proc.state == ProcessState.RUNNING,
            }

        return result

    def update_process(self, name: str, process: Any, pid: int) -> None:
        """
Update process object in executor (backward compatibility).

Used when external process lookup finds a running process.
        """
        if hasattr(self._executor, "update_process"):
            self._executor.update_process(name, process, pid)

        self._registry.update_state(name, ProcessState.RUNNING, pid=pid)
