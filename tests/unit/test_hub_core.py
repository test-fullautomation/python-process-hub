"""Unit tests for ProcessHubCore."""

import pytest
from ProcessHub.core.hub_core import ProcessHubCore, MessageType
from ProcessHub.core.models import (
    RegisterConnectionRequest,
    UnregisterConnectionRequest,
    ConnectionInfoRequest,
    ProcessStartRequest,
    ProcessStopRequest,
    ProcessRestartReady,
    ProcessState,
)
from ProcessHub.core.restart_state import RestartState


class MockExecutor:
    """Mock executor for testing."""

    def __init__(self):
        self.running = {}
        self.next_pid = 1000
        self.fail_start = set()  # Process names that should fail

    def start(self, name):
        if name in self.fail_start:
            return False, f"Failed to start {name}", None
        pid = self.next_pid
        self.next_pid += 1
        self.running[name] = pid
        return True, f"Started {name}", pid

    def stop(self, name, force=False):
        self.running.pop(name, None)
        return True

    def health_check(self, names):
        return [n for n in names if n not in self.running]


class TestProcessHubCore:
    """Tests for ProcessHubCore."""

    @pytest.fixture
    def executor(self):
        return MockExecutor()

    @pytest.fixture
    def core(self, executor):
        return ProcessHubCore(
            process_starter=executor.start,
            process_stopper=executor.stop,
            health_checker=executor.health_check,
        )

    # ========================================================================
    # Connection Tests
    # ========================================================================

    def test_register_connection(self, core):
        """Test registering a connection."""
        req = RegisterConnectionRequest(panel_id="panel_1", session_id="session_1")

        messages = core.handle_register(req)

        assert len(messages) == 1
        assert messages[0].msg_type == MessageType.REGISTER_RESPONSE
        assert messages[0].payload.panel_id == "panel_1"
        assert messages[0].payload.success is True
        assert core.is_registered("panel_1")

    def test_register_multiple_panels_same_session(self, core):
        """Test registering multiple panels in same session."""
        req1 = RegisterConnectionRequest(panel_id="panel_1", session_id="session_1")
        req2 = RegisterConnectionRequest(panel_id="panel_2", session_id="session_1")

        core.handle_register(req1)
        core.handle_register(req2)

        snapshot = core.get_state_snapshot()
        assert len(snapshot.connections) == 2

        # Both should have each other in session_panel_ids
        for conn in snapshot.connections:
            assert "panel_1" in conn.session_panel_ids
            assert "panel_2" in conn.session_panel_ids

    def test_unregister_connection(self, core):
        """Test unregistering a connection."""
        reg_req = RegisterConnectionRequest(panel_id="panel_1", session_id="session_1")
        core.handle_register(reg_req)

        unreg_req = UnregisterConnectionRequest(panel_id="panel_1")
        messages = core.handle_unregister(unreg_req)

        assert len(messages) == 1
        assert messages[0].msg_type == MessageType.UNREGISTER_RESPONSE
        assert not core.is_registered("panel_1")

    def test_connection_info_request(self, core):
        """Test connection info request."""
        reg_req = RegisterConnectionRequest(panel_id="panel_1", session_id="session_1")
        core.handle_register(reg_req)

        info_req = ConnectionInfoRequest(panel_id="panel_1")
        messages = core.handle_connection_info(info_req)

        assert len(messages) == 1
        assert messages[0].msg_type == MessageType.CONNECTION_INFO_RESPONSE
        assert "panel_1" in messages[0].payload.connections

    # ========================================================================
    # Process Start Tests
    # ========================================================================

    def test_start_process(self, core, executor):
        """Test starting a process."""
        # Register panel first
        reg_req = RegisterConnectionRequest(panel_id="panel_1", session_id="session_1")
        core.handle_register(reg_req)

        # Start process
        start_req = ProcessStartRequest(
            panel_id="panel_1",
            process_list=["proc_1"],
        )
        messages = core.handle_start_request(start_req)

        assert len(messages) == 1
        assert messages[0].msg_type == MessageType.START_RESPONSE
        assert messages[0].payload.success is True
        assert "proc_1" in executor.running

    def test_start_multiple_processes(self, core, executor):
        """Test starting multiple processes."""
        reg_req = RegisterConnectionRequest(panel_id="panel_1", session_id="session_1")
        core.handle_register(reg_req)

        start_req = ProcessStartRequest(
            panel_id="panel_1",
            process_list=["proc_1", "proc_2", "proc_3"],
        )
        messages = core.handle_start_request(start_req)

        assert messages[0].payload.success is True
        assert len(executor.running) == 3

    def test_start_process_failure_rollback(self, core, executor):
        """Test that failed start rolls back all processes."""
        reg_req = RegisterConnectionRequest(panel_id="panel_1", session_id="session_1")
        core.handle_register(reg_req)

        # Make proc_2 fail
        executor.fail_start.add("proc_2")

        start_req = ProcessStartRequest(
            panel_id="panel_1",
            process_list=["proc_1", "proc_2", "proc_3"],
        )
        messages = core.handle_start_request(start_req)

        assert messages[0].payload.success is False
        assert "proc_2" in messages[0].payload.failed_processes
        # All processes should be stopped (rollback)
        assert len(executor.running) == 0

    # ========================================================================
    # Process Stop Tests
    # ========================================================================

    def test_stop_process(self, core, executor):
        """Test stopping a process."""
        reg_req = RegisterConnectionRequest(panel_id="panel_1", session_id="session_1")
        core.handle_register(reg_req)

        # Start process
        start_req = ProcessStartRequest(panel_id="panel_1", process_list=["proc_1"])
        core.handle_start_request(start_req)
        assert "proc_1" in executor.running

        # Stop process
        stop_req = ProcessStopRequest(panel_id="panel_1", process_list=["proc_1"])
        messages = core.handle_stop_request(stop_req)

        assert messages[0].payload.success is True
        assert "proc_1" not in executor.running

    def test_stop_shared_process_keeps_running(self, core, executor):
        """Test that shared process stays running for other requesters."""
        # Register two panels
        core.handle_register(RegisterConnectionRequest(panel_id="panel_1", session_id="s1"))
        core.handle_register(RegisterConnectionRequest(panel_id="panel_2", session_id="s2"))

        # Both start same process
        core.handle_start_request(ProcessStartRequest(panel_id="panel_1", process_list=["proc_1"]))
        core.handle_start_request(ProcessStartRequest(panel_id="panel_2", process_list=["proc_1"]))

        # Panel 1 stops
        stop_req = ProcessStopRequest(panel_id="panel_1", process_list=["proc_1"])
        core.handle_stop_request(stop_req)

        # Process should still be running (panel_2 needs it)
        assert "proc_1" in executor.running

    def test_force_stop_shared_process(self, core, executor):
        """Test force stop removes process even if shared."""
        core.handle_register(RegisterConnectionRequest(panel_id="panel_1", session_id="s1"))
        core.handle_register(RegisterConnectionRequest(panel_id="panel_2", session_id="s2"))

        core.handle_start_request(ProcessStartRequest(panel_id="panel_1", process_list=["proc_1"]))
        core.handle_start_request(ProcessStartRequest(panel_id="panel_2", process_list=["proc_1"]))

        # Force stop
        stop_req = ProcessStopRequest(panel_id="panel_1", process_list=["proc_1"], force=True)
        core.handle_stop_request(stop_req)

        assert "proc_1" not in executor.running

    # ========================================================================
    # Health Check / Restart Tests
    # ========================================================================

    def test_tick_detects_dead_process(self, core, executor):
        """Test that tick detects dead processes."""
        core.handle_register(RegisterConnectionRequest(panel_id="panel_1", session_id="s1"))
        core.handle_start_request(ProcessStartRequest(panel_id="panel_1", process_list=["proc_1"]))

        # Kill the process externally
        del executor.running["proc_1"]

        # Tick should detect and notify
        messages = core.tick()

        assert len(messages) == 1
        assert messages[0].msg_type == MessageType.RESTART_NOTIFY
        assert "proc_1" in messages[0].payload.killed_processes

    def test_restart_flow(self, core, executor):
        """Test complete restart flow."""
        core.handle_register(RegisterConnectionRequest(panel_id="panel_1", session_id="s1"))
        core.handle_start_request(ProcessStartRequest(panel_id="panel_1", process_list=["proc_1"]))

        # Kill process
        del executor.running["proc_1"]

        # Tick detects
        messages = core.tick()
        assert len(messages) == 1
        assert messages[0].msg_type == MessageType.RESTART_NOTIFY

        # Panel acknowledges
        ready_req = ProcessRestartReady(panel_id="panel_1")
        messages = core.handle_restart_ready(ready_req)

        # Should restart and notify done
        assert len(messages) == 1
        assert messages[0].msg_type == MessageType.RESTART_DONE
        assert messages[0].payload.success is True
        assert "proc_1" in executor.running

    def test_restart_waits_for_all_panels(self, core, executor):
        """Test that restart waits for all affected panels."""
        core.handle_register(RegisterConnectionRequest(panel_id="panel_1", session_id="s1"))
        core.handle_register(RegisterConnectionRequest(panel_id="panel_2", session_id="s2"))

        # Both use same process
        core.handle_start_request(ProcessStartRequest(panel_id="panel_1", process_list=["proc_1"]))
        core.handle_start_request(ProcessStartRequest(panel_id="panel_2", process_list=["proc_1"]))

        # Kill process
        del executor.running["proc_1"]

        # Tick should notify both panels
        messages = core.tick()
        assert len(messages) == 2

        # Only panel_1 acknowledges
        messages = core.handle_restart_ready(ProcessRestartReady(panel_id="panel_1"))
        assert len(messages) == 0  # Still waiting for panel_2

        # panel_2 acknowledges
        messages = core.handle_restart_ready(ProcessRestartReady(panel_id="panel_2"))
        assert len(messages) == 2  # Both get notified
        assert all(m.msg_type == MessageType.RESTART_DONE for m in messages)

    # ========================================================================
    # State Snapshot Tests
    # ========================================================================

    def test_get_state_snapshot(self, core, executor):
        """Test getting state snapshot."""
        core.handle_register(RegisterConnectionRequest(panel_id="panel_1", session_id="s1"))
        core.handle_start_request(ProcessStartRequest(panel_id="panel_1", process_list=["proc_1"]))

        snapshot = core.get_state_snapshot()

        assert len(snapshot.connections) == 1
        assert snapshot.connections[0].panel_id == "panel_1"
        assert len(snapshot.processes) == 1
        assert snapshot.processes[0].name == "proc_1"
        assert snapshot.processes[0].state == ProcessState.RUNNING

    def test_snapshot_is_immutable(self, core):
        """Test that snapshot is immutable."""
        core.handle_register(RegisterConnectionRequest(panel_id="panel_1", session_id="s1"))
        snapshot = core.get_state_snapshot()

        with pytest.raises(AttributeError):
            snapshot.connections[0].panel_id = "modified"  # type: ignore

    # ========================================================================
    # Edge Cases
    # ========================================================================

    def test_unregister_cleans_up_orphaned_processes(self, core, executor):
        """Test that unregister stops processes only used by that panel."""
        core.handle_register(RegisterConnectionRequest(panel_id="panel_1", session_id="s1"))
        core.handle_start_request(ProcessStartRequest(panel_id="panel_1", process_list=["proc_1"]))

        assert "proc_1" in executor.running

        # Unregister should stop the process
        core.handle_unregister(UnregisterConnectionRequest(panel_id="panel_1"))

        assert "proc_1" not in executor.running

    def test_shutdown_stops_all_processes(self, core, executor):
        """Test that shutdown stops all processes."""
        core.handle_register(RegisterConnectionRequest(panel_id="panel_1", session_id="s1"))
        core.handle_start_request(ProcessStartRequest(panel_id="panel_1", process_list=["proc_1", "proc_2"]))

        assert len(executor.running) == 2

        core.shutdown()

        assert len(executor.running) == 0
