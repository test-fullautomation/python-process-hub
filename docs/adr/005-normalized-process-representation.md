# ADR-005: Normalized Process Representation with Typed State

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

The original implementation used inconsistent types for process state:

```python
# Original: Inconsistent status field
class ProcessManager:
    def __init__(self):
        self.shared_info = {}

    def register(self, name):
        # Status initialized as string
        self.shared_info[name] = {"status": "None", "pid": 0}

    def start(self, name):
        # Status changed to boolean True
        self.shared_info[name]["status"] = True

    def stop(self, name):
        # Status changed to boolean False
        self.shared_info[name]["status"] = False

    def health_check(self):
        for name, info in self.shared_info.items():
            if info["status"] == True:  # Compare bool
                # ... check if running ...
            elif info["status"] == "None":  # Compare string!
                # ... different handling ...
```

### Problems with Mixed Types

```python
# Problem 1: Type confusion
status = self.shared_info["proc1"]["status"]
if status:  # Is this True, "None", or something else?
    pass

# Problem 2: No IDE support
proc_info = self.shared_info["proc1"]
proc_info["stauts"] = True  # Typo not caught!

# Problem 3: Unclear semantics
# What does status=True mean?
# - Process is running?
# - Process started successfully?
# - Process should be running?

# Problem 4: No validation
self.shared_info["proc1"]["status"] = "maybe"  # Invalid but allowed
```

### State Representation Comparison

```
Original:
┌─────────────────────────────────────────────┐
│ shared_info["proc1"] = {                     │
│     "status": True/False/"None",  ← Mixed!  │
│     "pid": 1234,                            │
│     "requester": ["panel1", "panel2"]       │
│ }                                           │
└─────────────────────────────────────────────┘

Problems:
- "None" string vs None object
- True/False vs string status
- No IDE autocomplete
- No type checking
- Easy to make typos
```

## Decision

We will use **typed dataclasses with enums** for process representation:

### ProcessState Enum

```python
class ProcessState(Enum):
    """
    Explicit process states with clear semantics.

    Each state has a specific meaning:
    """
    REGISTERED = "registered"   # In config, not yet started
    STARTING = "starting"       # Subprocess created, waiting for confirmation
    RUNNING = "running"         # Confirmed running (health check passed)
    STOPPING = "stopping"       # Stop requested, waiting for termination
    STOPPED = "stopped"         # Process exited normally
    DEAD = "dead"               # Was running, killed unexpectedly
    FAILED = "failed"           # Start/restart failed
```

### State Transition Diagram

```
                    ┌──────────────┐
                    │  REGISTERED  │ (in config, not started)
                    └──────┬───────┘
                           │ start()
                           ▼
                    ┌──────────────┐
           ┌────────│   STARTING   │────────┐
           │        └──────────────┘        │
           │ success                        │ failure
           ▼                                ▼
    ┌──────────────┐                 ┌──────────────┐
    │   RUNNING    │                 │    FAILED    │
    └──────┬───────┘                 └──────────────┘
           │
     ┌─────┴─────┐
     │           │
stop()│           │ crash detected
     ▼           ▼
┌──────────┐  ┌──────────┐
│ STOPPING │  │   DEAD   │
└────┬─────┘  └──────────┘
     │
     ▼
┌──────────┐
│ STOPPED  │
└──────────┘
```

### ProcessInfo Dataclass

```python
@dataclass
class ProcessInfo:
    """
    Typed process information.

    Benefits:
    - IDE autocomplete for all fields
    - Type checking catches errors
    - Clear documentation
    - Immutable-friendly (can use frozen=True)
    """
    name: str
    state: ProcessState = ProcessState.REGISTERED
    pid: Optional[int] = None
    requesters: Set[str] = field(default_factory=set)
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_requester(self, requester: str) -> None:
        """Add a requester to this process."""
        self.requesters.add(requester)

    def remove_requester(self, requester: str) -> bool:
        """Remove requester. Returns True if no requesters remain."""
        self.requesters.discard(requester)
        return len(self.requesters) == 0
```

### ProcessSnapshot (Immutable for UI)

