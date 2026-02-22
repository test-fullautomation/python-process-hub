# Troubleshooting Guide Map

A problem-oriented index for ProcessHub developers. Find the symptom you
observe, then follow the links to ADRs, diagrams, and source files that explain
the relevant subsystem.

> **How to use:** Ctrl+F for a keyword (e.g. "timeout", "not starting",
> "stuck", "offline"), or browse the symptom categories below. Each entry links
> to the architecture decisions, diagrams, and source code relevant to that
> problem area.

---

## Quick Symptom Index

| # | Symptom | Category |
|---|---------|----------|
| [1](#1-process-start-request-returns-success-but-process-is-not-running) | Process start request returns success but process is not running | Process |
| [2](#2-process-stop-has-no-effect-or-process-keeps-running) | Process stop has no effect or process keeps running | Process |
| [3](#3-process-crash-not-detected-by-the-server) | Process crash not detected by the server | Process |
| [4](#4-restart-stuck-in-notifying-or-awaiting_ack-state) | Restart stuck in NOTIFYING or AWAITING_ACK state | Restart |
| [5](#5-restart-triggers-but-processes-never-come-back) | Restart triggers but processes never come back | Restart |
| [6](#6-client-never-receives-messages-from-server) | Client never receives messages from server | Transport |
| [7](#7-zmq-transport-bind-fails-with-address-already-in-use) | ZMQ transport bind fails with "address already in use" | Transport |
| [8](#8-eventbus-transport-messages-not-delivered) | EventBus transport messages not delivered | Transport |
| [9](#9-server-tick-loop-stops-or-becomes-unresponsive) | Server tick loop stops or becomes unresponsive | Server |
| [10](#10-server-reset-does-not-clear-all-state) | Server reset does not clear all state | Server |
| [11](#11-client-register-succeeds-but-start-request-fails) | Client register succeeds but start request fails | Client |
| [12](#12-multiple-panels-and-stop-does-not-stop-process) | Multiple panels and stop does not stop process | Ownership |
| [13](#13-web-dashboard-shows-stale-state) | Web dashboard shows stale state | UI |
| [14](#14-web-dashboard-fails-to-start-port-in-use) | Web dashboard fails to start (port in use) | UI |
| [15](#15-fleet-hub-shows-offline-after-running-fine) | Fleet hub shows "Offline" after running fine | Fleet |
| [16](#16-fleet-command-sent-but-no-result-received) | Fleet command sent but no result received | Fleet |
| [17](#17-orchestrator-status-not-updating-after-local-process-changes) | Orchestrator status not updating after local process changes | Fleet |
| [18](#18-fleet-web-api-returns-empty-hub-list) | Fleet web API returns empty hub list | Fleet |
| [19](#19-inmemory-transport-test-assertions-fail-on-message-content) | InMemory transport test assertions fail on message content | Testing |
| [20](#20-configuration-loader-fails-with-keyerror) | Configuration loader fails with KeyError | Config |

---

## Process Management

### 1. Process start request returns success but process is not running

The server responds with a successful start, but the process never actually
runs.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-008](adr/008-pluggable-process-executor.md) | Is the correct executor configured? `MockExecutor` simulates but doesn't launch real processes. |
| [ADR-005](adr/005-normalized-process-representation.md) | Is the process state tracked correctly? Check `ProcessState` transitions. |
| [sequence_process_start.puml](diagrams/sequence_process_start.puml) | Full process start message flow |
| [class_process.puml](diagrams/class_process.puml) | Executor class hierarchy |
| [`executor.py`](../ProcessHub/process/executor.py) | `SimpleExecutor.start()` — launches subprocess; `MockExecutor.start()` — fakes it |
| [`hub_core.py`](../ProcessHub/core/hub_core.py) | `handle_start_request()` — validates request, delegates to executor |
| [`models.py`](../ProcessHub/core/models.py) | `ProcessStartRequest` — `panel_id` + `process_list` fields |

**Common causes:**
- Using `MockExecutor` in production (it returns success without launching)
- `process_config` dictionary missing or has wrong keys (`script`, `args`)
- Script path does not exist or is not executable on the target machine
- Panel not registered before sending start request (start fails silently)
- `process_list` contains names not in `process_config`

---

### 2. Process stop has no effect or process keeps running

A stop request completes but the process continues running.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-015](adr/015-process-ownership-model.md) | Reference counting: process only stops when **all** requesters release it. |
| [ADR-008](adr/008-pluggable-process-executor.md) | Does the executor's `stop()` actually terminate the subprocess? |
| [`hub_core.py`](../ProcessHub/core/hub_core.py) | `handle_stop_request()` — checks requester count before stopping |
| [`process_registry.py`](../ProcessHub/core/process_registry.py) | `remove_requester()` — only marks stopped when requester set is empty |
| [`executor.py`](../ProcessHub/process/executor.py) | `SimpleExecutor.stop()` — sends signal, waits `stop_timeout` |

**Common causes:**
- Another panel still has the process requested (reference count > 0)
- `force=False` and the process ignores the termination signal
- `stop_timeout` too short — process killed before graceful shutdown completes
- Wrong `panel_id` in stop request (doesn't match the original requester)

---

### 3. Process crash not detected by the server

A process dies externally (Task Manager, `kill`, segfault) but the server still
shows it as running.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-009](adr/009-tcp-keepalive-for-crash-detection.md) | TCP keepalive detection timing (~25 seconds) |
| [ADR-004](adr/004-restart-state-machine.md) | Crash detection happens in `tick()` via `poll()` on subprocess handles |
| [state_restart.puml](diagrams/state_restart.puml) | Restart state machine transitions |
| [`hub_core.py`](../ProcessHub/core/hub_core.py) | `tick()` — polls process health, triggers restart if needed |
| [`executor.py`](../ProcessHub/process/executor.py) | `is_running()` — checks subprocess `poll()` return code |

**Common causes:**
- `tick()` not being called in the main loop (no health checking)
- `refresh_interval` too long — increase polling frequency
- Process spawned children that outlive the parent (orphan processes)
- `MockExecutor` always reports processes as running

---

## Restart Coordination

### 4. Restart stuck in NOTIFYING or AWAITING_ACK state

The restart state machine enters NOTIFYING or AWAITING_ACK and never
progresses.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-004](adr/004-restart-state-machine.md) | FSM states: IDLE → DETECTING → NOTIFYING → AWAITING_ACK → RESTARTING → DONE |
| [sequence_restart.puml](diagrams/sequence_restart.puml) | Restart coordination sequence |
| [sequence_restart_flow.puml](diagrams/sequence_restart_flow.puml) | Detailed restart flow |
| [state_restart.puml](diagrams/state_restart.puml) | Restart state transitions |
| [`restart_state.py`](../ProcessHub/core/restart_state.py) | `RestartStateMachine` — state transitions and timeout logic |
| [`hub_core.py`](../ProcessHub/core/hub_core.py) | `handle_restart_ready()` — processes RESTART_READY acknowledgements |
| [`client.py`](../ProcessHub/runtime/client.py) | `send_restart_ready()` — client must call this to acknowledge |

**Common causes:**
- **NOTIFYING**: Client never received the `RESTART_NOTIFY` message (transport issue)
- **AWAITING_ACK**: Client received notification but never sent `RESTART_READY` acknowledgement
- Client code missing `on_restart_notify` handler in `ClientController`
- Timeout not configured — restart waits indefinitely for all panels to ACK
- Panel disconnected during restart (its ACK will never arrive)

---

### 5. Restart triggers but processes never come back

Dead processes are detected and restart initiates, but the processes don't
actually restart.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-004](adr/004-restart-state-machine.md) | RESTARTING state: executor `start()` called for each dead process |
| [ADR-008](adr/008-pluggable-process-executor.md) | Executor `start()` may fail if the script/binary was deleted |
| [`hub_core.py`](../ProcessHub/core/hub_core.py) | Restart logic after AWAITING_ACK completes |
| [`executor.py`](../ProcessHub/process/executor.py) | `start()` — exceptions during restart are logged but may not propagate |

**Common causes:**
- Script or binary was moved/deleted since the original start
- Port conflict — restarted process tries to bind the same port
- Executor `start()` raises exception (caught and logged, restart marked failed)
- `process_config` was modified between the crash and restart

---

## Transport & Communication

### 6. Client never receives messages from server

Client connects and registers, but incoming messages (start response, stop
response, etc.) never arrive.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-003](adr/003-pluggable-transport-layer.md) | Transport interface: `register_handler()` + `send()`/`send_async()` |
| [ADR-006](adr/006-typed-protocol-messages.md) | Topic names must match exactly between server and client |
| [sequence_basic.puml](diagrams/sequence_basic.puml) | Basic server-client message flow |
| [sequence_registration.puml](diagrams/sequence_registration.puml) | Registration sequence |
| [class_transport.puml](diagrams/class_transport.puml) | Transport class hierarchy |
| [`base.py`](../ProcessHub/transport/base.py) | `TransportBase` ABC — `register_handler(topic, callback)` |
| [`server.py`](../ProcessHub/runtime/server.py) | `Topics` enum — all topic string values |
| [`client.py`](../ProcessHub/runtime/client.py) | `_setup_handlers()` — registers handlers for all response topics |

**Common causes:**
- Client and server using different transport instances (not connected)
- `register_handler()` called with wrong topic string (case-sensitive)
- Handler registered after the message was already sent (race condition)
- ZMQ: client connected to wrong address/port
- EventBus: different exchange names or routing key prefixes

---

### 7. ZMQ transport bind fails with "address already in use"

Starting the ZMQ transport raises `zmq.error.ZMQError: Address already in use`.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-003](adr/003-pluggable-transport-layer.md) | ZMQ PUB/SUB broker pattern with XPUB/XSUB proxy |
| [`zmq_transport.py`](../ProcessHub/transport/zmq_transport.py) | `start()` — binds XPUB and XSUB ports |

**Common causes:**
- Previous server instance didn't shut down cleanly (port still held)
- Another process is using the same port (check with `netstat -ano`)
- `start_broker=True` used by multiple processes (only one should be the broker)
- On Windows, `SO_REUSEADDR` behavior differs — port may stay bound for minutes

---

### 8. EventBus transport messages not delivered

Server and client use EventBusTransport but messages never arrive.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-014](adr/014-eventbus-transport-with-rabbitmq.md) | EventBus exchange topology, routing key prefix, serializer |
| [`eventbus_transport.py`](../ProcessHub/transport/eventbus_transport.py) | `EventBusConfig` — host, port, exchange, routing key prefix, serializer |

**Common causes:**
- RabbitMQ not running (check `localhost:15672` management UI)
- Mismatched `exchange_name` between server and client
- Mismatched `routing_key_prefix` (e.g. `processhub` vs `fleet`)
- Mismatched `serializer` (e.g. `PickleSerializer` on one side, JSON on the other)
- Firewall blocking AMQP port 5672
- `auto_reconnect=False` and the initial connection failed silently

---

## Server Lifecycle

### 9. Server tick loop stops or becomes unresponsive

The server runs but stops processing health checks and restart coordination.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-002](adr/002-separation-of-core-logic-and-runtime.md) | Server is a thin wrapper; `tick()` drives the core's periodic work |
| [`server.py`](../ProcessHub/runtime/server.py) | `_main_loop()` — calls `self._core.tick()` every `refresh_interval` |
| [`hub_core.py`](../ProcessHub/core/hub_core.py) | `tick()` — health check + restart FSM advancement |

**Common causes:**
- `refresh_interval` set too high (minutes instead of seconds)
- Exception in `tick()` breaks the main loop (check logs)
- Main thread blocked by a long-running operation
- Server started but `_main_loop()` not running (headless mode without loop)

---

### 10. Server reset does not clear all state

After `server.reset()`, some processes or connections remain.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-011](adr/011-hub-reset-without-restart.md) | Reset clears process registry and connection registry without restarting |
| [`server.py`](../ProcessHub/runtime/server.py) | `reset()` — stops processes, clears registries, sends notifications |
| [`hub_core.py`](../ProcessHub/core/hub_core.py) | Core reset logic |
| [`process_registry.py`](../ProcessHub/core/process_registry.py) | `clear()` — removes all process entries |

**Common causes:**
- Executor `stop()` timed out — processes killed but not cleaned up
- Restart state machine was active during reset (FSM left in stale state)
- External processes (not managed by executor) are not affected by reset

---

## Client & Ownership

### 11. Client register succeeds but start request fails

`RegisterConnectionRequest` succeeds but subsequent `ProcessStartRequest`
returns failure.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-006](adr/006-typed-protocol-messages.md) | Message fields: `panel_id` must match between register and start |
| [sequence_process_start.puml](diagrams/sequence_process_start.puml) | Start request flow |
| [`hub_core.py`](../ProcessHub/core/hub_core.py) | `handle_start_request()` — validates `panel_id` is registered |
| [`models.py`](../ProcessHub/core/models.py) | `ProcessStartRequest.panel_id` — must match a registered connection |

**Common causes:**
- `panel_id` in start request doesn't match the registered `panel_id`
- Process name not in `process_config` (server doesn't know how to start it)
- Connection was unregistered between register and start (timing issue)
- Restart in progress — server rejects start requests during RESTARTING state

---

### 12. Multiple panels and stop does not stop process

Panel A started a process, Panel B also started it, Panel A sends stop — but
the process keeps running.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-015](adr/015-process-ownership-model.md) | Reference counting model: process runs while any requester holds it |
| [`process_registry.py`](../ProcessHub/core/process_registry.py) | `_requesters` dict — set of panel IDs per process |
| [`hub_core.py`](../ProcessHub/core/hub_core.py) | `handle_stop_request()` — removes requester, checks if set is empty |

**Common causes:**
- This is **expected behavior** — the process has multiple requesters
- To force stop regardless of other requesters, use `force=True`
- Panel B disconnected without sending stop (its requester entry persists until
  the connection is unregistered)

---

## UI & Web Dashboard

### 13. Web dashboard shows stale state

The dashboard renders but process states or connection lists don't update.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-016](adr/016-immutable-state-snapshots.md) | UI receives frozen snapshots — is `render()` being called? |
| [ADR-007](adr/007-decoupled-ui-via-hub-view.md) | `HubView.render(snapshot)` called by the server main loop |
| [`web_view.py`](../ProcessHub/ui/web_view.py) | Web dashboard `render()` — updates internal state for API responses |
| [`server.py`](../ProcessHub/runtime/server.py) | `_main_loop()` — calls `self._view.render(snapshot)` after each tick |

**Common causes:**
- View not passed to server constructor (using `NullView` by default)
- `_main_loop()` not running (server started in headless mode)
- Browser not refreshing — web dashboard may require manual refresh or WebSocket
- FastAPI not installed (`HAS_FASTAPI = False`, web view unavailable)

---

### 14. Web dashboard fails to start (port in use)

Starting the web dashboard raises `OSError: [Errno 10048] address already in
use`.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-013](adr/013-fastapi-for-web-dashboard.md) | FastAPI + Uvicorn embedded deployment |
| [`web_view.py`](../ProcessHub/ui/web_view.py) | `start()` — binds Uvicorn to configured host:port |

**Common causes:**
- Previous dashboard instance still running (daemon thread didn't exit)
- Another application using the same port
- On Windows, port may remain in TIME_WAIT state for up to 4 minutes after close
- Fix: check port with `netstat -ano | findstr :<port>` and kill the holder

---

## Fleet Orchestrator

### 15. Fleet hub shows "Offline" after running fine

A hub was online but the orchestrator now marks it as offline.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-018](adr/018-heartbeat-based-hub-health-detection.md) | Health states: online → degraded → offline. Timeout = 30s default. |
| [state_hub_health.puml](diagrams/state_hub_health.puml) | Hub health state machine |
| [sequence_fleet_discovery.puml](diagrams/sequence_fleet_discovery.puml) | Hub discovery and heartbeat flow |
| [`hub_agent.py`](../ProcessHub/fleet/hub_agent.py) | `_heartbeat_loop()` — sends `HubAnnounce` every `heartbeat_interval` |
| [`hub_registry.py`](../ProcessHub/fleet/hub_registry.py) | `check_health()` — compares `last_seen` against timeout |
| [`orchestrator.py`](../ProcessHub/fleet/orchestrator.py) | `tick()` — calls `check_health()` periodically |

**Common causes:**
- Hub agent process crashed (no more heartbeats)
- Network partition between hub and orchestrator
- RabbitMQ/EventBus connection dropped and `auto_reconnect` failed
- `health_timeout` too short for the network latency
- Orchestrator `tick()` not being called (main loop stopped)

---

### 16. Fleet command sent but no result received

`orchestrator.send_command()` returns a command ID but no
`FleetCommandResult` arrives.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-019](adr/019-fleet-command-routing-through-orchestrator.md) | Command routing: orchestrator → transport → agent → server → result |
| [sequence_fleet_command.puml](diagrams/sequence_fleet_command.puml) | Full fleet command sequence |
| [`orchestrator.py`](../ProcessHub/fleet/orchestrator.py) | `send_command()` — publishes `FleetCommand` on `FLEET_COMMAND` topic |
| [`hub_agent.py`](../ProcessHub/fleet/hub_agent.py) | `_on_fleet_command()` — filters by `hub_id`, delegates to server |

**Common causes:**
- Target hub is offline (agent not running, no consumer for the command)
- `hub_id` in command doesn't match any running agent
- Agent's command handler threw an exception (result never sent)
- Fleet transport not connected (different exchange or routing key prefix)
- Agent registered on a different transport instance than the orchestrator

---

### 17. Orchestrator status not updating after local process changes

A panel starts/stops processes locally but the fleet orchestrator doesn't
reflect the change for up to 10 seconds.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-021](adr/021-event-driven-fleet-status-updates.md) | Event-driven updates via `server_transport` subscription (~0.5s) |
| [sequence_fleet_event_driven.puml](diagrams/sequence_fleet_event_driven.puml) | Event-driven status update flow |
| [fleet_overview.puml](diagrams/fleet_overview.puml) | Fleet overview showing local transport connection |
| [fleet_component.puml](diagrams/fleet_component.puml) | Fleet component diagram with transport subscriptions |
| [`hub_agent.py`](../ProcessHub/fleet/hub_agent.py) | `__init__()` — `server_transport` parameter; `_on_local_state_change()` handler |

**Common causes:**
- **`server_transport` not passed** to `HubAgent` constructor — agent falls back
  to polling only (10s `status_interval`). Pass the server's local transport:
  ```python
  agent = HubAgent(
      server=server,
      transport=fleet_transport,
      hub_id="my-hub",
      server_transport=local_transport,  # enables event-driven updates
  )
  ```
- Debounce suppression — multiple rapid changes within 0.5s produce only one
  report. The next periodic poll (10s) will catch the final state.
- Server transport was stopped/replaced after agent started (handler lost)

---

### 18. Fleet web API returns empty hub list

`GET /api/fleet/status` returns `total_hubs: 0` even though agents are running.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-017](adr/017-fleet-orchestrator-overlay-pattern.md) | Fleet is an overlay — agents must use the same transport as the orchestrator |
| [`web_api.py`](../ProcessHub/fleet/web_api.py) | REST endpoints query `orchestrator.get_fleet_snapshot()` |
| [`orchestrator.py`](../ProcessHub/fleet/orchestrator.py) | `get_fleet_snapshot()` → `_registry.get_fleet_snapshot()` |
| [`hub_registry.py`](../ProcessHub/fleet/hub_registry.py) | Registry only has entries from received `HubAnnounce` messages |

**Common causes:**
- Agents and orchestrator on different transport instances (not connected)
- Agents use `fleet.` routing prefix but orchestrator expects different prefix
- Orchestrator started but `start()` not called (handlers not registered)
- Agents started before orchestrator — heartbeats sent but nobody was listening
  (registry is empty until the first heartbeat arrives)

---

## Testing

### 19. InMemory transport test assertions fail on message content

Tests using `InMemoryTransport` pass message objects but assertions on dict
fields fail.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [ADR-003](adr/003-pluggable-transport-layer.md) | Transport `send()` delivers to handlers |
| [`inmemory_transport.py`](../ProcessHub/transport/inmemory_transport.py) | `get_sent_messages()` returns **original objects** (not dicts) |
| [`server.py`](../ProcessHub/runtime/server.py) | Server uses `asdict(message)` before `transport.send_async()` |

**Common causes:**
- **`get_sent_messages()` returns original objects**, not serialized dicts. If
  you send a dataclass directly (without `asdict()`), assertions like
  `msg["hub_id"]` fail with `TypeError` because `msg` is a dataclass, not a dict.
- Fix: always serialize with `asdict(message)` before calling `transport.send()`,
  matching what the server does:
  ```python
  from dataclasses import asdict
  transport.send(topic, asdict(my_message))  # dict, not dataclass
  ```
- `clear_messages()` clears sent messages but keeps handlers registered
- `message_count(topic)` counts entries in `_sent_messages`, not handler calls

---

## Configuration

### 20. Configuration loader fails with KeyError

Loading process config from JSON raises `KeyError` on expected fields.

**Investigate:**

| Resource | What to check |
|----------|---------------|
| [`loader.py`](../ProcessHub/config/loader.py) | `JsonConfigLoader`, `ProcessConfigLoader` — expected schema |
| [`schemas.py`](../ProcessHub/config/schemas.py) | `ProcessConfig`, `ServerConfig` — required fields |
| [05_configuration.py](../examples/05_configuration.py) | Configuration loading example |

**Common causes:**
- JSON config missing required fields (`script` is mandatory per process)
- Config key name mismatch (e.g. `command` vs `script`, `arguments` vs `args`)
- Nested structure wrong (processes should be a dict of name → config)
- File encoding issue (BOM in UTF-8 file)

---

## Cross-Reference: Architecture Layer Map

When you know *which layer* is involved, use this table to find all relevant
resources.

### Core Layer

| Component | Source | ADRs | Diagrams |
|-----------|--------|------|----------|
| ProcessHubCore | [`hub_core.py`](../ProcessHub/core/hub_core.py) | [001](adr/001-lock-based-operation-serialization.md), [002](adr/002-separation-of-core-logic-and-runtime.md) | [class_core.puml](diagrams/class_core.puml) |
| ProcessRegistry | [`process_registry.py`](../ProcessHub/core/process_registry.py) | [005](adr/005-normalized-process-representation.md), [015](adr/015-process-ownership-model.md) | [class_core.puml](diagrams/class_core.puml) |
| RestartStateMachine | [`restart_state.py`](../ProcessHub/core/restart_state.py) | [004](adr/004-restart-state-machine.md) | [state_restart.puml](diagrams/state_restart.puml), [sequence_restart.puml](diagrams/sequence_restart.puml) |
| Models | [`models.py`](../ProcessHub/core/models.py) | [006](adr/006-typed-protocol-messages.md), [016](adr/016-immutable-state-snapshots.md) | [class_core.puml](diagrams/class_core.puml) |

### Runtime Layer

| Component | Source | ADRs | Diagrams |
|-----------|--------|------|----------|
| ProcessHubServer | [`server.py`](../ProcessHub/runtime/server.py) | [002](adr/002-separation-of-core-logic-and-runtime.md), [010](adr/010-server-shutdown-notification.md) | [class_runtime.puml](diagrams/class_runtime.puml), [architecture_layered.puml](diagrams/architecture_layered.puml) |
| ProcessHubClient | [`client.py`](../ProcessHub/runtime/client.py) | [002](adr/002-separation-of-core-logic-and-runtime.md) | [class_runtime.puml](diagrams/class_runtime.puml), [sequence_basic.puml](diagrams/sequence_basic.puml) |
| ClientController | [`client_controller.py`](../ProcessHub/runtime/client_controller.py) | [002](adr/002-separation-of-core-logic-and-runtime.md) | [class_runtime.puml](diagrams/class_runtime.puml) |

### Transport Layer

| Component | Source | ADRs | Diagrams |
|-----------|--------|------|----------|
| TransportBase | [`base.py`](../ProcessHub/transport/base.py) | [003](adr/003-pluggable-transport-layer.md) | [class_transport.puml](diagrams/class_transport.puml) |
| ZmqTransport | [`zmq_transport.py`](../ProcessHub/transport/zmq_transport.py) | [003](adr/003-pluggable-transport-layer.md) | [class_transport.puml](diagrams/class_transport.puml) |
| EventBusTransport | [`eventbus_transport.py`](../ProcessHub/transport/eventbus_transport.py) | [014](adr/014-eventbus-transport-with-rabbitmq.md) | [class_transport.puml](diagrams/class_transport.puml) |
| InMemoryTransport | [`inmemory_transport.py`](../ProcessHub/transport/inmemory_transport.py) | [003](adr/003-pluggable-transport-layer.md) | [class_transport.puml](diagrams/class_transport.puml) |

### Process Layer

| Component | Source | ADRs | Diagrams |
|-----------|--------|------|----------|
| ProcessExecutor | [`executor.py`](../ProcessHub/process/executor.py) | [008](adr/008-pluggable-process-executor.md) | [class_process.puml](diagrams/class_process.puml) |
| ProcessManager | [`manager.py`](../ProcessHub/process/manager.py) | [008](adr/008-pluggable-process-executor.md) | [class_process.puml](diagrams/class_process.puml) |

### UI Layer

| Component | Source | ADRs | Diagrams |
|-----------|--------|------|----------|
| HubView (base) | [`base.py`](../ProcessHub/ui/base.py) | [007](adr/007-decoupled-ui-via-hub-view.md) | [class_ui.puml](diagrams/class_ui.puml) |
| ConsoleView | [`console_view.py`](../ProcessHub/ui/console_view.py) | [007](adr/007-decoupled-ui-via-hub-view.md) | [class_ui.puml](diagrams/class_ui.puml) |
| WebView | [`web_view.py`](../ProcessHub/ui/web_view.py) | [013](adr/013-fastapi-for-web-dashboard.md) | [class_ui.puml](diagrams/class_ui.puml) |
| NullView | [`null_view.py`](../ProcessHub/ui/null_view.py) | [007](adr/007-decoupled-ui-via-hub-view.md) | — |

### Fleet Layer (Overlay)

| Component | Source | ADRs | Diagrams |
|-----------|--------|------|----------|
| FleetOrchestrator | [`orchestrator.py`](../ProcessHub/fleet/orchestrator.py) | [017](adr/017-fleet-orchestrator-overlay-pattern.md), [019](adr/019-fleet-command-routing-through-orchestrator.md) | [fleet_overview.puml](diagrams/fleet_overview.puml), [fleet_component.puml](diagrams/fleet_component.puml) |
| HubAgent | [`hub_agent.py`](../ProcessHub/fleet/hub_agent.py) | [017](adr/017-fleet-orchestrator-overlay-pattern.md), [018](adr/018-heartbeat-based-hub-health-detection.md), [021](adr/021-event-driven-fleet-status-updates.md) | [sequence_fleet_event_driven.puml](diagrams/sequence_fleet_event_driven.puml), [sequence_fleet_command.puml](diagrams/sequence_fleet_command.puml) |
| HubRegistry | [`hub_registry.py`](../ProcessHub/fleet/hub_registry.py) | [018](adr/018-heartbeat-based-hub-health-detection.md), [020](adr/020-fleet-frozen-state-snapshots.md) | [state_hub_health.puml](diagrams/state_hub_health.puml) |
| FleetClient | [`fleet_client.py`](../ProcessHub/fleet/fleet_client.py) | [019](adr/019-fleet-command-routing-through-orchestrator.md) | [sequence_fleet_command.puml](diagrams/sequence_fleet_command.puml) |
| FleetWebAPI | [`web_api.py`](../ProcessHub/fleet/web_api.py) | [013](adr/013-fastapi-for-web-dashboard.md) | [fleet_overview.puml](diagrams/fleet_overview.puml) |
| Fleet Models | [`models.py`](../ProcessHub/fleet/models.py) | [006](adr/006-typed-protocol-messages.md), [020](adr/020-fleet-frozen-state-snapshots.md) | [class_fleet.puml](diagrams/class_fleet.puml) |
| Fleet Topics | [`topics.py`](../ProcessHub/fleet/topics.py) | [017](adr/017-fleet-orchestrator-overlay-pattern.md) | — |

### Configuration Layer

| Component | Source | ADRs | Diagrams |
|-----------|--------|------|----------|
| ConfigLoader | [`loader.py`](../ProcessHub/config/loader.py) | — | — |
| ConfigSchemas | [`schemas.py`](../ProcessHub/config/schemas.py) | — | — |

---

## Message Flow Quick Reference

For tracing a message through the system, start with the relevant sequence
diagram:

| Scenario | Diagram | Key Source Files |
|----------|---------|-----------------|
| Client registration | [sequence_registration.puml](diagrams/sequence_registration.puml) | `client.py` → `server.py` → `hub_core.py` |
| Process start | [sequence_process_start.puml](diagrams/sequence_process_start.puml) | `client.py` → `server.py` → `hub_core.py` → `executor.py` |
| Basic server-client | [sequence_basic.puml](diagrams/sequence_basic.puml) | `client.py` ↔ `server.py` via transport |
| Restart coordination | [sequence_restart.puml](diagrams/sequence_restart.puml) | `hub_core.py` → `restart_state.py` → `server.py` → `client.py` |
| Restart flow (detailed) | [sequence_restart_flow.puml](diagrams/sequence_restart_flow.puml) | Full restart FSM progression |
| Fleet hub discovery | [sequence_fleet_discovery.puml](diagrams/sequence_fleet_discovery.puml) | `hub_agent.py` → fleet transport → `orchestrator.py` → `hub_registry.py` |
| Fleet command routing | [sequence_fleet_command.puml](diagrams/sequence_fleet_command.puml) | `fleet_client.py` → `orchestrator.py` → fleet transport → `hub_agent.py` → `server.core` |
| Event-driven status | [sequence_fleet_event_driven.puml](diagrams/sequence_fleet_event_driven.puml) | Panel → `server.py` → local transport → `hub_agent.py` → fleet transport → `orchestrator.py` |

---

## Example Quick Reference

When learning a subsystem, start with the matching example:

| Example | Covers |
|---------|--------|
| [01_basic_server.py](../examples/01_basic_server.py) | Server setup, process config, executor |
| [02_basic_client.py](../examples/02_basic_client.py) | Client connection, start/stop requests |
| [03_multi_client.py](../examples/03_multi_client.py) | Multiple panels, ownership model |
| [04_restart_coordination.py](../examples/04_restart_coordination.py) | Restart FSM, RESTART_NOTIFY/READY |
| [05_configuration.py](../examples/05_configuration.py) | JSON config loading |
| [06_testing_with_inmemory.py](../examples/06_testing_with_inmemory.py) | InMemoryTransport for unit tests |
| [07_snapshot_and_views.py](../examples/07_snapshot_and_views.py) | Immutable snapshots, HubView |
| [08_web_dashboard.py](../examples/08_web_dashboard.py) | FastAPI web dashboard |
| [09_logging_integration.py](../examples/09_logging_integration.py) | Centralized logging |
| [10_admin_dashboard.py](../examples/10_admin_dashboard.py) | Admin controls |
| [11_eventbus_transport.py](../examples/11_eventbus_transport.py) | RabbitMQ EventBus setup |
| [12_fleet_basic.py](../examples/12_fleet_basic.py) | Fleet orchestrator + agents |
| [13_fleet_ci_integration.py](../examples/13_fleet_ci_integration.py) | Fleet CI/CD usage |
| [14_fleet_web_dashboard.py](../examples/14_fleet_web_dashboard.py) | Fleet REST API + dashboard |
