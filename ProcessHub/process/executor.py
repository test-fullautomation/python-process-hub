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
# File: executor.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Process executor interface and implementations.
#   Provides abstract ProcessExecutor interface, SimpleExecutor for basic
#   subprocess management, and factory function for platform-appropriate executor.
#
# Original author:
#   Nguyen Tan Phat (MS/EMC51)
#
# Original file:
#   ta-framework-tsb/ta_framework/project/process_hub/process_control.py
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Process executor interface and implementations.

This module provides:

- Abstract ProcessExecutor interface

- SimpleExecutor for basic subprocess management

- Factory function for platform-appropriate executor
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Try to import psutil (optional dependency)
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil not installed, some features will be limited")


class ProcessExecutor(ABC):
    """
Abstract process executor interface.

Implementations handle platform-specific process management.
    """

    @abstractmethod
    def start(
        self, name: str, config: dict
    ) -> tuple[bool, str, Optional[int]]:
        """
Start a process.

Args:

    name: Process name/identifier
    
    config: Process configuration dict with keys:
    
        - script: Path to script/executable
        
        - args: List of arguments
        
        - wait_time: Time to wait after start (seconds)
        
        - process_name: Actual process name to look for
        
        - env: Additional environment variables

Returns:

    Tuple of (success, message, pid)
        """
        pass

    @abstractmethod
    def stop(self, name: str, force: bool = False) -> tuple[bool, str]:
        """
Stop a process.

Args:
    name: Process name/identifier
    force: Force kill if graceful stop fails

Returns:
    Tuple of (success, message)
        """
        pass

    @abstractmethod
    def is_running(self, name: str) -> bool:
        """
Check if a process is running.

Args:

    name: Process name/identifier

Returns:

    True if process is running
        """
        pass

    def get_pid(self, name: str) -> Optional[int]:
        """
Get process ID.

Args:

    name: Process name/identifier

Returns:

    PID or None if not running
        """
        return None


