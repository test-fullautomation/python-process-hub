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
# File: windows.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Windows-specific process executor.
#   Uses cmd.exe, PowerShell, and psutil for process management.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Windows-specific process executor.

Uses Windows APIs for process management:

- cmd.exe with 'start' for launching minimized windows

- PowerShell for process termination

- psutil for process tracking
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import Optional

from ..executor import ProcessExecutor

logger = logging.getLogger(__name__)

# Try to import psutil
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil not installed, WindowsExecutor will have limited functionality")


class WindowsExecutor(ProcessExecutor):
    """
Windows process executor using cmd.exe and PowerShell.

This executor matches the original ta-framework behavior:

- Uses 'start /min' to launch processes in minimized windows

- Uses PowerShell terminate script for stopping processes

- Uses psutil for process tracking and health checks

Configuration dict keys:

- script: Path to script/executable

- args: List of arguments

- wait_time: Time to wait after start (default: 2.0)

- process_name: Actual process name to search for (for psutil)

- central_log: Whether to use central logging

- python_exe: Python executable path (default: uses system python)
    """

    def __init__(
        self,
        terminate_script: Optional[str] = None,
        use_python_venv: bool = False,
        default_wait_time: float = 2.0,
    ):
        """
Initialize Windows executor.

**Arguments:**

* ``terminate_script``

  / *Condition*: optional / *Type*: str / *Default*: None /

  Path to PowerShell terminate script.

* ``use_python_venv``

  / *Condition*: optional / *Type*: bool / *Default*: False /

  Whether to use 'python' from venv.

* ``default_wait_time``

  / *Condition*: optional / *Type*: float / *Default*: 2.0 /

  Default wait time after process start.
        """
        self._processes: dict[str, psutil.Process] = {}
        self._pids: dict[str, int] = {}
        self._terminate_script = terminate_script
        self._use_python_venv = use_python_venv
        self._default_wait_time = default_wait_time

    def start(
        self, name: str, config: dict
    ) -> tuple[bool, str, Optional[int]]:
        """
Start a process using Windows cmd.exe start command.
        """
        script = config.get("script", "")
        args = config.get("args", [])
        wait_time = config.get("wait_time", self._default_wait_time)
        process_name = config.get("process_name", name)

        # Expand environment variables
        script = os.path.expandvars(script)

        if not script:
            return False, "No script specified", None

        if not os.path.exists(script):
            return False, f"Script not found: {script}", None

        # Build command
        if script.endswith(".py"):
            python_exe = (
                "python"
                if self._use_python_venv
                else os.path.expandvars('"%RobotPythonPath%/python"')
            )
            script_part = f'{python_exe} "{script}"'
            if args:
                script_part += " " + " ".join(args)
        else:
            script_part = f'"{script}"'
            if args:
                script_part += " " + " ".join(args)

        # Use cmd.exe start to launch in new minimized window
        cmd = f'start /min "{name}" cmd.exe /k "{script_part}"'

        logger.debug("Starting process with command: %s", cmd)

        try:
            result = subprocess.run(
                cmd,
                check=True,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
                env=dict(os.environ),
            )

            if result.returncode != 0:
                return False, f"Start command failed: {result.stderr}", None

        except subprocess.CalledProcessError as e:
            return False, f"Failed to start: {e}", None
        except Exception as e:
            return False, str(e), None

        # Wait for process to start
        if wait_time > 0:
            time.sleep(wait_time)

        # Find the process
        if HAS_PSUTIL:
            proc = self._find_process(name, process_name)
            if proc and proc.is_running():
                self._processes[name] = proc
                self._pids[name] = proc.pid
                logger.info("Started process %s (pid=%d)", name, proc.pid)
                return True, f"Started {name}", proc.pid

            return False, f"Process {name} not found after start", None
        else:
            # Without psutil, we can't verify the process
            logger.warning("Cannot verify process without psutil")
            return True, f"Started {name} (unverified)", None

    def stop(self, name: str, force: bool = False) -> bool:
        """
Stop a process using PowerShell terminate script or psutil.
        """
        # Try PowerShell script first
        if self._terminate_script and os.path.exists(self._terminate_script):
            try:
                result = subprocess.run(
                    [
                        "powershell",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(self._terminate_script),
                        "-Title",
                        name,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                # Cleanup tracking
                self._processes.pop(name, None)
                self._pids.pop(name, None)

                if result.returncode == 0:
                    logger.info("Stopped process %s via PowerShell", name)
                    return True
                else:
                    logger.warning(
                        "PowerShell terminate returned %d: %s",
                        result.returncode,
                        result.stderr,
                    )

            except Exception as e:
                logger.warning("PowerShell terminate failed: %s", e)

        # Fallback: use psutil
        if HAS_PSUTIL:
            proc = self._processes.get(name)
            if proc:
                try:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        if force:
                            proc.kill()
                            proc.wait(timeout=2)

                    self._processes.pop(name, None)
                    self._pids.pop(name, None)
                    logger.info("Stopped process %s via psutil", name)
                    return True

                except psutil.NoSuchProcess:
                    # Already dead
                    self._processes.pop(name, None)
                    self._pids.pop(name, None)
                    return True
                except Exception as e:
                    logger.exception("Error stopping %s via psutil", name)

        # Cleanup anyway
        self._processes.pop(name, None)
        self._pids.pop(name, None)
        return True

    def is_running(self, name: str) -> bool:
        """
Check if process is running using psutil.
        """
        if not HAS_PSUTIL:
            return name in self._processes

        proc = self._processes.get(name)
        if proc:
            try:
                return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            except psutil.NoSuchProcess:
                self._processes.pop(name, None)
                self._pids.pop(name, None)
                return False
            except Exception:
                return False

        return False

    def get_pid(self, name: str) -> Optional[int]:
        """
Get process PID.
        """
        return self._pids.get(name)

    def _find_process(
        self, title: str, process_name: str
    ) -> Optional[psutil.Process]:
        """
Find a process by window title or process name.

Searches through all running processes looking for matches.
        """
        if not HAS_PSUTIL:
            return None

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(proc.cmdline() or [])

                # Check if title appears in command line
                if title in cmdline:
                    return proc

                # Check process name
                if process_name and process_name in proc.name():
                    return proc

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception:
                continue

        return None

    def update_process(
        self, name: str, process: psutil.Process, pid: int
    ) -> None:
        """
Update tracked process.

Used when a process is found externally (e.g., already running).
        """
        self._processes[name] = process
        self._pids[name] = pid
