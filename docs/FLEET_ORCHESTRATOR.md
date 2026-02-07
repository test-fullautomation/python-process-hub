# Fleet Orchestrator - Design & Implementation Plan

## Executive Summary

The **Fleet Orchestrator** is an optional overlay layer for ProcessHub that coordinates
multiple ProcessHub instances across PCs from a central point. It enables fleet-wide
visibility, centralized command routing, and health monitoring without modifying any
existing core, runtime, or transport code.

## The Problem We Solve

### Single-Hub Limitation

ProcessHub excels at managing processes on a single machine. But in production
environments - HIL/SIL test farms, CI/CD pipelines, distributed labs - there are
many machines, each running its own ProcessHub:

```
 PC-1 (ProcessHub)       PC-2 (ProcessHub)       PC-3 (ProcessHub)
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ worker_a (running)│  │ worker_c (running)│  │ worker_e (dead)  │
│ worker_b (stopped)│  │ worker_d (running)│  │ worker_f (running)│
└──────────────────┘  └──────────────────┘  └──────────────────┘
        ?                      ?                      ?
  No central view.   No cross-hub commands.   No fleet health check.
```

**Common issues without fleet coordination:**
- **No fleet visibility** - Operators must SSH into each machine to check status
- **No centralized control** - Starting/stopping processes requires per-machine scripts
- **No cross-hub health** - A dead hub goes unnoticed until tests fail
- **No single dashboard** - Monitoring requires opening N browser tabs
- **CI/CD complexity** - Pipelines need per-machine logic for each hub

### Fleet Orchestrator Approach

```
                     ┌──────────────────────┐
                     │  FleetOrchestrator   │  ← Central coordinator
                     │  (web dashboard +    │
                     │   REST API)          │
                     └──────────┬───────────┘
                                │
               EventBus (RabbitMQ) / fleet.* topics
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
   ┌──────▼───────┐     ┌──────▼───────┐     ┌──────▼───────┐
   │  HubAgent    │     │  HubAgent    │     │  HubAgent    │
   │  + Server    │     │  + Server    │     │  + Server    │
   │  (PC-1)      │     │  (PC-2)      │     │  (PC-3)      │
   └──────────────┘     └──────────────┘     └──────────────┘
```

**Fleet Orchestrator guarantees:**
- **Fleet-wide visibility** - Single dashboard for all hubs
- **Centralized commands** - Start/stop processes on any hub from one place
- **Health monitoring** - Detect offline hubs within seconds
- **Graceful degradation** - If orchestrator goes down, local hubs continue working
- **CI/CD integration** - Single FleetClient API for pipeline scripts

## Architecture

### Overlay Pattern

The fleet layer is a pure **overlay** - it adds coordination on top of existing
ProcessHub instances without modifying them. This is a critical design decision
(see [ADR-017](adr/017-fleet-orchestrator-overlay-pattern.md)).

```
┌─────────────────────────────────────────────────────┐
│                   Fleet Layer                        │  ← NEW (overlay)
│  ┌─────────────┐ ┌────────────┐ ┌───────────────┐   │
│  │ Orchestrator│ │ HubAgent   │ │ FleetClient   │   │
│  │ (central)   │ │ (per-hub)  │ │ (external API)│   │
│  └─────────────┘ └────────────┘ └───────────────┘   │
├─────────────────────────────────────────────────────┤
│                 Existing Layers                       │  ← UNCHANGED
│  ┌──────────┐ ┌───────────┐ ┌───────────┐           │
│  │   Core   │ │  Runtime  │ │ Transport │           │
│  │ (logic)  │ │ (wiring)  │ │ (ZMQ/EB)  │           │
│  └──────────┘ └───────────┘ └───────────┘           │
└─────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Role | Location |
|-----------|------|----------|
| **FleetOrchestrator** | Central coordinator - registry, health check, command routing | Central machine |
| **HubAgent** | Sidecar per ProcessHubServer - heartbeat, status, command handler | Each hub machine |
| **FleetClient** | External API for CI/CLI - status queries, batch commands | CI/CD runners, scripts |
| **HubRegistry** | Thread-safe hub tracking with health states | Inside Orchestrator |
| **FleetWebAPI** | Optional REST + WebSocket dashboard | Inside Orchestrator |

### Message Bus Communication

Fleet uses the existing EventBus (RabbitMQ) transport with a `fleet.` routing key prefix,
separate from local hub communication (`processhub.` prefix).
See [ADR-014](adr/014-eventbus-transport-with-rabbitmq.md) for EventBus details.

```
Local hub messages:    processhub.PROCESS_START_REQUEST
Fleet messages:        fleet.FLEET_HUB_ANNOUNCE
                       fleet.FLEET_COMMAND
                       fleet.FLEET_HUB_STATUS_REPORT
