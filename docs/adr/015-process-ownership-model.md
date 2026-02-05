# ADR-015: Process Ownership Model (Reference Counting)

## Status

Accepted

## Date

2026-01-22

## Author

Nguyen Huynh Tri Cuong (MS/EMC51)

## Reviewer

- Nguyen Huynh Tri Cuong (MS/EMC51)

## History

| Date | Version | Description |
|------|---------|-------------|
| 2026-01-22 | 1.0 | Initial version |

## Context

In ProcessHub, multiple clients (panels) often need the same process. For example:
- Test Panel A needs `system_manager` for test execution
- Test Panel B also needs `system_manager` for a different test
- Both panels run concurrently

### The Problem

How should ProcessHub handle shared processes?

**Scenario 1: Exclusive Ownership**
```
Panel A: request_start(system_manager)  → Process starts
Panel B: request_start(system_manager)  → ERROR: Already owned by A
```
Problem: Panel B cannot run tests until Panel A finishes.

**Scenario 2: No Ownership Tracking**
```
Panel A: request_start(system_manager)  → Process starts
Panel B: request_start(system_manager)  → No-op (already running)
Panel A: request_stop(system_manager)   → Process stops
Panel B: Still expects process running  → TEST FAILS
```
Problem: Panel A stopping the process breaks Panel B.

**Scenario 3: Duplicate Processes**
```
Panel A: request_start(system_manager)  → Process instance 1 starts
Panel B: request_start(system_manager)  → Process instance 2 starts
```
Problem: Some processes cannot have multiple instances (port conflicts, hardware access).

### Requirements

| Requirement | Description |
|-------------|-------------|
| Shared access | Multiple panels can use the same process |
| Safe stopping | Process stops only when no one needs it |
| No duplicates | Only one instance of each process runs |
| Crash recovery | All users notified when process dies |
| Visibility | Can see who is using each process |

## Decision

**Use reference counting with ownership tracking** for process management.

### The Model

Each process tracks a set of **requesters** (panels that have requested it):

```python
@dataclass
class ProcessInfo:
    name: str
    state: ProcessState
    pid: Optional[int]
    requesters: Set[str]  # Set of panel_ids
```

### Rules

| Action | Condition | Result |
|--------|-----------|--------|
| `request_start(P)` | Process not running | Start process, add requester |
| `request_start(P)` | Process already running | Just add requester (no-op on process) |
| `request_stop(P)` | Multiple requesters | Remove requester, process keeps running |
| `request_stop(P)` | Last requester | Remove requester, stop process |
| Panel disconnects | Panel was requester | Auto-remove from all processes |

### Visual Example

```
Time    Action                      Requesters      Process State
─────────────────────────────────────────────────────────────────
T1      Panel A: start(worker)      {A}             STARTING → RUNNING
T2      Panel B: start(worker)      {A, B}          RUNNING (no change)
T3      Panel C: start(worker)      {A, B, C}       RUNNING (no change)
T4      Panel A: stop(worker)       {B, C}          RUNNING (still needed)
T5      Panel B disconnects         {C}             RUNNING (still needed)
T6      Panel C: stop(worker)       {}              STOPPING → STOPPED
```

### Implementation

```python
class ProcessRegistry:
    def add_requester(self, process_name: str, panel_id: str) -> bool:
        """Add panel as requester. Returns True if process should start."""
        with self._lock:
            info = self._processes.get(process_name)
            if info is None:
                # New process
                self._processes[process_name] = ProcessInfo(
                    name=process_name,
                    state=ProcessState.REGISTERED,
                    requesters={panel_id},
                )
                return True  # Should start

            # Existing process
            info.requesters.add(panel_id)
            return info.state == ProcessState.STOPPED  # Start if stopped

    def remove_requester(self, process_name: str, panel_id: str) -> bool:
        """Remove panel as requester. Returns True if process should stop."""
        with self._lock:
            info = self._processes.get(process_name)
            if info is None:
                return False

            info.requesters.discard(panel_id)
            return len(info.requesters) == 0  # Stop if no requesters
```

### Crash Recovery with Ownership

When a process crashes, ProcessHub notifies **all requesters**:

```
Process "worker" dies unexpectedly

Server checks: requesters = {Panel_A, Panel_B, Panel_C}

Server sends ProcessRestartNotify to:
  - Panel_A
  - Panel_B
  - Panel_C

All three panels must acknowledge before restart.
```

This ensures every user of the process knows about the crash and can prepare for restart.

### Dashboard Visibility

The web dashboard shows ownership:

```
┌─────────────────────────────────────────────────────────────┐
│ Processes                                                   │
├──────────────┬───────┬────────────┬────────────────────────┤
│ Name         │ PID   │ Status     │ Owners                 │
├──────────────┼───────┼────────────┼────────────────────────┤
│ system_mgr   │ 12345 │ ● RUNNING  │ Panel_A, Panel_B       │
│ worker_1     │ 12346 │ ● RUNNING  │ Panel_A                │
│ worker_2     │ 12347 │ ● RUNNING  │ Panel_B, Panel_C       │
│ data_logger  │ -     │ ○ STOPPED  │ -                      │
└──────────────┴───────┴────────────┴────────────────────────┘
```

## Consequences

### Positive

- **Resource sharing**: Multiple panels can use expensive/limited resources
- **Safe cleanup**: Processes only stop when truly unused
- **No orphans**: Disconnecting panels auto-release their processes
- **Visibility**: Clear view of who uses what
- **Crash coordination**: All affected users notified on failure
- **Simple mental model**: "Request what you need, release when done"

### Negative

- **Memory overhead**: Tracking requester sets for each process
- **Complexity**: More logic than simple start/stop
- **Potential leaks**: If panel forgets to release, process keeps running

### Neutral

- **Different from traditional**: Not like systemd or supervisor (single owner)
- **Requires panel ID**: Each client must have unique identifier

## Alternatives Considered

### 1. Exclusive Ownership (Rejected)

Each process has exactly one owner.

```python
class ProcessInfo:
    owner: Optional[str]  # Single panel_id
```

Rejected because:
- Blocks concurrent access to shared resources
- Common in test automation to need same process from multiple panels
- Would require complex queuing/waiting mechanisms

### 2. No Ownership Tracking (Rejected)

Processes just run or don't run, no tracking of who started them.

Rejected because:
- Cannot safely stop processes (might break other users)
- No way to notify affected panels on crash
- No visibility into usage

### 3. Lease-Based Ownership (Deferred)

Ownership expires after timeout, must be renewed.

```python
class ProcessInfo:
    requesters: Dict[str, datetime]  # panel_id -> lease_expiry
```

Deferred because:
- Adds complexity (heartbeats, renewals)
- Current disconnect detection handles most cases
- Could add later if needed for very long-running scenarios

### 4. Priority-Based Ownership (Deferred)

Higher priority panels can preempt lower priority ones.

Deferred because:
- Adds complexity in deciding priorities
- Current model treats all panels equally
- Could add later for specific use cases

## References

- [Reference Counting (Wikipedia)](https://en.wikipedia.org/wiki/Reference_counting)
- [Shared Resource Pattern](https://en.wikipedia.org/wiki/Shared_resource)
- Source: `ProcessHub/core/process_registry.py`
- Related: ADR-004 (Restart State Machine)
