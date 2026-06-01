"""Tests for fleet hub registry."""

import time

import pytest

from ProcessHub.fleet.hub_registry import HubRegistry
from ProcessHub.fleet.models import HubAnnounce, HubStatusReport


class TestHubRegistry:
    """Test thread-safe hub registry."""

    @pytest.fixture
    def registry(self):
        return HubRegistry()

    @pytest.fixture
    def sample_announce(self):
        return HubAnnounce(
            hub_id="bench-1",
            hub_name="HIL Bench 1",
            host="10.0.0.5",
            capabilities=["hil", "can"],
        )

    def test_register_new_hub(self, registry, sample_announce):
        is_new = registry.register("bench-1", sample_announce)
        assert is_new is True
        assert registry.hub_count == 1

    def test_register_existing_hub_updates(self, registry, sample_announce):
        registry.register("bench-1", sample_announce)

        updated_announce = HubAnnounce(
            hub_id="bench-1",
            hub_name="Updated Name",
            host="10.0.0.6",
        )
        is_new = registry.register("bench-1", updated_announce)
        assert is_new is False
        assert registry.hub_count == 1

        hub = registry.get_hub("bench-1")
        assert hub is not None
        assert hub.hub_name == "Updated Name"
        assert hub.host == "10.0.0.6"

    def test_deregister_hub(self, registry, sample_announce):
        registry.register("bench-1", sample_announce)
        assert registry.hub_count == 1

        removed = registry.deregister("bench-1")
        assert removed is True
        assert registry.hub_count == 0

    def test_deregister_unknown_hub(self, registry):
        removed = registry.deregister("nonexistent")
        assert removed is False

    def test_get_hub_returns_snapshot(self, registry, sample_announce):
        registry.register("bench-1", sample_announce)
        hub = registry.get_hub("bench-1")

        assert hub is not None
        assert hub.hub_id == "bench-1"
        assert hub.hub_name == "HIL Bench 1"
        assert hub.host == "10.0.0.5"
        assert hub.status == "online"

    def test_get_hub_unknown_returns_none(self, registry):
        hub = registry.get_hub("nonexistent")
        assert hub is None

    def test_get_all_hubs(self, registry):
        registry.register("h1", HubAnnounce(hub_id="h1", hub_name="Hub 1"))
        registry.register("h2", HubAnnounce(hub_id="h2", hub_name="Hub 2"))
        registry.register("h3", HubAnnounce(hub_id="h3", hub_name="Hub 3"))

        hubs = registry.get_all_hubs()
        assert len(hubs) == 3
        hub_ids = {h.hub_id for h in hubs}
        assert hub_ids == {"h1", "h2", "h3"}

    def test_is_registered(self, registry, sample_announce):
        assert registry.is_registered("bench-1") is False
        registry.register("bench-1", sample_announce)
        assert registry.is_registered("bench-1") is True

    def test_update_status(self, registry, sample_announce):
        registry.register("bench-1", sample_announce)

        report = HubStatusReport(
            hub_id="bench-1",
            process_count=3,
            connection_count=2,
            processes=["worker_a", "worker_b", "worker_c"],
            connections=["panel_1", "panel_2"],
            restart_state="IDLE",
        )
        registry.update_status("bench-1", report)

        hub = registry.get_hub("bench-1")
        assert hub is not None
        assert hub.process_count == 3
        assert hub.connection_count == 2
        assert hub.processes == ("worker_a", "worker_b", "worker_c")
        assert hub.connections == ("panel_1", "panel_2")

    def test_update_status_unknown_hub(self, registry):
        """Updating status for unknown hub should not raise."""
        report = HubStatusReport(hub_id="unknown", process_count=1)
        registry.update_status("unknown", report)
        assert registry.hub_count == 0

    def test_update_heartbeat(self, registry, sample_announce):
        registry.register("bench-1", sample_announce)
        time.sleep(0.01)

        registry.update_heartbeat("bench-1")
        hub = registry.get_hub("bench-1")
        assert hub is not None
        assert hub.status == "online"

    def test_update_heartbeat_revives_degraded(self, registry, sample_announce):
        registry.register("bench-1", sample_announce)

        # Force degraded by manipulating last_seen
        with registry._lock:
            registry._hubs["bench-1"].status = "degraded"

        registry.update_heartbeat("bench-1")
        hub = registry.get_hub("bench-1")
        assert hub is not None
        assert hub.status == "online"


