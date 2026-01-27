"""Unit tests for RestartStateMachine."""

import pytest
import time
from ProcessHub.core.restart_state import (
    RestartState,
    RestartContext,
    RestartStateMachine,
)


class TestRestartContext:
    """Tests for RestartContext dataclass."""

    def test_default_state_is_idle(self):
        """Test default state is IDLE."""
        ctx = RestartContext()
        assert ctx.state == RestartState.IDLE

    def test_reset_clears_state(self):
        """Test reset clears all state."""
        ctx = RestartContext()
        ctx.state = RestartState.RESTARTING
        ctx.killed_processes = ["proc_1"]
        ctx.pending_panels = {"panel_1"}
        ctx.started_at = time.time()

        ctx.reset()

        assert ctx.state == RestartState.IDLE
        assert ctx.killed_processes == []
        assert ctx.pending_panels == set()
        assert ctx.started_at is None

    def test_reset_preserves_retry_count(self):
        """Test that reset does not clear retry count."""
        ctx = RestartContext()
        ctx.retry_count = 2

        ctx.reset()

        assert ctx.retry_count == 2  # Preserved across resets

    def test_is_timed_out(self):
        """Test timeout detection."""
        ctx = RestartContext(timeout_seconds=0.1)
        ctx.started_at = time.time() - 0.2  # Started 0.2s ago

        assert ctx.is_timed_out() is True

    def test_not_timed_out(self):
        """Test not timed out."""
        ctx = RestartContext(timeout_seconds=10.0)
        ctx.started_at = time.time()

        assert ctx.is_timed_out() is False

    def test_can_retry(self):
        """Test retry check."""
        ctx = RestartContext(max_retries=3)

        ctx.retry_count = 0
        assert ctx.can_retry() is True

        ctx.retry_count = 2
        assert ctx.can_retry() is True

        ctx.retry_count = 3
        assert ctx.can_retry() is False


