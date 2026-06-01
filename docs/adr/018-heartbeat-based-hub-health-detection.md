# ADR-018: Heartbeat-Based Hub Health Detection

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

The Fleet Orchestrator needs to know which hubs are alive and responsive. When a hub
machine crashes, loses network connectivity, or the ProcessHub process terminates, the
orchestrator must detect this and take appropriate action (mark offline, notify operators,
reroute work).

### Detection Requirements

| Requirement | Value |
|-------------|-------|
| Detection time | < 30 seconds for hard failure |
| False positive rate | Near zero (don't mark healthy hubs offline) |
| Network overhead | Minimal (hubs may be on slow links) |
| Scalability | Support 50+ hubs |
| Transport agnostic | Work over any TransportBase implementation |

### Hub Health States

```
  ┌────────┐    heartbeat received    ┌──────────┐
  │ ONLINE │◄────────────────────────│ DEGRADED │
  └───┬────┘                          └─────┬────┘
      │                                     │
      │  1 missed heartbeat                 │  timeout exceeded
      │                                     │
      ▼                                     ▼
  ┌──────────┐                         ┌─────────┐
  │ DEGRADED │────────────────────────►│ OFFLINE │
  └──────────┘    timeout exceeded     └─────────┘
```

## Decision

We will use a **push-based heartbeat** mechanism where each HubAgent periodically sends
`HubAnnounce` messages. The orchestrator passively tracks `last_seen` timestamps and
detects failures by timeout.

### Heartbeat Protocol

```python
# HubAgent sends periodic heartbeats
class HubAgent:
    def _heartbeat_loop(self):
        while self._running:
            self._transport.send(
                FleetTopics.HUB_ANNOUNCE,
                HubAnnounce(
                    hub_id=self._hub_id,
                    hub_name=self._hub_name,
                    host=self._host,
                    capabilities=self._capabilities,
                ),
            )
            time.sleep(self._heartbeat_interval)
```

```python
# Orchestrator tracks heartbeats passively
class FleetOrchestrator:
    def _on_hub_announce(self, data: dict):
        hub_id = data["hub_id"]
        self._registry.update_heartbeat(hub_id)
        if not self._registry.is_registered(hub_id):
            self._registry.register(hub_id, data)
```

### Health Check Logic

```python
class HubRegistry:
    def check_health(self, timeout_seconds: float) -> list[str]:
        """Check for timed-out hubs. Called by orchestrator tick()."""
        now = time.time()
        timed_out = []
        with self._lock:
            for hub_id, info in self._hubs.items():
                elapsed = now - info.last_seen
                if elapsed > timeout_seconds:
                    if info.status != "offline":
                        info.status = "offline"
                        timed_out.append(hub_id)
                elif elapsed > timeout_seconds / 2:
                    info.status = "degraded"
                else:
                    info.status = "online"
        return timed_out
```

### Default Timing

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `heartbeat_interval` | 5 seconds | Frequent enough for quick detection, low overhead |
| `status_interval` | 10 seconds | Detailed reports less frequently than heartbeats |
| `health_timeout` | 30 seconds | 6 missed heartbeats before offline (robust against jitter) |
| `tick_interval` | 5 seconds | Orchestrator health check frequency |

### Detection Timeline

```
t=0s    Last heartbeat received
t=5s    Expected heartbeat missed (hub may be slow)
t=15s   Status: DEGRADED (3 missed heartbeats, > timeout/2)
t=30s   Status: OFFLINE (6 missed heartbeats, > timeout)
        → Orchestrator broadcasts HUB_OFFLINE
```

## Consequences

### Positive

- **Simple implementation** - No complex protocol negotiation
- **Passive detection** - Orchestrator doesn't need to actively probe hubs
- **Transport agnostic** - Works over any message transport
- **Configurable sensitivity** - Adjust intervals per deployment
- **Self-healing** - Hub comes back online automatically when heartbeats resume
- **Low overhead** - Small heartbeat messages every few seconds

### Negative

- **Detection delay** - Up to `health_timeout` seconds to detect failure (30s default)
- **Network sensitivity** - Transient network issues can cause false DEGRADED states
- **Clock dependency** - Relies on monotonic clocks for timeout calculation
- **No partial failure** - Cannot distinguish "hub process crashed" from "network down"

### Neutral

- **Heartbeat overhead** - ~12 messages/minute per hub (negligible for RabbitMQ)
- **Registry memory** - One entry per hub with timestamps (negligible)
- **Tick frequency** - Orchestrator tick adds periodic CPU usage (negligible)

## Alternatives Considered

### 1. Pull-Based Health Check / Active Probing (Rejected)

Orchestrator periodically pings each hub and waits for response:

```python
class FleetOrchestrator:
    def _health_check(self):
        for hub_id in self._registry.get_all_hub_ids():
            self._transport.send(FleetTopics.HEALTH_PING, {"hub_id": hub_id})
            # Wait for HEALTH_PONG within timeout
```

Rejected because:
- More complex protocol (request-response vs fire-and-forget)
- Orchestrator must track outstanding pings
- Doesn't scale as well (orchestrator does O(N) work per tick)
- Hub agent is simpler with push-only design

### 2. TCP Connection Monitoring (Rejected)

Use the transport layer's TCP connection state to detect failures:

```python
# Detect when RabbitMQ connection to hub drops
transport.on_connection_lost(hub_id, callback)
```

Rejected because:
- Transport-specific (only works with connection-oriented transports)
- Requires modifying TransportBase interface
- InMemoryTransport has no connections (breaks testing)
- ZMQ PUB/SUB is connectionless

### 3. Lease-Based Registration (Deferred)

Hubs acquire a time-limited lease that must be renewed:

```python
# Hub must renew lease before expiry
lease = orchestrator.acquire_lease(hub_id, ttl=30)
# If not renewed, hub is automatically deregistered
```

Deferred because:
- More complex than simple heartbeat
- Requires orchestrator to actively manage leases
- Good for strict consistency requirements (not needed for monitoring)
- Could be added later as `HubRegistry` enhancement

## References

- [Heartbeat Pattern](https://microservices.io/patterns/observability/health-check-api.html)
- [Failure Detection in Distributed Systems](https://www.cs.cornell.edu/projects/Quicksilver/public_pdfs/SWIM.pdf)
- Related: ADR-009 (TCP Keepalive for Connection Health Monitoring)
- Related: ADR-017 (Fleet Orchestrator as Overlay Pattern)
- Source: `ProcessHub/fleet/hub_agent.py` - heartbeat loop
- Source: `ProcessHub/fleet/hub_registry.py` - health check logic
- Source: `ProcessHub/fleet/orchestrator.py` - tick and health broadcast
