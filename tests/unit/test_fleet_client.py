"""Tests for fleet client."""

import pytest

from ProcessHub.fleet.fleet_client import FleetClient
from ProcessHub.fleet.orchestrator import FleetOrchestrator
from ProcessHub.fleet.topics import FleetTopics
from ProcessHub.transport.inmemory_transport import InMemoryTransport


class TestFleetClient:
    """Test fleet client status queries and commands."""

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

        # Register two hubs
        for hub_id, hub_name in [("hub-1", "Hub 1"), ("hub-2", "Hub 2")]:
            announce = {"hub_id": hub_id, "hub_name": hub_name, "host": "localhost"}
            transport.send(FleetTopics.HUB_ANNOUNCE.value, announce)

        yield orch
        orch.stop()

    @pytest.fixture
    def client(self, transport, orchestrator):
        return FleetClient(transport=transport, orchestrator=orchestrator)

    def test_get_fleet_status(self, client):
        snapshot = client.get_fleet_status()
        assert snapshot.total_hubs == 2
        assert snapshot.online_hubs == 2

    def test_get_hub_status(self, client):
        hub = client.get_hub_status("hub-1")
        assert hub is not None
        assert hub.hub_id == "hub-1"
        assert hub.status == "online"

    def test_get_hub_status_unknown(self, client):
        hub = client.get_hub_status("nonexistent")
        assert hub is None

    def test_start_processes(self, client, transport):
        transport.clear_messages()

        cmd_id = client.start_processes("hub-1", ["worker_a", "worker_b"])
        assert cmd_id  # non-empty UUID

        commands = transport.get_sent_messages(FleetTopics.FLEET_COMMAND.value)
        assert len(commands) >= 1

        topic, msg, target = commands[0]
        assert msg["hub_id"] == "hub-1"
        assert msg["action"] == "start_process"
        assert msg["params"]["process_list"] == ["worker_a", "worker_b"]

    def test_stop_processes(self, client, transport):
        transport.clear_messages()

        cmd_id = client.stop_processes("hub-1", ["worker_a"], force=True)
        assert cmd_id

        commands = transport.get_sent_messages(FleetTopics.FLEET_COMMAND.value)
        assert len(commands) >= 1

        topic, msg, target = commands[0]
        assert msg["action"] == "stop_process"
        assert msg["params"]["force"] is True

    def test_reset_hub(self, client, transport):
        transport.clear_messages()

        cmd_id = client.reset_hub("hub-1")
        assert cmd_id

        commands = transport.get_sent_messages(FleetTopics.FLEET_COMMAND.value)
        assert len(commands) >= 1

        topic, msg, target = commands[0]
        assert msg["action"] == "reset"

    def test_get_hub_detail(self, client, transport):
        transport.clear_messages()

        cmd_id = client.get_hub_detail("hub-1")
        assert cmd_id

        commands = transport.get_sent_messages(FleetTopics.FLEET_COMMAND.value)
        assert len(commands) >= 1

        topic, msg, target = commands[0]
        assert msg["action"] == "get_status"


class TestFleetClientBatchOperations:
    """Test fleet client batch operations."""

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

        for hub_id in ["hub-1", "hub-2", "hub-3"]:
            announce = {"hub_id": hub_id, "hub_name": hub_id}
            transport.send(FleetTopics.HUB_ANNOUNCE.value, announce)

        yield orch
        orch.stop()

    @pytest.fixture
    def client(self, transport, orchestrator):
        return FleetClient(transport=transport, orchestrator=orchestrator)

    def test_start_on_all_hubs(self, client, transport):
        transport.clear_messages()

        results = client.start_on_all_hubs(["worker_a"])
        assert len(results) == 3
        assert "hub-1" in results
        assert "hub-2" in results
        assert "hub-3" in results

    def test_start_on_all_hubs_skips_offline(self, client, orchestrator, transport):
        # Make hub-3 offline
        with orchestrator.registry._lock:
            orchestrator.registry._hubs["hub-3"].status = "offline"

        transport.clear_messages()

        results = client.start_on_all_hubs(["worker_a"])
        assert len(results) == 2
        assert "hub-3" not in results

    def test_reset_all_hubs(self, client, transport):
        transport.clear_messages()

        results = client.reset_all_hubs()
        assert len(results) == 3


class TestFleetClientCallbacks:
    """Test fleet client event callbacks."""

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
        yield orch
        orch.stop()

    def test_on_hub_online_callback(self, transport, orchestrator):
        events = []
        client = FleetClient(transport=transport, orchestrator=orchestrator)
        client.on_hub_online(lambda data: events.append(data))

        # Trigger hub online
        announce = {"hub_id": "new-hub", "hub_name": "New Hub"}
        transport.send(FleetTopics.HUB_ANNOUNCE.value, announce)

        # The HUB_ONLINE event should have triggered callback
        assert len(events) >= 1

    def test_on_hub_offline_callback(self, transport, orchestrator):
        events = []
        client = FleetClient(transport=transport, orchestrator=orchestrator)
        client.on_hub_offline(lambda data: events.append(data))

        # Simulate hub offline broadcast
        offline_data = {"hub_id": "dead-hub", "reason": "timeout"}
        transport.send(FleetTopics.HUB_OFFLINE.value, offline_data)

        assert len(events) >= 1
        assert events[0].get("hub_id") == "dead-hub"
