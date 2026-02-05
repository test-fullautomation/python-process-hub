# ADR-016: Immutable State Snapshots for UI

## Status

Accepted

## Date

2026-01-22

## Author

Nguyen Huynh Tri Cuong (MS/EMC51)

## Reviewer

- Nguyen Huynh Tri Cuong (MS/EMC51)

## History

| Date | Version | Description |
|------|---------|-------------|
| 2026-01-22 | 1.0 | Initial version |

## Context

ProcessHub's UI (WebView, ConsoleView) needs to display:
- List of connections (panel_id, session_id, connected_at)
- List of processes (name, state, pid, requesters)
- Restart state (phase, pending_panels, killed_processes)

This state is managed by multiple components running in different threads:
- **Transport thread**: Receives messages, updates registries
- **Health check thread**: Monitors processes, triggers restarts
- **UI thread**: Renders dashboard, handles API requests

### The Problem

If UI directly accesses live state, race conditions occur:

```python
# PROBLEMATIC: Direct access to live state
class WebView:
    def render(self):
        # Thread A: UI iterating over processes
        for proc in self.hub.process_registry.processes:
            html += f"<tr>{proc.name}</tr>"

        # Thread B: Transport modifying processes (concurrent!)
        # self.hub.process_registry.processes.pop("worker_1")

        # Result: RuntimeError: dictionary changed size during iteration
```

### Traditional Solutions

**Option A: Lock Everything**
```python
def render(self):
    with self.hub._lock:  # Hold lock during entire render
        for proc in self.hub.process_registry.processes:
            html += f"<tr>{proc.name}</tr>"
```
Problem: UI rendering blocks all other operations. Slow renders cause system-wide delays.

**Option B: Lock and Copy**
```python
def render(self):
    with self.hub._lock:
        processes = list(self.hub.process_registry.processes)
    # Render without lock
    for proc in processes:
        html += f"<tr>{proc.name}</tr>"
```
Problem: Inconsistent view - connections, processes, and restart state captured at different times.

## Decision

**Use immutable state snapshots** for UI rendering.

The core provides a single method that returns a **frozen, consistent snapshot** of all state:

```python
@dataclass(frozen=True)
class HubStateSnapshot:
    """Immutable snapshot of hub state for UI rendering."""
    connections: Tuple[ConnectionInfo, ...]
    processes: Tuple[ProcessInfo, ...]
    restart: RestartStateSnapshot
    timestamp: float
```

### Key Properties

| Property | Description |
|----------|-------------|
| **Immutable** | `frozen=True` prevents modification |
| **Consistent** | All state captured under single lock |
| **Decoupled** | UI holds copy, not reference to live state |
| **Typed** | Dataclass with explicit fields |

### Implementation

```python
class ProcessHubCore:
    def get_state_snapshot(self) -> HubStateSnapshot:
        """
        Get immutable snapshot of current hub state.

        Thread-safe: acquires all locks, copies state, releases locks.
        UI can read snapshot without any locks.
        """
        # Acquire locks in consistent order to prevent deadlock
        with self._connection_registry._lock:
            with self._process_registry._lock:
                with self._restart_fsm._lock:
                    return HubStateSnapshot(
                        connections=tuple(
                            ConnectionInfo(
                                panel_id=c.panel_id,
                                session_id=c.session_id,
                                connected_at=c.connected_at,
                            )
                            for c in self._connection_registry.get_all()
                        ),
                        processes=tuple(
                            ProcessInfo(
                                name=p.name,
                                state=p.state,
                                pid=p.pid,
                                requesters=frozenset(p.requesters),
                            )
                            for p in self._process_registry.get_all()
                        ),
                        restart=RestartStateSnapshot(
                            phase=self._restart_fsm.phase,
                            killed_processes=tuple(self._restart_fsm.killed_processes),
                            pending_panels=tuple(self._restart_fsm.pending_panels),
                        ),
                        timestamp=time.time(),
                    )
```

### UI Usage