```

## Message Flows

### Hub Discovery

When a HubAgent starts, it announces itself to the orchestrator:

```
HubAgent (PC-1)                    FleetOrchestrator
     │                                    │
     │──── HUB_ANNOUNCE ────────────────►│  hub_id, name, host, capabilities
     │                                    │  registry.register(hub_id, info)
     │◄─── HUB_REGISTERED ──────────────│  success, fleet_id
     │                                    │
     │──── HUB_STATUS_REPORT ──────────►│  (periodic: process_count, etc.)
     │──── HUB_ANNOUNCE ────────────────►│  (periodic heartbeat)
     │                                    │
```

### Command Routing

Commands flow from FleetClient through the orchestrator to the target hub:

```
FleetClient           FleetOrchestrator           HubAgent (PC-2)
     │                       │                         │
     │── FLEET_COMMAND ────►│                         │
     │   (hub=PC-2,          │── FLEET_COMMAND ──────►│
     │    action=start)      │                         │  server.core.handle_start_request()
     │                       │                         │
     │                       │◄── COMMAND_RESULT ─────│  success=True
     │◄── COMMAND_RESULT ───│                         │
     │                       │                         │
```

### Health Check

The orchestrator detects offline hubs via heartbeat timeout:

```
HubAgent (PC-3)               FleetOrchestrator              FleetClient
     │                              │                              │
     │ (stops heartbeat -           │                              │
     │  network failure)            │                              │
     │                              │  tick(): check_health()      │
     │                              │  PC-3 last_seen > timeout    │
     │                              │  mark PC-3 OFFLINE           │
     │                              │                              │
     │                              │── HUB_OFFLINE ─────────────►│
     │                              │   (hub_id=PC-3)              │
```

## Module Design

### ProcessHub/fleet/models.py

Protocol messages extending `MessageBase` from `core/models.py`:

```python
# Fleet protocol messages (extend MessageBase for versioning + timestamps)
@dataclass
class HubAnnounce(MessageBase):
    hub_id: str = ""
    hub_name: str = ""
    host: str = ""
    capabilities: list[str] = field(default_factory=list)

@dataclass
class FleetCommand(MessageBase):
    command_id: str = ""
    hub_id: str = ""
    action: str = ""          # "start_process", "stop_process", "reset", "get_status"
    params: dict = field(default_factory=dict)

# Fleet frozen snapshots (for thread-safe fleet state queries)
@dataclass(frozen=True)
class HubSnapshot:
    hub_id: str
    hub_name: str
    host: str
    status: str               # "online", "degraded", "offline"
    process_count: int
    connection_count: int
    processes: tuple[str, ...]
    last_seen: float

@dataclass(frozen=True)
class FleetStateSnapshot:
    hubs: tuple[HubSnapshot, ...]
    total_hubs: int
    online_hubs: int
    total_processes: int
    timestamp: float
```

### ProcessHub/fleet/topics.py

```python
class FleetTopics(str, Enum):
    HUB_ANNOUNCE        = "FLEET_HUB_ANNOUNCE"
    HUB_REGISTERED      = "FLEET_HUB_REGISTERED"
    HUB_DEREGISTER      = "FLEET_HUB_DEREGISTER"
    HUB_STATUS_REPORT   = "FLEET_HUB_STATUS_REPORT"
    FLEET_STATUS_REQUEST = "FLEET_STATUS_REQUEST"
    FLEET_STATUS_RESPONSE= "FLEET_STATUS_RESPONSE"
    FLEET_COMMAND        = "FLEET_COMMAND"
    FLEET_COMMAND_RESULT = "FLEET_COMMAND_RESULT"
    HUB_ONLINE           = "FLEET_HUB_ONLINE"
    HUB_OFFLINE          = "FLEET_HUB_OFFLINE"
