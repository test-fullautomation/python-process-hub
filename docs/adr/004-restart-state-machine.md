# ADR-004: Restart Coordination as Explicit State Machine

## Status

Accepted

## Date

2026-01-16

## Author

Nguyen Huynh Tri Cuong (MS/EMC51)

## Reviewer

- Nguyen Huynh Tri Cuong (MS/EMC51)

## History

| Date | Version | Description |
|------|---------|-------------|
| 2026-01-16 | 1.0 | Initial version |

## Context

The original implementation tracked restart state using scattered flags and lists:

```python
# Original: Scattered restart state
class ProcessHubServer:
    def __init__(self):
        self.is_notify = False                    # Flag: notification in progress
        self.killed_process = []                  # List of dead processes
        self.not_ready_panels = []                # Panels not yet acknowledged
        self.restart_notify_panels = []           # All panels to notify

    def health_check(self):
        if dead_processes:
            self.is_notify = True
            self.killed_process = dead_processes
            self.restart_notify_panels = get_affected_panels()
            self.not_ready_panels = self.restart_notify_panels.copy()
            # Send notifications...

    def on_restart_ready(self, panel_id):
        if panel_id in self.not_ready_panels:
            self.not_ready_panels.remove(panel_id)

        if len(self.not_ready_panels) == 0:
            # All ready, do restart
            self.do_restart()
            self.is_notify = False
            self.killed_process = []
```

### Problems with Scattered State

```
┌─────────────────────────────────────────────────────────────┐
│                    Scattered State                           │
│                                                              │
│  is_notify = True      ← What state are we in?              │
│  killed_process = [A,B] ← Which processes died?             │
│  not_ready_panels = [P1] ← Who hasn't acknowledged?         │
│  restart_notify_panels = [P1,P2] ← Who was notified?        │
│                                                              │
│  Problems:                                                   │
│  1. Hard to understand current state                         │
│  2. No validation of state transitions                       │
│  3. No timeout handling                                      │
│  4. Possible inconsistent state                              │
│  5. Race conditions between check and update                 │
└─────────────────────────────────────────────────────────────┘
```

### Failure Scenarios

```python
# Scenario 1: Panel never acknowledges
health_check() → notify panels → wait forever (no timeout!)

# Scenario 2: Inconsistent state
self.is_notify = True
# Exception occurs here
self.killed_process = dead_processes  # Never set!

# Scenario 3: Unclear state
if self.is_notify and len(self.not_ready_panels) == 0:
    # Are we waiting? Restarting? Done?
```

## Decision

We will implement restart coordination as an **explicit finite state machine (FSM)** with all state in a single `RestartContext` dataclass under one lock.

### State Machine Diagram

```
                    ┌──────────────────┐
                    │                  │
                    ▼                  │
┌──────┐  detect  ┌─────────┐  send  ┌───────────┐
│ IDLE │─────────►│DETECTING│───────►│ NOTIFYING │
└──────┘          └─────────┘        └─────┬─────┘
    ▲                                      │
    │                                      │ all sent
    │                                      ▼
    │            ┌──────────┐        ┌───────────────┐
    │   reset    │  FAILED  │◄───────│ AWAITING_ACK  │
    │◄───────────┤          │timeout └───────┬───────┘
    │            └─────▲────┘                │
    │                  │                     │ all acked
    │                  │ error               ▼
    │                  │              ┌─────────────┐
    │                  └──────────────│ RESTARTING  │
    │                                 └──────┬──────┘
    │                                        │
    │                                        │ success
    │            ┌──────────┐                │
    └────────────┤   DONE   │◄───────────────┘
                 └──────────┘
```

#### State Transitions Explained

The state machine follows a linear flow for successful restart, with failure handling at critical points:

