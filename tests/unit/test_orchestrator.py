"""Tests for fleet orchestrator."""

import time

import pytest

from ProcessHub.fleet.orchestrator import FleetOrchestrator
from ProcessHub.fleet.topics import FleetTopics
from ProcessHub.transport.inmemory_transport import InMemoryTransport


class TestFleetOrchestrator:
    """Test fleet orchestrator hub discovery and management."""

    @pytest.fixture
    def transport(self):
        transport = InMemoryTransport()
        transport.start()
        yield transport
        transport.clear()

    @pytest.fixture
    def orchestrator(self, transport):
        orch = FleetOrchestrator(
            transport=transport,
            health_timeout=30.0,
        )
        orch.start()
        yield orch
        orch.stop()

    def test_orchestrator_creation(self, orchestrator):
        assert orchestrator.is_running is True
        assert orchestrator.registry.hub_count == 0

    def test_hub_discovery_via_announce(self, orchestrator, transport):
        """Sending HubAnnounce should register the hub."""
        announce = {
            "hub_id": "bench-1",
            "hub_name": "HIL Bench 1",
            "host": "10.0.0.5",
            "capabilities": ["hil"],
            "version": "1.0",
        }
        transport.send(FleetTopics.HUB_ANNOUNCE.value, announce)

        assert orchestrator.registry.hub_count == 1
        hub = orchestrator.registry.get_hub("bench-1")
        assert hub is not None
        assert hub.hub_name == "HIL Bench 1"
        assert hub.status == "online"

    def test_hub_registration_sends_confirmation(self, orchestrator, transport):
        """New hub should receive HUB_REGISTERED message."""
        transport.clear_messages()

        announce = {
            "hub_id": "bench-1",
            "hub_name": "HIL Bench 1",
            "host": "10.0.0.5",
        }
        transport.send(FleetTopics.HUB_ANNOUNCE.value, announce)

        registered_msgs = transport.get_sent_messages(FleetTopics.HUB_REGISTERED.value)
        assert len(registered_msgs) >= 1

        topic, msg, target = registered_msgs[0]
        assert msg["hub_id"] == "bench-1"
        assert msg["success"] is True

    def test_hub_online_event_broadcast(self, orchestrator, transport):
        """New hub should trigger HUB_ONLINE broadcast."""
        transport.clear_messages()

        announce = {
            "hub_id": "bench-1",
            "hub_name": "HIL Bench 1",
        }
        transport.send(FleetTopics.HUB_ANNOUNCE.value, announce)

        online_msgs = transport.get_sent_messages(FleetTopics.HUB_ONLINE.value)
        assert len(online_msgs) >= 1

    def test_duplicate_announce_updates_heartbeat(self, orchestrator, transport):
        """Repeated announces should update heartbeat, not re-register."""
        announce = {
            "hub_id": "bench-1",
            "hub_name": "HIL Bench 1",
        }
        transport.send(FleetTopics.HUB_ANNOUNCE.value, announce)
        assert orchestrator.registry.hub_count == 1

        transport.clear_messages()
        transport.send(FleetTopics.HUB_ANNOUNCE.value, announce)

        # Still only 1 hub
        assert orchestrator.registry.hub_count == 1

        # No new HUB_REGISTERED (only sent for first registration)
        registered_msgs = transport.get_sent_messages(FleetTopics.HUB_REGISTERED.value)
        assert len(registered_msgs) == 0

    def test_hub_deregistration(self, orchestrator, transport):
        announce = {
            "hub_id": "bench-1",
            "hub_name": "HIL Bench 1",
        }
        transport.send(FleetTopics.HUB_ANNOUNCE.value, announce)
        assert orchestrator.registry.hub_count == 1

        deregister = {
            "hub_id": "bench-1",
            "reason": "graceful_shutdown",
        }
        transport.send(FleetTopics.HUB_DEREGISTER.value, deregister)
        assert orchestrator.registry.hub_count == 0

    def test_status_report_updates_hub(self, orchestrator, transport):
        announce = {"hub_id": "bench-1", "hub_name": "HIL Bench 1"}
        transport.send(FleetTopics.HUB_ANNOUNCE.value, announce)

        report = {
            "hub_id": "bench-1",
            "process_count": 3,
            "connection_count": 2,
            "processes": ["worker_a", "worker_b", "worker_c"],
            "connections": ["panel_1", "panel_2"],
            "restart_state": "IDLE",
        }
        transport.send(FleetTopics.HUB_STATUS_REPORT.value, report)

        hub = orchestrator.registry.get_hub("bench-1")
        assert hub is not None
        assert hub.process_count == 3
        assert hub.connection_count == 2

    def test_multiple_hubs(self, orchestrator, transport):
        for i in range(5):
            announce = {
                "hub_id": f"hub-{i}",
                "hub_name": f"Hub {i}",
            }
            transport.send(FleetTopics.HUB_ANNOUNCE.value, announce)

        assert orchestrator.registry.hub_count == 5

        snapshot = orchestrator.get_fleet_snapshot()
        assert snapshot.total_hubs == 5
        assert snapshot.online_hubs == 5


