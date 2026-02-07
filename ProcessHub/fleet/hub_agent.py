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
# File: hub_agent.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / February 2026.
#
# Description:
#   Hub agent - lightweight sidecar alongside each ProcessHubServer.
#   Sends heartbeats and status reports to the fleet orchestrator,
#   and handles fleet commands by delegating to the local server.
#
# History:
#
# 06.02.2026 / V 1.1.0 / Nguyen Huynh Tri Cuong
# - Initial fleet orchestrator implementation
#
# *******************************************************************************
"""
Hub agent - lightweight sidecar alongside each ProcessHubServer.

The HubAgent runs alongside a local ProcessHubServer and provides:
- Periodic heartbeat (HubAnnounce) for liveness detection
- Periodic status reports (HubStatusReport) with server state
- Fleet command handler (start/stop/reset via local server APIs)

The agent uses only the server's public API - no core modifications needed.
"""

from __future__ import annotations

import logging
import platform
import threading
import time
from dataclasses import asdict
from typing import Any, Optional

from ..core.models import ProcessStartRequest, ProcessStopRequest
from ..transport.base import TransportBase
from .models import (
    FleetCommand,
    FleetCommandResult,
    HubAnnounce,
    HubDeregistered,
    HubStatusReport,
)
from .topics import FleetTopics

logger = logging.getLogger(__name__)


class HubAgent:
    """
Hub agent sidecar for ProcessHubServer.

Sits alongside a local ProcessHubServer and bridges it to the fleet:
- Announces hub to orchestrator via periodic heartbeats
- Reports server status periodically
- Handles fleet commands by delegating to local server

Usage:

    from ProcessHub.fleet import HubAgent

    agent = HubAgent(
        server=my_server,
        transport=fleet_transport,
        hub_id="bench-1",
        hub_name="HIL Bench 1",
    )
    agent.start()
    # ... server runs ...
    agent.stop()
    """

    def __init__(
        self,
        server: Any,
        transport: TransportBase,
        hub_id: str,
        hub_name: str = "",
        host: str = "",
        heartbeat_interval: float = 5.0,
        status_interval: float = 10.0,
        capabilities: Optional[list[str]] = None,
    ):
        """
Initialize the hub agent.

**Arguments:**

* ``server``

  / *Condition*: required / *Type*: ProcessHubServer /

  The local ProcessHubServer this agent is attached to.

* ``transport``

  / *Condition*: required / *Type*: TransportBase /

  Fleet transport for communication with orchestrator.

* ``hub_id``

  / *Condition*: required / *Type*: str /

  Unique identifier for this hub in the fleet.

* ``hub_name``

  / *Condition*: optional / *Type*: str / *Default*: "" /

  Human-readable name for this hub.

* ``host``

  / *Condition*: optional / *Type*: str / *Default*: "" /

  Hostname. Auto-detected if empty.

* ``heartbeat_interval``

  / *Condition*: optional / *Type*: float / *Default*: 5.0 /

  Seconds between heartbeat messages.

* ``status_interval``

  / *Condition*: optional / *Type*: float / *Default*: 10.0 /

  Seconds between status report messages.

* ``capabilities``

  / *Condition*: optional / *Type*: Optional[list[str]] / *Default*: None /

  List of capability tags for this hub.
        """
        self._server = server
        self._transport = transport
        self._hub_id = hub_id
        self._hub_name = hub_name or hub_id
        self._host = host or platform.node()
        self._heartbeat_interval = heartbeat_interval
        self._status_interval = status_interval
        self._capabilities = capabilities or []
        self._running = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._status_thread: Optional[threading.Thread] = None

    @property
    def hub_id(self) -> str:
        """Get the hub ID."""
        return self._hub_id

    @property
    def hub_name(self) -> str:
        """Get the hub name."""
        return self._hub_name

    @property
    def is_running(self) -> bool:
        """Check if the agent is running."""
        return self._running

    def start(self) -> None:
        """
Start the hub agent.

Registers fleet command handler, sends initial announcement,
and starts background heartbeat and status report loops.
        """
        if self._running:
            return

        logger.info("Starting HubAgent: %s (%s)", self._hub_id, self._hub_name)

        # Register command handler
        self._transport.register_handler(
            FleetTopics.FLEET_COMMAND.value,
            self._on_fleet_command,
        )

        # Send initial announcement
        self._send_announce()

        # Start background loops
        self._running = True

        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"fleet-heartbeat-{self._hub_id}",
            daemon=True,
        )
        self._heartbeat_thread.start()

        self._status_thread = threading.Thread(
            target=self._status_loop,
            name=f"fleet-status-{self._hub_id}",
            daemon=True,
        )
        self._status_thread.start()

        logger.info("HubAgent started: %s", self._hub_id)

    def stop(self) -> None:
        """
Stop the hub agent.

Sends deregistration message and stops background loops.
        """
        if not self._running:
            return

        logger.info("Stopping HubAgent: %s", self._hub_id)
        self._running = False

        # Send deregistration
        try:
            deregister = HubDeregistered(
                hub_id=self._hub_id,
                reason="graceful_shutdown",
            )
            self._transport.send(
                FleetTopics.HUB_DEREGISTER.value,
                self._serialize(deregister),
            )
        except Exception as e:
            logger.warning("Error sending deregister: %s", e)

        # Wait for threads to finish
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2.0)
        if self._status_thread and self._status_thread.is_alive():
            self._status_thread.join(timeout=2.0)

        logger.info("HubAgent stopped: %s", self._hub_id)

    # ========================================================================
    # Background Loops
    # ========================================================================

    def _heartbeat_loop(self) -> None:
        """Background loop sending periodic heartbeats."""
        while self._running:
            try:
                self._send_announce()
            except Exception as e:
                logger.warning("Error sending heartbeat: %s", e)
            # Sleep in small increments for responsive shutdown
            self._interruptible_sleep(self._heartbeat_interval)

    def _status_loop(self) -> None:
        """Background loop sending periodic status reports."""
        while self._running:
            try:
                self._send_status_report()
            except Exception as e:
                logger.warning("Error sending status report: %s", e)
            self._interruptible_sleep(self._status_interval)

    def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep that can be interrupted by stop()."""
        end_time = time.time() + seconds
        while self._running and time.time() < end_time:
            time.sleep(min(0.5, end_time - time.time()))

    # ========================================================================
    # Message Sending
    # ========================================================================

    def _serialize(self, message: Any) -> dict:
        """Serialize a dataclass message to dict for transport."""
        if hasattr(message, "__dataclass_fields__"):
            return asdict(message)
        return dict(message)

    def _send_announce(self) -> None:
        """Send a HubAnnounce message to the orchestrator."""
        announce = HubAnnounce(
            hub_id=self._hub_id,
            hub_name=self._hub_name,
            host=self._host,
            capabilities=self._capabilities,
        )
        self._transport.send(FleetTopics.HUB_ANNOUNCE.value, self._serialize(announce))

    def _send_status_report(self) -> None:
        """Send a HubStatusReport with current server state."""
        try:
            snapshot = self._server.core.get_state_snapshot()
            report = HubStatusReport(
                hub_id=self._hub_id,
                process_count=len(snapshot.processes),
                connection_count=len(snapshot.connections),
                processes=[p.name for p in snapshot.processes],
                connections=[c.panel_id for c in snapshot.connections],
                restart_state=snapshot.restart_state,
            )
            self._transport.send(FleetTopics.HUB_STATUS_REPORT.value, self._serialize(report))
        except Exception as e:
            logger.warning("Error collecting status: %s", e)

    # ========================================================================
    # Command Handler
    # ========================================================================

    def _on_fleet_command(self, data: Any) -> None:
        """