class TestRestartStateMachine:
    """Tests for RestartStateMachine."""

    def test_initial_state_is_idle(self):
        """Test initial state is IDLE."""
        fsm = RestartStateMachine()
        assert fsm.state == RestartState.IDLE

    def test_detect_killed_transitions_to_notifying(self):
        """Test detect_killed transition."""
        fsm = RestartStateMachine()

        result = fsm.detect_killed(
            killed_processes=["proc_1"],
            affected_panels=["panel_1", "panel_2"],
        )

        assert result is True
        assert fsm.state == RestartState.NOTIFYING
        assert fsm.killed_processes == ["proc_1"]
        assert fsm.pending_panels == {"panel_1", "panel_2"}

    def test_detect_killed_fails_if_not_idle(self):
        """Test detect_killed fails if not in IDLE state."""
        fsm = RestartStateMachine()
        fsm.detect_killed(["proc_1"], ["panel_1"])

        result = fsm.detect_killed(["proc_2"], ["panel_2"])

        assert result is False  # Already in restart

    def test_notifications_sent_transitions_to_awaiting_ack(self):
        """Test notifications_sent transition."""
        fsm = RestartStateMachine()
        fsm.detect_killed(["proc_1"], ["panel_1"])

        result = fsm.notifications_sent()

        assert result is True
        assert fsm.state == RestartState.AWAITING_ACK

    def test_panel_acknowledged_removes_from_pending(self):
        """Test panel acknowledgment."""
        fsm = RestartStateMachine()
        fsm.detect_killed(["proc_1"], ["panel_1", "panel_2"])
        fsm.notifications_sent()

        success, all_ack = fsm.panel_acknowledged("panel_1")

        assert success is True
        assert all_ack is False
        assert "panel_1" not in fsm.pending_panels
        assert "panel_2" in fsm.pending_panels

    def test_panel_acknowledged_returns_all_ack_when_done(self):
        """Test all_acknowledged flag when last panel acks."""
        fsm = RestartStateMachine()
        fsm.detect_killed(["proc_1"], ["panel_1"])
        fsm.notifications_sent()

        success, all_ack = fsm.panel_acknowledged("panel_1")

        assert success is True
        assert all_ack is True

    def test_begin_restart_transitions_to_restarting(self):
        """Test begin_restart transition."""
        fsm = RestartStateMachine()
        fsm.detect_killed(["proc_1"], ["panel_1"])
        fsm.notifications_sent()
        fsm.panel_acknowledged("panel_1")

        result = fsm.begin_restart()

        assert result is True
        assert fsm.state == RestartState.RESTARTING

    def test_begin_restart_fails_if_pending_panels(self):
        """Test begin_restart fails if panels still pending."""
        fsm = RestartStateMachine()
        fsm.detect_killed(["proc_1"], ["panel_1", "panel_2"])
        fsm.notifications_sent()
        fsm.panel_acknowledged("panel_1")  # Only one acked

        result = fsm.begin_restart()

        assert result is False

    def test_restart_completed_success(self):
        """Test restart completed successfully."""
        fsm = RestartStateMachine()
        fsm.detect_killed(["proc_1"], ["panel_1"])
        fsm.notifications_sent()
        fsm.panel_acknowledged("panel_1")
        fsm.begin_restart()

        result = fsm.restart_completed(success=True)

        assert result is True
        assert fsm.state == RestartState.DONE

    def test_restart_completed_failure(self):
        """Test restart completed with failure."""
        fsm = RestartStateMachine()
        fsm.detect_killed(["proc_1"], ["panel_1"])
        fsm.notifications_sent()
        fsm.panel_acknowledged("panel_1")
        fsm.begin_restart()

        result = fsm.restart_completed(success=False, error_message="Start failed")

        assert result is True
        assert fsm.state == RestartState.FAILED
        snapshot = fsm.get_snapshot()
        assert snapshot["error_message"] == "Start failed"
        assert snapshot["retry_count"] == 1

    def test_reset_to_idle(self):
        """Test reset to idle."""
        fsm = RestartStateMachine()
        fsm.detect_killed(["proc_1"], ["panel_1"])
        fsm.notifications_sent()
        fsm.panel_acknowledged("panel_1")
        fsm.begin_restart()
        fsm.restart_completed(success=True)

        fsm.reset_to_idle()

        assert fsm.state == RestartState.IDLE
        assert fsm.killed_processes == []

    def test_check_timeout(self):
        """Test timeout detection."""
        fsm = RestartStateMachine(timeout=0.01)  # Very short timeout
        fsm.detect_killed(["proc_1"], ["panel_1"])
        fsm.notifications_sent()

        time.sleep(0.02)  # Wait for timeout
        result = fsm.check_timeout()

        assert result is True
        assert fsm.state == RestartState.FAILED

    def test_get_snapshot(self):
        """Test get_snapshot returns complete state."""
        fsm = RestartStateMachine()
        fsm.detect_killed(["proc_1", "proc_2"], ["panel_1", "panel_2"])
        fsm.notifications_sent()
        fsm.panel_acknowledged("panel_1")

        snapshot = fsm.get_snapshot()

        assert snapshot["state"] == "awaiting_ack"
        assert set(snapshot["killed_processes"]) == {"proc_1", "proc_2"}
        assert set(snapshot["pending_panels"]) == {"panel_2"}
        assert set(snapshot["notified_panels"]) == {"panel_1", "panel_2"}

    def test_full_restart_flow(self):
        """Test complete restart flow."""
        fsm = RestartStateMachine()

        # 1. Detect killed process
        assert fsm.detect_killed(["proc_1"], ["panel_1", "panel_2"])
        assert fsm.state == RestartState.NOTIFYING

        # 2. Notifications sent
        assert fsm.notifications_sent()
        assert fsm.state == RestartState.AWAITING_ACK

        # 3. Panels acknowledge
        success, all_ack = fsm.panel_acknowledged("panel_1")
        assert success and not all_ack

        success, all_ack = fsm.panel_acknowledged("panel_2")
        assert success and all_ack

        # 4. Begin restart
        assert fsm.begin_restart()
        assert fsm.state == RestartState.RESTARTING

        # 5. Complete restart
        assert fsm.restart_completed(success=True)
        assert fsm.state == RestartState.DONE

        # 6. Reset
        fsm.reset_to_idle()
        assert fsm.state == RestartState.IDLE
