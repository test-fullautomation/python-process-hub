# ADR-014: EventBus Transport with RabbitMQ

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

ProcessHub needs a transport mechanism for **distributed deployments** where:
- Server and clients are on different machines/networks
- Communication must work across firewalls and NAT
- Messages need persistence during network outages
- Multiple geographic locations need to connect (e.g., Germany and Vietnam)

The existing ZMQ transport works well for local networks but has limitations:
- Requires direct network connectivity (no NAT traversal)
- No built-in message persistence
- No clustering/high availability
- Subscription management is manual

### Requirements for Distributed Transport

| Requirement | Priority | Description |
|-------------|----------|-------------|
| Message broker | Must | Central broker to route messages |
| Persistence | Must | Messages survive broker restart |
| Auto-reconnect | Must | Clients reconnect after network issues |
| Topic routing | Must | Filter messages by topic pattern |
| Cross-network | Must | Work across NAT/firewalls |
| Clustering | Nice | High availability setup |
| Management UI | Nice | Monitor queues and connections |

## Decision

**Use RabbitMQ** as the message broker for distributed deployments, accessed via the **EventBusClient** library.

### Why RabbitMQ

| Feature | RabbitMQ | Kafka | Redis Pub/Sub | MQTT |
|---------|----------|-------|---------------|------|
| Message persistence | Yes | Yes | No | Yes |
| Topic routing | Yes (exchanges) | Yes (topics) | Yes (patterns) | Yes |
| Auto-reconnect | Yes | Yes | Manual | Yes |
| Management UI | Yes (built-in) | No (needs tools) | No | Varies |
| Python support | Excellent | Good | Excellent | Good |
| Complexity | Medium | High | Low | Low |
| Existing library | EventBusClient | None | None | None |

**Key factor**: The **EventBusClient** library already exists and provides a well-tested RabbitMQ integration used in other projects.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    RabbitMQ Server                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Topic Exchange: "process_hub"           │   │
│  │                                                      │   │
│  │   Routing Keys:                                      │   │
│  │   - hub.register.*      → Registration messages      │   │
│  │   - hub.process.*       → Process control            │   │
│  │   - hub.restart.*       → Restart coordination       │   │
│  │   - panel.{id}.*        → Panel-specific messages    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
           │                              │
           │                              │
    ┌──────▼──────┐                ┌──────▼──────┐
    │ ProcessHub  │                │   Client    │
    │   Server    │                │  (Panel)    │
    │             │                │             │
    │ EventBus    │                │ EventBus    │
    │ Transport   │                │ Transport   │
    └─────────────┘                └─────────────┘
        Germany                       Vietnam
```

### Implementation

```python
from ProcessHub.transport.eventbus_transport import EventBusTransport

# Server in Germany
server_transport = EventBusTransport(
    host="rabbitmq.company.com",
    port=5672,
    exchange_name="process_hub",
    auto_reconnect=True,
    reconnect_delay=5.0,
)

# Client in Vietnam
client_transport = EventBusTransport(
    host="rabbitmq.company.com",
    port=5672,
    exchange_name="process_hub",
    auto_reconnect=True,
)
```

### Client Events

The transport provides event notifications for connection state changes:

```python
from ProcessHub.transport.eventbus_transport import ClientEvent

def on_event(event: ClientEvent, data: dict):
    if event == ClientEvent.CONNECTED:
        logger.info("Connected to RabbitMQ")
    elif event == ClientEvent.DISCONNECTED:
        logger.warning(f"Disconnected: {data.get('reason')}")
    elif event == ClientEvent.RECONNECTING:
        logger.info("Attempting to reconnect...")
    elif event == ClientEvent.ERROR:
        logger.error(f"Error: {data.get('error')}")

transport.register_event_handler(on_event)
```

### Message Flow

```
1. Client sends ProcessStartRequest
   └── Publish to: hub.process.start
       └── RabbitMQ routes to Server queue

2. Server sends ProcessStartResponse
   └── Publish to: panel.{panel_id}.response
       └── RabbitMQ routes to Client queue

3. Server broadcasts ProcessRestartNotify
   └── Publish to: hub.restart.notify
       └── RabbitMQ routes to ALL client queues
```

## Consequences

### Positive

- **Network flexibility**: Works across NAT, firewalls, geographic locations
- **Message persistence**: Messages survive broker restarts and network outages
- **Auto-reconnect**: Clients automatically reconnect after disconnection
- **Management UI**: RabbitMQ Management Plugin provides web-based monitoring
- **Proven technology**: RabbitMQ is battle-tested in production environments
- **Existing integration**: EventBusClient library already exists and is tested
- **Scalability**: RabbitMQ supports clustering for high availability

### Negative

- **Infrastructure requirement**: Requires running RabbitMQ server
- **Additional complexity**: More moving parts than ZMQ
- **Latency**: Higher latency than direct ZMQ connections
- **Dependency**: Requires EventBusClient package

### Neutral

- **Alternative to ZMQ**: Not a replacement; use ZMQ for local, EventBus for distributed
- **Configuration**: Requires RabbitMQ connection parameters
- **Docker-friendly**: Easy to run RabbitMQ in Docker for development

## Alternatives Considered

### 1. Apache Kafka (Rejected)

Distributed streaming platform with high throughput.

Rejected because:
- Overkill for ProcessHub's message patterns (not streaming data)
- Higher operational complexity
- No existing Python library integration in the project
- Designed for high-throughput streaming, not request/response

### 2. Redis Pub/Sub (Rejected)

In-memory data store with pub/sub capability.

Rejected because:
- No message persistence (messages lost if no subscriber)
- No built-in auto-reconnect
- Limited routing capabilities
- Not designed as primary message broker

### 3. MQTT (Deferred)

Lightweight IoT messaging protocol.

Deferred because:
- Would require new library integration
- Less feature-rich than RabbitMQ
- Better suited for IoT sensors than process management
- May consider for future embedded/IoT use cases

### 4. ZeroMQ over TCP (Rejected)

Using ZMQ with TCP transport across networks.

Rejected because:
- No built-in message persistence
- NAT traversal issues
- No central broker for management
- Subscription management complexity across networks

## References

- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)
- [RabbitMQ Topic Exchange](https://www.rabbitmq.com/tutorials/tutorial-five-python.html)
- [EventBusClient Repository](https://github.com/test-fullautomation/python-rabbitmq-messagebus)
- [AMQP Protocol](https://www.amqp.org/)
- Source: `ProcessHub/transport/eventbus_transport.py`
