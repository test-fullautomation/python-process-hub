# ADR-007: Decoupled UI via HubView Protocol

## Status

Accepted

## Date

2026-01-16

## Author

Nguyen Huynh Tri Cuong (MS/EMC51)

## Reviewer

- Nguyen Huynh Tri Cuong (MS/EMC51)

## History

| Date | Version | Description |
|------|---------|-------------|
| 2026-01-16 | 1.0 | Initial version |

## Context

The original implementation had the console UI hardcoded in the main server loop:

```python
# Original: UI hardcoded in main loop
class ProcessHubServer:
    def __init__(self):
        self.view = ProcessView()  # Only option

    def run(self):
        while self.running:
            # Health check
            self.health_check()

            # UI refresh (hardcoded)
            with self.shared_info_lock:
                proc_data = copy.deepcopy(self.shared_info)
            with self.connection_lock:
                conn_data = copy.deepcopy(self.connections)

            self.view.render(proc_data, conn_data)  # Blocking!
            time.sleep(0.5)  # Fixed refresh rate
```

### Problems

```
┌─────────────────────────────────────────────────────────────┐
│                    Original Design                           │
│                                                              │
│  ProcessHubServer                                            │
│  ├── self.view = ProcessView()  ← Hardcoded console UI      │
│  │                                                           │
│  └── run():                                                  │
│      └── self.view.render(...)  ← Blocking, main thread     │
│                                                              │
│  Problems:                                                   │
│  1. Cannot run headless (no UI)                              │
│  2. Cannot use different UI (web, mobile)                    │
│  3. UI blocks main loop                                      │
│  4. Lock contention for UI data                              │
│  5. Fixed refresh rate                                       │
└─────────────────────────────────────────────────────────────┘
```

### Lock Contention Issue

```python
# Main loop holds locks for UI copy
with self.shared_info_lock:      # Lock 1
    proc_data = copy.deepcopy(self.shared_info)
with self.connection_lock:       # Lock 2
    conn_data = copy.deepcopy(self.connections)

# Other threads blocked during copy!
# If UI is slow, it blocks process operations
```

## Decision

We will implement a **pluggable UI layer** via `HubView` protocol with immutable state snapshots:

### HubView Protocol

```python
class HubView(Protocol):
    """
    Protocol for hub UI implementations.

    Any class implementing these methods can be used as a view.
    """

    def start(self) -> None:
        """Start the view (e.g., start web server)."""
        ...

    def stop(self) -> None:
        """Stop the view."""
        ...

    def render(self, snapshot: HubStateSnapshot) -> None:
        """
        Render the current state.

        Args:
            snapshot: Immutable state snapshot (no locks needed)
        """
        ...
```

### View Implementations

```
HubView (Protocol)
    │
    ├── ConsoleView     # Terminal TUI with ASCII tables
    │
    ├── WebView         # FastAPI web dashboard with REST API
    │
    ├── NullView        # Headless operation (no UI)
    │
    └── (Future: TkView, QtView, MetricsView, etc.)
```

### Immutable State Snapshots

```python
@dataclass(frozen=True)
class HubStateSnapshot:
    """
    Immutable snapshot of hub state for UI.

    frozen=True ensures:
    - Immutable (hashable)
    - Thread-safe (no locks needed by UI)
    - No accidental modification
    """
    connections: tuple[ConnectionSnapshot, ...]
    processes: tuple[ProcessSnapshot, ...]
    restart_state: str
    killed_processes: tuple[str, ...]
    pending_panels: tuple[str, ...]


# Core creates snapshot (under lock)
def get_state_snapshot(self) -> HubStateSnapshot:
    with self._connection_lock:
        connections = tuple(...)

    processes = self._registry.get_snapshot()  # Also under lock

    return HubStateSnapshot(
        connections=connections,
        processes=processes,
        # ...
    )

# UI renders snapshot (no lock needed!)
def render(self, snapshot: HubStateSnapshot) -> None:
    for proc in snapshot.processes:  # Safe iteration
        print(f"{proc.name}: {proc.state}")
```

### ConsoleView Implementation

```python
class ConsoleView(HubViewBase):
    """Terminal-based console view with ASCII tables."""

    def render(self, snapshot: HubStateSnapshot) -> None:
        self._clear_screen()

        # Header
        print("=" * 60)
        print("  ProcessHub Server")
        print("=" * 60)

        # Connections table
        print("\n[Connections]")
        print(f"{'Panel ID':<20} {'Session ID':<20}")
        print("-" * 40)
        for conn in snapshot.connections:
            print(f"{conn.panel_id:<20} {conn.session_id:<20}")

        # Processes table
        print("\n[Processes]")
        print(f"{'Name':<20} {'State':<12} {'PID':<8}")
        print("-" * 40)
        for proc in snapshot.processes:
            print(f"{proc.name:<20} {proc.state.value:<12} {proc.pid:<8}")

        # Restart status
        if snapshot.restart_state != "idle":
            print(f"\n[Restart] {snapshot.restart_state}")
            print(f"  Killed: {snapshot.killed_processes}")
            print(f"  Pending: {snapshot.pending_panels}")
```

