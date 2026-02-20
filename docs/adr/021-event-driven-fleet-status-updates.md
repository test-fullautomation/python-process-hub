# ADR-021: Event-Driven Fleet Status Updates via Local Transport Subscription

## Status

Accepted

## Date

2026-02-18

## Author

Nguyen Huynh Tri Cuong (MS/EMC51)

## Reviewer

- Nguyen Huynh Tri Cuong (MS/EMC51)

## History

| Date | Version | Description |
|------|---------|-------------|
| 2026-02-18 | 1.0 | Initial version |

## Context

The Fleet Orchestrator (ADR-017) uses a **sidecar pattern**: a `HubAgent` sits alongside
each `ProcessHubServer` and periodically reports status to the central `FleetOrchestrator`.

Prior to this change, the orchestrator learned about process state changes through two
mechanisms only:

1. **Periodic status reports** (`_status_loop`, every 10 seconds) - polls
   `server.core.get_state_snapshot()`
2. **Post-command reports** - sends an immediate report after handling fleet commands
   (start/stop/reset)

### The Gap

When a panel (GUI/CLI) starts or stops processes **directly** through the local transport
(not via a fleet command), or when a process **crashes** and the restart state machine
activates, the orchestrator does not learn about the change until the next 10-second polling
cycle.

```
Panel starts "worker_a"  ─────────────────►  Orchestrator still shows 0 processes
        t=0s                                         │
                                                     │  up to 10s delay
                                                     │
                                          Orchestrator learns about worker_a
                                                   t=10s
```

This 10-second blind window is problematic for:
- **Web dashboards** that display real-time fleet state
- **CI/CD scripts** that wait for process readiness after issuing local commands
- **Crash visibility** where operators need to see failures immediately

### Why Not Modify the Core?

ADR-017 established that the fleet is a **pure overlay** with no modifications to `core/`,
`runtime/`, or `transport/`. The server already publishes state-change messages on its local
transport (`START_RESPONSE`, `STOP_RESPONSE`, `RESTART_NOTIFY`, `RESTART_DONE`) for panel
consumption. The HubAgent can subscribe to these same messages without any core changes.

## Decision

We will add an **optional `server_transport` parameter** to `HubAgent.__init__()`. When
provided, the agent subscribes to the server's local transport topics and sends immediate
fleet status reports on state changes.

### Subscribed Topics

| Local Topic | Trigger |
|-------------|---------|
| `Topics.START_RESPONSE` | Process started (or start failed) |
| `Topics.STOP_RESPONSE` | Process stopped |
| `Topics.RESTART_NOTIFY` | Crash detected, restart beginning |
| `Topics.RESTART_DONE` | Restart completed (success or failure) |

### Event Handler

```python
def _on_local_state_change(self, data: Any) -> None:
    now = time.time()
    if now - self._last_event_report < self._event_debounce:
        return  # Debounce: skip if < 0.5s since last report

    self._last_event_report = now
    self._send_status_report()  # Same report as periodic loop
```

### Debounce Strategy

When multiple state changes fire in rapid succession (e.g., starting 5 processes at once),
we avoid flooding the fleet transport with redundant reports. A simple timestamp-based
minimum interval is used:

```
Event 1 (t=0.0s)  → Report sent, _last_event_report = 0.0
Event 2 (t=0.1s)  → Skipped (0.1 < 0.5 debounce)
Event 3 (t=0.2s)  → Skipped (0.2 < 0.5 debounce)
Event 4 (t=0.3s)  → Skipped (0.3 < 0.5 debounce)
Event 5 (t=0.6s)  → Report sent, _last_event_report = 0.6
```

The 0.5-second debounce window was chosen because:
- Fast enough for real-time dashboards (human perception threshold is ~100ms)
- Effectively collapses batch operations into 1-2 reports
- Periodic polling (10s) still acts as a safety net for any events missed during debounce

### Message Flow

```
Panel ──► Server ──► Local Transport ──► HubAgent ──► Fleet Transport ──► Orchestrator
              │                              │
              │  START_RESPONSE              │  HUB_STATUS_REPORT
              │  STOP_RESPONSE               │  (immediate, debounced)
              │  RESTART_NOTIFY              │
              │  RESTART_DONE                │
```

### Backward Compatibility

The `server_transport` parameter is **optional** (default: `None`). When omitted:
- No local subscriptions are created
- Agent operates in polling-only mode (original behavior)
- No behavioral change for existing deployments

