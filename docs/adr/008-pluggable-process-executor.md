# ADR-008: Pluggable Process Executor

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

The original implementation had process execution logic tightly coupled to the server:

```python
# Original: Process execution mixed with server logic
class ProcessControl:
    @staticmethod
    def start_process(name, path, args, logging_conf, logging_host, logging_port):
        """Start process via command line - Windows specific."""
        path = os.path.normpath(path.strip().strip('"'))
        if not os.path.exists(path):
            return -1

        if path.endswith(".py"):
            # Windows-specific Python path
            python_exe = 'python' if USE_PYTHON_VENV else '"%RobotPythonPath%/python"'
            path = f'{python_exe} "{path}" ' + ' '.join(args)
        else:
            path = f'"{path}" {" ".join(args)}'

        # Windows-specific command
        cmd = f'start /min "{name}" cmd.exe /k "{path}"'

        subprocess.Popen(
            cmd,
            shell=True,  # Security risk
            # ... Windows-specific flags ...
        )
```

### Problems

```
┌─────────────────────────────────────────────────────────────┐
│                    Original Design                           │
│                                                              │
│  ProcessControl.start_process()                              │
│  ├── Windows-only: 'start /min' command                     │
│  ├── shell=True: Security vulnerability                      │
│  ├── Hardcoded Python path handling                          │
│  ├── Cannot mock for testing                                 │
│  └── No cross-platform support                               │
│                                                              │
│  Issues:                                                     │
│  1. Cannot test without actually starting processes          │
│  2. Windows-only implementation                              │
│  3. No way to customize process startup                      │
│  4. Security risks with shell=True                           │
└─────────────────────────────────────────────────────────────┘
```

### Testing Difficulty

```python
# Original: Must actually start processes to test
def test_process_start():
    control = ProcessControl()
    result = control.start_process("my_app", "/path/to/app", [])
    # Actually starts a real process!
    # Hard to verify, slow, side effects
```

## Decision

We will implement a **pluggable executor interface** with multiple implementations for different environments:

### Executor Interface

```python
class ProcessExecutor(ABC):
    """
    Abstract process executor interface.

    Implementations handle platform-specific process management.
    """

    @abstractmethod
    def start(self, name: str, config: dict) -> tuple[bool, str, Optional[int]]:
        """
        Start a process.

        Args:
            name: Process name/identifier
            config: Process configuration dict with keys:
                - script: Path to script/executable
                - args: List of arguments
                - wait_time: Time to wait after start (seconds)
                - process_name: Actual process name to look for
                - env: Additional environment variables

        Returns:
            Tuple of (success, message, pid)
        """
        pass

    @abstractmethod
    def stop(self, name: str, force: bool = False) -> bool:
        """Stop a process."""
        pass

    @abstractmethod
    def is_running(self, name: str) -> bool:
        """Check if process is running."""
        pass

    def get_pid(self, name: str) -> Optional[int]:
        """Get process ID (optional)."""
        return None
```

### Implementations

```
ProcessExecutor (Abstract)
    │
    ├── SimpleExecutor      # Cross-platform subprocess management
    │
    ├── MockExecutor        # Testing: Simulates processes without starting
    │
    ├── WindowsExecutor     # Windows-specific with service support
    │
    └── (Future: DockerExecutor, SSHExecutor, K8sExecutor, etc.)
```

### SimpleExecutor (Cross-Platform)

```python
class SimpleExecutor(ProcessExecutor):
    """
    Simple cross-platform executor using subprocess.

    Features:
    - Works on Windows, Linux, macOS
    - No shell=True (security)
    - psutil for process management
    - Graceful shutdown with SIGTERM
    """

    def start(self, name: str, config: dict) -> tuple[bool, str, Optional[int]]:
        script = config.get("script", "")
        args = config.get("args", [])
        wait_time = config.get("wait_time", 2.0)
        env = config.get("env", {})

        # Validate script
        script = os.path.expandvars(script)
        if not os.path.exists(script):
            return False, f"Script not found: {script}", None

        # Build command (no shell)
        if script.endswith(".py"):
            cmd = [sys.executable, script] + args
        else:
            cmd = [script] + args

        # Start process
        proc = subprocess.Popen(
            cmd,
            env={**os.environ, **env},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # Platform-specific flags
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP
                if sys.platform == "win32" else 0
            ),
        )

        self._processes[name] = proc
        self._pids[name] = proc.pid

        # Wait and verify
        if wait_time > 0:
            time.sleep(wait_time)

        if proc.poll() is not None:
            return False, f"Process exited immediately", None

        return True, f"Started {name}", proc.pid

    def stop(self, name: str, force: bool = False) -> bool:
        proc = self._processes.get(name)
        if proc is None:
            return True

        # Graceful shutdown first
        proc.terminate()
        try:
            proc.wait(timeout=self._stop_timeout)
        except subprocess.TimeoutExpired:
            if force:
                proc.kill()
                proc.wait(timeout=2.0)
            else:
                return False

        del self._processes[name]
        return True
```

### MockExecutor (Testing)

