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
# File: orchestrator.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / February 2026.
#
# Description:
#   Fleet orchestrator - central coordinator for multiple ProcessHub instances.
#   Manages hub registry, routes commands, monitors health, and provides
#   fleet-wide state snapshots.
#
# History:
#
# 06.02.2026 / V 1.1.0 / Nguyen Huynh Tri Cuong
# - Initial fleet orchestrator implementation
#
# *******************************************************************************
"""
Fleet orchestrator - central coordinator for multiple ProcessHub instances.

The FleetOrchestrator:
- Discovers hubs via HubAnnounce messages
- Tracks hub health via heartbeat timeouts
- Routes commands from FleetClient to target hubs
- Provides fleet-wide state snapshots
- Broadcasts hub online/offline events

Usage:

    from ProcessHub.fleet import FleetOrchestrator

    orchestrator = FleetOrchestrator(
        transport=fleet_transport,
        health_timeout=30.0,
    )
    orchestrator.start()

    # Main loop
    while True:
        orchestrator.tick()
        time.sleep(5)

    orchestrator.stop()
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from typing import Any, Optional

from dataclasses import asdict

from ..transport.base import TransportBase
from .hub_registry import HubRegistry
from .models import (
    FleetCommand,
    FleetStateSnapshot,
    HubAnnounce,
    HubDeregistered,
    HubRegistered,
    HubSnapshot,
    HubStatusReport,
)
from .topics import FleetTopics

logger = logging.getLogger(__name__)


class FleetOrchestrator:
    """
Fleet orchestrator - central coordinator.

Responsibilities:
- Hub discovery and registration
- Health monitoring via heartbeat timeouts
- Command routing to target hubs
- Fleet-wide state snapshots

The orchestrator is passive: it reacts to hub messages and provides
APIs for FleetClient and FleetWebAPI to use.
    """

    def __init__(
        self,
        transport: TransportBase,
        health_timeout: float = 30.0,
        tick_interval: float = 5.0,
    ):
        """
Initialize the fleet orchestrator.

**Arguments:**

* ``transport``

  / *Condition*: required / *Type*: TransportBase /

  Fleet transport for communication with hub agents.

* ``health_timeout``

  / *Condition*: optional / *Type*: float / *Default*: 30.0 /

  Seconds after which a hub with no heartbeat is marked offline.

* ``tick_interval``

  / *Condition*: optional / *Type*: float / *Default*: 5.0 /

  Recommended interval between tick() calls (for callers).
        """
        self._transport = transport
        self._health_timeout = health_timeout
        self._tick_interval = tick_interval
        self._registry = HubRegistry()
        self._running = False

    @property
    def registry(self) -> HubRegistry:
        """Get the hub registry."""
        return self._registry

    @property
    def is_running(self) -> bool:
        """Check if the orchestrator is running."""
        return self._running

    def start(self) -> None:
        """
Start the fleet orchestrator.

Registers message handlers and starts the transport.
        """
        if self._running:
            return

        logger.info("Starting FleetOrchestrator")

        # Register message handlers
        self._transport.register_handler(
            FleetTopics.HUB_ANNOUNCE.value,
            self._on_hub_announce,
        )
        self._transport.register_handler(
            FleetTopics.HUB_DEREGISTER.value,
            self._on_hub_deregister,
        )
        self._transport.register_handler(
            FleetTopics.HUB_STATUS_REPORT.value,
            self._on_hub_status_report,
        )

        self._running = True
        logger.info("FleetOrchestrator started")

    def stop(self) -> None:
        """
Stop the fleet orchestrator.
        """
        if not self._running:
            return

        logger.info("Stopping FleetOrchestrator")
        self._running = False
        logger.info("FleetOrchestrator stopped")

    def _serialize(self, message: Any) -> dict:
        """Serialize a dataclass message to dict for transport."""
        if hasattr(message, "__dataclass_fields__"):
            return asdict(message)
        return dict(message)

    def tick(self) -> None:
        """
Periodic health check and maintenance.

