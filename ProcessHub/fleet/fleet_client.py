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
# File: fleet_client.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / February 2026.
#
# Description:
#   Fleet client - external API for CI/CD pipelines, CLI tools, and scripts.
#   Provides high-level methods for fleet status queries, process control,
#   and batch operations.
#
# History:
#
# 06.02.2026 / V 1.1.0 / Nguyen Huynh Tri Cuong
# - Initial fleet orchestrator implementation
#
# *******************************************************************************
"""
Fleet client - external API for CI/CD pipelines and CLI tools.

Provides high-level methods to:
- Query fleet and hub status
- Start/stop processes on specific hubs
- Reset hubs
- Batch operations across multiple hubs
- Event callbacks for hub online/offline events

Usage:

    from ProcessHub.fleet import FleetClient

    client = FleetClient(transport=fleet_transport, orchestrator=orchestrator)

    # Check fleet health
    snapshot = client.get_fleet_status()
    assert snapshot.online_hubs >= 2

    # Start processes on a specific hub
    client.start_processes("bench-1", ["ecu_simulator", "can_bridge"])

    # Stop all processes on all hubs
    client.stop_all_processes()
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from ..transport.base import TransportBase
from .models import FleetStateSnapshot, HubSnapshot
from .orchestrator import FleetOrchestrator
from .topics import FleetTopics

logger = logging.getLogger(__name__)


class FleetClient:
    """
Fleet client for external systems.

Wraps FleetOrchestrator to provide a clean API for CI/CD, CLI, and scripts.
Supports event callbacks for hub lifecycle events.
    """

    def __init__(
        self,
        transport: TransportBase,
        orchestrator: Optional[FleetOrchestrator] = None,
    ):
        """
Initialize the fleet client.

**Arguments:**

* ``transport``

  / *Condition*: required / *Type*: TransportBase /

  Fleet transport (same as orchestrator uses).

* ``orchestrator``

  / *Condition*: optional / *Type*: Optional[FleetOrchestrator] / *Default*: None /

  Direct reference to orchestrator (for in-process usage).
  If None, the client communicates purely via transport messages.
        """
        self._transport = transport
        self._orchestrator = orchestrator
        self._on_hub_online_callbacks: list[Callable] = []
        self._on_hub_offline_callbacks: list[Callable] = []

        # Register event handlers
        self._transport.register_handler(
            FleetTopics.HUB_ONLINE.value,
            self._handle_hub_online,
        )
        self._transport.register_handler(
            FleetTopics.HUB_OFFLINE.value,
            self._handle_hub_offline,
        )

    # ========================================================================
    # Status Queries
    # ========================================================================

    def get_fleet_status(self) -> FleetStateSnapshot:
        """
Get current fleet-wide status.

**Returns:**

  / *Type*: FleetStateSnapshot /

  Immutable snapshot of the entire fleet.
        """
        if self._orchestrator is not None:
            return self._orchestrator.get_fleet_snapshot()
        raise RuntimeError(
            "FleetClient requires orchestrator reference for status queries"
        )

    def get_hub_status(self, hub_id: str) -> Optional[HubSnapshot]:
        """
Get status of a specific hub.

**Arguments:**

* ``hub_id``

  / *Condition*: required / *Type*: str /

  The hub to query.

**Returns:**

  / *Type*: Optional[HubSnapshot] /

  Hub snapshot if found, None otherwise.
        """
        if self._orchestrator is not None:
            return self._orchestrator.get_hub_snapshot(hub_id)
        raise RuntimeError(
            "FleetClient requires orchestrator reference for status queries"
        )

    # ========================================================================
    # Single-Hub Commands
    # ========================================================================

    def start_processes(
        self,
        hub_id: str,
        process_list: list[str],
        panel_id: str = "fleet",
    ) -> str:
        """
Start processes on a specific hub.

**Arguments:**

* ``hub_id``

  / *Condition*: required / *Type*: str /

  Target hub identifier.

* ``process_list``

  / *Condition*: required / *Type*: list[str] /

  Process names to start.

* ``panel_id``

  / *Condition*: optional / *Type*: str / *Default*: "fleet" /

  Panel ID for process ownership.

**Returns:**

  / *Type*: str /

  Command ID for result tracking.
        """
        if self._orchestrator is None:
            raise RuntimeError("FleetClient requires orchestrator reference")

        return self._orchestrator.send_command(
            hub_id=hub_id,
            action="start_process",
            params={"process_list": process_list, "panel_id": panel_id},
        )

    def stop_processes(
        self,
        hub_id: str,
        process_list: list[str],
        panel_id: str = "fleet",
        force: bool = False,
    ) -> str:
        """
Stop processes on a specific hub.

**Arguments:**

* ``hub_id``

  / *Condition*: required / *Type*: str /

  Target hub identifier.

* ``process_list``

  / *Condition*: required / *Type*: list[str] /

  Process names to stop.

* ``panel_id``

  / *Condition*: optional / *Type*: str / *Default*: "fleet" /

  Panel ID for process ownership.

* ``force``

  / *Condition*: optional / *Type*: bool / *Default*: False /

  Force stop (kill) processes.

