"""Unit tests for ProcessRegistry."""

import pytest
import threading
from ProcessHub.core.process_registry import ProcessRegistry
from ProcessHub.core.models import ProcessState


class TestProcessRegistry:
    """Tests for ProcessRegistry."""

    def test_register_new_process(self):
        """Test registering a new process."""
        registry = ProcessRegistry()

        result = registry.register("test_proc", requester="panel_1")

        assert result is True  # Newly registered
        assert registry.exists("test_proc")
        assert registry.get_requesters("test_proc") == ["panel_1"]

    def test_register_existing_process_adds_requester(self):
        """Test that registering existing process adds requester."""
        registry = ProcessRegistry()
        registry.register("test_proc", requester="panel_1")

        result = registry.register("test_proc", requester="panel_2")

        assert result is False  # Already existed
        requesters = registry.get_requesters("test_proc")
        assert "panel_1" in requesters
        assert "panel_2" in requesters

    def test_unregister_removes_requester(self):
        """Test unregistering removes requester."""
        registry = ProcessRegistry()
        registry.register("test_proc", requester="panel_1")
        registry.register("test_proc", requester="panel_2")

        can_stop = registry.unregister("test_proc", requester="panel_1")

        assert can_stop is False  # Still has panel_2
        assert registry.get_requesters("test_proc") == ["panel_2"]

    def test_unregister_returns_true_when_no_requesters(self):
        """Test unregister returns True when last requester removed."""
        registry = ProcessRegistry()
        registry.register("test_proc", requester="panel_1")

        can_stop = registry.unregister("test_proc", requester="panel_1")

        assert can_stop is True

    def test_update_state(self):
        """Test updating process state."""
        registry = ProcessRegistry()
        registry.register("test_proc")

        registry.update_state("test_proc", ProcessState.RUNNING, pid=1234)

        proc = registry.get("test_proc")
        assert proc.state == ProcessState.RUNNING
        assert proc.pid == 1234

    def test_get_returns_copy(self):
        """Test that get returns a copy, not the original."""
        registry = ProcessRegistry()
        registry.register("test_proc", requester="panel_1")

        proc = registry.get("test_proc")
        proc.requesters.add("panel_99")  # Modify the copy

        # Original should be unchanged
        assert "panel_99" not in registry.get_requesters("test_proc")

    def test_get_snapshot_returns_immutable(self):
        """Test get_snapshot returns frozen dataclasses."""
        registry = ProcessRegistry()
        registry.register("test_proc", requester="panel_1")
        registry.update_state("test_proc", ProcessState.RUNNING, pid=1234)

        snapshot = registry.get_snapshot()

        assert len(snapshot) == 1
        proc = snapshot[0]
        assert proc.name == "test_proc"
        assert proc.state == ProcessState.RUNNING
        assert proc.pid == 1234
        assert "panel_1" in proc.requesters

        # Should be frozen (immutable)
        with pytest.raises(AttributeError):
            proc.name = "modified"  # type: ignore

    def test_get_active_processes(self):
        """Test getting active processes."""
        registry = ProcessRegistry()
        registry.register("proc_1")
        registry.register("proc_2")
        registry.register("proc_3")

        registry.update_state("proc_1", ProcessState.RUNNING)
        registry.update_state("proc_2", ProcessState.STOPPED)
        registry.update_state("proc_3", ProcessState.RUNNING)

        active = registry.get_active_processes()

        assert "proc_1" in active
        assert "proc_2" not in active
        assert "proc_3" in active

    def test_mark_dead(self):
        """Test marking processes as dead."""
        registry = ProcessRegistry()
        registry.register("proc_1")
        registry.register("proc_2")
        registry.update_state("proc_1", ProcessState.RUNNING)
        registry.update_state("proc_2", ProcessState.RUNNING)

        registry.mark_dead(["proc_1"])

        assert registry.get_state("proc_1") == ProcessState.DEAD
        assert registry.get_state("proc_2") == ProcessState.RUNNING

    def test_remove_requester_from_all(self):
        """Test removing requester from all processes."""
        registry = ProcessRegistry()
        registry.register("proc_1", requester="panel_1")
        registry.register("proc_1", requester="panel_2")
        registry.register("proc_2", requester="panel_1")
        registry.register("proc_3", requester="panel_2")

        orphaned = registry.remove_requester_from_all("panel_1")

        # proc_2 should be orphaned (only had panel_1)
        assert "proc_2" in orphaned
        # proc_1 still has panel_2
        assert "proc_1" not in orphaned

    def test_thread_safety(self):
        """Test thread safety with concurrent access."""
        registry = ProcessRegistry()
        errors = []

        def register_many(start, count):
            try:
                for i in range(count):
                    registry.register(f"proc_{start + i}", requester=f"panel_{start}")
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = [
            threading.Thread(target=register_many, args=(i * 100, 100))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(registry) == 1000