| Transition | Trigger | Description |
|------------|---------|-------------|
| IDLE → DETECTING | Health check finds dead processes | System detects one or more processes have crashed unexpectedly |
| DETECTING → NOTIFYING | Affected panels identified | System identifies which panels need to be notified about the dead processes |
| NOTIFYING → AWAITING_ACK | All notifications sent | Notifications sent to all affected panels; now waiting for acknowledgments |
| AWAITING_ACK → RESTARTING | All panels acknowledged | Every affected panel has called `notify_restart_ready()`, safe to restart |
| AWAITING_ACK → FAILED | Timeout exceeded | Some panels did not acknowledge within timeout period (default: 300s) |
| RESTARTING → DONE | Restart complete | Dead processes successfully restarted |
| RESTARTING → FAILED | Restart error | One or more processes failed to restart |
| DONE → IDLE | Reset | Cleanup and return to monitoring state |
| FAILED → IDLE | Reset | Log error, cleanup, and return to monitoring state |

#### Why Each State Matters

1. **IDLE**: Normal operation - health checks run periodically looking for dead processes

2. **DETECTING**: Brief transition state where we identify affected panels before sending notifications

3. **NOTIFYING**: Sending `ProcessRestartNotify` messages to all affected panels

4. **AWAITING_ACK**: Critical coordination phase - panels must stop their work and acknowledge they're ready for processes to restart. This prevents data corruption from restarting processes while panels are actively using them.

5. **RESTARTING**: Actually stopping dead processes and starting fresh instances

6. **DONE**: Success state - send `ProcessRestartDone` to panels so they can resume work

7. **FAILED**: Error state - restart could not complete (timeout or restart failure). Panels are notified of failure.

### State Definitions

```python
class RestartState(Enum):
    IDLE = "idle"               # No restart in progress
    DETECTING = "detecting"     # Dead processes detected
    NOTIFYING = "notifying"     # Sending notifications to panels
    AWAITING_ACK = "awaiting"   # Waiting for panel acknowledgments
    RESTARTING = "restarting"   # Performing restart
    DONE = "done"               # Restart complete
    FAILED = "failed"           # Restart failed (timeout or error)
```

### Restart Context (Single Source of Truth)

```python
@dataclass
class RestartContext:
    """All restart state in one place, under one lock."""
    state: RestartState = RestartState.IDLE
    killed_processes: list[str] = field(default_factory=list)
    notified_panels: set[str] = field(default_factory=set)
    pending_panels: set[str] = field(default_factory=set)
    started_at: float = 0.0          # For timeout detection
    retry_count: int = 0             # For retry logic
    error_message: Optional[str] = None
```

### State Machine Implementation

```python
class RestartStateMachine:
    """
    Explicit FSM for restart coordination.

    Benefits:
    - Clear state transitions
    - Timeout detection via started_at
    - Retry logic via retry_count
    - Single lock for all state
    - Impossible invalid states
    """

    def __init__(self, timeout: float = 300.0, max_retries: int = 3):
        self._context = RestartContext()
        self._lock = threading.Lock()
        self._timeout = timeout
        self._max_retries = max_retries

    @property
    def state(self) -> RestartState:
        with self._lock:
            return self._context.state

    def detect_killed(self, processes: list[str], panels: list[str]) -> bool:
        """Transition: IDLE → DETECTING → NOTIFYING"""
        with self._lock:
            if self._context.state != RestartState.IDLE:
                return False  # Already in restart

            self._context.state = RestartState.DETECTING
            self._context.killed_processes = processes
            self._context.notified_panels = set(panels)
            self._context.pending_panels = set(panels)
            self._context.started_at = time.time()
            return True

    def notifications_sent(self) -> bool:
        """Transition: NOTIFYING → AWAITING_ACK"""
        with self._lock:
            if self._context.state != RestartState.DETECTING:
                return False
            self._context.state = RestartState.AWAITING_ACK
            return True

    def panel_acknowledged(self, panel_id: str) -> tuple[bool, bool]:
        """
        Record panel acknowledgment.
        Returns (success, all_ready).
        """
        with self._lock:
            if self._context.state != RestartState.AWAITING_ACK:
                return False, False

            self._context.pending_panels.discard(panel_id)
            all_ready = len(self._context.pending_panels) == 0
            return True, all_ready

    def begin_restart(self) -> bool:
        """Transition: AWAITING_ACK → RESTARTING"""
        with self._lock:
            if self._context.state != RestartState.AWAITING_ACK:
                return False
            if len(self._context.pending_panels) > 0:
                return False  # Still waiting
            self._context.state = RestartState.RESTARTING
            return True

    def check_timeout(self) -> bool:
        """Check if restart has timed out."""
        with self._lock:
            if self._context.state == RestartState.IDLE:
                return False
            elapsed = time.time() - self._context.started_at
            return elapsed > self._timeout

    def get_snapshot(self) -> dict:
        """Get immutable snapshot for UI."""
        with self._lock:
            return {
                "state": self._context.state.value,
                "killed_processes": list(self._context.killed_processes),
                "pending_panels": list(self._context.pending_panels),
                "notified_panels": list(self._context.notified_panels),
            }
```

