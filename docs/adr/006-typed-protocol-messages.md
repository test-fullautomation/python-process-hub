# ADR-006: Typed Protocol Messages with Versioning

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

The original implementation used plain dictionaries for protocol messages:

```python
# Original: Untyped dict messages
def start_process(self, msg):
    panel_id = msg.data["panel_id"]
    process_list = msg.data["process_list"]
    timeout = msg.data.get("timeout", 20)  # Default buried in code

def send_response(self, panel_id, success, failed):
    self.event_bus.send_message_async(
        topic=PROCESS_START_RESPONSE,
        msg=DictMsg({
            "panel_id": panel_id,
            "status": success,        # "status" vs "success"?
            "failed_proc": failed,    # "failed_proc" vs "failed_processes"?
            "failed_msg": error_msg   # Inconsistent naming
        })
    )
```

### Problems with Dict Messages

```python
# Problem 1: No schema documentation
# What fields does PROCESS_START_REQUEST expect?
# Developer must read code to find out

# Problem 2: Typos not caught
msg.data["panle_id"]  # Typo: "panle" vs "panel"

# Problem 3: Inconsistent field names
# Request uses "process_list"
# Response uses "failed_proc"
# Another response uses "processes"

# Problem 4: No versioning
# How to evolve protocol without breaking clients?

# Problem 5: No default values documentation
timeout = msg.data.get("timeout", 20)  # Default hidden in code
```

### Message Schema Chaos

```
PROCESS_START_REQUEST:
  panel_id: str
  process_list: list[str]
  timeout?: int (default: 20? 30? depends on code)

PROCESS_START_RESPONSE:
  panel_id: str
  status: bool          ← or is it "success"?
  failed_proc: list     ← or "failed_processes"?
  failed_msg: str       ← or "error_message"?
```

## Decision

We will use **typed dataclass messages** with explicit schema, versioning, and consistent naming:

### Base Message Class

```python
@dataclass
class MessageBase:
    """
    Base class for all protocol messages.

    Provides:
    - Protocol version for evolution
    - Timestamp for debugging/ordering
    - Request ID for correlation
    """
    version: str = "1.0"
    timestamp: float = field(default_factory=time.time)
    request_id: Optional[str] = None
```

### Request Messages

```python
@dataclass
class ProcessStartRequest(MessageBase):
    """
    Request to start processes.

    Attributes:
        panel_id: ID of the requesting panel
        process_list: List of process names to start
        timeout_per_process: Max seconds to wait per process (default: 20)
    """
    panel_id: str = ""
    process_list: list[str] = field(default_factory=list)
    timeout_per_process: float = 20.0  # Default documented here!


@dataclass
class ProcessStopRequest(MessageBase):
    """Request to stop processes."""
    panel_id: str = ""
    process_list: list[str] = field(default_factory=list)
    force: bool = False  # Force stop without graceful shutdown


@dataclass
class RegisterConnectionRequest(MessageBase):
    """Request to register a panel connection."""
    panel_id: str = ""
    session_id: str = ""
```

### Response Messages

```python
@dataclass
class ProcessStartResponse(MessageBase):
    """
    Response to process start request.

    Consistent naming: "success" not "status", "failed_processes" not "failed_proc"
    """
    panel_id: str = ""
    success: bool = False
    failed_processes: list[str] = field(default_factory=list)
    error_message: str = ""


@dataclass
class ProcessStopResponse(MessageBase):
    """Response to process stop request."""
    panel_id: str = ""
    success: bool = False
    message: str = ""
```

### Notification Messages

```python
@dataclass
class ProcessRestartNotify(MessageBase):
    """
    Notification that processes have died and restart is needed.

    Sent to all affected panels.
    """
    panel_id: str = ""
    killed_processes: list[str] = field(default_factory=list)


@dataclass
class ProcessRestartReady(MessageBase):
    """Panel acknowledgment that it's ready for restart."""
    panel_id: str = ""


@dataclass
class ProcessRestartDone(MessageBase):
    """Notification that restart is complete."""
    panel_id: str = ""
    success: bool = False
    failed_processes: list[str] = field(default_factory=list)
```

### Schema Documentation (Auto-Generated)

