"""Tests for fleet protocol messages and frozen snapshots."""

import time

import pytest

from ProcessHub.fleet.models import (
    FleetCommand,
    FleetCommandResult,
    FleetStateSnapshot,
    FleetStatusRequest,
    FleetStatusResponse,
    HubAnnounce,
    HubDeregistered,
    HubRegistered,
    HubSnapshot,
    HubStatusReport,
)
from ProcessHub.core.models import PROTOCOL_VERSION


class TestFleetMessages:
    """Test fleet protocol message creation and defaults."""

    def test_hub_announce_defaults(self):
        msg = HubAnnounce()
        assert msg.hub_id == ""
        assert msg.hub_name == ""
        assert msg.host == ""
        assert msg.capabilities == []
        assert msg.version == PROTOCOL_VERSION
        assert msg.timestamp > 0
        assert msg.request_id is None

    def test_hub_announce_with_values(self):
        msg = HubAnnounce(
            hub_id="bench-1",
            hub_name="HIL Bench 1",
            host="10.0.0.5",
            capabilities=["hil", "can"],
        )
        assert msg.hub_id == "bench-1"
        assert msg.hub_name == "HIL Bench 1"
        assert msg.host == "10.0.0.5"
        assert msg.capabilities == ["hil", "can"]

    def test_hub_registered_defaults(self):
        msg = HubRegistered()
        assert msg.hub_id == ""
        assert msg.success is True
        assert msg.message == ""
        assert msg.fleet_id == ""

    def test_hub_deregistered(self):
        msg = HubDeregistered(hub_id="bench-1", reason="graceful_shutdown")
        assert msg.hub_id == "bench-1"
        assert msg.reason == "graceful_shutdown"

    def test_hub_status_report(self):
        msg = HubStatusReport(
            hub_id="bench-1",
            process_count=3,
            connection_count=2,
            processes=["worker_a", "worker_b", "worker_c"],
            connections=["panel_1", "panel_2"],
            restart_state="IDLE",
        )
        assert msg.hub_id == "bench-1"
        assert msg.process_count == 3
        assert msg.connection_count == 2
        assert len(msg.processes) == 3
        assert len(msg.connections) == 2
        assert msg.restart_state == "IDLE"

    def test_fleet_command(self):
        msg = FleetCommand(
            command_id="cmd-123",
            hub_id="bench-1",
            action="start_process",
            params={"process_list": ["worker_a"]},
        )
        assert msg.command_id == "cmd-123"
        assert msg.hub_id == "bench-1"
        assert msg.action == "start_process"
        assert msg.params == {"process_list": ["worker_a"]}

    def test_fleet_command_result(self):
        msg = FleetCommandResult(
            command_id="cmd-123",
            hub_id="bench-1",
            success=True,
            message="Started 1 process(es)",
            data={"process_list": ["worker_a"]},
        )
        assert msg.command_id == "cmd-123"
        assert msg.success is True
        assert msg.data == {"process_list": ["worker_a"]}

    def test_fleet_status_request(self):
        msg = FleetStatusRequest(requester_id="ci-runner")
        assert msg.requester_id == "ci-runner"

    def test_fleet_status_response(self):
        msg = FleetStatusResponse(
            total_hubs=3,
            online_hubs=2,
            total_processes=7,
            hubs=[{"hub_id": "h1"}, {"hub_id": "h2"}],
        )
        assert msg.total_hubs == 3
        assert msg.online_hubs == 2
        assert len(msg.hubs) == 2

    def test_messages_inherit_from_message_base(self):
        """All fleet messages should have version, timestamp, request_id."""
        messages = [
            HubAnnounce(),
            HubRegistered(),
            HubDeregistered(),
            HubStatusReport(),
            FleetCommand(),
            FleetCommandResult(),
            FleetStatusRequest(),
            FleetStatusResponse(),
        ]
        for msg in messages:
            assert msg.version == PROTOCOL_VERSION
            assert isinstance(msg.timestamp, float)
            assert msg.request_id is None


class TestFleetSnapshots:
    """Test immutable fleet state snapshots."""

    def test_hub_snapshot_immutable(self):
        snap = HubSnapshot(
            hub_id="bench-1",
            hub_name="HIL Bench 1",
            host="10.0.0.5",
            status="online",
            process_count=2,
            connection_count=1,
            processes=("worker_a", "worker_b"),
            connections=("panel_1",),
            configured_processes=("worker_a", "worker_b"),
            last_seen=time.time(),
        )
        assert snap.hub_id == "bench-1"
        assert snap.status == "online"
        assert len(snap.processes) == 2

        with pytest.raises(AttributeError):
            snap.status = "offline"  # type: ignore

    def test_hub_snapshot_uses_tuples(self):
        snap = HubSnapshot(
            hub_id="h1",
            hub_name="H1",
            host="localhost",
            status="online",
            process_count=0,
            connection_count=0,
            processes=(),
            connections=(),
            configured_processes=(),
            last_seen=0.0,
        )
        assert isinstance(snap.processes, tuple)
        assert isinstance(snap.connections, tuple)

    def test_fleet_state_snapshot_immutable(self):
        hub = HubSnapshot(
            hub_id="h1",
            hub_name="H1",
            host="localhost",
            status="online",
            process_count=2,
            connection_count=1,
            processes=("p1", "p2"),
            connections=("c1",),
            configured_processes=("p1", "p2"),
            last_seen=time.time(),
        )
        snap = FleetStateSnapshot(
            hubs=(hub,),
            total_hubs=1,
            online_hubs=1,
            total_processes=2,
        )
        assert snap.total_hubs == 1
        assert snap.online_hubs == 1
        assert snap.total_processes == 2
        assert len(snap.hubs) == 1
        assert snap.hubs[0].hub_id == "h1"

        with pytest.raises(AttributeError):
            snap.total_hubs = 5  # type: ignore

    def test_fleet_state_snapshot_empty(self):
        snap = FleetStateSnapshot(
            hubs=(),
            total_hubs=0,
            online_hubs=0,
            total_processes=0,
        )
        assert snap.total_hubs == 0
        assert len(snap.hubs) == 0
