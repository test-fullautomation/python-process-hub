# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the python-process-hub project.

ADRs document important architectural decisions made during the development of the project, along with their context, rationale, and consequences.

## Index

| ADR | Title | Status | Date | Author | Reviewer |
|-----|-------|--------|------|--------|----------|
| [ADR-001](001-lock-based-operation-serialization.md) | Lock-Based Operation Serialization vs Flag-Based Rollback | Accepted | 2026-01-16 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-002](002-separation-of-core-logic-and-runtime.md) | Separation of Core Logic and Runtime | Accepted | 2026-01-16 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-003](003-pluggable-transport-layer.md) | Pluggable Transport Layer | Accepted | 2026-01-16 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-004](004-restart-state-machine.md) | Restart Coordination as Explicit State Machine | Accepted | 2026-01-16 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-005](005-normalized-process-representation.md) | Normalized Process Representation with Typed State | Accepted | 2026-01-16 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-006](006-typed-protocol-messages.md) | Typed Protocol Messages with Versioning | Accepted | 2026-01-16 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-007](007-decoupled-ui-via-hub-view.md) | Decoupled UI via HubView Protocol | Accepted | 2026-01-16 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-008](008-pluggable-process-executor.md) | Pluggable Process Executor | Accepted | 2026-01-16 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-009](009-tcp-keepalive-for-crash-detection.md) | TCP Keepalive for Connection Health Monitoring | Accepted | 2026-01-21 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-010](010-server-shutdown-notification.md) | Server Shutdown Notification Protocol | Accepted | 2026-01-21 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-011](011-hub-reset-without-restart.md) | Hub Reset Without Server Restart | Accepted | 2026-01-21 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-012](012-strategy-pattern-for-extensibility.md) | Strategy Pattern for Core Extensibility | Proposed | 2026-01-22 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-013](013-fastapi-for-web-dashboard.md) | FastAPI for Web Dashboard | Accepted | 2026-01-15 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-014](014-eventbus-transport-with-rabbitmq.md) | EventBus Transport with RabbitMQ | Accepted | 2026-01-22 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-015](015-process-ownership-model.md) | Process Ownership Model (Reference Counting) | Accepted | 2026-01-22 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-016](016-immutable-state-snapshots.md) | Immutable State Snapshots for UI | Accepted | 2026-01-22 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-017](017-fleet-orchestrator-overlay-pattern.md) | Fleet Orchestrator as Overlay Pattern | Accepted | 2026-02-06 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-018](018-heartbeat-based-hub-health-detection.md) | Heartbeat-Based Hub Health Detection | Accepted | 2026-02-06 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-019](019-fleet-command-routing-through-orchestrator.md) | Fleet Command Routing Through Orchestrator | Accepted | 2026-02-06 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |
| [ADR-020](020-fleet-frozen-state-snapshots.md) | Fleet Frozen State Snapshots | Accepted | 2026-02-06 | Nguyen Huynh Tri Cuong | Nguyen Huynh Tri Cuong |

## Summary of Design Decisions

### Core Architecture (ADR-001, ADR-002)

The system is built on two fundamental principles:

1. **Lock-Based Serialization** (ADR-001): Process operations are serialized using a mutex lock instead of flag-based coordination, eliminating race conditions and ensuring exception safety.

2. **Layered Architecture** (ADR-002): The system is separated into three layers:
   - **Core Layer**: Pure business logic with no I/O knowledge
   - **Transport Layer**: Pluggable message transport
   - **Runtime Layer**: Thin adapter wiring components together

### Pluggability (ADR-003, ADR-007, ADR-008, ADR-014)

Key components are designed as pluggable interfaces:

| Component | Interface | Implementations |
|-----------|-----------|-----------------|
| Transport | `TransportBase` | ZmqTransport, EventBusTransport, InMemoryTransport |
| View | `HubView` | ConsoleView, WebView, NullView |
| Executor | `ProcessExecutor` | SimpleExecutor, MockExecutor, WindowsExecutor |

**EventBus Transport (ADR-014)**: RabbitMQ-based transport for distributed deployments across networks, with auto-reconnect and message persistence.

### State Management (ADR-004, ADR-005, ADR-015, ADR-016)

1. **Restart State Machine** (ADR-004): Restart coordination is modeled as an explicit FSM with states: IDLE → DETECTING → NOTIFYING → AWAITING_ACK → RESTARTING → DONE

2. **Typed Process State** (ADR-005): Process state uses enums (`ProcessState`) and dataclasses (`ProcessInfo`) instead of mixed-type dictionaries.

