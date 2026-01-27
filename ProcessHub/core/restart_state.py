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
# File: restart_state.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Restart state machine - explicit FSM for restart coordination.
#   This module implements improvement 3.3: RestartState enum with explicit states.
#   RestartContext holds all restart-related data.
#   RestartStateMachine manages state transitions under single lock.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Restart state machine - explicit FSM for restart coordination.

This module implements improvement 3.3:

- Define RestartState enum with explicit states

- RestartContext holds all restart-related data

- RestartStateMachine manages state transitions under single lock

Benefits:
- Logic becomes easier to reason about

- Future features (timeout, partial restart, retry) become possible

- All restart state protected by single lock
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Set


class RestartState(Enum):
    """
RestartState: Explicit restart states.

Replaces implicit state spread across:

- self.is_notify flag

- self.killed_process list

- self.not_ready_panels list

- self.restart_notify_panels list

- threading.Event flags
    """

    IDLE = "idle"  # No restart in progress
    DETECTING = "detecting"  # Health check found killed processes
    NOTIFYING = "notifying"  # Sending restart notifications
    AWAITING_ACK = "awaiting_ack"  # Waiting for panel acknowledgments
    RESTARTING = "restarting"  # Performing restart sequence
    DONE = "done"  # Restart completed successfully
    FAILED = "failed"  # Restart failed (timeout, error, etc.)


@dataclass
class RestartContext:
    """
RestartContext: All restart-related state in one place.

Replaces scattered state:

- self.killed_process -> killed_processes

- self.not_ready_panels -> pending_panels

- self.restart_notify_panels -> notified_panels

- self.is_notify -> state == NOTIFYING/AWAITING_ACK

New fields for future features:

- started_at: for timeout detection (was missing)

- retry_count: for max retry logic (was missing)

- error_message: for failure reporting (was missing)
    """

    state: RestartState = RestartState.IDLE
    killed_processes: list[str] = field(default_factory=list)
    pending_panels: Set[str] = field(default_factory=set)
    notified_panels: Set[str] = field(default_factory=set)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: float = 300.0  # 5 minute max restart time
    error_message: Optional[str] = None

    def reset(self) -> None:
        """
Reset to idle state.

Clears all restart-related data except retry_count which accumulates across restart attempts.
        """
        self.state = RestartState.IDLE
        self.killed_processes.clear()
        self.pending_panels.clear()
        self.notified_panels.clear()
        self.started_at = None
        self.completed_at = None
        self.error_message = None
        # Note: retry_count is NOT reset - accumulates across restart attempts

    def is_timed_out(self) -> bool:
        """
Check if restart has exceeded timeout.

**Returns:**

  / *Type*: bool /

  True if the restart has exceeded the timeout_seconds, False otherwise.
        """
        if self.started_at is None:
            return False
        return (time.time() - self.started_at) > self.timeout_seconds

    def can_retry(self) -> bool:
        """
Check if retry is allowed.

**Returns:**

  / *Type*: bool /

  True if retry_count is less than max_retries.
        """
        return self.retry_count < self.max_retries

    def elapsed_time(self) -> Optional[float]:
        """
Get elapsed time since restart started.

**Returns:**

  / *Type*: Optional[float] /

  Elapsed time in seconds, or None if restart hasn't started.
        """
        if self.started_at is None:
            return None
        end = self.completed_at or time.time()
        return end - self.started_at


