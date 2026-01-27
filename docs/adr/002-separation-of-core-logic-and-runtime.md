# ADR-002: Separation of Core Logic and Runtime

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

The original `ta-framework-tsb/process_hub` implementation was monolithic, with business logic tightly coupled to I/O operations:

```python
# Original: Monolithic ProcessHubServer
class ProcessHubServer:
    def __init__(self):
        # ZMQ communication (hardcoded)
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)

        # Process management (mixed with I/O)
        self.process_control = ProcessControl()

        # UI rendering (inline)
        self.view = ProcessView()

        # Configuration loading (inline)
        self.config = load_config()

    def start_process(self, msg):
        # Business logic mixed with transport
        panel_id = msg.data["panel_id"]
        for process in msg.data["process_list"]:
            result = self.process_control.start_process_by_name(panel_id, process)
            # Direct ZMQ send
            self.event_bus.send_message_async(topic, DictMsg({...}))
```

### Problems with Monolithic Design

```
┌─────────────────────────────────────────────────────────────┐
│                    ProcessHubServer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ ZMQ Comms   │  │  Business   │  │     UI      │          │
│  │ (hardcoded) │◄─┤   Logic     ├─►│ (hardcoded) │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│         │                │                │                  │
│         └────────────────┴────────────────┘                  │
│                    TIGHTLY COUPLED                           │
└─────────────────────────────────────────────────────────────┘

Issues:
1. Cannot test business logic without ZMQ
2. Cannot swap transport (HTTP, gRPC, in-memory)
3. Cannot run headless (no UI)
4. Hard to reason about - everything mixed together
```

## Decision

We will separate the system into **three distinct layers**:

1. **Core Layer** (`ProcessHubCore`) - Pure business logic, no I/O
2. **Transport Layer** - Pluggable message transport (ZMQ, in-memory, etc.)
3. **Runtime Layer** (`ProcessHubServer`) - Thin adapter wiring core to transport

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    ProcessHubServer                          │
│                   (thin runtime adapter)                     │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  • Wire transport handlers to core                   │    │
│  │  • Run main loop (tick + UI refresh)                 │    │
│  │  • Handle shutdown signals                           │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   Transport   │  │ ProcessHubCore│  │    HubView    │
│   (ZMQ, etc.) │  │ (pure logic)  │  │ (Console,Web) │
└───────────────┘  └───────────────┘  └───────────────┘
        │                  │                  │
        │          No I/O knowledge           │
        │          No ZMQ dependency          │
        │          Fully testable             │
        │                                     │
   Pluggable                             Pluggable
```

### Core Layer Implementation

```python
class ProcessHubCore:
    """
    Pure business logic - no I/O, no transport knowledge.

    Benefits:
    - Testable without ZMQ, files, or network
    - Can be embedded in other transports (HTTP, gRPC)
    - Clear separation of concerns
    """

    def __init__(
        self,
        process_starter: Callable[[str], tuple[bool, str, Optional[int]]],
        process_stopper: Callable[[str, bool], bool],
        health_checker: Callable[[list[str]], list[str]],
    ):
        # Callbacks instead of direct I/O
        self._process_starter = process_starter
        self._process_stopper = process_stopper
        self._health_checker = health_checker

        # Internal state
        self._registry = ProcessRegistry()
        self._restart_fsm = RestartStateMachine()

    def handle_start_request(self, req: ProcessStartRequest) -> list[OutgoingMessage]:
        """
        Handle incoming request, return outgoing messages.
        No direct I/O - caller handles transport.
        """
        # Pure business logic
        for proc_name in req.process_list:
            success, msg, pid = self._process_starter(proc_name)
            # ... process result ...

        # Return messages for transport layer to send
        return [OutgoingMessage(
            msg_type=MessageType.START_RESPONSE,
            payload=ProcessStartResponse(...),
        )]

    def get_state_snapshot(self) -> HubStateSnapshot:
        """Return immutable state for UI (no locks needed by caller)."""
        return HubStateSnapshot(...)
```

### Runtime Layer Implementation

```python
class ProcessHubServer:
    """
    Thin runtime adapter - wires core to transport.

    Responsibilities:
    - Register transport handlers
    - Call core methods
    - Send outgoing messages
    - Run main loop
    """

    def __init__(self, transport: TransportBase, executor: ProcessExecutor, view: HubView):
        self._transport = transport
        self._executor = executor
        self._view = view

        # Create core with executor callbacks
        self._core = ProcessHubCore(
            process_starter=self._start_process,
            process_stopper=self._stop_process,
            health_checker=self._check_health,
        )

    def _on_start_request(self, data: dict) -> None:
        """Transport handler - delegate to core."""
        req = ProcessStartRequest(**data)
        messages = self._core.handle_start_request(req)
        self._send_messages(messages)  # Send via transport

    def run(self) -> None:
        """Main loop - tick core, update view."""
        while self._running:
            messages = self._core.tick()
            self._send_messages(messages)

            snapshot = self._core.get_state_snapshot()
            self._view.render(snapshot)

            time.sleep(0.5)
```

## Consequences

### Positive

1. **Testable without I/O**: Core can be unit tested with mock callbacks
   ```python
   def test_start_request():
       core = ProcessHubCore(
           process_starter=lambda n: (True, "ok", 1234),
           process_stopper=lambda n, f: True,
           health_checker=lambda ns: [],
       )
       messages = core.handle_start_request(req)
       assert messages[0].payload.success == True
   ```

2. **Pluggable transport**: Can use ZMQ, HTTP, gRPC, or in-memory
   ```python
   # Production
   server = ProcessHubServer(transport=ZmqTransport())

   # Testing
   server = ProcessHubServer(transport=InMemoryTransport())
   ```

3. **Embeddable**: Core can be embedded in other systems
   ```python
   # Embed in Flask app
   @app.route('/start', methods=['POST'])
   def start():
       messages = core.handle_start_request(req)
       return jsonify(messages[0].payload)
   ```

4. **Clear responsibilities**: Each layer has single responsibility

5. **Easier debugging**: Issues isolated to specific layer

### Negative

1. **More files/classes**: Three layers instead of one monolith

2. **Indirection**: Request flows through multiple layers

3. **Learning curve**: Developers must understand the layered architecture

### Neutral

1. **Message passing overhead**: Minimal - just function calls and dataclasses

## Alternatives Considered

### 1. Keep Monolithic Design (Rejected)

Would maintain tight coupling and prevent testing without full environment.

### 2. Hexagonal Architecture (Deferred)

Full ports-and-adapters pattern with interfaces for every boundary:

```python
class ProcessStarterPort(Protocol):
    def start(self, name: str) -> StartResult: ...

class ZmqProcessStarterAdapter(ProcessStarterPort):
    def start(self, name: str) -> StartResult: ...
```

Deferred because:
- Current design is sufficient
- Can evolve to hexagonal if needed
- Simpler callbacks work well for our use case

### 3. Event-Driven Architecture (Deferred)

Using event bus for all communication:

```python
event_bus.publish(ProcessStartRequested(name="proc1"))
# Core subscribes to events
event_bus.subscribe(ProcessStartRequested, core.handle_start)
```

Deferred because:
- Adds complexity for async event handling
- Current request-response model is sufficient
- May be useful for distributed scenarios

## References

- [Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- Source: `ProcessHub/core/hub_core.py`, `ProcessHub/runtime/server.py`
