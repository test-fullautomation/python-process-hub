# ADR-020: Fleet Frozen State Snapshots

## Status

Accepted

## Date

2026-02-06

## Author

Nguyen Huynh Tri Cuong (MS/EMC51)

## Reviewer

- Nguyen Huynh Tri Cuong (MS/EMC51)

## History

| Date | Version | Description |
|------|---------|-------------|
| 2026-02-06 | 1.0 | Initial version |

## Context

The Fleet Orchestrator maintains state about all registered hubs: their identity,
health status, process counts, and last-seen timestamps. Multiple consumers need to
read this state concurrently:

- **FleetWebAPI** - REST endpoints serving hub status to dashboards
- **FleetClient** - Status queries from CI pipelines
- **Orchestrator tick** - Health check logic reading and updating hub states
- **Command routing** - Checking hub availability before forwarding commands

This is analogous to the local hub state problem solved by ADR-016 (Immutable State
Snapshots for UI), but at the fleet level.

### The Problem

```python
# PROBLEMATIC: Direct access to mutable registry
class FleetWebAPI:
    @app.get("/api/fleet/hubs")
    async def get_hubs(self):
        # Thread A: Web request iterating hubs
        hubs = []
        for hub_id, info in self.registry._hubs.items():
            hubs.append({"hub_id": hub_id, "status": info.status})

        # Thread B: Orchestrator tick modifying registry
        # self.registry._hubs["hub-3"].status = "offline"
        # Result: Inconsistent data, potential RuntimeError
```

## Decision

We will use **frozen dataclass snapshots** for fleet state, following the same pattern
established in ADR-016 for local hub state.

### Fleet Snapshots

```python
@dataclass(frozen=True)
class HubSnapshot:
    """Immutable snapshot of a single hub's state."""
    hub_id: str
    hub_name: str
    host: str
    status: str                    # "online", "degraded", "offline"
    process_count: int
    connection_count: int
    processes: tuple[str, ...]     # tuple, not list (immutable)
    connections: tuple[str, ...]
    last_seen: float
    version: str

@dataclass(frozen=True)
class FleetStateSnapshot:
    """Immutable snapshot of the entire fleet."""
    hubs: tuple[HubSnapshot, ...]  # tuple, not list (immutable)
    total_hubs: int
    online_hubs: int
    total_processes: int
    timestamp: float
```

### Snapshot Creation

```python
class HubRegistry:
    def get_snapshot(self) -> FleetStateSnapshot:
        """Get immutable fleet state snapshot. Thread-safe."""
        with self._lock:
            hub_snapshots = []
            total_procs = 0
            online = 0
            for hub_id, info in self._hubs.items():
                snap = HubSnapshot(
                    hub_id=info.hub_id,
                    hub_name=info.hub_name,
                    host=info.host,
                    status=info.status,
                    process_count=info.process_count,
                    connection_count=info.connection_count,
                    processes=tuple(info.processes),
                    connections=tuple(info.connections),
                    last_seen=info.last_seen,
                    version=info.version,
                )
                hub_snapshots.append(snap)
                total_procs += info.process_count
                if info.status == "online":
                    online += 1

            return FleetStateSnapshot(
                hubs=tuple(hub_snapshots),
                total_hubs=len(hub_snapshots),
                online_hubs=online,
                total_processes=total_procs,
                timestamp=time.time(),
            )
```

### Consumer Usage

```python
# REST API - no locks needed
@app.get("/api/fleet/status")
async def get_fleet_status():
    snapshot = orchestrator.get_fleet_snapshot()
    return {
        "total_hubs": snapshot.total_hubs,
        "online_hubs": snapshot.online_hubs,
        "hubs": [asdict(h) for h in snapshot.hubs],
    }

# FleetClient - no locks needed
class FleetClient:
    def get_fleet_status(self) -> FleetStateSnapshot:
        return self._orchestrator.get_fleet_snapshot()

# CI Pipeline - no locks needed
snapshot = fleet_client.get_fleet_status()
assert snapshot.online_hubs >= 2, "Need at least 2 hubs online"
```

### Design Rules

| Rule | Rationale |
|------|-----------|
| `frozen=True` on all snapshots | Prevents accidental mutation |
| `tuple` for collections | Immutable (lists are mutable even in frozen dataclasses) |
| Single lock for creation | Consistent snapshot of all fields |
| No back-references | Snapshots don't reference mutable registry objects |

## Consequences

### Positive

- **Thread safety** - Consumers read without locks
- **Consistency** - Snapshot is a single point-in-time view
- **Composability** - Works identically to local `HubStateSnapshot` pattern
- **Testability** - Easy to create snapshots in tests
- **Serializable** - `dataclasses.asdict()` works for JSON serialization

### Negative

- **Memory allocation** - New snapshot objects on each query
- **Staleness** - Snapshot is immediately outdated (acceptable for fleet monitoring)
- **Tuple conversion** - Lists must be converted to tuples

### Neutral

- **Follows precedent** - Same pattern as ADR-016, consistent codebase
- **No reactive updates** - Consumers must poll for new snapshots

## Alternatives Considered

### 1. Direct Registry Access with Locks (Rejected)

Consumers acquire the registry lock to read state:

```python
with registry._lock:
    for hub in registry._hubs.values():
        # read hub state
```

Rejected because:
- Consumers hold lock during processing (blocks updates)
- Exposes internal lock (encapsulation violation)
- Same problems as local hub state (see ADR-016)

### 2. Copy-on-Read Dictionaries (Rejected)

Return deep copies of internal dictionaries:

```python
def get_all_hubs(self) -> dict[str, dict]:
    with self._lock:
        return copy.deepcopy(self._hubs)
```

Rejected because:
- Untyped (dict instead of dataclass)
- No IDE autocomplete
- No immutability guarantee
- Higher copy overhead than targeted snapshot

### 3. Event-Sourced State (Deferred)

Consumers subscribe to state change events:

```python
registry.on_change(lambda event: dashboard.apply(event))
```

Deferred because:
- More complex implementation
- Consumers must maintain their own state
- Snapshot approach is sufficient for current needs
- Could be added for WebSocket real-time updates later

## References

- [Immutable Object Pattern](https://en.wikipedia.org/wiki/Immutable_object)
- [Python frozen dataclasses](https://docs.python.org/3/library/dataclasses.html#frozen-instances)
- Related: ADR-016 (Immutable State Snapshots for UI) - same pattern at local level
- Related: ADR-017 (Fleet Orchestrator as Overlay Pattern)
- Source: `ProcessHub/fleet/models.py` - `HubSnapshot`, `FleetStateSnapshot`
- Source: `ProcessHub/fleet/hub_registry.py` - `get_snapshot()`
