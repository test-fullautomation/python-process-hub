# ADR-012: Strategy Pattern for Core Extensibility

## Status

Proposed

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

The ProcessHub core logic (`ProcessHubCore`) handles connection management, process lifecycle, restart coordination, and health checking. As the system evolves, different deployments may require variations in these behaviors:

- **Different restart strategies**: Some deployments may want immediate restart, others may want exponential backoff, and some may want manual intervention
- **Different health check policies**: Some may need aggressive health checks, others may prefer passive monitoring
- **Different process selection**: Some may want round-robin, others may want priority-based selection
- **Different notification policies**: Some may want immediate notification, others may batch notifications

The question arose: Should we make `ProcessHubCore` itself pluggable, allowing complete replacement of the core logic?

### Current Architecture

```
ProcessHubServer
    └── ProcessHubCore (fixed implementation)
            ├── ProcessRegistry
            ├── RestartStateMachine
            └── ConnectionRegistry
```

### Proposed Pluggable Core Architecture

```
ProcessHubServer
    └── ProcessHubCoreBase (abstract)
            ├── DefaultProcessHubCore
            ├── CustomProcessHubCore1
            └── CustomProcessHubCore2
```

## Decision

**We adopt the Strategy Pattern for specific extensibility points rather than making the entire core pluggable.**

Instead of replacing the entire `ProcessHubCore`, we inject strategy objects that customize specific behaviors while keeping the overall orchestration logic fixed.

### Strategy Interfaces

```python
# ProcessHub/core/strategies.py
"""Strategy interfaces for extensible behaviors."""

from abc import ABC, abstractmethod
from typing import Protocol
from .models import ProcessInfo, ProcessState


class RestartStrategy(Protocol):
    """Strategy for restart behavior."""

    def should_restart(self, process: ProcessInfo, failure_count: int) -> bool:
        """Determine if process should be restarted."""
        ...

    def get_restart_delay(self, process: ProcessInfo, failure_count: int) -> float:
        """Get delay before restart attempt (seconds)."""
        ...

    def on_restart_failed(self, process: ProcessInfo, failure_count: int) -> None:
        """Called when restart fails."""
        ...


class HealthCheckStrategy(Protocol):
    """Strategy for health check behavior."""

    def get_check_interval(self) -> float:
        """Get interval between health checks (seconds)."""
        ...

    def is_healthy(self, process: ProcessInfo, executor: "ProcessExecutor") -> bool:
        """Check if process is healthy."""
        ...

    def on_unhealthy(self, process: ProcessInfo) -> None:
        """Called when process becomes unhealthy."""
        ...


class NotificationStrategy(Protocol):
    """Strategy for client notification behavior."""

    def should_notify_immediately(self, event_type: str) -> bool:
        """Determine if event should trigger immediate notification."""
        ...

    def batch_notifications(self, events: list) -> list:
        """Optionally batch multiple events into fewer notifications."""
        ...
```

### Default Implementations

```python
# ProcessHub/core/strategies.py (continued)

@dataclass
class ImmediateRestartStrategy:
    """Restart immediately on failure."""
    max_retries: int = 3

    def should_restart(self, process: ProcessInfo, failure_count: int) -> bool:
        return failure_count < self.max_retries

    def get_restart_delay(self, process: ProcessInfo, failure_count: int) -> float:
        return 0.0  # No delay

    def on_restart_failed(self, process: ProcessInfo, failure_count: int) -> None:
        pass  # Log only


@dataclass
class ExponentialBackoffRestartStrategy:
    """Restart with exponential backoff."""
    max_retries: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0

    def should_restart(self, process: ProcessInfo, failure_count: int) -> bool:
        return failure_count < self.max_retries

    def get_restart_delay(self, process: ProcessInfo, failure_count: int) -> float:
        delay = self.base_delay * (2 ** failure_count)
        return min(delay, self.max_delay)

    def on_restart_failed(self, process: ProcessInfo, failure_count: int) -> None:
        pass


@dataclass
class ManualRestartStrategy:
    """Never auto-restart, require manual intervention."""

    def should_restart(self, process: ProcessInfo, failure_count: int) -> bool:
        return False  # Never auto-restart

    def get_restart_delay(self, process: ProcessInfo, failure_count: int) -> float:
        return 0.0

    def on_restart_failed(self, process: ProcessInfo, failure_count: int) -> None:
        # Could trigger alert/notification
        pass


@dataclass
class DefaultHealthCheckStrategy:
    """Standard health check using process alive check."""
    check_interval: float = 1.0

    def get_check_interval(self) -> float:
        return self.check_interval

    def is_healthy(self, process: ProcessInfo, executor) -> bool:
        return executor.is_running(process.name)

    def on_unhealthy(self, process: ProcessInfo) -> None:
        pass
```

### Updated ProcessHubCore