```python
# Messages are self-documenting
>>> from dataclasses import fields
>>> for f in fields(ProcessStartRequest):
...     print(f"{f.name}: {f.type} = {f.default}")

panel_id: str = ''
process_list: list[str] = <factory>
timeout_per_process: float = 20.0
version: str = '1.0'
timestamp: float = <factory>
request_id: Optional[str] = None
```

### Usage Comparison

```python
# Original: Error-prone dict access
def handle_start(self, msg):
    panel_id = msg.data["panel_id"]
    procs = msg.data["process_list"]
    timeout = msg.data.get("timout", 20)  # Typo not caught!

# New: Type-safe dataclass access
def handle_start(self, req: ProcessStartRequest):
    panel_id = req.panel_id          # IDE autocomplete
    procs = req.process_list         # Type checked
    timeout = req.timeout_per_process  # Default in class definition
```

### Version Evolution

```python
# Adding new field with backward compatibility
@dataclass
class ProcessStartRequest(MessageBase):
    panel_id: str = ""
    process_list: list[str] = field(default_factory=list)
    timeout_per_process: float = 20.0
    # New field with default - old clients still work
    priority: int = 0  # Added in v1.1

# Version check for new features
def handle_start(self, req: ProcessStartRequest):
    if version_gte(req.version, "1.1"):
        # Use priority field
        pass
```

### Serialization

```python
from dataclasses import asdict

# Serialize to dict for transport
req = ProcessStartRequest(
    panel_id="panel_1",
    process_list=["proc1", "proc2"],
)
data = asdict(req)
# {'panel_id': 'panel_1', 'process_list': ['proc1', 'proc2'],
#  'timeout_per_process': 20.0, 'version': '1.0', ...}

# Deserialize from dict
data = {"panel_id": "panel_1", "process_list": ["proc1"]}
req = ProcessStartRequest(**data)
```

## Consequences

### Positive

1. **Self-documenting protocol**: Message classes are the schema
   ```python
   # Just read the class definition to understand the protocol
   class ProcessStartRequest(MessageBase):
       panel_id: str = ""
       process_list: list[str] = field(default_factory=list)
       timeout_per_process: float = 20.0
   ```

2. **IDE support**: Autocomplete for all fields
   ```python
   req.  # IDE shows: panel_id, process_list, timeout_per_process, ...
   ```

3. **Type checking**: Catch errors at development time
   ```python
   req.panel_id = 123  # Type error: expected str
   ```

4. **Consistent naming**: Field names defined once, used everywhere

5. **Versioning**: Built-in version field for protocol evolution

6. **Default values documented**: In class definition, not buried in code

7. **Request/response correlation**: request_id field for tracking

### Negative

1. **More boilerplate**: Must define class for each message type

2. **Serialization overhead**: Must convert to/from dict

3. **Schema changes**: Adding required fields breaks compatibility

### Neutral

1. **Learning curve**: Developers must learn the message types

## Alternatives Considered

### 1. Keep Dict Messages (Rejected)

Would perpetuate inconsistent naming and lack of documentation.

### 2. Protocol Buffers (Deferred)

```protobuf
message ProcessStartRequest {
  string panel_id = 1;
  repeated string process_list = 2;
  float timeout_per_process = 3;
}
```

Deferred because:
- Adds complexity (protoc compiler, generated code)
- Useful for cross-language communication
- Current Python-only usage doesn't need it

### 3. JSON Schema (Deferred)

External JSON schema files for validation:

```json
{
  "type": "object",
  "properties": {
    "panel_id": {"type": "string"},
    "process_list": {"type": "array", "items": {"type": "string"}}
  }
}
```

Deferred because:
- Schema separate from code (can get out of sync)
- Dataclasses serve as both schema and implementation

### 4. Pydantic Models (Considered)

```python
class ProcessStartRequest(BaseModel):
    panel_id: str
    process_list: list[str]
    timeout_per_process: float = 20.0

    @validator('process_list')
    def validate_process_list(cls, v):
        if not v:
            raise ValueError('process_list cannot be empty')
        return v
```

Not rejected but not required because:
- Adds dependency
- Standard dataclass is sufficient for current needs
- Can migrate to Pydantic if validation complexity grows

## References

- [Python Dataclasses](https://docs.python.org/3/library/dataclasses.html)
- [Protocol Versioning Best Practices](https://cloud.google.com/apis/design/versioning)
- Source: `ProcessHub/core/models.py`
