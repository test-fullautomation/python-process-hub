# ADR-019: Fleet Command Routing Through Orchestrator

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

External systems (CI pipelines, CLI tools, dashboards) need to send commands to specific
hubs in the fleet - starting processes, stopping processes, resetting hubs, querying status.

### Design Question

How should commands flow from external clients to target hubs?

```
Option A: Direct routing           Option B: Through orchestrator

FleetClient ─────► HubAgent       FleetClient ──► Orchestrator ──► HubAgent
(must know hub     (receives       (knows only     (routes to       (receives
 transport addr)    directly)       orchestrator)   target hub)      from orch)
```

### Requirements

| Requirement | Description |
|-------------|-------------|
| Single entry point | Clients shouldn't need per-hub connection details |
| Hub validation | Commands to unknown/offline hubs should be rejected |
| Audit trail | All commands should be observable at a central point |
| Batch operations | Support "start X on all hubs" without client-side loop |
| Result correlation | Match command results to original requests |

## Decision

All fleet commands will **route through the FleetOrchestrator**. Clients never communicate
directly with HubAgents.

### Command Flow

```
FleetClient           FleetOrchestrator           HubAgent (target)
     │                       │                         │
     │  1. FleetCommand      │                         │
     │  (command_id=abc,     │                         │
     │   hub_id=PC-2,       │                         │
     │   action=start,      │                         │
     │   params={procs})    │                         │
     │─────────────────────►│                         │
     │                       │  2. Validate:           │
     │                       │  - hub exists?          │
     │                       │  - hub online?          │
     │                       │  - action valid?        │
     │                       │                         │
     │                       │  3. Forward command     │
     │                       │─────────────────────────►│
     │                       │                         │  4. Execute locally:
     │                       │                         │  server.core.handle_start_request()
     │                       │                         │
     │                       │  5. FleetCommandResult  │
     │                       │◄────────────────────────│
     │  6. FleetCommandResult│                         │
     │◄─────────────────────│                         │
     │                       │                         │
```

### Command Protocol

```python
@dataclass
class FleetCommand(MessageBase):
    """Command from client/orchestrator to hub agent."""
    command_id: str = ""      # UUID for correlation
    hub_id: str = ""          # Target hub (empty = broadcast)
    action: str = ""          # "start_process", "stop_process", "reset", "get_status"
    params: dict = field(default_factory=dict)

@dataclass
class FleetCommandResult(MessageBase):
    """Result from hub agent back to orchestrator/client."""
    command_id: str = ""      # Correlates to FleetCommand
    hub_id: str = ""          # Which hub executed it
    success: bool = True
    message: str = ""
    data: dict = field(default_factory=dict)
```

### Supported Actions

| Action | Params | Hub Agent Behavior |
|--------|--------|--------------------|
| `start_process` | `{"process_list": [...], "panel_id": "fleet"}` | `server.core.handle_start_request()` |
| `stop_process` | `{"process_list": [...], "panel_id": "fleet"}` | `server.core.handle_stop_request()` |
| `reset` | `{}` | `server.reset()` |
| `get_status` | `{}` | `server.core.get_state_snapshot()` |

### Orchestrator Validation

```python
class FleetOrchestrator:
    def send_command(self, hub_id: str, action: str, params: dict) -> str:
        command_id = str(uuid.uuid4())

        # Validate hub exists and is reachable
        hub = self._registry.get_hub(hub_id)
        if hub is None:
            raise ValueError(f"Unknown hub: {hub_id}")
        if hub.status == "offline":
            raise ValueError(f"Hub is offline: {hub_id}")

        command = FleetCommand(
            command_id=command_id,
            hub_id=hub_id,
            action=action,
            params=params,
        )
        self._transport.send(FleetTopics.FLEET_COMMAND, command)
        return command_id
```

### Batch Operations

The orchestrator enables batch commands that clients don't need to implement:

```python
class FleetClient:
    def start_on_all_hubs(self, process_list: list[str]) -> dict[str, str]:
        """Start processes on every online hub. Returns {hub_id: command_id}."""
        results = {}
        snapshot = self.get_fleet_status()
        for hub in snapshot.hubs:
            if hub.status == "online":
                cmd_id = self.start_processes(hub.hub_id, process_list)
                results[hub.hub_id] = cmd_id
        return results
```

## Consequences

### Positive

- **Single entry point** - Clients only need orchestrator address
- **Hub validation** - Orchestrator rejects commands to unknown/offline hubs
- **Central audit** - All commands pass through orchestrator (loggable)
- **Batch support** - Orchestrator can fan-out commands to multiple hubs
- **Hub discovery** - Clients don't need to know hub transport addresses
- **Access control** - Future: orchestrator can enforce permissions

### Negative

- **Single point of routing** - If orchestrator is down, no fleet commands
  (local hub commands via direct clients still work)
- **Additional latency** - Extra hop through orchestrator (~ms, negligible for RabbitMQ)
- **Orchestrator load** - All commands pass through one point (acceptable for expected scale)

### Neutral

- **Command correlation** - UUID-based `command_id` enables async result matching
- **Fire-and-forget option** - Clients can send commands without waiting for results
- **Extensible actions** - New actions can be added without protocol changes

## Alternatives Considered

### 1. Direct Client-to-Hub Communication (Rejected)

FleetClient sends commands directly to HubAgent transport addresses:

```python
client.send_to_hub("tcp://10.0.0.5:5556", FleetCommand(...))
```

Rejected because:
- Clients must know hub transport addresses (tight coupling)
- No central validation or audit
- Batch operations require client-side implementation
- Hub address changes require client reconfiguration

### 2. Shared Command Queue (Deferred)

All commands go to a shared queue; hubs pull commands for themselves:

```python
# All hubs subscribe to FLEET_COMMAND and filter by hub_id
transport.register_handler(FleetTopics.FLEET_COMMAND, self._filter_my_commands)
```

Deferred because:
- Current topic-based routing already achieves this
- Could be optimized later with hub-specific topics if needed
- Simpler to have orchestrator do explicit forwarding for now

### 3. Peer-to-Peer Command Mesh (Rejected)

Hubs can send commands to each other:

```python
# Hub A can command Hub B
hub_a.send_command(hub_id="hub-b", action="start", ...)
```

Rejected because:
- No single point of control or audit
- Complex authorization model
- Harder to reason about command flow
- Not needed for current use cases

## References

- [API Gateway Pattern](https://microservices.io/patterns/apigateway.html)
- [Command Pattern](https://en.wikipedia.org/wiki/Command_pattern)
- [Message Router Pattern](https://www.enterpriseintegrationpatterns.com/patterns/messaging/MessageRouter.html)
- Related: ADR-017 (Fleet Orchestrator as Overlay Pattern)
- Related: ADR-018 (Heartbeat-Based Hub Health Detection)
- Source: `ProcessHub/fleet/orchestrator.py` - command routing
- Source: `ProcessHub/fleet/fleet_client.py` - client API
- Source: `ProcessHub/fleet/hub_agent.py` - command handler
