"""Tests for fleet hub agent."""

import time

import pytest

from ProcessHub.fleet.hub_agent import HubAgent
from ProcessHub.fleet.topics import FleetTopics
from ProcessHub.process.executor import MockExecutor
from ProcessHub.runtime.server import ProcessHubServer
from ProcessHub.transport.inmemory_transport import InMemoryTransport
from ProcessHub.ui.null_view import NullView


class TestHubAgent:
    """Test hub agent sidecar functionality."""

    @pytest.fixture
    def local_transport(self):
        transport = InMemoryTransport()
        yield transport
        transport.clear()

    @pytest.fixture
    def fleet_transport(self):
        transport = InMemoryTransport()
        yield transport
        transport.clear()

    @pytest.fixture
    def executor(self):
        return MockExecutor()

    @pytest.fixture
    def server(self, local_transport, executor):
        server = ProcessHubServer(
            transport=local_transport,
            executor=executor,
            view=NullView(),
            process_config={
                "worker_a": {"script": "python", "args": ["-c", "pass"]},
                "worker_b": {"script": "python", "args": ["-c", "pass"]},
            },
        )
        server.start()
        yield server
        server.stop()

    @pytest.fixture
    def agent(self, server, fleet_transport):
        agent = HubAgent(
            server=server,
            transport=fleet_transport,
            hub_id="test-hub",
            hub_name="Test Hub",
            heartbeat_interval=60.0,   # Long interval to prevent background sends
            status_interval=60.0,
        )
        yield agent
        if agent.is_running:
            agent.stop()

    def test_agent_creation(self, agent):
        assert agent.hub_id == "test-hub"
        assert agent.hub_name == "Test Hub"
        assert agent.is_running is False

    def test_agent_start_sends_announce(self, agent, fleet_transport):
        agent.start()
        assert agent.is_running is True

        # Should have sent initial HubAnnounce
        messages = fleet_transport.get_sent_messages(FleetTopics.HUB_ANNOUNCE.value)
        assert len(messages) >= 1

        topic, msg, target = messages[0]
        assert msg["hub_id"] == "test-hub"
        assert msg["hub_name"] == "Test Hub"

    def test_agent_stop_sends_deregister(self, agent, fleet_transport):
        agent.start()
        fleet_transport.clear_messages()

        agent.stop()
        assert agent.is_running is False

        messages = fleet_transport.get_sent_messages(FleetTopics.HUB_DEREGISTER.value)
        assert len(messages) == 1
        topic, msg, target = messages[0]
        assert msg["hub_id"] == "test-hub"
        assert msg["reason"] == "graceful_shutdown"

    def test_agent_registers_command_handler(self, agent, fleet_transport):
        agent.start()

        # Verify handler was registered
        handlers = fleet_transport._handlers.get(FleetTopics.FLEET_COMMAND.value, [])
        assert len(handlers) > 0