Should be called periodically (e.g., every tick_interval seconds).
Checks hub health, marks offline hubs, and broadcasts HUB_OFFLINE events.
        """
        if not self._running:
            return

        newly_offline = self._registry.check_health(self._health_timeout)

        for hub_id in newly_offline:
            logger.warning("Broadcasting hub offline: %s", hub_id)
            offline_msg = HubDeregistered(
                hub_id=hub_id,
                reason="heartbeat_timeout",
            )
            try:
                self._transport.send(
                    FleetTopics.HUB_OFFLINE.value, self._serialize(offline_msg)
                )
            except Exception as e:
                logger.warning("Error broadcasting hub offline: %s", e)

    def send_command(
        self,
        hub_id: str,
        action: str,
        params: Optional[dict] = None,
    ) -> str:
        """
Send a command to a specific hub.

**Arguments:**

* ``hub_id``

  / *Condition*: required / *Type*: str /

  Target hub identifier.

* ``action``

  / *Condition*: required / *Type*: str /

  Command action (start_process, stop_process, reset, get_status).

* ``params``

  / *Condition*: optional / *Type*: Optional[dict] / *Default*: None /

  Action parameters.

**Returns:**

  / *Type*: str /

  Command ID for result correlation.

**Raises:**

  ValueError: If hub is unknown or offline.
        """
        hub = self._registry.get_hub(hub_id)
        if hub is None:
            raise ValueError(f"Unknown hub: {hub_id}")
        if hub.status == "offline":
            raise ValueError(f"Hub is offline: {hub_id}")

        command_id = str(uuid.uuid4())
        command = FleetCommand(
            command_id=command_id,
            hub_id=hub_id,
            action=action,
            params=params or {},
        )

        logger.info(
            "Sending command: action=%s, hub=%s, command_id=%s",
            action,
            hub_id,
            command_id,
        )
        self._transport.send(FleetTopics.FLEET_COMMAND.value, self._serialize(command))

        return command_id

    def get_fleet_snapshot(self) -> FleetStateSnapshot:
        """
Get an immutable snapshot of the fleet state.

**Returns:**

  / *Type*: FleetStateSnapshot /

  Current fleet state.
        """
        return self._registry.get_snapshot()

    def get_hub_snapshot(self, hub_id: str) -> Optional[HubSnapshot]:
        """
Get an immutable snapshot of a single hub.

**Arguments:**

* ``hub_id``

  / *Condition*: required / *Type*: str /

  The hub to look up.

**Returns:**

  / *Type*: Optional[HubSnapshot] /

  Hub snapshot if found, None otherwise.
        """
        return self._registry.get_hub(hub_id)

    # ========================================================================
    # Message Handlers
    # ========================================================================

    def _on_hub_announce(self, data: Any) -> None:
        """Handle hub announcement / heartbeat."""
        if not isinstance(data, dict):
            return

        hub_id = data.get("hub_id", "")
        if not hub_id:
            return

        announce = HubAnnounce(
            hub_id=hub_id,
            hub_name=data.get("hub_name", ""),
            host=data.get("host", ""),
            capabilities=data.get("capabilities", []),
            version=data.get("version", ""),
        )

        is_new = self._registry.register(hub_id, announce)

        if is_new:
            # Send registration confirmation
            registered = HubRegistered(
                hub_id=hub_id,
                success=True,
                message="Hub registered successfully",
            )
            self._transport.send(
                FleetTopics.HUB_REGISTERED.value, self._serialize(registered)
            )

            # Broadcast hub online event
            self._transport.send(FleetTopics.HUB_ONLINE.value, data)
            logger.info("New hub discovered: %s (%s)", hub_id, announce.hub_name)
        else:
            # Update heartbeat timestamp
            self._registry.update_heartbeat(hub_id)

    def _on_hub_deregister(self, data: Any) -> None:
        """Handle hub deregistration."""
        if not isinstance(data, dict):
            return

        hub_id = data.get("hub_id", "")
        if not hub_id:
            return

        removed = self._registry.deregister(hub_id)
        if removed:
            logger.info(
                "Hub deregistered: %s (reason: %s)",
                hub_id,
                data.get("reason", "unknown"),
            )

    def _on_hub_status_report(self, data: Any) -> None:
        """Handle hub status report."""
        if not isinstance(data, dict):
            return

        hub_id = data.get("hub_id", "")
        if not hub_id:
            return

        report = HubStatusReport(
            hub_id=hub_id,
            process_count=data.get("process_count", 0),
            connection_count=data.get("connection_count", 0),
            processes=data.get("processes", []),
            connections=data.get("connections", []),
            restart_state=data.get("restart_state", ""),
        )

        self._registry.update_status(hub_id, report)
