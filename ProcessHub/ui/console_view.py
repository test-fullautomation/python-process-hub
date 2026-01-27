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
# File: console_view.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Console TUI view - decoupled from server.
#   Implements improvement 3.6: Pluggable views.
#   Displays connections and process state in ASCII table format.
#
# Original author:
#   Nguyen Tan Phat (MS/EMC51)
#
# Original file:
#   ta-framework-tsb/ta_framework/project/process_hub/process_view.py
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Console TUI view - decoupled from server.

This module implements improvement 3.6:

- Moved out of ProcessHubServer.run()

- Takes HubStateSnapshot instead of raw dicts

- Can be replaced with rich/textual for better TUI
"""

from __future__ import annotations

import os
import sys

from ..core.models import HubStateSnapshot, ProcessState
from .base import HubViewBase


class ConsoleView(HubViewBase):
    """
Console-based TUI for process hub.

Displays connections and process state in ASCII table format.

Updates are non-blocking (just print to stdout).

Example output::

    === Process HUB ===
    
    Process Hub is listening for process updates...

    Panel ID      Session ID
    --------------------------------------------------
    panel_1       session_abc
    panel_2       session_abc

    PID      OWNER                STATUS       PROCESS
    ------------------------------------------------------------
    1234     panel_1              running      system_manager
    5678     panel_1,panel_2      running      edge_compute

    Press Ctrl+C to exit.
    """

    def __init__(self, clear_screen: bool = True):
        """
Initialize console view.

**Arguments:**

* ``clear_screen``

  / *Condition*: optional / *Type*: bool / *Default*: True /

  Whether to clear screen before each render.
        """
        self._index = 0
        self._clear_screen = clear_screen

    def clear(self) -> None:
        """
Clear console screen.
        """
        if not self._clear_screen:
            return
        if sys.platform == "win32":
            os.system("cls")
        else:
            os.system("clear")

    def render(self, snapshot: HubStateSnapshot) -> None:
        """
Render hub state to console.
        """
        self.clear()

        # Animate listening indicator
        self._index = (self._index + 1) % 5

        print("=== Process HUB ===")
        print(f"Process Hub is listening for process updates{'.' * self._index}")
        print()

        # Connection info
        self._render_connections(snapshot)

        # Process info
        self._render_processes(snapshot)

        # Restart info (if any)
        self._render_restart_info(snapshot)

        print("\nPress Ctrl+C to exit.")

    def _render_connections(self, snapshot: HubStateSnapshot) -> None:
        """
Render connections table.
        """
        print(f"{'Panel ID':<16} {'Session ID':<16}")
        print("-" * 50)

        if not snapshot.connections:
            print("  (no connections)")
        else:
            for conn in snapshot.connections:
                print(f"{conn.panel_id:<16} {conn.session_id:<16}")

        print()

    def _render_processes(self, snapshot: HubStateSnapshot) -> None:
        """
Render processes table.
        """
        print(f"{'PID':<8} {'OWNER':<20} {'STATUS':<12} PROCESS")
        print("-" * 60)

        if not snapshot.processes:
            print("  (no processes)")
        else:
            for proc in snapshot.processes:
                # Truncate owner list if too long
                owners = ",".join(proc.requesters[:3])
                if len(proc.requesters) > 3:
                    owners += f"...+{len(proc.requesters) - 3}"

                # Color-code status (ANSI codes)
                status = proc.state.value
                if proc.state == ProcessState.RUNNING:
                    status_display = f"\033[92m{status}\033[0m"  # Green
                elif proc.state == ProcessState.DEAD:
                    status_display = f"\033[91m{status}\033[0m"  # Red
                elif proc.state == ProcessState.FAILED:
                    status_display = f"\033[91m{status}\033[0m"  # Red
                elif proc.state == ProcessState.STARTING:
                    status_display = f"\033[93m{status}\033[0m"  # Yellow
                else:
                    status_display = status

                # For terminals that don't support ANSI, fall back to plain
                if not self._supports_ansi():
                    status_display = status

                print(f"{proc.pid:<8} {owners:<20} {status_display:<12} {proc.name}")

        print()

    def _render_restart_info(self, snapshot: HubStateSnapshot) -> None:
        """
Render restart status if active.
        """
        if not snapshot.killed_processes:
            return

        print()
        print("Killed Processes:")
        for proc in snapshot.killed_processes:
            print(f"  - {proc}")

        print()
        print(f"Restart State: {snapshot.restart_state}")

        if snapshot.pending_panels:
            print(f"Waiting for panels: {list(snapshot.pending_panels)}")

    def _supports_ansi(self) -> bool:
        """
Check if terminal supports ANSI escape codes.
        """
        # Windows 10+ supports ANSI in cmd/powershell with VT mode
        # Most Unix terminals support it
        if sys.platform == "win32":
            # Check for Windows Terminal or ConEmu
            return os.environ.get("WT_SESSION") is not None or \
                   os.environ.get("ConEmuANSI") == "ON"
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