class TestFleetOrchestratorCommands:
    """Test orchestrator command routing."""

    @pytest.fixture
    def transport(self):
        transport = InMemoryTransport()
        transport.start()
        yield transport
        transport.clear()

    @pytest.fixture
    def orchestrator(self, transport):
        orch = FleetOrchestrator(transport=transport, health_timeout=30.0)
        orch.start()

        # Register a hub
        announce = {"hub_id": "bench-1", "hub_name": "HIL Bench 1"}
        transport.send(FleetTopics.HUB_ANNOUNCE.value, announce)

        yield orch
        orch.stop()

    def test_send_command(self, orchestrator, transport):
        transport.clear_messages()

        command_id = orchestrator.send_command(
            hub_id="bench-1",
            action="start_process",
            params={"process_list": ["worker_a"]},
        )

        assert command_id  # non-empty UUID string

        commands = transport.get_sent_messages(FleetTopics.FLEET_COMMAND.value)
        assert len(commands) >= 1

        topic, msg, target = commands[0]
        assert msg["command_id"] == command_id
        assert msg["hub_id"] == "bench-1"
        assert msg["action"] == "start_process"

    def test_send_command_unknown_hub_raises(self, orchestrator):
        with pytest.raises(ValueError, match="Unknown hub"):
            orchestrator.send_command(
                hub_id="nonexistent",
                action="get_status",
            )

    def test_send_command_offline_hub_raises(self, orchestrator):
        # Make hub offline
        with orchestrator.registry._lock:
            orchestrator.registry._hubs["bench-1"].status = "offline"

        with pytest.raises(ValueError, match="Hub is offline"):
            orchestrator.send_command(
                hub_id="bench-1",
                action="get_status",
            )

    def test_get_fleet_snapshot(self, orchestrator):
        snapshot = orchestrator.get_fleet_snapshot()
        assert snapshot.total_hubs == 1
        assert snapshot.online_hubs == 1

    def test_get_hub_snapshot(self, orchestrator):
        hub = orchestrator.get_hub_snapshot("bench-1")
        assert hub is not None
        assert hub.hub_id == "bench-1"

    def test_get_hub_snapshot_unknown(self, orchestrator):
        hub = orchestrator.get_hub_snapshot("nonexistent")
        assert hub is None


class TestFleetOrchestratorHealthCheck:
    """Test orchestrator health check tick."""

    @pytest.fixture
    def transport(self):
        transport = InMemoryTransport()
        transport.start()
        yield transport
        transport.clear()

    @pytest.fixture
    def orchestrator(self, transport):
        orch = FleetOrchestrator(transport=transport, health_timeout=10.0)
        orch.start()
        yield orch
        orch.stop()

    def test_tick_detects_offline_hub(self, orchestrator, transport):
        announce = {"hub_id": "bench-1", "hub_name": "HIL Bench 1"}
        transport.send(FleetTopics.HUB_ANNOUNCE.value, announce)

        # Make hub appear timed out
        with orchestrator.registry._lock:
            orchestrator.registry._hubs["bench-1"].last_seen = time.time() - 11.0

        transport.clear_messages()
        orchestrator.tick()

        # Should broadcast HUB_OFFLINE
        offline_msgs = transport.get_sent_messages(FleetTopics.HUB_OFFLINE.value)
        assert len(offline_msgs) >= 1

        topic, msg, target = offline_msgs[0]
        assert msg["hub_id"] == "bench-1"

    def test_tick_does_nothing_for_healthy_hubs(self, orchestrator, transport):
        announce = {"hub_id": "bench-1", "hub_name": "HIL Bench 1"}
        transport.send(FleetTopics.HUB_ANNOUNCE.value, announce)

        transport.clear_messages()
        orchestrator.tick()

        # No HUB_OFFLINE messages
        offline_msgs = transport.get_sent_messages(FleetTopics.HUB_OFFLINE.value)
        assert len(offline_msgs) == 0

    def test_tick_when_stopped_is_noop(self, transport):
        orch = FleetOrchestrator(transport=transport, health_timeout=10.0)
        # Don't start - tick should be a no-op
        orch.tick()
