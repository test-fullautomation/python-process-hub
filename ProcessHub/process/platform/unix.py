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
# File: unix.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Unix-specific process executor.
#   Uses POSIX APIs for process management.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Unix-specific process executor.

Uses POSIX APIs for process management:

- subprocess.Popen for starting processes

- os.kill / signal for termination

- psutil (if available) for process tracking
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from typing import Any, Optional

from .base import PlatformExecutor

logger = logging.getLogger(__name__)

# Try to import psutil
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.debug("psutil not installed, using subprocess only")


class UnixExecutor(PlatformExecutor):
    """
Unix/Linux/macOS process executor.

Uses POSIX APIs:

- subprocess.Popen for starting

- SIGTERM/SIGKILL for stopping

- psutil for process tracking (if available)

Configuration:

- script: Path to script/executable

- args: List of arguments

- wait_time: Time to wait after start (default: 2.0)

- process_name: Process name for lookup

- env: Additional environment variables

- working_dir: Working directory

- daemon: Run as daemon (default: False)

- shell: Use shell execution (default: False)
    """

    def __init__(
        self,
        stop_timeout: float = 5.0,
        use_process_group: bool = True,
    ):
        """
Initialize Unix executor.

Args:

    stop_timeout: Timeout for graceful stop (seconds)
    
    use_process_group: Create new process group for children
        """
        super().__init__(stop_timeout=stop_timeout)
        self._use_process_group = use_process_group

    def start(
        self, name: str, config: dict
    ) -> tuple[bool, str, Optional[int]]:
        """
Start a process using subprocess.
        """
        script = self._get_script_path(config)
        if not script:
            return False, f"Script not found: {config.get('script', '')}", None

        args = self._get_args(config)
        env = self._get_env(config)
        wait_time = self._get_wait_time(config)
        working_dir = config.get("working_dir")
        use_shell = config.get("shell", False)
        daemon = config.get("daemon", False)

        # Build command
        if script.endswith(".py"):
            cmd = [sys.executable, script] + args
        else:
            cmd = [script] + args

        logger.debug("Starting process %s: %s", name, " ".join(cmd))

        try:
            # Set up process group for proper child cleanup
            kwargs: dict[str, Any] = {
                "env": env,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "stdin": subprocess.DEVNULL,
            }

            if working_dir:
                kwargs["cwd"] = working_dir

            if self._use_process_group:
                kwargs["start_new_session"] = True

            if use_shell:
                cmd = " ".join(cmd)
                kwargs["shell"] = True

            if daemon:
                # Detach from parent
                kwargs["start_new_session"] = True

            # Start process
            proc = subprocess.Popen(cmd, **kwargs)

            self._processes[name] = proc
            self._pids[name] = proc.pid

            # Wait for process to start
            if wait_time > 0:
                time.sleep(wait_time)

            # Verify process is running
            if proc.poll() is not None:
                # Process already exited
                stdout, stderr = proc.communicate()
                error_msg = stderr.decode() if stderr else "Process exited immediately"
                return False, error_msg, None

            # Try to get psutil.Process for better tracking
            if HAS_PSUTIL:
                try:
                    ps_proc = psutil.Process(proc.pid)
                    self._processes[name] = ps_proc
                except psutil.NoSuchProcess:
                    pass

            logger.info("Started process %s (pid=%d)", name, proc.pid)
            return True, f"Started {name}", proc.pid

        except FileNotFoundError:
            return False, f"Executable not found: {script}", None
        except PermissionError:
            return False, f"Permission denied: {script}", None
        except Exception as e:
            logger.exception("Failed to start %s", name)
            return False, str(e), None

    def stop(self, name: str, force: bool = False) -> bool:
        """
Stop a process using signals.
        """
        proc = self._processes.get(name)
        pid = self._pids.get(name)

        if proc is None and pid is None:
            logger.debug("Process %s not tracked", name)
            return True

        try:
            if HAS_PSUTIL and isinstance(proc, psutil.Process):
                return self._stop_psutil(name, proc, force)
            elif isinstance(proc, subprocess.Popen):
                return self._stop_popen(name, proc, force)
            elif pid:
                return self._stop_by_pid(name, pid, force)
            else:
                self.cleanup(name)
                return True

        except Exception as e:
            logger.exception("Error stopping %s", name)
            self.cleanup(name)
            return False

    def _stop_popen(
        self, name: str, proc: subprocess.Popen, force: bool
    ) -> bool:
        """
Stop a Popen process.
        """
        try:
            # Send SIGTERM
            proc.terminate()

            try:
                proc.wait(timeout=self._stop_timeout)
            except subprocess.TimeoutExpired:
                if force:
                    proc.kill()
                    proc.wait(timeout=2.0)
                else:
                    return False

            self.cleanup(name)
            logger.info("Stopped process %s", name)
            return True

        except Exception as e:
            logger.exception("Error stopping Popen %s", name)
            self.cleanup(name)
            return False

    def _stop_psutil(
        self, name: str, proc: psutil.Process, force: bool
    ) -> bool:
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
                    return False

            self.cleanup(name)
            logger.info("Stopped process %s", name)
            return True

        except psutil.NoSuchProcess:
            # Already dead
            self.cleanup(name)
            return True
        except Exception as e:
            logger.exception("Error stopping psutil %s", name)
            self.cleanup(name)
            return False

    def _stop_by_pid(self, name: str, pid: int, force: bool) -> bool:
        """
Stop a process by PID using signals.
        """
        try:
            # Send SIGTERM
            os.kill(pid, signal.SIGTERM)

            # Wait for termination
            start_time = time.time()
            while time.time() - start_time < self._stop_timeout:
                try:
                    os.kill(pid, 0)  # Check if still alive
                    time.sleep(0.1)
                except OSError:
                    # Process is dead
                    self.cleanup(name)
                    return True

            # Still alive, force kill if requested
            if force:
                os.kill(pid, signal.SIGKILL)
                time.sleep(0.5)

            self.cleanup(name)
            return True

        except OSError as e:
            if e.errno == 3:  # No such process
                self.cleanup(name)
                return True
            raise

    def is_running(self, name: str) -> bool:
        """
Check if process is running.
        """
        proc = self._processes.get(name)
        pid = self._pids.get(name)

        if proc is None and pid is None:
            return False

        try:
            if HAS_PSUTIL and isinstance(proc, psutil.Process):
                return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            elif isinstance(proc, subprocess.Popen):
                return proc.poll() is None
            elif pid:
                # Check by sending signal 0
                try:
                    os.kill(pid, 0)
                    return True
                except OSError:
                    return False
            else:
                return False

        except Exception:
            return False

    def find_process(
        self, name: str, process_name: Optional[str] = None
    ) -> Optional[Any]:
        """
Find a process by name.

Args:

    name: Process name (used in command line)
    
    process_name: Actual process name (e.g., "python")

Returns:

    psutil.Process if found, None otherwise
        """
        if not HAS_PSUTIL:
            return None

        search_names = [name]
        if process_name:
            search_names.append(process_name)

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(proc.cmdline() or [])

                for search_name in search_names:
                    if search_name in cmdline or search_name in proc.name():
                        return proc

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return None
