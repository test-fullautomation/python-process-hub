# ProcessHub
[![License: Apache v2](https://img.shields.io/pypi/l/robotframework.svg)](http://www.apache.org/licenses/LICENSE-2.0.html)

**A Python library for managing and coordinating processes across distributed systems.**

ProcessHub provides a centralized hub for starting, stopping, monitoring, and coordinating processes across multiple clients. Whether you're building test automation systems, managing microservices, or orchestrating distributed workflows, ProcessHub gives you the tools to manage process lifecycles reliably.

## Why ProcessHub?

### The Problem

In distributed systems and test automation environments, you often need to:

- Start and stop processes on demand from multiple clients
- Share processes between different applications or test panels
- Detect when processes crash and coordinate recovery
- Monitor process status in real-time
- Control processes remotely via web interface or API

Managing this manually leads to race conditions, orphaned processes, inconsistent state, and complex error handling scattered across your codebase.

### The Solution

ProcessHub centralizes all process management into a single, reliable hub:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Client A   │     │  Client B   │     │  Client C   │
│  (Panel 1)  │     │  (Panel 2)  │     │  (Browser)  │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                    ┌──────▼──────┐
                    │ ProcessHub  │
                    │   Server    │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
    │ Process 1 │    │ Process 2 │    │ Process 3 │
    └───────────┘    └───────────┘    └───────────┘
```

## Key Features

- **Process Lifecycle Management** - Start, stop, and monitor processes with health checking
- **Multi-Client Coordination** - Multiple clients can share and coordinate process ownership
- **Crash Recovery** - Automatic detection and coordinated restart when processes die
- **Pluggable Transport** - ZMQ for local networks, RabbitMQ for enterprise, in-memory for testing
- **Web Dashboard** - Real-time browser-based monitoring with REST API
- **Admin API** - Remote process control, configuration management, and hub reset
- **Fleet Orchestrator** - Coordinate multiple ProcessHub instances across PCs from a central point
- **Platform Support** - Works on Windows and Linux/Unix

## Real-World Scenarios

### Automotive Test Bench

In automotive testing, you have a test bench with multiple components: ECU (Electronic Control Unit), measurement devices, power supplies, and CAN bus interfaces. Multiple test engineers run tests from different workstations.

**The Challenge:**
- Engineer A starts the ECU simulator for their test
- Engineer B also needs the ECU simulator for a different test
- When Engineer A finishes, the simulator shouldn't stop (Engineer B still needs it)
- If the simulator crashes, both engineers need to be notified and tests paused

**With ProcessHub:**
```python
# Engineer A's test panel
client_a.request_process_start(["ecu_simulator", "can_interface"])

# Engineer B's test panel (ECU simulator is shared, not started twice)
client_b.request_process_start(["ecu_simulator", "power_supply"])

# If ECU simulator crashes, both panels are notified automatically
# ProcessHub restarts it and both tests can resume
```

### Hardware-in-the-Loop (HIL) Testing

HIL testing involves real hardware interacting with simulated environments. A central server manages simulators, data loggers, and test execution across multiple test stations.

**The Challenge:**
- Vehicle dynamics simulator must run before sensor simulation
- Multiple test stations share expensive simulation resources
- Tests must pause gracefully if any component crashes
- Remote engineers need to monitor and control tests via web browser

**With ProcessHub:**
```python
# Define the HIL infrastructure
process_config = {
    "vehicle_dynamics": {"script": "start_dynamics.py", "wait_time": 10.0, "mandatory": True},
    "sensor_simulation": {"script": "start_sensors.py", "wait_time": 5.0},
    "data_logger": {"script": "start_logger.py", "wait_time": 2.0},
}

# Web dashboard for remote monitoring
view = WebView(host="0.0.0.0", port=2507)
server = ProcessHubServer(transport=transport, view=view, ...)

# Test stations connect and request what they need
# ProcessHub handles sharing, crash recovery, and coordination
```

### Factory Production Line

A manufacturing line has multiple stations: assembly robots, quality inspection cameras, barcode scanners, and packaging machines. A central system coordinates all stations.

**The Challenge:**
- Each station has its own control software
- Quality inspection must run whenever assembly is active
- If a robot controller crashes, downstream stations must pause
- Operators need a dashboard to see status of all stations

**With ProcessHub:**
```python
# Production line configuration
process_config = {
    "robot_arm_1": {"script": "robot_controller.py", "args": ["--station=1"]},
    "robot_arm_2": {"script": "robot_controller.py", "args": ["--station=2"]},
    "vision_system": {"script": "quality_inspection.py", "mandatory": True},
    "barcode_scanner": {"script": "scanner_service.py"},
    "packaging": {"script": "packaging_controller.py"},
}

# When vision_system crashes, ProcessHub notifies all dependent stations
# Operators see real-time status on web dashboard
```

### Distributed Test Lab

A company has a test lab with limited hardware resources (oscilloscopes, protocol analyzers, device programmers) shared across multiple teams.

**The Challenge:**
- Team A in Germany needs the logic analyzer at 9 AM
- Team B in Vietnam needs the same analyzer at 3 PM (overlapping hours)
- When a test finishes, resources should be released for others
- Lab manager needs visibility into who is using what

**With ProcessHub + EventBus (RabbitMQ):**
```python
# Using RabbitMQ for distributed access across locations
transport = EventBusTransport(
    host="rabbitmq.company.com",
    exchange_name="test_lab",
)

# Team A in Germany
client_germany.request_process_start(["logic_analyzer", "power_supply"])

# Team B in Vietnam (sees logic_analyzer is in use)
# ProcessHub prevents conflicts and shows current owners
```

## Use Cases

### Test Automation

Coordinate test infrastructure across multiple test panels:

```python
# Test Panel A needs the system manager
client_a.request_process_start(["system_manager"])

# Test Panel B also needs system manager (shared) + edge compute
client_b.request_process_start(["system_manager", "edge_compute"])

# When Panel A disconnects, system_manager keeps running for Panel B
client_a.unregister_connection()

# When Panel B disconnects, both processes stop (no more owners)
client_b.unregister_connection()
```

### Microservice Orchestration

Manage dependent services with automatic recovery:

```python
# Configure services with dependencies
process_config = {
    "database": {"script": "start_postgres.sh", "wait_time": 5.0},
    "cache": {"script": "start_redis.sh", "wait_time": 2.0},
    "api_server": {"script": "start_api.sh", "wait_time": 3.0},
}

# ProcessHub handles startup order and crash recovery
server = ProcessHubServer(
    transport=transport,
    executor=executor,
    process_config=process_config,
)
```

### Remote Process Control

Control processes from anywhere via web dashboard or REST API:

```bash
# Start a process via API
curl -X POST http://localhost:2507/api/admin/processes/worker_1/start

# Check process status
curl http://localhost:2507/api/processes

# Stop all processes and reset hub
curl -X POST http://localhost:2507/api/admin/reset
```

### CI/CD Pipelines

Integrate process management into automated workflows:

```python
# In your CI script
client = ProcessHubClient(transport=transport)
client.start()
client.register_connection(session_id="ci_pipeline_123")

# Start required services for tests
client.request_process_start(["test_server", "mock_api"])

# Run tests...
run_tests()

# Cleanup happens automatically when client disconnects
client.stop()
```

## Installation

```bash
# Basic installation
pip install python-process-hub

# With ZMQ transport (recommended for local networks)
pip install python-process-hub[zmq]

# With web dashboard
pip install python-process-hub[web]

# With fleet orchestrator (multi-hub coordination)
pip install python-process-hub[fleet]

# All optional dependencies
pip install python-process-hub[zmq,web,fleet]

# From source
git clone https://github.com/test-fullautomation/python-process-hub.git
cd python-process-hub
pip install -e .
```

### Transport-Specific Requirements

**ZMQ Transport** (default, recommended):
```bash
pip install pyzmq
```

**EventBus Transport** (RabbitMQ-based, for distributed environments):
```bash
# Install RabbitMQ
docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:management

# Install EventBusClient
git clone https://github.com/test-fullautomation/python-rabbitmq-messagebus.git
cd python-rabbitmq-messagebus && pip install -e .
```

**Web Dashboard**:
```bash
pip install fastapi uvicorn
```

## Quick Start

### 1. Create a Server

```python
import sys
from ProcessHub.runtime.server import ProcessHubServer
from ProcessHub.transport.zmq_transport import ZmqTransport
from ProcessHub.ui.console_view import ConsoleView
from ProcessHub.process.executor import SimpleExecutor

# Define processes to manage
process_config = {
    "worker_1": {
        "script": sys.executable,
        "args": ["-c", "import time; print('Worker 1 running'); time.sleep(3600)"],
        "wait_time": 2.0,
    },
    "worker_2": {
        "script": sys.executable,
        "args": ["-c", "import time; print('Worker 2 running'); time.sleep(3600)"],
        "wait_time": 2.0,
    },
}

# Create server with ZMQ transport
transport = ZmqTransport(start_broker=True, xpub_port=5555, xsub_port=5556)
view = ConsoleView()
executor = SimpleExecutor(process_config)

server = ProcessHubServer(
    transport=transport,
    view=view,
    executor=executor,
    process_config=process_config,
)

print("Server running on ZMQ ports 5555/5556")
print("Press Ctrl+C to stop")
server.run()
```

### 2. Create a Client

```python
import time
from ProcessHub.runtime.client import ProcessHubClient
from ProcessHub.transport.zmq_transport import ZmqTransport

# Connect to existing server
transport = ZmqTransport(start_broker=False, xpub_port=5555, xsub_port=5556)
client = ProcessHubClient(transport=transport, panel_id="my_panel")
client.start()

# Register with server
client.register_connection(session_id="session_001")
if client.wait_for_registration(timeout=10.0):
    print("Connected to ProcessHub!")

    # Request processes
    client.request_process_start(["worker_1", "worker_2"])
    print("Processes started")

    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    # Cleanup
    client.request_process_stop(["worker_1", "worker_2"])
    client.unregister_connection()

client.stop()
```

### 3. Add Web Dashboard

```python
from ProcessHub.ui import WebView

# Replace ConsoleView with WebView
view = WebView(host="0.0.0.0", port=2507)

server = ProcessHubServer(
    transport=transport,
    view=view,
    executor=executor,
    process_config=process_config,
)

# Dashboard available at http://localhost:2507
server.run()
```

### 4. Using Top-Level Imports

ProcessHub provides convenient top-level imports for common components:

```python
from ProcessHub import ProcessHubServer, ProcessHubClient
from ProcessHub import ZmqTransport, InMemoryTransport
from ProcessHub import ConsoleView, NullView
from ProcessHub import SimpleExecutor, MockExecutor

# WebView requires fastapi: pip install fastapi uvicorn
from ProcessHub.ui import WebView

# EventBusTransport requires EventBusClient package
from ProcessHub.transport import EventBusTransport, EventBusConfig

# Fleet orchestrator (requires: pip install fastapi uvicorn)
from ProcessHub import FleetOrchestrator, HubAgent, FleetClient, FleetTopics

# Version info
from ProcessHub import __version__, __version_date__
```

## Web Dashboard

ProcessHub includes a modern web dashboard for real-time monitoring and control.

### Features

- **Real-time Status** - Auto-refreshing display of all connections and processes
- **Process Control** - Start, stop, and kill processes with one click
- **Configuration Management** - Add, edit, and remove process configurations
- **Log Viewer** - View and filter process logs with multiple filter options
- **REST API** - Full programmatic access to all functionality

### Dashboard Views

The dashboard provides:

- **Statistics Cards** - Connection count, process count, running processes, restart phase
- **Restart Status** - Current phase with pending panels list
- **Connections Table** - Panel IDs, session IDs, connection times
- **Processes Table** - Status badges, PIDs, owners, and action buttons
- **Configuration Manager** - Add, edit, remove process configurations with form UI
- **Console Logs** - Filterable log viewer with level and logger filters

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Complete hub state |
| `/api/connections` | GET | All connected clients |
| `/api/processes` | GET | All managed processes |
| `/api/logs` | GET | Process logs with filtering |
| `/api/admin/processes/{name}/start` | POST | Start a process |
| `/api/admin/processes/{name}/stop` | POST | Stop a process |
| `/api/admin/config` | GET/POST | Manage configurations |
| `/api/admin/reset` | POST | Reset hub state |

## Transport Options

ProcessHub supports multiple transport mechanisms for different deployment scenarios.

### ZMQ Transport (Recommended)

Best for local networks and single-machine deployments:

```python
from ProcessHub.transport.zmq_transport import ZmqTransport

# Server (starts the broker)
server_transport = ZmqTransport(
    start_broker=True,
    xpub_port=5555,
    xsub_port=5556,
)

# Client (connects to broker)
client_transport = ZmqTransport(
    start_broker=False,
    xpub_port=5555,
    xsub_port=5556,
)
```

### EventBus Transport (RabbitMQ)

Best for distributed environments and enterprise deployments:

```python
from ProcessHub.transport.eventbus_transport import EventBusTransport

transport = EventBusTransport(
    host="rabbitmq.example.com",
    port=5672,
    exchange_name="process_hub",
)

# Or with config file
transport = EventBusTransport(config_path="eventbus_config.jsonp")
```

Features:
- Robust message broker with persistence and clustering
- Auto-reconnect on connection loss
- Topic-based message filtering
- Client event notifications (connected, disconnected, reconnecting, error)

### In-Memory Transport (Testing)

Best for unit tests without network dependencies:

```python
from ProcessHub.transport.inmemory_transport import InMemoryTransport

transport = InMemoryTransport()
# Direct message passing, no network needed
```

## Crash Recovery

ProcessHub automatically detects crashed processes and coordinates recovery across all affected clients.

### How It Works

1. **Detection** - Health checks detect when a process dies unexpectedly
2. **Notification** - Server notifies all clients that requested the process
3. **Acknowledgment** - Clients save their state and acknowledge readiness
4. **Restart** - Server restarts the process once all clients acknowledge
5. **Completion** - Clients receive notification and resume operation

### Handling Restarts in Your Client

```python
def on_restart_notify(killed_processes):
    print(f"Processes died: {killed_processes}")
    # Save your application state here
    save_state()
    # Signal ready for restart
    client.notify_restart_ready()

def on_restart_done(restarted_processes, success):
    if success:
        print(f"Processes restarted: {restarted_processes}")
        # Restore your application state
        restore_state()

client.controller.connect("restart_notify", on_restart_notify)
client.controller.connect("restart_done", on_restart_done)
```

## Fleet Orchestrator

ProcessHub includes an optional **Fleet Orchestrator** for coordinating multiple ProcessHub instances across different PCs from a central point. The fleet layer is a pure overlay - it does not modify the core, runtime, or transport modules.

```
                        ┌──────────────────┐
                        │ FleetOrchestrator│
                        │  (Central PC)    │
                        │  + HubRegistry   │
                        │  + FleetWebAPI   │
                        └────────┬─────────┘
                                 │
                    ┌────────────┼────────────┐
                    │   EventBus (RabbitMQ)    │
                    │   fleet.* routing keys   │
                    └────┬───────┬───────┬────┘
                         │       │       │
               ┌─────────▼┐ ┌───▼─────┐ ┌▼─────────┐
               │ Hub PC 1  │ │ Hub PC 2│ │ Hub PC N  │
               │ HubAgent  │ │ HubAgent│ │ HubAgent  │
               │ + Server  │ │ + Server│ │ + Server  │
               └───────────┘ └─────────┘ └───────────┘
```

### Key Concepts

- **FleetOrchestrator** - Central coordinator that discovers hubs, monitors health, and routes commands
- **HubAgent** - Lightweight sidecar that runs alongside each ProcessHubServer (heartbeats, status reports, command handling)
- **HubRegistry** - Thread-safe tracking of all hubs with health state transitions (online -> degraded -> offline)
- **FleetClient** - High-level API for CI/CD pipelines, CLI tools, and scripts
- **FleetWebAPI** - Optional REST API + web dashboard for fleet monitoring

### Quick Start

```python
from ProcessHub.fleet import FleetOrchestrator, HubAgent, FleetClient
from ProcessHub.transport.inmemory_transport import InMemoryTransport

# --- Central PC: Start orchestrator ---
fleet_transport = InMemoryTransport()
fleet_transport.start()

orchestrator = FleetOrchestrator(transport=fleet_transport, health_timeout=30.0)
orchestrator.start()

# --- Hub PC: Attach agent to existing server ---
agent = HubAgent(
    server=my_server,            # existing ProcessHubServer
    transport=fleet_transport,
    hub_id="bench-1",
    hub_name="HIL Bench 1",
)
agent.start()  # Sends heartbeats and status reports automatically

# --- CI/CD: Use FleetClient ---
client = FleetClient(transport=fleet_transport, orchestrator=orchestrator)

# Check fleet health
snapshot = client.get_fleet_status()
print(f"Online hubs: {snapshot.online_hubs}/{snapshot.total_hubs}")

# Start processes on a specific hub
client.start_processes("bench-1", ["ecu_simulator", "can_bridge"])

# Batch operations across all online hubs
client.start_on_all_hubs(["data_logger"])
client.reset_all_hubs()
```

### Fleet Web Dashboard

```python
from ProcessHub.fleet.web_api import FleetWebAPI

web = FleetWebAPI(orchestrator=orchestrator, host="0.0.0.0", port=2510)
web.start()
# Dashboard at http://localhost:2510
# Swagger docs at http://localhost:2510/docs
```

### Fleet REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/fleet/status` | GET | Fleet-wide status snapshot |
| `/api/fleet/hubs` | GET | List all registered hubs |
| `/api/fleet/hubs/{hub_id}` | GET | Single hub details |
| `/api/fleet/command` | POST | Send command to a hub |
| `/api/fleet/hubs/{hub_id}/start` | POST | Start processes on a hub |
| `/api/fleet/hubs/{hub_id}/stop` | POST | Stop processes on a hub |
| `/api/fleet/hubs/{hub_id}/reset` | POST | Reset a hub |

For detailed architecture and design decisions, see:
- [Fleet Orchestrator Plan](docs/FLEET_ORCHESTRATOR.md)
- [ADR-017: Fleet Orchestrator Overlay Pattern](docs/adr/017-fleet-orchestrator-overlay-pattern.md)
- [ADR-018: Heartbeat-Based Hub Health Detection](docs/adr/018-heartbeat-based-hub-health-detection.md)
- [ADR-019: Fleet Command Routing Through Orchestrator](docs/adr/019-fleet-command-routing-through-orchestrator.md)
- [ADR-020: Fleet Frozen State Snapshots](docs/adr/020-fleet-frozen-state-snapshots.md)

## Process Configuration

Define processes with various options:

```python
process_config = {
    "my_service": {
        # Required
        "script": "/path/to/script.py",  # or sys.executable for Python

        # Optional
        "args": ["--config", "prod.json"],  # Command line arguments
        "wait_time": 2.0,  # Seconds to wait after starting
        "env": {"DEBUG": "1"},  # Environment variables
        "enable": True,  # Whether process is enabled
        "description": "Main service",  # Human-readable description
        "mandatory": False,  # If true, cannot be deselected
        "central_log": True,  # Enable centralized logging
        "warning_on_deselect": "This will stop data collection",
    },
}
```

## Admin API

Enable admin features for remote control:

```python
from ProcessHub.ui import WebView

def start_process(name: str) -> tuple[bool, str]:
    # Your logic to start a process
    return True, f"Started {name}"

def stop_process(name: str, force: bool) -> tuple[bool, str]:
    # Your logic to stop a process
    return True, f"Stopped {name}"

view = WebView(
    host="0.0.0.0",
    port=2507,
    on_process_start=start_process,
    on_process_stop=stop_process,
    get_available_processes=lambda: ["worker_1", "worker_2"],
    reset_hub=lambda: (True, "Hub reset"),
)
```

## Architecture

ProcessHub follows clean architecture principles:

```
┌─────────────────────────────────────────────────────────────┐
│               Fleet Orchestrator Layer (optional)            │
│  FleetOrchestrator │ HubAgent │ FleetClient │ FleetWebAPI   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                        UI Layer                             │
│     ConsoleView  │  WebView  │  NullView  │  Custom...      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Runtime Layer                          │
│           ProcessHubServer  │  ProcessHubClient             │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                       Core Layer                            │
│  ProcessHubCore  │  ProcessRegistry  │  RestartStateMachine │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Transport Layer                          │
│        ZmqTransport  │  EventBusTransport  │  InMemory      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                     Process Layer                           │
│      SimpleExecutor  │  WindowsExecutor  │  MockExecutor    │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Separation of Concerns** - Core logic has no I/O dependencies
2. **Dependency Injection** - All components are pluggable
3. **Explicit State Machines** - Complex flows use clear state transitions
4. **Immutable Snapshots** - UI receives copies, avoiding lock contention
5. **Protocol-Oriented** - Well-defined interfaces between components

### Project Structure

```
python-process-hub/
├── ProcessHub/
│   ├── __init__.py           # Package exports
│   ├── version.py            # Version information
│   │
│   ├── core/                 # Pure business logic (no I/O)
│   │   ├── models.py         # Data models, protocol messages
│   │   ├── restart_state.py  # Restart state machine
│   │   ├── process_registry.py # Process state management
│   │   └── hub_core.py       # Core hub logic
│   │
│   ├── transport/            # Message transport adapters
│   │   ├── base.py           # Abstract interface
│   │   ├── zmq_transport.py  # ZMQ implementation
│   │   ├── eventbus_transport.py # RabbitMQ implementation
│   │   └── inmemory_transport.py # Testing
│   │
│   ├── process/              # Process execution
│   │   ├── executor.py       # Abstract executor
│   │   └── platform/         # Platform-specific
│   │       ├── windows.py
│   │       └── unix.py
│   │
│   ├── ui/                   # View layer
│   │   ├── base.py           # Abstract view
│   │   ├── console_view.py   # Console TUI
│   │   ├── web_view.py       # Web dashboard (requires fastapi)
│   │   └── null_view.py      # Headless
│   │
│   ├── config/               # Configuration management
│   │   ├── loader.py         # Config file loading
│   │   └── schemas.py        # Config dataclasses
│   │
│   ├── logging/              # Logging server integration
│   │   └── integration.py    # Fluentbit/Telegraf support
│   │
│   ├── fleet/                # Fleet orchestrator overlay (optional)
│   │   ├── models.py         # Fleet protocol messages & snapshots
│   │   ├── topics.py         # FleetTopics enum
│   │   ├── hub_registry.py   # Thread-safe hub tracking
│   │   ├── hub_agent.py      # Sidecar for ProcessHubServer
│   │   ├── orchestrator.py   # Central coordinator
│   │   ├── fleet_client.py   # External API for CI/CLI
│   │   └── web_api.py        # REST API + web dashboard
│   │
│   └── runtime/              # Server/Client wiring
│       ├── server.py
│       ├── client.py
│       └── client_controller.py
│
├── examples/                 # Example scripts (01-14)
├── tests/                    # Unit and integration tests
├── docs/
│   ├── adr/                  # Architecture Decision Records
│   └── diagrams/             # PlantUML architecture diagrams
└── setup.py                  # Setup script
```

## Diagrams

Architecture and design diagrams are available in the `docs/diagrams/` folder in PlantUML format.

| Diagram | File | Description |
|---------|------|-------------|
| **Use Cases** | `usecases.puml` | Actors and use cases for the library |
| **Architecture** | `architecture.puml` | High-level component diagram |
| **Layered Architecture** | `architecture_layered.puml` | Layered view with data flow |
| **Component** | `component.puml` | Component diagram with interfaces |
| **Core Classes** | `class_core.puml` | Core module classes |
| **Transport Classes** | `class_transport.puml` | Transport layer classes |
| **Runtime Classes** | `class_runtime.puml` | Runtime module classes |
| **Restart State** | `state_restart.puml` | Restart state machine diagram |
| **Restart Flow** | `sequence_restart_flow.puml` | Restart coordination sequence |
| **Basic Flow** | `sequence_basic.puml` | Basic client-server operations |
| **Fleet Overview** | `fleet_overview.puml` | Fleet system overview with orchestrator, hubs, and clients |
| **Fleet Component** | `fleet_component.puml` | Fleet component diagram with module dependencies |
| **Fleet Classes** | `class_fleet.puml` | Fleet models, registry, orchestrator, agent, client classes |
| **Fleet Discovery** | `sequence_fleet_discovery.puml` | Hub discovery, heartbeat, and deregistration sequence |
| **Fleet Commands** | `sequence_fleet_command.puml` | Command routing from client through orchestrator to hub |
| **Hub Health State** | `state_hub_health.puml` | Hub health state machine (online/degraded/offline) |

### Rendering Diagrams

```bash
# Using PlantUML CLI
java -jar plantuml.jar docs/diagrams/*.puml

# Or use online renderer
# Paste content into: https://www.plantuml.com/plantuml/uml/
```

## Examples

The `examples/` directory contains complete working examples:

| Example | Description |
|---------|-------------|
| `01_basic_server.py` | Minimal server setup |
| `02_basic_client.py` | Client connection and process control |
| `03_multi_panel.py` | Multiple clients sharing processes |
| `04_restart_handling.py` | Crash recovery coordination |
| `05_custom_executor.py` | Custom process execution logic |
| `06_web_dashboard.py` | Web-based dashboard |
| `07_console_view.py` | Console TUI display |
| `08_inmemory_transport.py` | Testing without network |
| `09_logging_integration.py` | Centralized logging (Fluentbit) |
| `10_admin_dashboard.py` | Full admin API with config management |
| `11_eventbus_transport.py` | RabbitMQ-based transport |
| `12_fleet_basic.py` | Basic fleet orchestrator with two hub agents |
| `13_fleet_ci_integration.py` | Fleet integration in CI/CD pipelines |
| `14_fleet_web_dashboard.py` | Fleet web dashboard with EventBus transport |

## Testing

ProcessHub is designed for testability:

```python
from ProcessHub.transport.inmemory_transport import InMemoryTransport
from ProcessHub.process.executor import MockExecutor
from ProcessHub.ui.null_view import NullView

# Create test environment without real processes or network
transport = InMemoryTransport()
executor = MockExecutor(process_config)
view = NullView()

server = ProcessHubServer(
    transport=transport,
    executor=executor,
    view=view,
)

# Now test your logic without side effects
```

Run the test suite:

```bash
pytest
pytest --cov=ProcessHub  # With coverage
```

## Documentation

- **[Full Documentation (PDF)](ProcessHub/ProcessHub.pdf)** - Complete guide with architecture details
- **[API Reference](http://localhost:2507/docs)** - Interactive Swagger UI (when running WebView)
- **[Architecture Diagrams](docs/diagrams/)** - PlantUML diagrams of system design

## Architecture Decision Records (ADRs)

Design decisions are documented in `docs/adr/`:

| ADR | Title | Status |
|-----|-------|--------|
| ADR-001 | Lock-Based Operation Serialization | Accepted |
| ADR-002 | Separation of Core Logic and Runtime | Accepted |
| ADR-003 | Pluggable Transport Layer | Accepted |
| ADR-004 | Restart Coordination as Explicit State Machine | Accepted |
| ADR-005 | Normalized Process Representation with Typed State | Accepted |
| ADR-006 | Typed Protocol Messages with Versioning | Accepted |
| ADR-007 | Decoupled UI via HubView Protocol | Accepted |
| ADR-008 | Pluggable Process Executor | Accepted |
| ADR-009 | TCP Keepalive for Connection Health Monitoring | Accepted |
| ADR-010 | Server Shutdown Notification Protocol | Accepted |
| ADR-011 | Hub Reset Without Server Restart | Accepted |
| ADR-017 | Fleet Orchestrator Overlay Pattern | Accepted |
| ADR-018 | Heartbeat-Based Hub Health Detection | Accepted |
| ADR-019 | Fleet Command Routing Through Orchestrator | Accepted |
| ADR-020 | Fleet Frozen State Snapshots | Accepted |

## Feedback

To give us a feedback, you can send an email to [Nguyen Huynh Tri Cuong](mailto:Cuong.NguyenHuynhTri@vn.bosch.com) or [Thomas
Pollerspöck](mailto:Thomas.Pollerspoeck@de.bosch.com)

In case you want to report a bug or request any interesting feature,
please don\'t hesitate to raise a ticket.

## Maintainers

[Nguyen Huynh Tri Cuong](mailto:Cuong.NguyenHuynhTri@vn.bosch.com)

## Contributors

[Nguyen Huynh Tri Cuong](mailto:Cuong.NguyenHuynhTri@vn.bosch.com)

[Thomas Pollerspöck](mailto:Thomas.Pollerspoeck@de.bosch.com)

## License

Copyright 2020-2025 Robert Bosch GmbH

Licensed under the Apache License, Version 2.0 (the \"License\"); you
may not use this file except in compliance with the License. You may
obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an \"AS IS\" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

## Contributing

Contributions are welcome! Please read the contributing guidelines and submit pull requests to the repository.