3. **Process Ownership Model** (ADR-015): Reference counting allows multiple panels to share processes. Process stops only when all requesters release it.

4. **Immutable Snapshots** (ADR-016): UI receives frozen dataclass copies of state, enabling lock-free rendering without race conditions.

### Protocol Design (ADR-006)

Protocol messages are typed dataclasses with:
- Consistent field naming
- Built-in versioning
- Self-documenting schema
- IDE autocomplete support

### Operational Resilience (ADR-009, ADR-010, ADR-011)

Features for production reliability:

| Feature | ADR | Description |
|---------|-----|-------------|
| Crash Detection | ADR-009 | TCP keepalive detects dead server in ~25 seconds |
| Graceful Shutdown | ADR-010 | Clients notified before server stops/resets |
| Hub Reset | ADR-011 | Clear all state without restarting server |

### Extensibility (ADR-012)

The core logic uses the **Strategy Pattern** for customization rather than making the entire core pluggable:

| Strategy | Purpose | Default Implementation |
|----------|---------|------------------------|
| `RestartStrategy` | Control restart behavior | `ImmediateRestartStrategy` |
| `HealthCheckStrategy` | Control health monitoring | `DefaultHealthCheckStrategy` |
| `NotificationStrategy` | Control client notifications | `DefaultNotificationStrategy` |

This approach provides:
- **Focused extensibility**: Customize specific behaviors without rewriting orchestration
- **Type safety**: Protocol classes ensure implementations are complete
- **Composability**: Mix and match different strategies
- **Backward compatibility**: Default strategies maintain existing behavior

### Web Dashboard (ADR-013)

**FastAPI** was chosen for the web dashboard because:

| Requirement | FastAPI Solution |
|-------------|------------------|
| Async support | Native async/await |
| API documentation | Automatic OpenAPI/Swagger |
| Type validation | Pydantic models |
| Performance | Built on Starlette (high performance) |
| Embedded deployment | Runs with Uvicorn in background thread |

Alternatives considered: Flask, Django REST, Tornado, Starlette, plain HTTP server.

### Fleet Orchestrator (ADR-017, ADR-018, ADR-019, ADR-020)

The Fleet Orchestrator coordinates multiple ProcessHub instances across machines:

| Feature | ADR | Description |
|---------|-----|-------------|
| Overlay Pattern | ADR-017 | Fleet is an additive layer, no core modifications |
| Health Detection | ADR-018 | Heartbeat-based hub liveness monitoring |
| Command Routing | ADR-019 | Centralized command flow through orchestrator |
| Fleet Snapshots | ADR-020 | Immutable snapshots for fleet state queries |

Key design choices:
- **Sidecar pattern**: HubAgent runs alongside ProcessHubServer, using only public APIs
- **Graceful degradation**: If orchestrator fails, local hubs continue working independently
- **Push-based health**: Hubs send heartbeats; orchestrator detects absence passively
- **Central routing**: All fleet commands pass through orchestrator for validation and audit

See [Fleet Orchestrator Plan](../FLEET_ORCHESTRATOR.md) for full architecture details.

## Design Principles

These ADRs collectively establish the following design principles:

1. **Testability**: Every component can be tested in isolation using mocks/stubs
2. **Type Safety**: Enums and dataclasses provide compile-time error detection
3. **Separation of Concerns**: Each layer/component has a single responsibility
4. **Explicit State**: State machines and immutable snapshots make state visible
5. **Thread Safety**: Single-lock patterns prevent race conditions

## ADR Template

When creating a new ADR, copy the template file [000-template.md](000-template.md) and follow the instructions inside.

### Quick Reference

```markdown
# ADR-XXX: Title

## Status
[Proposed | Accepted | Deprecated | Superseded]

## Date
YYYY-MM-DD

## Author
Name (Department/Team)

## Reviewer
- Reviewer Name (Department/Team)

## History

| Date | Version | Description |
|------|---------|-------------|
| YYYY-MM-DD | 1.0 | Initial version |

## Context
What is the issue that we're seeing that is motivating this decision?

## Decision
What is the change that we're proposing and/or doing?

## Consequences

### Positive
What becomes easier?

### Negative
What becomes more difficult?

### Neutral
What other changes are required?

## Alternatives Considered
What other options were evaluated and why were they rejected or deferred?

## References
Links to relevant documentation, patterns, or source code.
```

## References

- [ADR GitHub Organization](https://adr.github.io/)
- [Michael Nygard's ADR Article](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [Documenting Architecture Decisions](https://www.thoughtworks.com/radar/techniques/lightweight-architecture-decision-records)