```

### ProcessHub/fleet/hub_registry.py

Thread-safe registry with health state tracking:

```python
class HubRegistry:
    def register(self, hub_id: str, info: HubAnnounce) -> bool
    def deregister(self, hub_id: str) -> bool
    def update_status(self, hub_id: str, report: HubStatusReport) -> None
    def update_heartbeat(self, hub_id: str) -> None
    def get_hub(self, hub_id: str) -> Optional[HubSnapshot]
    def get_all_hubs(self) -> list[HubSnapshot]
    def get_online_hubs(self) -> list[HubSnapshot]
    def check_health(self, timeout_seconds: float) -> list[str]  # timed-out hub IDs
    def get_snapshot(self) -> FleetStateSnapshot
```

Health states: `online` -> `degraded` (1 missed heartbeat) -> `offline` (timeout exceeded).

### ProcessHub/fleet/hub_agent.py

Lightweight sidecar alongside each ProcessHubServer:

```python
class HubAgent:
    def __init__(self, server: ProcessHubServer, transport: TransportBase,
                 hub_id: str, hub_name: str = "", heartbeat_interval: float = 5.0,
                 status_interval: float = 10.0)

    def start(self) -> None       # Start heartbeat + status loops, register handlers
    def stop(self) -> None        # Stop loops, send deregister

    # Background loops (threaded)
    def _heartbeat_loop(self)     # Periodic HubAnnounce
    def _status_loop(self)        # Periodic HubStatusReport from server.core

    # Command handler
    def _on_fleet_command(self, data: dict) -> None
        # Routes to: server.core.handle_start_request / handle_stop_request / reset
```

### ProcessHub/fleet/orchestrator.py

Central coordinator:

```python
class FleetOrchestrator:
    def __init__(self, transport: TransportBase, health_timeout: float = 30.0,
                 tick_interval: float = 5.0)

    def start(self) -> None       # Start transport, register handlers
    def stop(self) -> None        # Stop transport
    def tick(self) -> None        # Health check, mark offline hubs

    # Command routing
    def send_command(self, hub_id: str, action: str, params: dict) -> str  # returns command_id

    # State
    def get_fleet_snapshot(self) -> FleetStateSnapshot
    @property
    def registry(self) -> HubRegistry
```

### ProcessHub/fleet/fleet_client.py

For external systems (CI, CLI):

```python
class FleetClient:
    def __init__(self, transport: TransportBase)

    # Status queries
    def get_fleet_status(self) -> FleetStateSnapshot
    def get_hub_status(self, hub_id: str) -> Optional[HubSnapshot]

    # Single-hub commands
    def start_processes(self, hub_id: str, process_list: list[str]) -> str
    def stop_processes(self, hub_id: str, process_list: list[str]) -> str
    def reset_hub(self, hub_id: str) -> str

    # Batch operations
    def start_on_all_hubs(self, process_list: list[str]) -> dict[str, str]
    def stop_all_processes(self) -> dict[str, str]

    # Event callbacks
    def on_hub_online(self, callback: Callable) -> None
    def on_hub_offline(self, callback: Callable) -> None
```

### ProcessHub/fleet/web_api.py

Optional REST API + web dashboard (requires FastAPI):

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/fleet/status` | Fleet-wide status snapshot |
| GET | `/api/fleet/hubs` | List all registered hubs |
| GET | `/api/fleet/hubs/{hub_id}` | Single hub details |
| POST | `/api/fleet/command` | Send fleet command |
| POST | `/api/fleet/hubs/{hub_id}/start` | Start processes on hub |
| POST | `/api/fleet/hubs/{hub_id}/stop` | Stop processes on hub |
| POST | `/api/fleet/hubs/{hub_id}/reset` | Reset hub |
| GET | `/` | HTML fleet dashboard |

## Files to Create

| # | File | Description |
|---|------|-------------|
| 1 | `ProcessHub/fleet/__init__.py` | Package exports |
| 2 | `ProcessHub/fleet/models.py` | Messages + frozen snapshots |
| 3 | `ProcessHub/fleet/topics.py` | FleetTopics enum |
| 4 | `ProcessHub/fleet/hub_registry.py` | Thread-safe hub tracking |
| 5 | `ProcessHub/fleet/hub_agent.py` | Per-hub sidecar |
| 6 | `ProcessHub/fleet/orchestrator.py` | Central coordinator |
| 7 | `ProcessHub/fleet/fleet_client.py` | External API |
| 8 | `ProcessHub/fleet/web_api.py` | Optional REST dashboard |