```python
# ProcessHub/core/hub_core.py

class ProcessHubCore:
    """Core hub logic with pluggable strategies."""

    def __init__(
        self,
        process_executor: Callable[[str], tuple[bool, str]],
        process_stopper: Callable[[str, bool], bool],
        health_checker: Callable[[list[str]], list[str]],
        restart_timeout: float = 300.0,
        # Strategy injection points
        restart_strategy: RestartStrategy | None = None,
        health_check_strategy: HealthCheckStrategy | None = None,
        notification_strategy: NotificationStrategy | None = None,
    ):
        self._process_executor = process_executor
        self._process_stopper = process_stopper
        self._health_checker = health_checker

        # Use defaults if not provided
        self._restart_strategy = restart_strategy or ImmediateRestartStrategy()
        self._health_strategy = health_check_strategy or DefaultHealthCheckStrategy()
        self._notify_strategy = notification_strategy or DefaultNotificationStrategy()

        # ... rest of initialization

    def _handle_dead_process(self, name: str) -> list[OutgoingMessage]:
        """Handle dead process using restart strategy."""
        process = self._registry.get(name)
        failure_count = self._get_failure_count(name)

        if self._restart_strategy.should_restart(process, failure_count):
            delay = self._restart_strategy.get_restart_delay(process, failure_count)
            if delay > 0:
                self._schedule_restart(name, delay)
            else:
                return self._perform_restart([name])
        else:
            self._restart_strategy.on_restart_failed(process, failure_count)
            self._registry.update_state(name, ProcessState.FAILED)

        return []
```

### Usage Example

```python
# examples/custom_restart_strategy.py

from ProcessHub.runtime import ProcessHubServer
from ProcessHub.transport import ZmqTransport
from ProcessHub.process import SimpleExecutor
from ProcessHub.core.strategies import ExponentialBackoffRestartStrategy

# Create custom restart strategy
restart_strategy = ExponentialBackoffRestartStrategy(
    max_retries=10,
    base_delay=2.0,
    max_delay=120.0,
)

transport = ZmqTransport(start_broker=True)
executor = SimpleExecutor()

server = ProcessHubServer(
    transport=transport,
    executor=executor,
    restart_strategy=restart_strategy,  # Inject custom strategy
)

server.run()
```

### Architecture with Strategies

```
ProcessHubServer
    └── ProcessHubCore
            ├── ProcessRegistry
            ├── RestartStateMachine
            ├── ConnectionRegistry
            │
            ├── RestartStrategy  ←── ImmediateRestartStrategy (default)
            │                    ←── ExponentialBackoffRestartStrategy
            │                    ←── ManualRestartStrategy
            │                    ←── CustomRestartStrategy
            │
            ├── HealthCheckStrategy ←── DefaultHealthCheckStrategy
            │                       ←── AggressiveHealthCheckStrategy
            │                       ←── PassiveHealthCheckStrategy
            │
            └── NotificationStrategy ←── DefaultNotificationStrategy
                                     ←── BatchedNotificationStrategy
```

## Consequences

### Positive

- **Focused extensibility**: Users customize specific behaviors without rewriting orchestration
- **Type safety**: Strategy protocols ensure implementations are complete and correct
- **Composability**: Different strategies can be mixed and matched
- **Testability**: Strategies are simple, stateless objects easy to unit test
- **Backward compatible**: Default strategies maintain existing behavior
- **Single Responsibility**: Each strategy handles one concern
- **Open/Closed**: Core is closed for modification, open for extension via strategies

### Negative

- **Limited flexibility**: Cannot change fundamental orchestration flow
- **More interfaces**: Need to maintain strategy protocol definitions
- **Learning curve**: Users must understand available extension points
- **Strategy explosion**: May end up with many small strategy classes

### Neutral

- Documentation must clearly explain available extension points
- Examples needed for each strategy type
- Strategy protocols should be stable once defined

## Alternatives Considered

### 1. Pluggable Core (Rejected)

Make `ProcessHubCore` itself an abstract base class that can be completely replaced.

```python
class ProcessHubCoreBase(ABC):
    @abstractmethod
    def handle_register(self, req): ...
    @abstractmethod
    def handle_start_request(self, req): ...
    @abstractmethod
    def tick(self): ...
    # ... many abstract methods

class DefaultProcessHubCore(ProcessHubCoreBase):
    # Full implementation

class CustomProcessHubCore(ProcessHubCoreBase):
    # Complete reimplementation
```

Rejected because:

- **High duplication**: Custom implementations must reimplement all orchestration logic
- **Error prone**: Easy to miss subtle interactions between components
- **Testing burden**: Each implementation needs comprehensive integration tests
- **API stability risk**: Any change to `ProcessHubCoreBase` breaks all implementations
- **Over-engineering**: Most customizations only need to change specific behaviors, not the entire flow

### 2. Event Hooks (Deferred)

Add event hooks at key points instead of strategy objects.

```python
class ProcessHubCore:
    def __init__(self):
        self.on_before_restart = []  # List of callbacks
        self.on_after_restart = []
        self.on_process_died = []
```

Deferred because:

- Strategy pattern is more structured and type-safe
- Hooks can be added later if needed for cross-cutting concerns
- Hooks are harder to compose and test than strategy objects

### 3. Configuration-Only Extensibility (Rejected)

Make behaviors configurable via parameters only, no custom code.

```python
class ProcessHubCore:
    def __init__(
        self,
        max_restart_retries: int = 3,
        restart_delay: float = 0.0,
        health_check_interval: float = 1.0,
    ):
        pass
```

Rejected because:

- Cannot express complex logic (e.g., exponential backoff)
- Parameter explosion as features grow
- No way to add truly custom behavior
- Strategy pattern encompasses this (strategies can have parameters)

## References

- [Strategy Pattern - Refactoring Guru](https://refactoring.guru/design-patterns/strategy)
- [Protocol Classes - Python docs](https://docs.python.org/3/library/typing.html#typing.Protocol)
- ADR-002: Separation of Core Logic and Runtime
- ADR-004: Restart Coordination as Explicit State Machine
- ADR-008: Pluggable Process Executor
- Source: `ProcessHub/core/hub_core.py`
- Source: `ProcessHub/core/strategies.py` (to be created)