class TestHubAgentCommands:
    """Test hub agent command handling."""

    @pytest.fixture
    def local_transport(self):
        transport = InMemoryTransport()
        yield transport
        transport.clear()

    @pytest.fixture
    def fleet_transport(self):
        transport = InMemoryTransport()
        yield transport
        transport.clear()

    @pytest.fixture
    def executor(self):
        return MockExecutor()

    @pytest.fixture
    def server(self, local_transport, executor):
        server = ProcessHubServer(
            transport=local_transport,
            executor=executor,
            view=NullView(),
            process_config={
                "worker_a": {"script": "python", "args": ["-c", "pass"]},
                "worker_b": {"script": "python", "args": ["-c", "pass"]},
            },
        )
        server.start()
        yield server
        server.stop()

    @pytest.fixture
    def agent(self, server, fleet_transport):
        agent = HubAgent(
            server=server,
            transport=fleet_transport,
            hub_id="test-hub",
            hub_name="Test Hub",
            heartbeat_interval=60.0,
            status_interval=60.0,
        )
        agent.start()
        yield agent
        if agent.is_running:
            agent.stop()

    def test_start_process_command(self, agent, fleet_transport, server):
        """Test that start_process command starts processes via server core."""
        # First register a panel so start_request succeeds
        from ProcessHub.core.models import RegisterConnectionRequest
        server.core.handle_register(
            RegisterConnectionRequest(panel_id="fleet", session_id="fleet")
        )

        fleet_transport.clear_messages()

        # Send start command
        command = {
            "command_id": "cmd-001",
            "hub_id": "test-hub",
            "action": "start_process",
            "params": {"process_list": ["worker_a"], "panel_id": "fleet"},
        }
        agent._on_fleet_command(command)

        # Check result was sent
        results = fleet_transport.get_sent_messages(FleetTopics.FLEET_COMMAND_RESULT.value)
        assert len(results) >= 1

        topic, msg, target = results[0]
        assert msg["command_id"] == "cmd-001"
        assert msg["hub_id"] == "test-hub"
        assert msg["success"] is True

    def test_stop_process_command(self, agent, fleet_transport, server):
        """Test that stop_process command stops processes via server core."""
        from ProcessHub.core.models import RegisterConnectionRequest
        server.core.handle_register(
            RegisterConnectionRequest(panel_id="fleet", session_id="fleet")
        )

        fleet_transport.clear_messages()

        command = {
            "command_id": "cmd-002",
            "hub_id": "test-hub",
            "action": "stop_process",
            "params": {"process_list": ["worker_a"], "panel_id": "fleet"},
        }
        agent._on_fleet_command(command)

        results = fleet_transport.get_sent_messages(FleetTopics.FLEET_COMMAND_RESULT.value)
        assert len(results) >= 1

        topic, msg, target = results[0]
        assert msg["command_id"] == "cmd-002"

    def test_reset_command(self, agent, fleet_transport):
        fleet_transport.clear_messages()

        command = {
            "command_id": "cmd-003",
            "hub_id": "test-hub",
            "action": "reset",
            "params": {},
        }
        agent._on_fleet_command(command)

        results = fleet_transport.get_sent_messages(FleetTopics.FLEET_COMMAND_RESULT.value)
        assert len(results) >= 1

        topic, msg, target = results[0]
        assert msg["command_id"] == "cmd-003"
        assert msg["success"] is True

    def test_get_status_command(self, agent, fleet_transport):
        fleet_transport.clear_messages()

        command = {
            "command_id": "cmd-004",
            "hub_id": "test-hub",
            "action": "get_status",
            "params": {},
        }
        agent._on_fleet_command(command)

        results = fleet_transport.get_sent_messages(FleetTopics.FLEET_COMMAND_RESULT.value)
        assert len(results) >= 1

        topic, msg, target = results[0]
        assert msg["command_id"] == "cmd-004"
        assert msg["success"] is True
        assert "process_count" in msg["data"]
        assert "connection_count" in msg["data"]

    def test_unknown_action_returns_error(self, agent, fleet_transport):
        fleet_transport.clear_messages()

        command = {
            "command_id": "cmd-005",
            "hub_id": "test-hub",
            "action": "nonexistent_action",
            "params": {},
        }
        agent._on_fleet_command(command)

        results = fleet_transport.get_sent_messages(FleetTopics.FLEET_COMMAND_RESULT.value)
        assert len(results) >= 1

        topic, msg, target = results[0]
        assert msg["success"] is False
        assert "Unknown action" in msg["message"]

    def test_command_for_other_hub_is_ignored(self, agent, fleet_transport):
        fleet_transport.clear_messages()

        command = {
            "command_id": "cmd-006",
            "hub_id": "other-hub",
            "action": "get_status",
            "params": {},
        }
        agent._on_fleet_command(command)

        # Should not send any result (command was for another hub)
        results = fleet_transport.get_sent_messages(FleetTopics.FLEET_COMMAND_RESULT.value)
        assert len(results) == 0