```python
class WebView(HubViewBase):
    def render(self, snapshot: HubStateSnapshot) -> None:
        """Render dashboard from immutable snapshot."""
        # No locks needed - snapshot is immutable
        for conn in snapshot.connections:
            self._render_connection(conn)

        for proc in snapshot.processes:
            self._render_process(proc)

        self._render_restart_status(snapshot.restart)

class ConsoleView(HubViewBase):
    def render(self, snapshot: HubStateSnapshot) -> None:
        """Render console table from immutable snapshot."""
        print(f"Connections: {len(snapshot.connections)}")
        print(f"Processes: {len(snapshot.processes)}")
        print(f"Restart Phase: {snapshot.restart.phase}")
```

### REST API Usage

```python
@app.get("/api/state")
async def get_state() -> HubStateResponse:
    snapshot = hub_core.get_state_snapshot()
    return HubStateResponse(
        connections=[...snapshot.connections...],
        processes=[...snapshot.processes...],
        restart=snapshot.restart,
    )
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     ProcessHubCore                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Connection  │  │  Process    │  │  Restart    │         │
│  │  Registry   │  │  Registry   │  │    FSM      │         │
│  │  (mutable)  │  │  (mutable)  │  │  (mutable)  │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          │                                  │
│                 get_state_snapshot()                        │
│                          │                                  │
│                          ▼                                  │
│              ┌───────────────────────┐                      │
│              │  HubStateSnapshot     │                      │
│              │  (frozen dataclass)   │                      │
│              │  - connections: Tuple │                      │
│              │  - processes: Tuple   │                      │
│              │  - restart: Snapshot  │                      │
│              └───────────┬───────────┘                      │
└──────────────────────────┼──────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
       ┌─────────────┐          ┌─────────────┐
       │   WebView   │          │ ConsoleView │
       │  (no locks) │          │  (no locks) │
       └─────────────┘          └─────────────┘
```

## Consequences

### Positive

- **Thread safety**: UI never blocks core operations
- **Consistency**: Snapshot represents state at single point in time
- **Simplicity**: UI code has no lock management
- **Performance**: Lock held only during snapshot creation (fast)
- **Testability**: Snapshots are easy to create in tests
- **Debuggability**: Can log/store snapshots for debugging

### Negative

- **Memory overhead**: Creates copies of state on each render
- **Staleness**: Snapshot is immediately "old" (acceptable for UI)
- **Boilerplate**: Need to define snapshot dataclasses

### Neutral

- **Render frequency**: UI must decide how often to get new snapshots
- **Tuple vs List**: Using tuples enforces immutability but requires conversion

## Alternatives Considered

### 1. Direct Access with Global Lock (Rejected)

UI holds global lock during entire render.

```python
def render(self):
    with hub.global_lock:
        # Render everything
```

Rejected because:
- Blocks all operations during slow renders
- Long API requests could freeze the system
- Deadlock risk with nested locks

### 2. Read-Write Locks (Rejected)

Use RWLock to allow multiple readers.

```python
def render(self):
    with hub.rwlock.read():
        # Multiple UIs can read concurrently
```

Rejected because:
- Still blocks writes during reads
- More complex lock management
- Inconsistent state if reading multiple registries

### 3. Copy-on-Write (Deferred)

State structures use copy-on-write semantics.

Deferred because:
- More complex implementation
- Python doesn't have native COW support
- Snapshot approach is simpler and sufficient

### 4. Event-Based Updates (Deferred)

UI subscribes to state change events.

```python
hub.on_state_change(lambda delta: ui.apply_delta(delta))
```

Deferred because:
- Complex delta calculation
- UI must maintain own state copy
- Harder to ensure consistency
- Could add later for real-time WebSocket updates

## References

- [Immutable Object Pattern](https://en.wikipedia.org/wiki/Immutable_object)
- [Snapshot Isolation](https://en.wikipedia.org/wiki/Snapshot_isolation)
- [Python frozen dataclasses](https://docs.python.org/3/library/dataclasses.html#frozen-instances)
- Source: `ProcessHub/core/hub_core.py` - `get_state_snapshot()`
- Source: `ProcessHub/core/models.py` - `HubStateSnapshot`
- Related: ADR-007 (Decoupled UI via HubView Protocol)
