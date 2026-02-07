# ADR-017: Fleet Orchestrator as Overlay Pattern

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

ProcessHub manages processes on a single machine. In production environments (HIL/SIL test
farms, CI/CD pipelines), many machines each run their own ProcessHub instance. Operators
need fleet-wide visibility, centralized commands, and cross-hub health monitoring.

### The Problem

There are two fundamental approaches to adding multi-hub coordination:

1. **Modify core** - Add fleet awareness into `ProcessHubCore`, `ProcessHubServer`, and
   the transport layer
2. **Add an overlay** - Create a separate fleet layer that observes and commands existing
   hubs without modifying them

### Constraints

- Existing hubs must continue working independently
- No breaking changes to the core, runtime, or transport APIs
- Fleet coordination is optional - not all deployments need it
- Must be possible to add/remove fleet without affecting local operation

## Decision

We will implement the Fleet Orchestrator as a **pure overlay layer** in `ProcessHub/fleet/`.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Fleet Layer (NEW)                       │
│  ┌──────────────┐  ┌───────────┐  ┌───────────────────┐ │
│  │ Orchestrator │  │ HubAgent  │  │ FleetClient       │ │
│  │ (central)    │  │ (sidecar) │  │ (external API)    │ │
│  └──────┬───────┘  └─────┬─────┘  └───────────────────┘ │
│         │                │                               │
│         │    EventBus (fleet.* topics)                    │
│         │                │                               │
├─────────┴────────────────┴───────────────────────────────┤
│              Existing Layers (UNCHANGED)                   │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐              │
│  │   Core   │  │  Runtime  │  │ Transport │              │
│  └──────────┘  └───────────┘  └───────────┘              │
└───────────────────────────────────────────────────────────┘
```

### Key Rules

1. **No modifications** to `core/`, `runtime/`, `transport/` directories
2. **Minimal modifications** to `ProcessHub/__init__.py` (optional imports only)
3. Fleet uses **its own transport instance** with `fleet.` routing key prefix
4. HubAgent reads server state via **existing public APIs** (`server.core.get_state_snapshot()`)
5. HubAgent sends commands via **existing public APIs** (`server.core.handle_start_request()`)
6. All fleet code lives in `ProcessHub/fleet/` package

### HubAgent Interaction with Server

The HubAgent is a sidecar that sits alongside `ProcessHubServer`. It does NOT inherit from
or modify the server. It uses only the public API:

```python
class HubAgent:
    def __init__(self, server: ProcessHubServer, fleet_transport: TransportBase, ...):
        self._server = server
        self._fleet_transport = fleet_transport  # Separate transport for fleet

    def _collect_status(self):
        # Uses EXISTING public API - no modifications needed
        snapshot = self._server.core.get_state_snapshot()
        return HubStatusReport(
            process_count=len(snapshot.processes),
            connection_count=len(snapshot.connections),
            ...
        )

    def _handle_start_command(self, process_list):
        # Uses EXISTING public API
        request = ProcessStartRequest(panel_id="fleet", process_list=process_list)
        messages = self._server.core.handle_start_request(request)
        # Fleet handles the response, doesn't need to send via local transport
```

### Optional Dependency Pattern

Fleet follows the same optional import pattern as ZMQ and EventBus transports:

```python
# In ProcessHub/__init__.py
try:
    from .fleet import FleetOrchestrator, HubAgent, FleetClient
    HAS_FLEET = True
except ImportError:
    HAS_FLEET = False
```

## Consequences

### Positive

- **Zero risk to existing functionality** - Core code is untouched
- **Independent deployment** - Fleet can be added to existing installations
- **Graceful degradation** - If orchestrator fails, local hubs continue working
- **Clean separation** - Fleet code is isolated in its own package
- **Easy removal** - Delete `ProcessHub/fleet/` to remove fleet completely
- **Independent versioning** - Fleet can evolve without core version bumps

### Negative

- **Limited integration depth** - Cannot intercept internal core events
- **Status polling** - HubAgent must poll `get_state_snapshot()` instead of subscribing
  to internal state changes
- **Separate transport** - Fleet needs its own transport instance (additional connection
  to RabbitMQ)
- **API surface dependency** - HubAgent depends on server public API stability

### Neutral

- **Additional process** - HubAgent runs as additional threads alongside the server
- **New message protocol** - Fleet defines its own messages (doesn't conflict with existing)
- **New package** - `ProcessHub/fleet/` is a new sub-package

## Alternatives Considered

### 1. Modify ProcessHubCore to Be Fleet-Aware (Rejected)

Add fleet coordination directly into the core:

```python
class ProcessHubCore:
    def __init__(self, ..., fleet_orchestrator=None):
        self._fleet = fleet_orchestrator
        # Emit fleet events on every state change
```

Rejected because:
- Violates single responsibility principle
- Adds complexity to well-tested core
- Makes fleet a hard dependency for testing
- Core changes affect all deployments, not just fleet users

### 2. ProcessHubServer Subclass (Rejected)

Create `FleetAwareServer(ProcessHubServer)`:

```python
class FleetAwareServer(ProcessHubServer):
    def _on_start_request(self, data):
        super()._on_start_request(data)
        self._notify_fleet(...)
```

Rejected because:
- Tight coupling to server internals
- Fragile to server refactoring
- Cannot add fleet to existing server instances
- Inheritance is the wrong relationship (fleet is not a type of server)

### 3. Event Hook System in Core (Deferred)

Add a hook/plugin system to ProcessHubCore:

```python
core.register_hook("on_process_started", fleet_callback)
core.register_hook("on_state_changed", fleet_callback)
```

Deferred because:
- Requires core modification (contradicts overlay principle)
- Good idea for future extensibility (see ADR-012 Strategy Pattern)
- Can be added later without affecting fleet overlay design
- Current polling approach is sufficient for fleet update frequency

## References

- [Sidecar Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/sidecar)
- [Ambassador Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/ambassador)
- Related: ADR-002 (Separation of Core Logic and Runtime)
- Related: ADR-003 (Pluggable Transport Layer)
- Related: ADR-014 (EventBus Transport with RabbitMQ)
- Source: `ProcessHub/fleet/` (entire fleet package)
- Source: `ProcessHub/fleet/hub_agent.py` (sidecar implementation)