```python
# Existing code continues to work unchanged
agent = HubAgent(server=server, transport=fleet_transport, hub_id="hub-1")

# New code opts in to event-driven updates
agent = HubAgent(
    server=server,
    transport=fleet_transport,
    hub_id="hub-1",
    server_transport=local_transport,  # NEW: enables event-driven updates
)
```

### Overlay Pattern Compliance

This change **preserves the overlay principle** (ADR-017):

| Rule | Compliance |
|------|------------|
| No modifications to `core/` | The HubAgent subscribes to messages the server already publishes |
| No modifications to `runtime/server.py` | Server is unaware of the subscription |
| No modifications to `transport/` | Uses existing `register_handler()` API |
| Fleet code stays in `fleet/` | Only `fleet/hub_agent.py` is modified |
| Server public API only | `register_handler()` is a public TransportBase method |

## Consequences

### Positive

- **Near-real-time visibility** - Orchestrator learns about state changes within ~0.5s
  instead of up to 10s
- **Zero core modifications** - Subscribes to existing local transport messages
- **Backward compatible** - Optional parameter, existing deployments unaffected
- **Crash visibility** - Orchestrator sees `RESTART_NOTIFY` immediately when a process
  crashes, before the restart even completes
- **Dashboard responsiveness** - Web dashboards backed by fleet state update in near
  real-time for locally-initiated changes
- **Debounce prevents flooding** - Batch operations produce 1-2 reports, not N

### Negative

- **Dual transport subscription** - HubAgent now holds references to two transports
  (fleet + local), increasing coupling surface slightly
- **Debounce may miss intermediate states** - If process A starts and process B stops
  within 0.5s, the first report won't reflect B's stop (but the next report or periodic
  poll will)
- **Handler ordering** - The agent's handler runs alongside panel handlers on the same
  local transport; a slow `_send_status_report()` could delay panel message delivery
  (mitigated by the lightweight nature of the report)

### Neutral

- **Polling still runs** - The 10-second `_status_loop` continues as a safety net; it is
  not replaced
- **No new message types** - Reuses existing `HUB_STATUS_REPORT` on the fleet transport
- **No new threads** - The handler runs synchronously on the local transport's dispatch
  thread

## Alternatives Considered

### 1. Core Event Hook System (Deferred)

Add a plugin/hook API to `ProcessHubCore`:

```python
core.register_hook("on_state_changed", fleet_callback)
```

Deferred because:
- Requires modifying core (violates ADR-017 overlay principle)
- A good general extensibility feature but out of scope for this change
- Already noted as a future option in ADR-017 and ADR-012
- Local transport subscription achieves the same result without core changes

### 2. Shorter Polling Interval (Rejected)

Reduce `status_interval` from 10s to 1s:

Rejected because:
- Increases fleet transport traffic by 10x for all hubs
- Still has up to 1s delay (not truly event-driven)
- Wastes resources when no state changes occur
- Doesn't scale well with many hubs

### 3. Threading-Based Debounce with Timer (Rejected)

Use a `threading.Timer` to delay the report by 0.5s after the last event:

```python
def _on_local_state_change(self, data):
    if self._debounce_timer:
        self._debounce_timer.cancel()
    self._debounce_timer = threading.Timer(0.5, self._send_status_report)
    self._debounce_timer.start()
```

Rejected because:
- Adds **0.5s latency** to every single event (even isolated ones)
- More complex (timer lifecycle, thread safety, cancellation)
- The timestamp approach sends the **first** event immediately and only debounces
  subsequent rapid events, giving better latency for isolated changes

## References

- Related: ADR-017 (Fleet Orchestrator as Overlay Pattern) - addresses the "Status polling"
  limitation listed in its Negative consequences
- Related: ADR-018 (Heartbeat-Based Hub Health Detection) - complements heartbeats with
  event-driven status
- Related: ADR-012 (Strategy Pattern for Extensibility) - future hook system alternative
- Diagram: `docs/diagrams/sequence_fleet_event_driven.puml`
- Source: `ProcessHub/fleet/hub_agent.py` - `_on_local_state_change()`, `server_transport`
- Source: `ProcessHub/runtime/server.py` - `Topics` enum, `_send_messages()`
- Tests: `tests/unit/test_hub_agent.py` - `TestHubAgentEventDriven`