### WebView Implementation

```python
class WebView(HubViewBase):
    """
    FastAPI web dashboard.

    Features:
    - REST API for state access
    - Auto-generated Swagger docs
    - Real-time dashboard with auto-refresh
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 2507):
        self._host = host
        self._port = port
        self._app = FastAPI(title="ProcessHub Dashboard")
        self._current_state: Optional[HubStateSnapshot] = None
        self._setup_routes()

    def _setup_routes(self):
        @self._app.get("/api/state")
        def get_state():
            return self._snapshot_to_dict(self._current_state)

        @self._app.get("/api/processes")
        def get_processes():
            return [asdict(p) for p in self._current_state.processes]

        @self._app.get("/")
        def dashboard():
            return HTMLResponse(self._render_dashboard())

    def render(self, snapshot: HubStateSnapshot) -> None:
        # Just update state - web requests serve it
        self._current_state = snapshot

    def start(self) -> None:
        # Start FastAPI in background thread
        self._server_thread = threading.Thread(
            target=uvicorn.run,
            args=(self._app,),
            kwargs={"host": self._host, "port": self._port},
        )
        self._server_thread.start()
```

### NullView Implementation

```python
class NullView(HubViewBase):
    """
    Headless view that does nothing.

    Use for:
    - Testing
    - CI/CD environments
    - When no UI is needed
    """

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def render(self, snapshot: HubStateSnapshot) -> None:
        pass  # Do nothing
```

### Usage Examples

```python
# Console UI
from ProcessHub import ProcessHubServer, ZmqTransport, ConsoleView

server = ProcessHubServer(
    transport=ZmqTransport(start_broker=True),
    view=ConsoleView(),
)
server.run()

# Web dashboard
from ProcessHub.ui import WebView

server = ProcessHubServer(
    transport=ZmqTransport(start_broker=True),
    view=WebView(host="0.0.0.0", port=2507),
)
server.run()
# Access http://localhost:2507 for dashboard
# Access http://localhost:2507/docs for API docs

# Headless (testing/CI)
from ProcessHub import NullView

server = ProcessHubServer(
    transport=InMemoryTransport(),
    view=NullView(),  # No UI overhead
)
```

### Lock-Free UI Rendering

```python
# Original: Multiple locks, blocking
def run(self):
    while running:
        with self.shared_info_lock:          # Blocks operations
            proc_data = copy.deepcopy(...)
        with self.connection_lock:           # Blocks operations
            conn_data = copy.deepcopy(...)
        self.view.render(proc_data, conn_data)

# New: Single snapshot, no UI-side locking
def run(self):
    while running:
        # Snapshot created atomically in core
        snapshot = self._core.get_state_snapshot()
        # View renders without any locks
        self._view.render(snapshot)
```

## Consequences

### Positive

1. **Pluggable UI**: Easy to swap between console, web, or headless
   ```python
   view = ConsoleView() if args.console else WebView()
   ```

2. **No UI-side locking**: Immutable snapshots are thread-safe
   ```python
   # UI can iterate safely without locks
   for proc in snapshot.processes:
       render_process(proc)
   ```

3. **Testable**: Use NullView to test without UI overhead
   ```python
   def test_process_start():
       server = ProcessHubServer(view=NullView())
       # No UI rendering during test
   ```

4. **Multiple UIs**: Can render to multiple views simultaneously
   ```python
   class MultiView(HubViewBase):
       def render(self, snapshot):
           self.console.render(snapshot)
           self.web.render(snapshot)
   ```

5. **Non-blocking**: UI doesn't block main loop (especially WebView)

6. **Future extensibility**: Easy to add new views (mobile, metrics, etc.)

### Negative

1. **Snapshot overhead**: Creating immutable copies has cost

2. **State lag**: Snapshot may be slightly stale by render time

3. **More code**: Each view is a separate class

### Neutral

1. **Learning curve**: Developers must understand view abstraction

## Alternatives Considered

### 1. Keep Hardcoded Console UI (Rejected)

Would prevent headless operation and alternative UIs.

### 2. Observer Pattern (Considered)

Views subscribe to state changes:

```python
core.on_state_change(lambda state: view.render(state))
```

Not rejected but simplified because:
- Current polling approach is simpler
- Snapshot-based rendering is sufficient
- Can add observer pattern later if needed

### 3. Reactive Streams (Deferred)

Using RxPY or similar for state streams:

```python
state_stream = core.state_observable()
state_stream.subscribe(view.render)
```

Deferred because:
- Adds dependency
- Complexity not justified for current use
- May be useful for real-time web UI later

## References

- [Protocol Structural Subtyping (PEP 544)](https://www.python.org/dev/peps/pep-0544/)
- [Immutable Data Structures](https://en.wikipedia.org/wiki/Immutable_object)
- Source: `ProcessHub/ui/base.py`, `ProcessHub/ui/console_view.py`, `ProcessHub/ui/web_view.py`
