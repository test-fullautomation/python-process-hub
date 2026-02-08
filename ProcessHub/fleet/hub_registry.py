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
# File: hub_registry.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / February 2026.
#
# Description:
#   Thread-safe hub registry for fleet orchestrator.
#   Tracks registered hubs, their health state, and provides
#   immutable snapshots for concurrent consumers.
#
# History:
#
# 06.02.2026 / V 1.1.0 / Nguyen Huynh Tri Cuong
# - Initial fleet orchestrator implementation
#
# *******************************************************************************
"""
Thread-safe hub registry for fleet orchestrator.

Tracks registered hubs with health state transitions:
online -> degraded -> offline

Provides immutable FleetStateSnapshot for concurrent consumers
(REST API, FleetClient, orchestrator tick).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from .models import (
    FleetStateSnapshot,
    HubAnnounce,
    HubSnapshot,
    HubStatusReport,
)

logger = logging.getLogger(__name__)


@dataclass
class _HubEntry:
    """Mutable internal hub tracking entry."""

    hub_id: str
    hub_name: str = ""
    host: str = ""
    capabilities: list[str] = field(default_factory=list)
    status: str = "online"
    process_count: int = 0
    connection_count: int = 0
    processes: list[str] = field(default_factory=list)
    connections: list[str] = field(default_factory=list)
    configured_processes: list[str] = field(default_factory=list)
    process_configs: dict = field(default_factory=dict)
    last_seen: float = field(default_factory=time.time)
    registered_at: float = field(default_factory=time.time)
    version: str = ""


class HubRegistry:
    """
Thread-safe registry of fleet hubs.

Provides:
- Hub registration and deregistration
- Status and heartbeat updates
- Health checking with timeout-based state transitions
- Immutable snapshots for concurrent consumers

Health states:
- online: heartbeat received within timeout/2
- degraded: heartbeat missed, within timeout
- offline: heartbeat missed, exceeded timeout
    """

    def __init__(self):
        self._hubs: dict[str, _HubEntry] = {}
        self._lock = threading.Lock()

    def register(self, hub_id: str, info: HubAnnounce) -> bool:
        """
Register a hub in the fleet.

**Arguments:**

* ``hub_id``

  / *Condition*: required / *Type*: str /

  Unique identifier for the hub.

* ``info``

  / *Condition*: required / *Type*: HubAnnounce /

  Hub announcement message with hub details.

**Returns:**

  / *Type*: bool /

  True if newly registered, False if already existed (updated instead).
        """
        with self._lock:
            is_new = hub_id not in self._hubs
            if is_new:
                self._hubs[hub_id] = _HubEntry(
                    hub_id=hub_id,
                    hub_name=info.hub_name,
                    host=info.host,
                    capabilities=list(info.capabilities),
                    status="online",
                    last_seen=time.time(),
                    version=info.version,
                )
                logger.info("Hub registered: %s (%s)", hub_id, info.hub_name)
            else:
                entry = self._hubs[hub_id]
                entry.hub_name = info.hub_name
                entry.host = info.host
                entry.capabilities = list(info.capabilities)
                entry.last_seen = time.time()
                entry.version = info.version
                if entry.status == "offline":
                    entry.status = "online"
                    logger.info("Hub back online: %s (%s)", hub_id, info.hub_name)
            return is_new

    def deregister(self, hub_id: str) -> bool:
        """
Remove a hub from the fleet.

**Arguments:**

* ``hub_id``

  / *Condition*: required / *Type*: str /

  The hub to remove.

**Returns:**

  / *Type*: bool /

  True if hub was found and removed, False if not found.
        """
        with self._lock:
            if hub_id in self._hubs:
                del self._hubs[hub_id]
                logger.info("Hub deregistered: %s", hub_id)
                return True
            return False

    def update_status(self, hub_id: str, report: HubStatusReport) -> None:
        """
Update hub status from a HubStatusReport message.

**Arguments:**

* ``hub_id``

  / *Condition*: required / *Type*: str /

  The hub to update.

* ``report``

  / *Condition*: required / *Type*: HubStatusReport /

  Status report from the hub agent.
        """
        with self._lock:
            entry = self._hubs.get(hub_id)
            if entry is None:
                logger.warning("Status report from unknown hub: %s", hub_id)
                return
            entry.process_count = report.process_count
            entry.connection_count = report.connection_count
            entry.processes = list(report.processes)
            entry.connections = list(report.connections)
            if report.configured_processes:
                entry.configured_processes = list(report.configured_processes)
            if report.process_configs:
                entry.process_configs = dict(report.process_configs)
            entry.restart_state = report.restart_state if hasattr(report, "restart_state") else ""
            entry.last_seen = time.time()

    def update_heartbeat(self, hub_id: str) -> None:
        """
