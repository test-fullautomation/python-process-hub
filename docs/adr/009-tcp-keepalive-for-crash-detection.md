# ADR-009: TCP Keepalive for Connection Health Monitoring

## Status

Accepted

## Date

2026-01-21

## Author

Nguyen Huynh Tri Cuong (MS/EMC51)

## Reviewer

- Nguyen Huynh Tri Cuong (MS/EMC51)

## History

| Date | Version | Description |
|------|---------|-------------|
| 2026-01-21 | 1.0 | Initial version |

## Context

When a ProcessHub server crashes unexpectedly (process killed, power failure, network disconnect), it cannot send any shutdown notification to clients. This leaves clients in a problematic state:

1. **Clients remain "registered"**: They believe they're still connected
2. **Requests hang**: Any new requests wait indefinitely for responses
3. **No automatic recovery**: Clients don't know to reconnect

```
Normal Shutdown:
  Server → [SHUTDOWN_NOTIFY] → Client → handles gracefully

Crash Scenario:
  Server ──X (dead)
  Client → [REQUEST] → ... waiting forever ...
```

### The Problem with Application-Level Heartbeat

One solution is application-level heartbeat where clients periodically ping the server:

```python
# Application heartbeat approach
while running:
    send_ping()
    if not receive_pong(timeout=5):
        handle_server_down()
    sleep(5)
```

However, this has drawbacks:
- **Thread overhead**: Requires dedicated heartbeat thread per client
- **Network overhead**: Constant ping/pong traffic even when idle
- **Latency concerns**: Some users worried about performance impact

## Decision

We will use **TCP Keepalive** at the socket level to detect dead connections. This is configured via `TcpKeepaliveConfig` dataclass:

```python
@dataclass
class TcpKeepaliveConfig:
    """TCP keepalive configuration for ZMQ sockets."""

    enabled: bool = True
    idle: int = 10      # Seconds before first probe
    interval: int = 5   # Seconds between probes
    count: int = 3      # Failed probes before dead

    def detection_time(self) -> float:
        """Detection time = idle + (interval × count)"""
        return self.idle + (self.interval * self.count)
```

### How TCP Keepalive Works

```
Client                          Server (crashed)
   │                                 X
   │──── [idle=10s passes] ─────────►
   │──── TCP KEEPALIVE probe 1 ─────► (no response)
   │──── [interval=5s] ─────────────►
   │──── TCP KEEPALIVE probe 2 ─────► (no response)
   │──── [interval=5s] ─────────────►
   │──── TCP KEEPALIVE probe 3 ─────► (no response)
   │
   └──── Connection marked DEAD (after 25 seconds)
```

### Configuration in ZmqTransport

```python
from ProcessHub.transport import ZmqTransport, TcpKeepaliveConfig

# Default: 25 second detection (10 + 5×3)
transport = ZmqTransport(start_broker=False)

# Faster detection: 13 seconds (5 + 2×4)
transport = ZmqTransport(
    start_broker=False,
    keepalive=TcpKeepaliveConfig(idle=5, interval=2, count=4),
)

# Disable keepalive (not recommended)
transport = ZmqTransport(
    start_broker=False,
    keepalive=TcpKeepaliveConfig(enabled=False),
)
```

### Socket Configuration

Applied to both PUB and SUB sockets:

```python
def _apply_keepalive(self, socket: zmq.Socket) -> None:
    if not self._keepalive.enabled:
        socket.setsockopt(zmq.TCP_KEEPALIVE, 0)
        return

    socket.setsockopt(zmq.TCP_KEEPALIVE, 1)
    socket.setsockopt(zmq.TCP_KEEPALIVE_IDLE, self._keepalive.idle)
    socket.setsockopt(zmq.TCP_KEEPALIVE_INTVL, self._keepalive.interval)
    socket.setsockopt(zmq.TCP_KEEPALIVE_CNT, self._keepalive.count)
```

## Consequences

### Positive

1. **Zero application overhead**: Handled by OS kernel, no extra threads
2. **No network overhead when active**: Only probes during idle periods
3. **Configurable detection time**: Users can tune for their needs
4. **Works transparently**: No changes to application code required
5. **Cross-platform**: Supported on Linux, Windows, macOS

### Negative

1. **Not instant detection**: Minimum ~10-25 seconds vs instant with heartbeat
2. **Firewall issues**: Some firewalls/NAT may drop keepalive packets
3. **OS-level tuning**: Some environments may override socket settings
4. **PUB/SUB limitation**: Detection happens on next send/recv, not proactively

### Neutral

1. **Default enabled**: Keepalive is on by default with 25s detection
2. **Complements shutdown notification**: Works alongside `ServerShutdownNotify` for graceful cases

## Alternatives Considered

### 1. Application-Level Heartbeat (Deferred)

Client sends periodic PING, server responds with PONG:

```python
# Client side
def heartbeat_loop():
    while running:
        send("HEARTBEAT_PING", {})
        if not wait_for_pong(timeout=5):
            on_server_disconnected()
        sleep(5)
```

Deferred because:
- User concern about performance impact
- Adds complexity (new message types, dedicated thread)
- TCP keepalive sufficient for most use cases

May be added later if faster detection (<5s) is required.

### 2. ZMQ Socket Monitoring (Rejected)

Use ZMQ's built-in socket monitor API:

```python
monitor = socket.get_monitor_socket(zmq.EVENT_DISCONNECTED)
```

Rejected because:
- `EVENT_DISCONNECTED` only fires for explicit close, not crashes
- PUB/SUB pattern doesn't have persistent connections in traditional sense
- Unreliable detection across different ZMQ versions

### 3. No Crash Detection (Rejected)

Rely solely on request timeouts:

```python
response = client.request(timeout=30)
if response is None:
    # Server might be down
```

Rejected because:
- Only detects on active requests
- Idle clients never know server is down
- Poor user experience

## References

- [TCP Keepalive HOWTO](https://tldp.org/HOWTO/TCP-Keepalive-HOWTO/)
- [ZMQ Socket Options](http://api.zeromq.org/4-2:zmq-setsockopt)
- Source: `ProcessHub/transport/zmq_transport.py`