### State Transition Validation

```python
# Valid transitions only
VALID_TRANSITIONS = {
    RestartState.IDLE: [RestartState.DETECTING],
    RestartState.DETECTING: [RestartState.AWAITING_ACK],
    RestartState.AWAITING_ACK: [RestartState.RESTARTING, RestartState.FAILED],
    RestartState.RESTARTING: [RestartState.DONE, RestartState.FAILED],
    RestartState.DONE: [RestartState.IDLE],
    RestartState.FAILED: [RestartState.IDLE],
}

# Invalid transition caught at runtime
def transition_to(self, new_state: RestartState) -> bool:
    with self._lock:
        if new_state not in VALID_TRANSITIONS[self._context.state]:
            logger.error("Invalid transition: %s → %s", self._context.state, new_state)
            return False
        self._context.state = new_state
        return True
```

## Consequences

### Positive

1. **Clear current state**: Always know exactly what phase restart is in
   ```python
   if fsm.state == RestartState.AWAITING_ACK:
       print(f"Waiting for {len(fsm.pending_panels)} panels")
   ```

2. **Timeout handling**: Built-in timeout detection
   ```python
   if fsm.check_timeout():
       fsm.transition_to(RestartState.FAILED)
   ```

3. **Retry logic**: Easy to implement retry with counter
   ```python
   if fsm.retry_count < fsm.max_retries:
       fsm.retry()
   ```

4. **Impossible invalid states**: State machine enforces valid transitions

5. **Single lock**: No race conditions between state variables

6. **Debuggable**: Can log state transitions for debugging
   ```
   [INFO] Transition: IDLE → DETECTING (killed: [proc1, proc2])
   [INFO] Transition: DETECTING → AWAITING_ACK (panels: [P1, P2])
   [INFO] Panel P1 acknowledged (pending: [P2])
   [INFO] Panel P2 acknowledged (pending: [])
   [INFO] Transition: AWAITING_ACK → RESTARTING
   ```

### Negative

1. **More code**: FSM is more verbose than simple flags

2. **Learning curve**: Developers must understand state machine pattern

3. **Rigidity**: Adding new states requires updating transition table

### Neutral

1. **State explosion**: More states means more explicit handling, but also more clarity

## Alternatives Considered

### 1. Keep Flag-Based Approach (Rejected)

Would perpetuate unclear state and race condition issues.

### 2. Event-Sourced State (Deferred)

Track all events and derive current state:

```python
events = [
    ProcessKilled(["proc1"]),
    PanelNotified("P1"),
    PanelAcknowledged("P1"),
    RestartCompleted(),
]
current_state = derive_state(events)
```

Deferred because:
- More complex implementation
- Useful for audit trails but overkill for current needs

### 3. Actor Model (Deferred)

Each restart as an actor with message passing:

```python
class RestartActor:
    async def receive(self, msg):
        match msg:
            case DetectKilled(processes):
                self.state = "detecting"
                await self.notify_panels()
```

Deferred because:
- Requires async infrastructure
- Current synchronous FSM is sufficient

## References

- [Finite State Machine Pattern](https://en.wikipedia.org/wiki/Finite-state_machine)
- [State Pattern (GoF)](https://refactoring.guru/design-patterns/state)
- Source: `ProcessHub/core/restart_state.py`
