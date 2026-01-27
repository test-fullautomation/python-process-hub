# ADR-010: Server Shutdown Notification Protocol

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

When the ProcessHub server shuts down gracefully or resets, connected clients were not notified. This caused several problems:

1. **Clients remain in "registered" state**: They believe they're still connected
2. **Subsequent requests fail unexpectedly**: No clear error message
3. **No opportunity to cleanup**: Clients can't save state before disconnect
4. **Reset triggers restart coordination**: Stopping processes during reset caused the server to detect them as "dead" and initiate restart protocol

```
Original Behavior (Reset):

  Admin clicks "Reset Hub"
       │
       ▼
  Server stops all processes
       │
       ▼
  Health check detects "dead" processes
       │
       ▼
  Restart coordination triggered (WRONG!)
       │
       ▼
  Clients confused - they weren't notified
```

### The Reset Problem

When implementing hub reset functionality, we discovered a critical issue:

```python
# Original reset - BROKEN
def reset_hub():
    for process in processes:
        executor.stop(process)  # Server detects as "dead"
    # Health check runs...
    # "Dead processes detected! Starting restart coordination!"
    # Clients get RESTART_NOTIFY instead of knowing hub was reset
```

## Decision

We will implement a **Server Shutdown Notification Protocol** with a new message type `ServerShutdownNotify`:

### Message Definition

```python
@dataclass
class ServerShutdownNotify(MessageBase):
    """
    Server -> Client notification for shutdown/reset.

    Sent to all connected clients before:
    - Server shutdown (stop() called)
    - Hub reset (reset() called)
    """
    panel_id: str = ""
    reason: str = "shutdown"  # "shutdown" or "reset"
    message: str = ""
```

### Protocol Flow

```
Graceful Shutdown:

  Server.stop() called
       │
       ▼
  Create SHUTDOWN_NOTIFY for each client
       │
       ├──► Client A: {reason: "shutdown", message: "Server shutting down"}
       ├──► Client B: {reason: "shutdown", message: "Server shutting down"}
       └──► Client C: {reason: "shutdown", message: "Server shutting down"}
       │
       ▼
  Stop transport
       │
       ▼
  Server exits


Hub Reset:

  Server.reset() called
       │
       ▼
  Create SHUTDOWN_NOTIFY for each client
       │
       ├──► Client A: {reason: "reset", message: "Hub is being reset"}
       ├──► Client B: {reason: "reset", message: "Hub is being reset"}
       └──► Client C: {reason: "reset", message: "Hub is being reset"}
       │
       ▼
  Stop all processes (no restart triggered - registry cleared)
       │
       ▼
  Clear connection registry
       │
       ▼
  Reset restart state machine to IDLE
       │
       ▼
  Server continues running (ready for new connections)
```

### Server Implementation

```python
# ProcessHubCore
def reset(self) -> tuple[bool, str, list[OutgoingMessage]]:
    messages = []

    # Collect panel IDs BEFORE clearing
    panel_ids = list(self._connections.keys())

    # Create notifications
    for panel_id in panel_ids:
        messages.append(OutgoingMessage(
            msg_type=MessageType.SHUTDOWN_NOTIFY,
            payload=ServerShutdownNotify(
                panel_id=panel_id,
                reason="reset",
                message="Hub is being reset. All connections will be cleared.",
            ),
            target_panel=panel_id,
        ))

    # Now safe to clear everything
    self._registry.clear_all()
    self._connections.clear()
    self._restart_fsm.reset_to_idle()

    return True, "Reset complete", messages


def shutdown(self) -> list[OutgoingMessage]:
    messages = []

    for panel_id in self._connections.keys():
        messages.append(OutgoingMessage(
            msg_type=MessageType.SHUTDOWN_NOTIFY,
            payload=ServerShutdownNotify(
                panel_id=panel_id,
                reason="shutdown",
                message="Server is shutting down.",
            ),
            target_panel=panel_id,
        ))

    # Cleanup...
    return messages
```

### Client Handling

```python
# ProcessHubClient
def _on_shutdown_notify(self, data: dict) -> None:
    reason = data.get("reason", "unknown")
    message = data.get("message", "")

    logger.warning("Server %s: %s", reason, message)

    # Mark as unregistered
    self._is_registered = False

    # Notify application
    self.controller.on_server_shutdown(data)


# Application code
client.controller.connect("server_shutdown", on_shutdown)

def on_shutdown(data):
    if data["reason"] == "reset":
        # Server reset - can reconnect immediately
        schedule_reconnect(delay=1)
    else:
        # Server shutdown - wait longer or exit
        schedule_reconnect(delay=10)
```

## Consequences

### Positive

1. **Clear client notification**: Clients know exactly why they're being disconnected
2. **Distinguishes reset from shutdown**: Different handling for each case
3. **Prevents false restart coordination**: Reset clears state before health check runs
4. **Graceful cleanup opportunity**: Clients can save state before disconnect
5. **Immediate reconnect possible**: After reset, clients can reconnect right away

### Negative

1. **Not guaranteed delivery**: If server crashes, notification can't be sent (see ADR-009 for crash detection)
2. **Race condition window**: Small window between notification and actual disconnect
3. **New message type**: Clients must handle new `SHUTDOWN_NOTIFY` topic

### Neutral

1. **Backward compatible**: Old clients ignore unknown message types
2. **Complements TCP keepalive**: Graceful cases use notification, crashes use keepalive

## Alternatives Considered

### 1. Reuse RESTART_NOTIFY for Reset (Rejected)

Send `RESTART_NOTIFY` with empty process list to indicate reset:

```python
ProcessRestartNotify(panel_id=id, killed_processes=[])  # Means "reset"
```

Rejected because:
- Semantic confusion: restart ≠ reset
- Clients would try restart coordination protocol
- No way to distinguish shutdown from reset

### 2. Connection-Level Disconnect Message (Rejected)

Send `UnregisterConnectionResponse` to each client:

```python
UnregisterConnectionResponse(panel_id=id, message="Server shutting down")
```

Rejected because:
- Implies client-initiated unregister
- Doesn't convey reason (shutdown vs reset)
- Misleading semantics

### 3. Rely on Transport Disconnect Only (Rejected)

Let clients detect disconnect via transport layer:

```python
# Client detects TCP disconnect
on_transport_disconnect():
    handle_server_gone()
```

Rejected because:
- No distinction between crash and intentional shutdown
- No distinction between shutdown and reset
- No opportunity for graceful handling

## References

- [Graceful Shutdown Patterns](https://docs.microsoft.com/en-us/azure/architecture/patterns/graceful-degradation)
- ADR-009: TCP Keepalive for crash detection (complementary)
- Source: `ProcessHub/core/models.py` (ServerShutdownNotify)
- Source: `ProcessHub/core/hub_core.py` (reset, shutdown methods)
- Source: `ProcessHub/runtime/client.py` (_on_shutdown_notify)