Update the last-seen timestamp for a hub.

Called when any message is received from the hub.

**Arguments:**

* ``hub_id``

  / *Condition*: required / *Type*: str /

  The hub to update.
        """
        with self._lock:
            entry = self._hubs.get(hub_id)
            if entry is not None:
                entry.last_seen = time.time()
                if entry.status in ("degraded", "offline"):
                    entry.status = "online"

    def get_hub(self, hub_id: str) -> Optional[HubSnapshot]:
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
        with self._lock:
            entry = self._hubs.get(hub_id)
            if entry is None:
                return None
            return self._entry_to_snapshot(entry)

    def get_all_hubs(self) -> list[HubSnapshot]:
        """
Get immutable snapshots of all registered hubs.

**Returns:**

  / *Type*: list[HubSnapshot] /

  List of hub snapshots.
        """
        with self._lock:
            return [self._entry_to_snapshot(e) for e in self._hubs.values()]

    def get_online_hubs(self) -> list[HubSnapshot]:
        """
Get immutable snapshots of all online hubs.

**Returns:**

  / *Type*: list[HubSnapshot] /

  List of hub snapshots with status 'online'.
        """
        with self._lock:
            return [
                self._entry_to_snapshot(e)
                for e in self._hubs.values()
                if e.status == "online"
            ]

    def is_registered(self, hub_id: str) -> bool:
        """
Check if a hub is registered.

**Arguments:**

* ``hub_id``

  / *Condition*: required / *Type*: str /

  The hub to check.

**Returns:**

  / *Type*: bool /

  True if hub is registered.
        """
        with self._lock:
            return hub_id in self._hubs

    def check_health(self, timeout_seconds: float) -> list[str]:
        """
Check for timed-out hubs and update health states.

Called periodically by the orchestrator tick().

Health transitions:
- last_seen within timeout/2: online
- last_seen within timeout: degraded
- last_seen exceeded timeout: offline (returned in list)

**Arguments:**

* ``timeout_seconds``

  / *Condition*: required / *Type*: float /

  Maximum time since last heartbeat before a hub is considered offline.

**Returns:**

  / *Type*: list[str] /

  List of hub IDs that just transitioned to offline.
        """
        now = time.time()
        newly_offline = []
        with self._lock:
            for hub_id, entry in self._hubs.items():
                elapsed = now - entry.last_seen
                if elapsed > timeout_seconds:
                    if entry.status != "offline":
                        entry.status = "offline"
                        newly_offline.append(hub_id)
                        logger.warning(
                            "Hub offline: %s (last seen %.1fs ago)",
                            hub_id,
                            elapsed,
                        )
                elif elapsed > timeout_seconds / 2:
                    if entry.status == "online":
                        entry.status = "degraded"
                        logger.info(
                            "Hub degraded: %s (last seen %.1fs ago)",
                            hub_id,
                            elapsed,
                        )
                else:
                    if entry.status != "online":
                        entry.status = "online"
        return newly_offline

    def get_snapshot(self) -> FleetStateSnapshot:
        """
Get an immutable snapshot of the entire fleet state.

Thread-safe: acquires lock, copies state, releases lock.
Consumers can read the snapshot without locks.

**Returns:**

  / *Type*: FleetStateSnapshot /

  Immutable fleet state snapshot.
        """
        with self._lock:
            hub_snapshots = []
            total_procs = 0
            online = 0
            for entry in self._hubs.values():
                snap = self._entry_to_snapshot(entry)
                hub_snapshots.append(snap)
                total_procs += entry.process_count
                if entry.status == "online":
                    online += 1

            return FleetStateSnapshot(
                hubs=tuple(hub_snapshots),
                total_hubs=len(hub_snapshots),
                online_hubs=online,
                total_processes=total_procs,
                timestamp=time.time(),
            )

    @property
    def hub_count(self) -> int:
        """Get total number of registered hubs."""
        with self._lock:
            return len(self._hubs)

    def _entry_to_snapshot(self, entry: _HubEntry) -> HubSnapshot:
        """Convert mutable entry to immutable snapshot. Must be called under lock."""
        return HubSnapshot(
            hub_id=entry.hub_id,
            hub_name=entry.hub_name,
            host=entry.host,
            status=entry.status,
            process_count=entry.process_count,
            connection_count=entry.connection_count,
            processes=tuple(entry.processes),
            connections=tuple(entry.connections),
            configured_processes=tuple(entry.configured_processes),
            process_configs=dict(entry.process_configs),
            last_seen=entry.last_seen,
            version=entry.version,
        )
