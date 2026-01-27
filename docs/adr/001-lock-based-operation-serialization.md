# ADR-001: Lock-Based Operation Serialization vs Flag-Based Rollback

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

The original `ta-framework-tsb/process_hub` implementation used a flag-based approach (`rollback_event`) to coordinate process start/stop operations and prevent race conditions during rollback:

```python
# Original approach
class ProcessControl:
    def __init__(self):
        self.rollback_event = threading.Event()

    def get_rollback_status(self):
        return self.rollback_event.is_set()

    def start_process_by_name(self, requester, cmd_name):
        # Check flag before starting
        if self.get_rollback_status():
            return (False, f"[Rollback] Skipped starting {cmd_name}")
        # ... start process ...

# In server
def start_process(self, msg):
    if failed:
        self.process_control.rollback_event.set()   # Block new starts
        for process in started_processes:
            self.stop_process(process)              # Rollback
        self.process_control.rollback_event.clear() # Allow starts again
```

This approach has several issues:

1. **Race conditions**: Time gap between checking the flag and performing the operation allows another thread to change state.

2. **Exception safety**: Manual `set()`/`clear()` calls can leave the flag in an incorrect state if an exception occurs.

3. **Forgotten checks**: Developers must remember to check `get_rollback_status()` in every location that starts processes.

4. **Scattered logic**: Rollback coordination logic is spread across multiple classes and methods.

### Illustrated Risks of Flag-Based Approach

```python
# Risk 1: Race condition
if not self.get_rollback_status():  # Check
    # ← Another thread could set rollback_event HERE
    self.start_process(name)         # Start (but rollback already started!)

# Risk 2: Forgotten clear on exception
self.rollback_event.set()
for proc in processes:
    self.stop_process(proc)  # ← If exception here, flag stays set forever!
self.rollback_event.clear()

# Risk 3: Forgotten check
def some_other_function():
    # Developer forgets to check get_rollback_status()
    self.start_process(name)  # Oops, started during rollback
```

### Thread Interleaving Scenario

```
Thread A: Start [proc1, proc2, proc3]
Thread B: Start [proc4, proc5]

Timeline with Flag-Based Approach:
─────────────────────────────────────────────────────────────────────────────────
Thread A: check flag ─→ start proc1 ─→ start proc2 ─→ FAIL ─→ set flag ─→ ...
Thread B:          check flag ─→ start proc4 ← RACE! Started during rollback!
─────────────────────────────────────────────────────────────────────────────────

Timeline with Lock-Based Approach:
─────────────────────────────────────────────────────────────────────────────────
Thread A: [lock] start proc1 → start proc2 → FAIL → rollback proc2,proc1 [unlock]
Thread B: [waiting.................................................] [lock] start proc4...
─────────────────────────────────────────────────────────────────────────────────
```

## Decision

We will use a **lock-based approach** with Python's `threading.Lock` to serialize all process start/stop operations, with automatic rollback contained within the locked section.

### New Approach (Lock-based)

```python
def handle_start_request(self, req):
    with self._operation_lock:  # ← Atomic, exception-safe
        started_procs = []
        # No other thread can start/stop while we're here
        for proc in req.process_list:
            success = self._process_starter(proc)
            if not success:
                # Rollback happens HERE, still inside lock
                for started in started_procs:
                    self._process_stopper(started)
                break
            started_procs.append(proc)
        # Lock automatically released, even on exception
```

### Full Implementation

```python
# New approach
class ProcessHubCore:
    def __init__(self):
        self._operation_lock = threading.Lock()

    def handle_start_request(self, req: ProcessStartRequest) -> list[OutgoingMessage]:
        with self._operation_lock:  # Atomic, exception-safe
            started_procs = []
            failed_procs = []

            for proc_name in req.process_list:
                success, msg, pid = self._process_starter(proc_name)
                if success:
                    started_procs.append(proc_name)
                else:
                    failed_procs.append(proc_name)
                    break  # Stop on first failure

            # Automatic rollback on failure (still inside lock)
            if failed_procs:
                for name in started_procs:
                    self._process_stopper(name, force=True)
                    self._registry.update_state(name, ProcessState.STOPPED)

            return [...]  # Response message
        # Lock automatically released here, even on exception
```

### Key Design Principles

1. **Single point of serialization**: All operations go through `_operation_lock`.

2. **Atomic operations**: The entire start request (including potential rollback) is one atomic operation.

3. **Exception safety**: The `with` statement guarantees lock release.

4. **Encapsulation**: Rollback is an internal implementation detail, not exposed to external code.

## Consequences

### Positive

1. **No race conditions**: Operations are truly atomic - impossible for another thread to interfere mid-operation.

2. **Exception-safe**: Lock is always released by the `with` statement, even if an exception occurs.

3. **No forgotten checks**: Serialization is enforced by design, not by developer discipline.

4. **Simpler code**: No need to scatter `get_rollback_status()` checks throughout the codebase.

5. **Better encapsulation**: External code doesn't need to know about rollback mechanics.

6. **Easier testing**: Single lock is easier to reason about than distributed flags.

### Negative

1. **No external visibility**: External code cannot query "is rollback in progress?" This is intentional - rollback is an internal detail.

2. **Potential blocking**: If one operation takes a long time, others must wait. However, this is the desired behavior for consistency.

3. **Deadlock risk**: If the lock is acquired recursively or in wrong order with other locks, deadlocks could occur. Mitigated by:
   - Clear lock ordering documentation
   - Single entry points for operations
   - No nested lock acquisition in public methods

### Neutral

1. **Different mental model**: Developers familiar with the flag-based approach need to understand the new design.

## Alternatives Considered

### 1. Keep Flag-Based Approach (Rejected)

Keeping `rollback_event` would maintain compatibility but perpetuate the race condition and exception safety issues.

### 2. Read-Write Lock (Rejected)

Using `threading.RWLock` to allow concurrent reads but exclusive writes:

```python
# Multiple threads can check status
with self._rwlock.read():
    if self.is_rollback_in_progress:
        return

# Only one thread can modify
with self._rwlock.write():
    self._do_rollback()
```

Rejected because:
- Adds complexity without clear benefit
- Our operations are mostly writes (start/stop), not reads
- Python's GIL already limits true concurrency

### 3. Queue-Based Approach (Deferred)

Using a command queue to serialize operations:

```python
class OperationQueue:
    def submit(self, operation: Operation) -> Future:
        self._queue.put(operation)
        return operation.future

# Worker thread processes operations sequentially
def _worker(self):
    while True:
        op = self._queue.get()
        result = op.execute()
        op.future.set_result(result)
```

Deferred because:
- More complex implementation
- May be useful for future async/distributed scenarios
- Current lock-based approach is sufficient for single-process deployment

### 4. Hybrid Approach (Rejected)

Combining lock with status flag:

```python
with self._operation_lock:
    self._rollback_in_progress = True
    try:
        # ... rollback ...
    finally:
        self._rollback_in_progress = False
```

Rejected because:
- The flag is redundant - if you have the lock, you know you're the only one operating
- Adds complexity without benefit

## References

- [Python threading.Lock documentation](https://docs.python.org/3/library/threading.html#lock-objects)
- [RAII pattern](https://en.wikipedia.org/wiki/Resource_acquisition_is_initialization)
- Original implementation: `ta-framework-tsb/ta_framework/project/process_hub/process_control.py`