```python
class MockExecutor(ProcessExecutor):
    """
    Mock executor for testing.

    Simulates process start/stop without actually running processes.
    """

    def __init__(self):
        self._running: dict[str, int] = {}  # name -> fake pid
        self._next_pid = 1000

    def start(self, name: str, config: dict) -> tuple[bool, str, Optional[int]]:
        # Simulate failure if configured
        if config.get("fail_start"):
            return False, "Simulated failure", None

        if name in self._running:
            return True, f"{name} already running", self._running[name]

        pid = self._next_pid
        self._next_pid += 1
        self._running[name] = pid

        return True, f"Started {name}", pid

    def stop(self, name: str, force: bool = False) -> bool:
        self._running.pop(name, None)
        return True

    def is_running(self, name: str) -> bool:
        return name in self._running

    def kill(self, name: str) -> None:
        """Simulate external process death (for testing)."""
        self._running.pop(name, None)
```

### WindowsExecutor (Platform-Specific)

```python
class WindowsExecutor(ProcessExecutor):
    """
    Windows-specific executor with advanced features.

    Features:
    - Windows service support
    - Job objects for process groups
    - PowerShell for graceful shutdown
    """

    def start(self, name: str, config: dict) -> tuple[bool, str, Optional[int]]:
        # Windows-specific implementation
        pass

    def stop(self, name: str, force: bool = False) -> bool:
        if not force:
            # Try graceful PowerShell stop
            self._powershell_stop(name)
        # Fall back to terminate
        pass
```

### Factory Function

```python
def create_executor(executor_type: str = "simple") -> ProcessExecutor:
    """
    Factory function to create an executor.

    Args:
        executor_type: "simple", "mock", or "windows"

    Returns:
        ProcessExecutor implementation
    """
    if executor_type == "mock":
        return MockExecutor()
    elif executor_type == "windows":
        from .platform.windows import WindowsExecutor
        return WindowsExecutor()
    else:
        return SimpleExecutor()
```

### Usage Examples

```python
# Production: Real process execution
from ProcessHub import ProcessHubServer, ZmqTransport, SimpleExecutor

server = ProcessHubServer(
    transport=ZmqTransport(start_broker=True),
    executor=SimpleExecutor(),
    process_config=config,
)
server.run()

# Testing: Mock executor
from ProcessHub import MockExecutor, InMemoryTransport

executor = MockExecutor()
transport = InMemoryTransport()

server = ProcessHubServer(
    transport=transport,
    executor=executor,
    view=NullView(),
)

# Test process start
def test_process_start():
    transport.send_async("PROCESS_START_REQUEST", {
        "panel_id": "test",
        "process_list": ["proc1"],
    })

    assert executor.is_running("proc1")
    assert executor.get_pid("proc1") == 1000

# Test process death detection
def test_health_check():
    executor.kill("proc1")  # Simulate crash
    # Health check should detect and trigger restart
```

### Custom Executor

```python
# Custom executor for Docker containers
class DockerExecutor(ProcessExecutor):
    def __init__(self, docker_client):
        self._client = docker_client
        self._containers = {}

    def start(self, name: str, config: dict) -> tuple[bool, str, Optional[int]]:
        image = config.get("image")
        container = self._client.containers.run(
            image,
            detach=True,
            name=name,
        )
        self._containers[name] = container
        return True, f"Started container {name}", container.id

    def stop(self, name: str, force: bool = False) -> bool:
        container = self._containers.get(name)
        if container:
            container.stop(timeout=10 if not force else 0)
            return True
        return False

    def is_running(self, name: str) -> bool:
        container = self._containers.get(name)
        if container:
            container.reload()
            return container.status == "running"
        return False
```

## Consequences

### Positive

1. **Testable**: MockExecutor enables unit testing without real processes
   ```python
   def test_restart_coordination():
       executor = MockExecutor()
       server = ProcessHubServer(executor=executor)

       # Start processes
       executor.start("proc1", {})

       # Simulate crash
       executor.kill("proc1")

       # Verify restart logic
       # No real processes involved!
   ```

2. **Cross-platform**: SimpleExecutor works on all platforms

3. **Secure**: No shell=True, proper argument handling

4. **Extensible**: Easy to add Docker, SSH, K8s executors

5. **Customizable**: Inject custom executor for special needs

6. **Separation of concerns**: Process execution separate from hub logic

### Negative

1. **Abstraction overhead**: Extra layer between hub and processes

2. **Feature parity**: Must ensure all executors support same features

3. **Platform differences**: Some features only available on certain platforms

### Neutral

1. **Configuration**: Executor config may differ between implementations

## Alternatives Considered

### 1. Keep Inline Execution (Rejected)

Would prevent testing and cross-platform support.

### 2. Subprocess Wrapper Only (Rejected)

Just wrapping subprocess without interface:

```python
def start_process(name, script, args):
    return subprocess.Popen([script] + args)
```

Rejected because:
- Cannot mock for testing
- No consistent interface
- Platform-specific code leaks out

### 3. Process Pool (Deferred)

Using concurrent.futures for process management:

```python
executor = ProcessPoolExecutor(max_workers=10)
future = executor.submit(run_process, name, config)
```

Deferred because:
- Different use case (parallel execution vs lifecycle management)
- May be useful for batch operations later

## References

- [Python subprocess documentation](https://docs.python.org/3/library/subprocess.html)
- [psutil documentation](https://psutil.readthedocs.io/)
- [Strategy Pattern](https://refactoring.guru/design-patterns/strategy)
- Source: `ProcessHub/process/executor.py`