class SimpleExecutor(ProcessExecutor):
    """
Simple process executor using subprocess.

This executor:

- Tracks processes by name in a dict

- Uses psutil for process management (if available)

- Falls back to subprocess for basic operations

Suitable for testing and simple use cases.

For production Windows use, consider WindowsExecutor.
    """

    def __init__(
        self,
        start_callback: Optional[Callable[[str, dict], subprocess.Popen]] = None,
        stop_timeout: float = 5.0,
    ):
        """
Initialize executor.

Args:
    
    start_callback: Optional custom start function

    stop_timeout: Timeout for graceful stop (seconds)
        """
        self._processes: dict[str, Any] = {}  # name -> process object
        self._pids: dict[str, int] = {}  # name -> pid
        self._start_callback = start_callback
        self._stop_timeout = stop_timeout

    def start(
        self, name: str, config: dict
    ) -> tuple[bool, str, Optional[int]]:
        """
Start a process.
        """
        # Check if process is already running
        if self.is_running(name):
            pid = self._pids.get(name)
            return True, f"Process {name} is already running", pid

        script = config.get("script", "")
        args = config.get("args", [])
        wait_time = config.get("wait_time", 2.0)
        env = config.get("env", {})

        # Use custom start callback if provided
        if self._start_callback:
            try:
                proc = self._start_callback(name, config)
                self._processes[name] = proc
                self._pids[name] = proc.pid
                return True, f"Started {name}", proc.pid
            except Exception as e:
                return False, str(e), None

        # Validate script path
        if not script:
            return False, "No script specified", None

        script = os.path.expandvars(script)

        # Check if script exists as file or can be found in PATH
        if not os.path.exists(script):
            # Try to find in PATH
            found = shutil.which(script)
            if found:
                script = found
            else:
                return False, f"Script not found: {script}", None

        # Build command
        if script.endswith(".py"):
            cmd = [sys.executable, script] + args
        else:
            cmd = [script] + args

        # Prepare environment
        proc_env = os.environ.copy()
        proc_env.update(env)

        try:
            # Start process
            proc = subprocess.Popen(
                cmd,
                env=proc_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    if sys.platform == "win32"
                    else 0
                ),
            )

            self._processes[name] = proc
            self._pids[name] = proc.pid

            # Wait for process to start
            if wait_time > 0:
                time.sleep(wait_time)

            # Verify process is running
            if proc.poll() is not None:
                return False, f"Process {name} exited immediately", None

            logger.info("Started process %s (pid=%d)", name, proc.pid)
            return True, f"Started {name}", proc.pid

        except Exception as e:
            logger.exception("Failed to start process %s", name)
            return False, str(e), None

    def stop(self, name: str, force: bool = False) -> tuple[bool, str]:
        """
Stop a process.
        """
        proc = self._processes.get(name)
        if proc is None:
            # Check if we ever knew about this process
            if name not in self._pids:
                return True, f"Process {name} is not running"
            # We knew about it but it's gone
            self._pids.pop(name, None)
            return True, f"Process {name} was already stopped"

        # Check if actually running
        if not self.is_running(name):
            self._processes.pop(name, None)
            self._pids.pop(name, None)
            return True, f"Process {name} was already stopped"

        try:
            if HAS_PSUTIL and isinstance(proc, psutil.Process):
                return self._stop_psutil(name, proc, force)
            elif isinstance(proc, subprocess.Popen):
                return self._stop_popen(name, proc, force)
            else:
                # Try to find by PID
                pid = self._pids.get(name)
                if pid and HAS_PSUTIL:
                    try:
                        ps_proc = psutil.Process(pid)
                        return self._stop_psutil(name, ps_proc, force)
                    except psutil.NoSuchProcess:
                        pass

                # Cleanup
                self._processes.pop(name, None)
                self._pids.pop(name, None)
                return True, f"Process {name} stopped"

        except Exception as e:
            logger.exception("Error stopping process %s", name)
            # Force cleanup
            self._processes.pop(name, None)
            self._pids.pop(name, None)
            return False, f"Error stopping {name}: {str(e)}"

    def _stop_popen(
        self, name: str, proc: subprocess.Popen, force: bool
    ) -> tuple[bool, str]:
        """
Stop a Popen process.
        """
        try:
            # Try graceful termination
            proc.terminate()
            try:
                proc.wait(timeout=self._stop_timeout)
            except subprocess.TimeoutExpired:
                if force:
                    proc.kill()
                    proc.wait(timeout=2.0)
                else:
                    return False, f"Process {name} did not stop gracefully (use force=True)"

            # Cleanup
            self._processes.pop(name, None)
            self._pids.pop(name, None)
            return True, f"Process {name} stopped"

        except Exception as e:
            logger.exception("Error stopping Popen process %s", name)
            return False, f"Error stopping {name}: {str(e)}"

    def _stop_psutil(
        self, name: str, proc: psutil.Process, force: bool
    ) -> tuple[bool, str]:
        """
Stop a psutil Process.
        """
        try:
            # Try graceful termination
            proc.terminate()
            try:
                proc.wait(timeout=self._stop_timeout)
            except psutil.TimeoutExpired:
                if force:
                    proc.kill()
                    proc.wait(timeout=2.0)
                else:
                    return False, f"Process {name} did not stop gracefully (use force=True)"

            # Cleanup
            self._processes.pop(name, None)
            self._pids.pop(name, None)
            return True, f"Process {name} stopped"

        except psutil.NoSuchProcess:
            # Already dead
            self._processes.pop(name, None)
            self._pids.pop(name, None)
            return True, f"Process {name} was already stopped"
        except Exception as e:
            logger.exception("Error stopping psutil process %s", name)
            return False, f"Error stopping {name}: {str(e)}"

    def is_running(self, name: str) -> bool:
        """
Check if process is running.
        """
        proc = self._processes.get(name)
        if proc is None:
            return False

        try:
            if HAS_PSUTIL and isinstance(proc, psutil.Process):
                return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            elif isinstance(proc, subprocess.Popen):
                return proc.poll() is None
            else:
                # Try by PID
                pid = self._pids.get(name)
                if pid and HAS_PSUTIL:
                    try:
                        ps_proc = psutil.Process(pid)
                        return ps_proc.is_running()
                    except psutil.NoSuchProcess:
                        return False
                return False

        except Exception as e:
            logger.warning("Error checking process %s: %s", name, e)
            return False

    def get_pid(self, name: str) -> Optional[int]:
        """
Get process PID.
        """
        return self._pids.get(name)

    def update_process(self, name: str, process: Any, pid: int) -> None:
        """
Update tracked process (e.g., after finding external process).

Args:

    name: Process name
    
    process: Process object (psutil.Process or Popen)
    
    pid: Process ID
        """
        self._processes[name] = process
        self._pids[name] = pid


class MockExecutor(ProcessExecutor):
    """
Mock executor for testing.

Simulates process start/stop without actually running processes.
    """

    def __init__(self):
        self._running: dict[str, int] = {}  # name -> fake pid
        self._next_pid = 1000

    def start(
        self, name: str, config: dict
    ) -> tuple[bool, str, Optional[int]]:
        """
Simulate starting a process.
        """
        if name in self._running:
            return True, f"{name} already running", self._running[name]

        pid = self._next_pid
        self._next_pid += 1
        self._running[name] = pid

        # Simulate failure if config says so
        if config.get("fail_start"):
            del self._running[name]
            return False, "Simulated failure", None

        return True, f"Started {name}", pid

    def stop(self, name: str, force: bool = False) -> tuple[bool, str]:
        """
Simulate stopping a process.
        """
        if name in self._running:
            del self._running[name]
            return True, f"Process {name} stopped"
        return True, f"Process {name} was already stopped"

    def is_running(self, name: str) -> bool:
        """
Check if mock process is running.
        """
        return name in self._running

    def get_pid(self, name: str) -> Optional[int]:
        """
Get mock PID.
        """
        return self._running.get(name)

    def kill(self, name: str) -> None:
        """
Simulate a process being killed externally.
        """
        self._running.pop(name, None)


def create_executor(executor_type: str = "simple") -> ProcessExecutor:
    """
Factory function to create an executor.

Args:

    executor_type: "simple", "mock", or "windows"

Returns:

    ProcessExecutor implementation
    """
    if executor_type == "mock":
        return MockExecutor()
    elif executor_type == "windows":
        from .platform.windows import WindowsExecutor

        return WindowsExecutor()
    else:
        return SimpleExecutor()