Handle incoming fleet commands.

Only processes commands addressed to this hub.
        """
        if isinstance(data, dict):
            hub_id = data.get("hub_id", "")
            command_id = data.get("command_id", "")
            action = data.get("action", "")
            params = data.get("params", {})
        else:
            return

        # Ignore commands for other hubs
        if hub_id != self._hub_id:
            return

        logger.info(
            "Fleet command received: action=%s, command_id=%s",
            action,
            command_id,
        )

        try:
            if action == "start_process":
                result = self._handle_start_process(params)
            elif action == "stop_process":
                result = self._handle_stop_process(params)
            elif action == "reset":
                result = self._handle_reset()
            elif action == "get_status":
                result = self._handle_get_status()
            else:
                result = FleetCommandResult(
                    command_id=command_id,
                    hub_id=self._hub_id,
                    success=False,
                    message=f"Unknown action: {action}",
                )

            result.command_id = command_id
            result.hub_id = self._hub_id

            self._transport.send(
                FleetTopics.FLEET_COMMAND_RESULT.value, self._serialize(result)
            )

        except Exception as e:
            logger.exception("Error handling fleet command: %s", action)
            error_result = FleetCommandResult(
                command_id=command_id,
                hub_id=self._hub_id,
                success=False,
                message=str(e),
            )
            self._transport.send(
                FleetTopics.FLEET_COMMAND_RESULT.value, self._serialize(error_result)
            )

    def _handle_start_process(self, params: dict) -> FleetCommandResult:
        """Handle start_process command."""
        process_list = params.get("process_list", [])
        panel_id = params.get("panel_id", "fleet")

        req = ProcessStartRequest(
            panel_id=panel_id,
            process_list=process_list,
        )
        messages = self._server.core.handle_start_request(req)

        # Check result from outgoing messages
        success = True
        failed = []
        for msg in messages:
            payload = msg.payload
            if hasattr(payload, "success") and not payload.success:
                success = False
            if hasattr(payload, "failed_processes"):
                failed.extend(payload.failed_processes)

        return FleetCommandResult(
            success=success,
            message=f"Started {len(process_list)} process(es)" if success else f"Failed: {failed}",
            data={"process_list": process_list, "failed": failed},
        )

    def _handle_stop_process(self, params: dict) -> FleetCommandResult:
        """Handle stop_process command."""
        process_list = params.get("process_list", [])
        panel_id = params.get("panel_id", "fleet")
        force = params.get("force", False)

        req = ProcessStopRequest(
            panel_id=panel_id,
            process_list=process_list,
            force=force,
        )
        messages = self._server.core.handle_stop_request(req)

        success = True
        for msg in messages:
            payload = msg.payload
            if hasattr(payload, "success") and not payload.success:
                success = False

        return FleetCommandResult(
            success=success,
            message=f"Stopped {len(process_list)} process(es)" if success else "Stop failed",
            data={"process_list": process_list},
        )

    def _handle_reset(self) -> FleetCommandResult:
        """Handle reset command."""
        success, message = self._server.reset()
        return FleetCommandResult(
            success=success,
            message=message,
        )

    def _handle_get_status(self) -> FleetCommandResult:
        """Handle get_status command."""
        snapshot = self._server.core.get_state_snapshot()
        return FleetCommandResult(
            success=True,
            message="Status retrieved",
            data={
                "process_count": len(snapshot.processes),
                "connection_count": len(snapshot.connections),
                "processes": [p.name for p in snapshot.processes],
                "connections": [c.panel_id for c in snapshot.connections],
                "restart_state": snapshot.restart_state,
            },
        )
