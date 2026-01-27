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
# File: base.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Base platform executor interface.
#   Defines abstract base class for platform-specific process executors.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Base platform executor interface.

This module defines the abstract base class for platform-specific
process executors. Each platform (Windows, Unix) implements this
interface with appropriate system calls.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PlatformExecutor(ABC):
    """
Abstract base class for platform-specific process executors.

Subclasses implement platform-specific process management:

- WindowsExecutor: Uses cmd.exe, PowerShell, Win32 APIs

- UnixExecutor: Uses fork/exec, signals, /proc filesystem

Configuration dict keys (common):

- script: Path to script/executable

- args: List of arguments

- wait_time: Time to wait after start (seconds)

- process_name: Actual process name (for lookup)

- env: Additional environment variables

- working_dir: Working directory for process

- central_log: Whether to use central logging
    """

    def __init__(self, stop_timeout: float = 5.0):
        """
Initialize executor.

Args:

    stop_timeout: Timeout for graceful stop (seconds)
        """
        self._stop_timeout = stop_timeout
        self._processes: dict[str, Any] = {}
        self._pids: dict[str, int] = {}

    @abstractmethod
    def start(
        self, name: str, config: dict
    ) -> tuple[bool, str, Optional[int]]:
        """
Start a process.

Args:

    name: Process name/identifier
    
    config: Process configuration

Returns:

    Tuple of (success, message, pid)
        """
        pass

    @abstractmethod
    def stop(self, name: str, force: bool = False) -> bool:
        """
Stop a process.

Args:

    name: Process name/identifier
    
    force: Force kill if graceful stop fails

Returns:

    True if stopped successfully
        """
        pass

    @abstractmethod
    def is_running(self, name: str) -> bool:
        """
Check if a process is running.

Args:
    name: Process name/identifier

Returns:
    True if running
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
        return self._pids.get(name)

    def update_process(self, name: str, process: Any, pid: int) -> None:
        """
Update tracked process.

Used when external lookup finds a running process.

Args:

    name: Process name
    
    process: Process object
    
    pid: Process ID
        """
        self._processes[name] = process
        self._pids[name] = pid

    def cleanup(self, name: str) -> None:
        """
Clean up tracking for a process.

Args:

    name: Process name
        """
        self._processes.pop(name, None)
        self._pids.pop(name, None)

    def cleanup_all(self) -> None:
        """Clean up all tracked processes."""
        self._processes.clear()
        self._pids.clear()

    # ========================================================================
    # Helper methods for subclasses
    # ========================================================================

    def _get_script_path(self, config: dict) -> Optional[str]:
        """
Extract and validate script path from config.
        """
        import os

        script = config.get("script", "")
        if not script:
            return None

        script = os.path.expandvars(script)
        if not os.path.exists(script):
            return None

        return script

    def _get_args(self, config: dict) -> list[str]:
        """
Extract arguments from config.
        """
        args = config.get("args", [])
        if isinstance(args, str):
            args = args.split()
        return list(args)

    def _get_env(self, config: dict) -> dict[str, str]:
        """
Get environment variables from config.
        """
        import os

        env = os.environ.copy()
        env.update(config.get("env", {}))
        return env

    def _get_wait_time(self, config: dict, default: float = 2.0) -> float:
        """
Get wait time from config.
        """
        return float(config.get("wait_time", default))
