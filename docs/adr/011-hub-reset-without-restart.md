# ADR-011: Hub Reset Without Server Restart

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

During development and testing, administrators need a way to reset the ProcessHub to a clean state without restarting the server process. Use cases include:

1. **Testing**: Clear state between test runs without restarting server
2. **Recovery**: Clear stale connections after network issues
3. **Maintenance**: Remove all clients and processes for maintenance window
4. **Development**: Quick reset during development iterations

### The Problem

Without a reset function, the only way to get a clean state was to restart the server:

```bash
# Old approach - restart entire server
pkill -f process_hub_server
python process_hub_server.py
```

This was problematic because:
- **Downtime**: Server unavailable during restart
- **Lost configuration**: Runtime configuration lost
- **Slow**: Full startup sequence required
- **Disruptive**: All infrastructure (ZMQ broker, web server) restarts

### Initial Reset Attempt (Failed)

The first implementation simply stopped processes via the executor:

```python
# First attempt - BROKEN
def reset_hub():
    for name in process_config.keys():
        if executor.is_running(name):
            executor.stop(name, force=True)
    return True, "Reset complete"
```

This failed because:
1. Server's health check detected stopped processes as "dead"
2. Restart coordination was triggered
3. Connections were not cleared
4. Server tried to restart the "dead" processes

## Decision

We will implement a comprehensive `reset()` method on `ProcessHubCore` and `ProcessHubServer` that atomically clears all state:

### Reset Operation Sequence

```
reset() called
     │
     ▼
┌─────────────────────────────────────────┐
│  1. Collect connected panel IDs         │
│     (before clearing connections)       │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│  2. Create SHUTDOWN_NOTIFY messages     │
│     for each connected client           │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│  3. Stop all processes via executor     │
│     (within operation lock)             │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│  4. Clear process registry              │
│     (prevents "dead" detection)         │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│  5. Clear connection registry           │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│  6. Reset restart state machine to IDLE │
│     (prevents pending restart)          │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│  7. Send notifications to clients       │
└─────────────────────────────────────────┘
     │
     ▼
  Return (success, message)
```

### Implementation

```python
# ProcessHubCore
def reset(self) -> tuple[bool, str, list[OutgoingMessage]]:
    """
    Reset the hub to a fresh state.

    Returns:
        (success, message, outgoing_messages)
    """
    logger.info("Resetting ProcessHubCore to fresh state")

    stopped_count = 0
    errors = []
    messages = []

    # 1. Collect panel IDs before clearing
    with self._connection_lock:
        panel_ids = list(self._connections.keys())
        conn_count = len(panel_ids)

    # 2. Create shutdown notifications
    for panel_id in panel_ids:
        messages.append(OutgoingMessage(
            msg_type=MessageType.SHUTDOWN_NOTIFY,
            payload=ServerShutdownNotify(
                panel_id=panel_id,
                reason="reset",
                message="Hub is being reset.",
            ),
            target_panel=panel_id,
        ))

    # 3-4. Stop processes and clear registry (atomic)
    with self._operation_lock:
        for name in self._registry.get_all_names():
            try:
                if self._process_stopper(name, force=True):
                    stopped_count += 1
            except Exception as e:
                errors.append(f"{name}: {e}")

        # Clear IMMEDIATELY after stopping
        self._registry.clear_all()

    # 5. Clear connections
    with self._connection_lock:
        self._connections.clear()

    # 6. Reset restart state machine
    self._restart_fsm.reset_to_idle()

    msg = f"Stopped {stopped_count} processes, cleared {conn_count} connections."
    return True, msg, messages


# ProcessHubServer
def reset(self) -> tuple[bool, str]:
    """Reset hub and send notifications."""
    success, message, messages = self._core.reset()

    if messages:
        self._send_messages(messages)

    return success, message
```

### Web Dashboard Integration

```python
# WebView admin endpoint
@app.post("/api/admin/reset")
async def reset_hub():
    if self._reset_hub is None:
        raise HTTPException(501, "Reset not enabled")

    success, message = self._reset_hub()
    return {"success": success, "message": message}
```

```javascript
// Dashboard UI
function resetHub() {
    if (!confirm('Reset hub? All connections will be cleared.')) {
        return;
    }

    fetch('/api/admin/reset', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            showResult(data.success, data.message);
            fetchData();  // Refresh dashboard
        });
}
```

## Consequences

### Positive

1. **No server restart required**: Hub can be reset in milliseconds
2. **Atomic operation**: All state cleared together, no inconsistency
3. **No false restart triggers**: Registry cleared before health check runs
4. **Clients notified**: Clients receive `SHUTDOWN_NOTIFY` with reason="reset"
5. **Preserves configuration**: Process configs remain, only runtime state cleared
6. **Web dashboard support**: Reset available via admin UI

### Negative

1. **Destructive operation**: All state lost (by design, but needs confirmation)
2. **No partial reset**: Cannot reset just processes or just connections
3. **Client reconnection required**: Clients must re-register after reset

### Neutral

1. **Idempotent**: Calling reset() multiple times is safe
2. **Returns notification messages**: Server responsible for sending them

## Alternatives Considered

### 1. Restart Server Process (Rejected)

Kill and restart the entire server:

```bash
pkill process_hub && python process_hub_server.py
```

Rejected because:
- Downtime during restart
- Lost runtime configuration
- Slow startup sequence
- Disruptive to infrastructure (broker, web server)

### 2. Clear Registries Individually (Rejected)

Expose separate methods for each registry:

```python
server.clear_connections()
server.clear_processes()
server.reset_restart_state()
```

Rejected because:
- Inconsistent state between calls
- Race conditions with health check
- User must call in correct order
- Easy to forget one

### 3. Soft Reset (Mark as Disconnected) (Rejected)

Mark connections as disconnected without clearing:

```python
for conn in connections:
    conn.state = "disconnected"
```

Rejected because:
- Stale data remains in memory
- Confusing state
- Eventually need hard reset anyway

### 4. Reset with Grace Period (Deferred)

Wait for clients to acknowledge before clearing:

```python
def reset(self, grace_period=30):
    notify_all_clients("reset_pending")
    wait(grace_period)
    clear_all()
```

Deferred because:
- Adds complexity
- Current use cases don't need it
- Can be added later if required

## References

- ADR-010: Server Shutdown Notification (notification protocol)
- ADR-004: Restart State Machine (reset_to_idle method)
- Source: `ProcessHub/core/hub_core.py` (reset method)
- Source: `ProcessHub/runtime/server.py` (server reset wrapper)
- Source: `ProcessHub/ui/web_view.py` (admin reset endpoint)