class RestartStateMachine:
    """
RestartStateMachine: State machine for restart coordination.

All transitions are explicit and guarded. Single lock protects all state transitions.

State diagram:

    IDLE -> DETECTING -> NOTIFYING -> AWAITING_ACK -> RESTARTING -> DONE -> IDLE

    _________________________________________________________\|___________________\|

    _________________________________________________________v__________________v

    ____________________________________________________FAILED --------------> IDLE (retry or give up)

Usage:
    fsm = RestartStateMachine()

    # Health check detected dead processes

    if fsm.detect_killed(["proc1"], ["panel1", "panel2"]):

        send_notifications()

        fsm.notifications_sent()

    # Panel acknowledged

    success, all_ready = fsm.panel_acknowledged("panel1")

    if all_ready and fsm.begin_restart():

        do_restart()

        fsm.restart_completed(success=True)

        fsm.reset_to_idle()
    """

    def __init__(self, timeout: float = 300.0, max_retries: int = 3):
        """
Initialize state machine.

**Arguments:**

* ``timeout``

  / *Condition*: optional / *Type*: float / *Default*: 300.0 /

  Maximum time in seconds for restart coordination.

* ``max_retries``

  / *Condition*: optional / *Type*: int / *Default*: 3 /

  Maximum restart attempts before giving up.
        """
        self._context = RestartContext(
            timeout_seconds=timeout,
            max_retries=max_retries,
        )
        self._lock = threading.Lock()

    @property
    def state(self) -> RestartState:
        """
Get current state (thread-safe).

**Returns:**

  / *Type*: RestartState /

  The current restart state.
        """
        with self._lock:
            return self._context.state

    @property
    def killed_processes(self) -> list[str]:
        """
Get killed processes (thread-safe copy).

**Returns:**

  / *Type*: list[str] /

  Copy of the list of killed process names.
        """
        with self._lock:
            return self._context.killed_processes.copy()

    @property
    def pending_panels(self) -> Set[str]:
        """
Get pending panels (thread-safe copy).

**Returns:**

  / *Type*: Set[str] /

  Copy of the set of panels that haven't acknowledged yet.
        """
        with self._lock:
            return self._context.pending_panels.copy()

    def get_snapshot(self) -> dict:
        """
Get immutable snapshot of restart state.

Returns dict suitable for HubStateSnapshot.

**Returns:**

  / *Type*: dict /

  Dictionary containing all restart state information.
        """
        with self._lock:
            return {
                "state": self._context.state.value,
                "killed_processes": tuple(self._context.killed_processes),
                "pending_panels": tuple(self._context.pending_panels),
                "notified_panels": tuple(self._context.notified_panels),
                "started_at": self._context.started_at,
                "retry_count": self._context.retry_count,
                "error_message": self._context.error_message,
            }

    # ========================================================================
    # State Transitions
    # ========================================================================

    def detect_killed(self, killed_processes: list[str], affected_panels: list[str]) -> bool:
        """
Transition: IDLE -> DETECTING -> NOTIFYING

Called when health check detects killed processes.

**Arguments:**

* ``killed_processes``

  / *Condition*: required / *Type*: list[str] /

  List of dead process names.

* ``affected_panels``

  / *Condition*: required / *Type*: list[str] /

  List of panel IDs that need notification.

**Returns:**

  / *Type*: bool /

  True if transition successful, False if restart already in progress.
        """
        with self._lock:
            if self._context.state != RestartState.IDLE:
                return False  # Already handling a restart

            self._context.state = RestartState.DETECTING
            self._context.killed_processes = killed_processes.copy()
            self._context.pending_panels = set(affected_panels)
            self._context.notified_panels = set(affected_panels)
            self._context.started_at = time.time()
            self._context.state = RestartState.NOTIFYING
            return True

    def notifications_sent(self) -> bool:
        """
Transition: NOTIFYING -> AWAITING_ACK

Called after all restart notifications have been sent.

**Returns:**

  / *Type*: bool /

  True if transition successful.
        """
        with self._lock:
            if self._context.state != RestartState.NOTIFYING:
                return False

            self._context.state = RestartState.AWAITING_ACK
            return True

    def panel_acknowledged(self, panel_id: str) -> tuple[bool, bool]:
        """
Record panel acknowledgment.

**Arguments:**

* ``panel_id``

  / *Condition*: required / *Type*: str /

  Panel ID that acknowledged.

**Returns:**

  / *Type*: tuple[bool, bool] /

  Tuple of (success, all_acknowledged):
  - success: True if acknowledgment was recorded
  - all_acknowledged: True if all panels have now acknowledged
        """
        with self._lock:
            if self._context.state != RestartState.AWAITING_ACK:
                return False, False

            self._context.pending_panels.discard(panel_id)
            all_ack = len(self._context.pending_panels) == 0
            return True, all_ack

    def begin_restart(self) -> bool:
        """
Transition: AWAITING_ACK -> RESTARTING

Called when all panels have acknowledged.

**Returns:**

  / *Type*: bool /

  True if transition successful.
        """
        with self._lock:
            if self._context.state != RestartState.AWAITING_ACK:
                return False
            if self._context.pending_panels:
                return False  # Still waiting for panels

            self._context.state = RestartState.RESTARTING
            return True

    def restart_completed(
        self, success: bool, error_message: Optional[str] = None
    ) -> bool:
        """
Transition: RESTARTING -> DONE | FAILED

**Arguments:**

* ``success``

  / *Condition*: required / *Type*: bool /

  Whether restart succeeded.

* ``error_message``

  / *Condition*: optional / *Type*: Optional[str] / *Default*: None /

  Error details if failed.

**Returns:**

  / *Type*: bool /

  True if transition successful.
        """
        with self._lock:
            if self._context.state != RestartState.RESTARTING:
                return False

            self._context.completed_at = time.time()
            if success:
                self._context.state = RestartState.DONE
            else:
                self._context.state = RestartState.FAILED
                self._context.error_message = error_message
                self._context.retry_count += 1
            return True

    def reset_to_idle(self) -> None:
        """
Transition: DONE | FAILED -> IDLE

Called after notifying clients of restart completion.
        """
        with self._lock:
            self._context.reset()

    def check_timeout(self) -> bool:
        """
Check for timeout and transition to FAILED if exceeded.

Should be called periodically during AWAITING_ACK or RESTARTING states.

**Returns:**

  / *Type*: bool /

  True if timed out (state changed to FAILED).
        """
        with self._lock:
            if self._context.state in (
                RestartState.IDLE,
                RestartState.DONE,
                RestartState.FAILED,
            ):
                return False

            if self._context.is_timed_out():
                self._context.state = RestartState.FAILED
                self._context.error_message = (
                    f"Restart timed out after {self._context.timeout_seconds}s"
                )
                self._context.retry_count += 1
                return True
            return False

    def force_fail(self, error_message: str) -> bool:
        """
Force transition to FAILED state.

Use for unrecoverable errors during restart.

**Arguments:**

* ``error_message``

  / *Condition*: required / *Type*: str /

  Error message describing the failure.

**Returns:**

  / *Type*: bool /

  True if state was changed.
        """
        with self._lock:
            if self._context.state in (RestartState.IDLE, RestartState.DONE):
                return False

            self._context.state = RestartState.FAILED
            self._context.error_message = error_message
            self._context.retry_count += 1
            return True