```python
@dataclass(frozen=True)
class ProcessSnapshot:
    """
    Immutable snapshot for UI rendering.

    frozen=True makes this hashable and prevents accidental modification.
    """
    name: str
    state: ProcessState
    pid: int
    requesters: tuple[str, ...]  # tuple instead of set for immutability
```

### Usage Comparison

```python
# Original: Error-prone
proc = shared_info["proc1"]
if proc["status"] == True:  # Type confusion
    pid = proc["pid"]
    reqs = proc["requester"]  # Typo: "requester" vs "requesters"

# New: Type-safe
proc: ProcessInfo = registry.get("proc1")
if proc.state == ProcessState.RUNNING:  # Clear intent
    pid = proc.pid  # IDE autocomplete
    reqs = proc.requesters  # IDE catches typos

# New: Pattern matching (Python 3.10+)
match proc.state:
    case ProcessState.RUNNING:
        print(f"Process {proc.name} running with PID {proc.pid}")
    case ProcessState.DEAD:
        print(f"Process {proc.name} died unexpectedly")
    case ProcessState.FAILED:
        print(f"Process {proc.name} failed: {proc.error_message}")
```

### Validation Example

```python
# Original: No validation
shared_info["proc1"]["status"] = "invalid"  # Silently accepted

# New: Validation built-in
proc.state = "invalid"  # TypeError: must be ProcessState

# With explicit validation
def update_state(self, name: str, state: ProcessState) -> bool:
    if not isinstance(state, ProcessState):
        raise TypeError(f"Expected ProcessState, got {type(state)}")
    # ...
```

## Consequences

### Positive

1. **Type safety**: IDE and type checkers catch errors
   ```python
   proc.staet = ProcessState.RUNNING  # IDE: "staet" not found
   proc.state = "running"  # Type error: expected ProcessState
   ```

2. **Clear semantics**: Each state has documented meaning
   ```python
   # Before: What does True mean?
   if status == True: ...

   # After: Crystal clear
   if state == ProcessState.RUNNING: ...
   ```

3. **IDE support**: Autocomplete for all fields and states
   ```python
   proc.  # IDE shows: name, state, pid, requesters, error_message
   ProcessState.  # IDE shows: REGISTERED, STARTING, RUNNING, ...
   ```

4. **Exhaustive handling**: Can check all states are handled
   ```python
   match proc.state:
       case ProcessState.REGISTERED: ...
       case ProcessState.STARTING: ...
       # Linter warns if cases missing
   ```

5. **Self-documenting**: Code is its own documentation

6. **Refactoring safety**: Rename a field and IDE updates all usages

### Negative

1. **More verbose**: Enum values longer than True/False

2. **Migration effort**: Existing code must be updated

3. **Python version**: Pattern matching requires Python 3.10+

### Neutral

1. **Learning curve**: Developers must learn the state enum

## Alternatives Considered

### 1. Keep Dict with String Status (Rejected)

Would perpetuate type confusion and lack of IDE support.

### 2. String Constants (Rejected)

```python
STATUS_RUNNING = "running"
STATUS_STOPPED = "stopped"

if proc["status"] == STATUS_RUNNING:
    ...
```

Rejected because:
- Still allows typos in dict keys
- No IDE autocomplete
- Easy to assign invalid values

### 3. TypedDict (Partial)

```python
class ProcessDict(TypedDict):
    name: str
    status: str
    pid: int
```

Rejected because:
- Still uses dict syntax
- No methods (add_requester, etc.)
- Status still a string

### 4. Pydantic Models (Considered)

```python
class ProcessInfo(BaseModel):
    name: str
    state: ProcessState
    pid: Optional[int]
```

Not rejected but not required because:
- Adds dependency
- Standard dataclass is sufficient
- Can migrate to Pydantic if validation needs grow

## References

- [Python Enum Documentation](https://docs.python.org/3/library/enum.html)
- [Python Dataclasses](https://docs.python.org/3/library/dataclasses.html)
- [Type Hints PEP 484](https://www.python.org/dev/peps/pep-0484/)
- Source: `ProcessHub/core/models.py`
