# ADR-003: Pluggable Transport Layer

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

The original implementation had ZMQ transport hardcoded throughout the codebase:

```python
# Original: ZMQ hardcoded everywhere
class ProcessHubServer:
    def __init__(self):
        self.context = zmq.Context()
        self.pub_socket = self.context.socket(zmq.PUB)
        self.sub_socket = self.context.socket(zmq.SUB)
        # ... ZMQ-specific setup ...

    def send_response(self, topic, data):
        # Direct ZMQ call
        self.pub_socket.send_multipart([topic.encode(), json.dumps(data).encode()])
```

### Problems

1. **Cannot test without ZMQ**: Unit tests require ZMQ infrastructure
2. **Cannot swap transport**: No way to use HTTP, gRPC, or other protocols
3. **Race conditions in tests**: ZMQ subscription propagation timing issues
4. **Platform dependencies**: ZMQ has native dependencies that can be problematic

## Decision

We will implement a **pluggable transport layer** with abstract base class and multiple implementations:

### Transport Interface

```python
class TransportBase(ABC):
    """Abstract transport interface."""

    @abstractmethod
    def start(self) -> None:
        """Start the transport."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the transport."""
        pass

    @abstractmethod
    def register_handler(self, topic: str, handler: Callable[[Any], None]) -> None:
        """Register a message handler for a topic."""
        pass

    @abstractmethod
    def send_async(self, topic: str, data: Any) -> None:
        """Send a message asynchronously."""
        pass

    @property
    @abstractmethod
    def is_started(self) -> bool:
        """Check if transport is running."""
        pass
```

### Implementations

```
TransportBase (Abstract)
    │
    ├── ZmqTransport          # Production: ZMQ PUB/SUB with XPUB/XSUB broker
    │
    ├── InMemoryTransport     # Testing: Direct function calls, no network
    │
    └── (Future: HttpTransport, GrpcTransport, etc.)
```

### ZMQ Transport Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      ZMQ Broker                              │
│  ┌─────────────┐              ┌─────────────┐               │
│  │    XSUB     │◄────────────►│    XPUB     │               │
│  │  (port 5556)│   forwards   │  (port 5555)│               │
│  └──────▲──────┘              └──────┬──────┘               │
│         │                            │                       │
└─────────┼────────────────────────────┼───────────────────────┘
          │                            │
    ┌─────┴─────┐                ┌─────┴─────┐
    │    PUB    │                │    SUB    │
    │  (Server) │                │  (Client) │
    └───────────┘                └───────────┘

Server publishes → XSUB → XPUB → Client subscribes
Client publishes → XSUB → XPUB → Server subscribes
```

### In-Memory Transport (Testing)

```python
class InMemoryTransport(TransportBase):
    """
    In-memory transport for testing.

    Benefits:
    - No network dependencies
    - No timing issues
    - Deterministic behavior
    - Fast execution
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}
        self._started = False

    def register_handler(self, topic: str, handler: Callable) -> None:
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)

    def send_async(self, topic: str, data: Any) -> None:
        """Directly call handlers - no network involved."""
        for handler in self._handlers.get(topic, []):
            handler(data)
```

### Usage Comparison

```python
# Production: ZMQ transport
from ProcessHub import ProcessHubServer, ZmqTransport

transport = ZmqTransport(
    start_broker=True,
    xpub_port=5555,
    xsub_port=5556,
)
server = ProcessHubServer(transport=transport)
server.run()

# Testing: In-memory transport
from ProcessHub import ProcessHubServer, InMemoryTransport, MockExecutor

transport = InMemoryTransport()
executor = MockExecutor()
server = ProcessHubServer(
    transport=transport,
    executor=executor,
)

# Test without any network
def test_process_start():
    # Simulate client request
    transport.send_async("PROCESS_START_REQUEST", {
        "panel_id": "test_panel",
        "process_list": ["proc1"],
    })

    # Verify response
    assert executor.is_running("proc1")
```

## Consequences

### Positive

1. **Testable without network**:
   ```python
   def test_registration():
       transport = InMemoryTransport()
       server = ProcessHubServer(transport=transport)
       # No ZMQ needed!
   ```

2. **Swappable transports**:
   ```python
   # Can easily switch to different transport
   if config.use_http:
       transport = HttpTransport(port=2507)
   else:
       transport = ZmqTransport()
   ```

3. **No race conditions in tests**: In-memory transport is synchronous

4. **Reduced dependencies**: Tests don't need pyzmq installed

5. **Future extensibility**: Easy to add HTTP, gRPC, WebSocket transports

### Negative

1. **Abstraction overhead**: Extra layer between business logic and transport

2. **Feature parity**: Must ensure all transports support same features

3. **Transport-specific features**: Some ZMQ features may not map to other transports

### Neutral

1. **Configuration complexity**: Need to configure transport separately from server

## Alternatives Considered

### 1. Keep Hardcoded ZMQ (Rejected)

Would prevent testing without ZMQ and limit future transport options.

### 2. Dependency Injection Without Interface (Rejected)

Just passing ZMQ objects without abstraction:

```python
def __init__(self, pub_socket, sub_socket):
    self.pub = pub_socket
    self.sub = sub_socket
```

Rejected because:
- Still ZMQ-specific
- Cannot swap to non-ZMQ transport
- No clear contract

### 3. Message Queue Abstraction (Deferred)

Using a more generic message queue abstraction:

```python
class MessageQueue(Protocol):
    def publish(self, topic: str, message: Message) -> None: ...
    def subscribe(self, topic: str) -> AsyncIterator[Message]: ...
```

Deferred because:
- Current interface is sufficient
- Can evolve to this if needed for Kafka, RabbitMQ, etc.

## References

- [ZeroMQ Guide](https://zguide.zeromq.org/)
- [Dependency Injection Principle](https://en.wikipedia.org/wiki/Dependency_injection)
- Source: `ProcessHub/transport/base.py`, `ProcessHub/transport/zmq_transport.py`, `ProcessHub/transport/inmemory_transport.py`