class TestHubRegistryHealth:
    """Test health checking with timeout-based state transitions."""

    @pytest.fixture
    def registry(self):
        return HubRegistry()

    def test_healthy_hubs_stay_online(self, registry):
        registry.register("h1", HubAnnounce(hub_id="h1"))
        newly_offline = registry.check_health(timeout_seconds=30.0)
        assert newly_offline == []

        hub = registry.get_hub("h1")
        assert hub is not None
        assert hub.status == "online"

    def test_hub_becomes_degraded(self, registry):
        registry.register("h1", HubAnnounce(hub_id="h1"))

        # Set last_seen to just over half the timeout
        with registry._lock:
            registry._hubs["h1"].last_seen = time.time() - 16.0

        newly_offline = registry.check_health(timeout_seconds=30.0)
        assert newly_offline == []

        hub = registry.get_hub("h1")
        assert hub is not None
        assert hub.status == "degraded"

    def test_hub_becomes_offline(self, registry):
        registry.register("h1", HubAnnounce(hub_id="h1"))

        # Set last_seen to exceed timeout
        with registry._lock:
            registry._hubs["h1"].last_seen = time.time() - 31.0

        newly_offline = registry.check_health(timeout_seconds=30.0)
        assert newly_offline == ["h1"]

        hub = registry.get_hub("h1")
        assert hub is not None
        assert hub.status == "offline"

    def test_already_offline_not_reported_again(self, registry):
        registry.register("h1", HubAnnounce(hub_id="h1"))

        with registry._lock:
            registry._hubs["h1"].last_seen = time.time() - 31.0

        # First check should report
        newly_offline = registry.check_health(timeout_seconds=30.0)
        assert newly_offline == ["h1"]

        # Second check should not report again
        newly_offline = registry.check_health(timeout_seconds=30.0)
        assert newly_offline == []

    def test_offline_hub_recovers(self, registry):
        registry.register("h1", HubAnnounce(hub_id="h1"))

        # Go offline
        with registry._lock:
            registry._hubs["h1"].last_seen = time.time() - 31.0
        registry.check_health(timeout_seconds=30.0)

        # Heartbeat revives
        registry.update_heartbeat("h1")
        hub = registry.get_hub("h1")
        assert hub is not None
        assert hub.status == "online"

    def test_re_register_revives_offline_hub(self, registry):
        registry.register("h1", HubAnnounce(hub_id="h1"))

        # Go offline
        with registry._lock:
            registry._hubs["h1"].last_seen = time.time() - 31.0
            registry._hubs["h1"].status = "offline"

        # Re-register (hub comes back)
        is_new = registry.register("h1", HubAnnounce(hub_id="h1", hub_name="H1 Back"))
        assert is_new is False

        hub = registry.get_hub("h1")
        assert hub is not None
        assert hub.status == "online"


class TestHubRegistrySnapshot:
    """Test fleet state snapshot generation."""

    @pytest.fixture
    def registry(self):
        return HubRegistry()

    def test_empty_snapshot(self, registry):
        snap = registry.get_snapshot()
        assert snap.total_hubs == 0
        assert snap.online_hubs == 0
        assert snap.total_processes == 0
        assert len(snap.hubs) == 0

    def test_snapshot_with_hubs(self, registry):
        registry.register("h1", HubAnnounce(hub_id="h1", hub_name="Hub 1"))
        registry.register("h2", HubAnnounce(hub_id="h2", hub_name="Hub 2"))

        report = HubStatusReport(hub_id="h1", process_count=3)
        registry.update_status("h1", report)

        snap = registry.get_snapshot()
        assert snap.total_hubs == 2
        assert snap.online_hubs == 2
        assert snap.total_processes == 3

    def test_snapshot_is_immutable(self, registry):
        registry.register("h1", HubAnnounce(hub_id="h1"))
        snap = registry.get_snapshot()

        with pytest.raises(AttributeError):
            snap.total_hubs = 99  # type: ignore

    def test_snapshot_counts_online_correctly(self, registry):
        registry.register("h1", HubAnnounce(hub_id="h1"))
        registry.register("h2", HubAnnounce(hub_id="h2"))

        # Make h2 offline
        with registry._lock:
            registry._hubs["h2"].last_seen = time.time() - 31.0
        registry.check_health(timeout_seconds=30.0)

        snap = registry.get_snapshot()
        assert snap.total_hubs == 2
        assert snap.online_hubs == 1

    def test_get_online_hubs(self, registry):
        registry.register("h1", HubAnnounce(hub_id="h1"))
        registry.register("h2", HubAnnounce(hub_id="h2"))

        with registry._lock:
            registry._hubs["h2"].status = "offline"

        online = registry.get_online_hubs()
        assert len(online) == 1
        assert online[0].hub_id == "h1"