## Files to Modify (minimal)

| File | Change |
|------|--------|
| `ProcessHub/__init__.py` | Add optional fleet imports (try/except `HAS_FLEET`) |
| `pyproject.toml` | Add `fleet` optional dependency group |

## Tests to Create

| File | Coverage |
|------|----------|
| `tests/unit/test_fleet_models.py` | Message creation, serialization, snapshot immutability |
| `tests/unit/test_hub_registry.py` | Register, deregister, health check, snapshot |
| `tests/unit/test_hub_agent.py` | Heartbeat, status reports, command handling |
| `tests/unit/test_orchestrator.py` | Hub discovery, command routing, health tick |
| `tests/unit/test_fleet_client.py` | Status queries, command sending, batch ops |

All tests use `InMemoryTransport` - no RabbitMQ needed.

## Architecture Decision Records

| ADR | Title | Summary |
|-----|-------|---------|
| [ADR-017](adr/017-fleet-orchestrator-overlay-pattern.md) | Fleet Orchestrator as Overlay | Fleet is an additive layer, not a core modification |
| [ADR-018](adr/018-heartbeat-based-hub-health-detection.md) | Heartbeat-Based Hub Health Detection | Periodic heartbeats for hub liveness detection |
| [ADR-019](adr/019-fleet-command-routing-through-orchestrator.md) | Fleet Command Routing Through Orchestrator | All commands route through central orchestrator |
| [ADR-020](adr/020-fleet-frozen-state-snapshots.md) | Fleet Frozen State Snapshots | Immutable snapshots for fleet state queries |

## Integration Examples

| Example | Description |
|---------|-------------|
| [12_fleet_basic.py](../examples/12_fleet_basic.py) | Basic fleet setup: orchestrator + 2 hub agents |
| [13_fleet_ci_integration.py](../examples/13_fleet_ci_integration.py) | CI/CD pipeline using FleetClient for automation |
| [14_fleet_web_dashboard.py](../examples/14_fleet_web_dashboard.py) | Fleet web dashboard with REST API and monitoring |

## Design Principles

### 1. Overlay, Not Modification

Fleet adds coordination without changing existing behavior. If you remove the fleet
layer, all local hubs continue working exactly as before.

### 2. Graceful Degradation

If the orchestrator goes down:
- Local hubs continue operating normally
- Clients connected directly to local hubs are unaffected
- When orchestrator comes back, hub agents re-announce

### 3. Existing Patterns

Fleet follows all existing codebase patterns:
- Apache 2.0 license headers
- `MessageBase` for protocol messages
- `@dataclass(frozen=True)` with tuples for snapshots
- `(str, Enum)` for topics
- `TransportBase` ABC for communication
- try/except with `HAS_FLEET` for optional imports
- pytest class-based tests with `InMemoryTransport`

### 4. Single Source of Truth

The orchestrator's `HubRegistry` is the single source of truth for fleet state.
Hub agents push state; the orchestrator never pulls.

## Deployment Topology

### Minimal (2 machines)

```
Machine A:  FleetOrchestrator + HubAgent + ProcessHubServer
Machine B:  HubAgent + ProcessHubServer
```

### Standard (N+1 machines)

```
Orchestrator Machine:  FleetOrchestrator (+ optional FleetWebAPI)
Hub Machine 1..N:      HubAgent + ProcessHubServer
CI Runner:             FleetClient
```

### Development (single machine)

```
Single Machine:  FleetOrchestrator + HubAgent + ProcessHubServer
                 (all using InMemoryTransport for testing)
```

## Future Extensions

These are **not** in scope for the initial implementation but are enabled by the architecture:

- **Hub Groups** - Tag hubs by role (e.g., "HIL", "SIL") and target commands by group
- **Process Templates** - Define process configs centrally, deploy to hub groups
- **Fleet Events Log** - Persist all fleet events for audit/debugging
- **Multi-Orchestrator** - Active-passive orchestrator failover
- **Metrics Export** - Prometheus/Grafana integration for fleet monitoring