**Returns:**

  / *Type*: str /

  Command ID for result tracking.
        """
        if self._orchestrator is None:
            raise RuntimeError("FleetClient requires orchestrator reference")

        return self._orchestrator.send_command(
            hub_id=hub_id,
            action="stop_process",
            params={
                "process_list": process_list,
                "panel_id": panel_id,
                "force": force,
            },
        )

    def reset_hub(self, hub_id: str) -> str:
        """
Reset a specific hub (clear all state).

**Arguments:**

* ``hub_id``

  / *Condition*: required / *Type*: str /

  Target hub identifier.

**Returns:**

  / *Type*: str /

  Command ID for result tracking.
        """
        if self._orchestrator is None:
            raise RuntimeError("FleetClient requires orchestrator reference")

        return self._orchestrator.send_command(
            hub_id=hub_id,
            action="reset",
        )

    def get_hub_detail(self, hub_id: str) -> str:
        """
Request detailed status from a specific hub.

**Arguments:**

* ``hub_id``

  / *Condition*: required / *Type*: str /

  Target hub identifier.

**Returns:**

  / *Type*: str /

  Command ID for result tracking.
        """
        if self._orchestrator is None:
            raise RuntimeError("FleetClient requires orchestrator reference")

        return self._orchestrator.send_command(
            hub_id=hub_id,
            action="get_status",
        )

    # ========================================================================
    # Batch Operations
    # ========================================================================

    def start_on_all_hubs(
        self,
        process_list: list[str],
        panel_id: str = "fleet",
    ) -> dict[str, str]:
        """
Start processes on all online hubs.

**Arguments:**

* ``process_list``

  / *Condition*: required / *Type*: list[str] /

  Process names to start on each hub.

* ``panel_id``

  / *Condition*: optional / *Type*: str / *Default*: "fleet" /

  Panel ID for process ownership.

**Returns:**

  / *Type*: dict[str, str] /

  Mapping of hub_id to command_id.
        """
        results = {}
        snapshot = self.get_fleet_status()
        for hub in snapshot.hubs:
            if hub.status == "online":
                try:
                    cmd_id = self.start_processes(hub.hub_id, process_list, panel_id)
                    results[hub.hub_id] = cmd_id
                except Exception as e:
                    logger.warning("Failed to start on %s: %s", hub.hub_id, e)
        return results

    def stop_all_processes(
        self,
        panel_id: str = "fleet",
        force: bool = False,
    ) -> dict[str, str]:
        """
Stop all processes on all online hubs.

**Arguments:**

* ``panel_id``

  / *Condition*: optional / *Type*: str / *Default*: "fleet" /

  Panel ID for process ownership.

* ``force``

  / *Condition*: optional / *Type*: bool / *Default*: False /

  Force stop (kill) processes.

**Returns:**

  / *Type*: dict[str, str] /

  Mapping of hub_id to command_id.
        """
        results = {}
        snapshot = self.get_fleet_status()
        for hub in snapshot.hubs:
            if hub.status == "online" and hub.process_count > 0:
                try:
                    cmd_id = self.stop_processes(
                        hub.hub_id,
                        list(hub.processes),
                        panel_id,
                        force,
                    )
                    results[hub.hub_id] = cmd_id
                except Exception as e:
                    logger.warning("Failed to stop on %s: %s", hub.hub_id, e)
        return results

    def reset_all_hubs(self) -> dict[str, str]:
        """
Reset all online hubs.

**Returns:**

  / *Type*: dict[str, str] /

  Mapping of hub_id to command_id.
        """
        results = {}
        snapshot = self.get_fleet_status()
        for hub in snapshot.hubs:
            if hub.status == "online":
                try:
                    cmd_id = self.reset_hub(hub.hub_id)
                    results[hub.hub_id] = cmd_id
                except Exception as e:
                    logger.warning("Failed to reset %s: %s", hub.hub_id, e)
        return results

    # ========================================================================
    # Event Callbacks
    # ========================================================================

    def on_hub_online(self, callback: Callable[[dict], None]) -> None:
        """
Register a callback for hub online events.

**Arguments:**

* ``callback``

  / *Condition*: required / *Type*: Callable[[dict], None] /

  Called with hub data when a hub comes online.
        """
        self._on_hub_online_callbacks.append(callback)

    def on_hub_offline(self, callback: Callable[[dict], None]) -> None:
        """
Register a callback for hub offline events.

**Arguments:**

* ``callback``

  / *Condition*: required / *Type*: Callable[[dict], None] /

  Called with hub data when a hub goes offline.
        """
        self._on_hub_offline_callbacks.append(callback)

    def _handle_hub_online(self, data: Any) -> None:
        """Handle hub online event from transport."""
        for callback in self._on_hub_online_callbacks:
            try:
                callback(data if isinstance(data, dict) else {})
            except Exception as e:
                logger.warning("Error in hub_online callback: %s", e)

    def _handle_hub_offline(self, data: Any) -> None:
        """Handle hub offline event from transport."""
        for callback in self._on_hub_offline_callbacks:
            try:
                callback(data if isinstance(data, dict) else {})
            except Exception as e:
                logger.warning("Error in hub_offline callback: %s", e)
