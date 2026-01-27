# ProcessHub Library Concept

## Executive Summary

ProcessHub is a **centralized process lifecycle management system** designed for distributed environments where multiple clients need to coordinate shared processes. It solves the fundamental challenge of managing processes that are used by multiple applications simultaneously, with automatic crash detection and coordinated recovery.

## The Problem We Solve

### Traditional Approach (Without ProcessHub)

In a typical distributed system or test automation environment:

```
Client A starts process X  ──────►  Process X running
Client B also needs X      ──────►  Conflict! Who owns it?
Client A finishes          ──────►  Should X stop? B still needs it!
Process X crashes          ──────►  A and B don't know, tests fail randomly
```

**Common issues:**
- **Orphaned processes** - Processes left running after clients disconnect
- **Race conditions** - Multiple clients trying to start/stop the same process
- **No crash recovery** - Dead processes go unnoticed, causing downstream failures
- **No visibility** - No central view of what's running and who owns it
- **Inconsistent state** - Each client has different view of process status

### ProcessHub Approach

```
                    ┌─────────────────────┐
                    │     ProcessHub      │
                    │   (Central Hub)     │
                    └──────────┬──────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
   ┌────▼────┐            ┌────▼────┐            ┌────▼────┐
   │Client A │            │Client B │            │Client C │
   │(owner)  │            │(owner)  │            │(monitor)│
   └─────────┘            └─────────┘            └─────────┘
```

**ProcessHub guarantees:**
- **Shared ownership** - Multiple clients can request the same process
- **Reference counting** - Process stops only when ALL owners release it
- **Crash detection** - Automatic health monitoring
- **Coordinated recovery** - All affected clients notified before restart
- **Single source of truth** - Central state visible to everyone

## Core Concepts

### 1. Hub-and-Spoke Architecture

ProcessHub uses a **hub-and-spoke** model where:
- **Hub (Server)** - Central coordinator that manages all processes
- **Spokes (Clients)** - Applications that request and use processes

This differs from peer-to-peer approaches because:
- All state is centralized (no distributed consensus needed)
- Clients don't need to know about each other
- Single point of control simplifies debugging

### 2. Process Ownership Model

Processes are not "started" or "stopped" - they are **requested** and **released**.

```python
# Client A requests process (becomes owner)
client_a.request_process_start(["worker"])  # worker starts

# Client B also requests (becomes co-owner)
client_b.request_process_start(["worker"])  # worker already running, no-op

# Client A releases (B still owns it)
client_a.request_process_stop(["worker"])   # worker keeps running

# Client B releases (no more owners)
client_b.request_process_stop(["worker"])   # worker stops
```

This **reference counting** model prevents:
- Premature process termination
- Orphaned processes
- Conflicts between clients

### 3. Restart Coordination Protocol

When a process crashes, ProcessHub doesn't just restart it. It **coordinates** with all affected clients:

```
Phase 1: DETECT     Server detects process died
Phase 2: NOTIFY     Server notifies all clients that requested the process
Phase 3: WAIT       Clients save state, acknowledge readiness
Phase 4: RESTART    Server restarts the process
Phase 5: COMPLETE   Clients notified, resume operation
```

This ensures:
- No client is surprised by a process restart
- Clients can save state before restart
- Clients can restore state after restart
- Timeouts prevent deadlocks

### 4. Pluggable Transport Layer

Communication is abstracted behind a transport interface:

| Transport | Use Case |
|-----------|----------|
| **ZMQ** | Local network, low latency, simple setup |
| **EventBus (RabbitMQ)** | Distributed, enterprise, persistence |
| **InMemory** | Unit testing without network |

All transports implement the same interface, so switching is seamless.

### 5. Clean Architecture

ProcessHub separates concerns into distinct layers:

```
┌─────────────────────────────────────────┐
│           UI Layer                       │  ← How we display
│   (WebView, ConsoleView, NullView)       │
├─────────────────────────────────────────┤
│         Runtime Layer                    │  ← How we wire things
│   (ProcessHubServer, ProcessHubClient)   │
├─────────────────────────────────────────┤
│          Core Layer                      │  ← What we do (logic)
│   (ProcessHubCore, Registries, FSM)      │
├─────────────────────────────────────────┤
│       Transport Layer                    │  ← How we communicate
│   (ZMQ, EventBus, InMemory)              │
├─────────────────────────────────────────┤
│        Process Layer                     │  ← How we execute
│   (SimpleExecutor, WindowsExecutor)      │
└─────────────────────────────────────────┘
```

Benefits:
- **Core logic is testable** without I/O
- **Components are replaceable** (swap ZMQ for RabbitMQ)
- **Clear boundaries** make code maintainable

## Key Features

### For Test Automation

| Feature | Benefit |
|---------|---------|
| Multi-panel support | Multiple test stations share resources |
| Session grouping | Related panels grouped for coordination |
| Automatic cleanup | Processes stop when all panels disconnect |
| Crash recovery | Tests pause, recover, and resume |

### For Operations

| Feature | Benefit |
|---------|---------|
| Web dashboard | Real-time monitoring from browser |
| REST API | Integrate with CI/CD, scripts |
| Admin controls | Start/stop/kill from dashboard |
| Log aggregation | Centralized logs with filtering |

### For Developers

| Feature | Benefit |
|---------|---------|
| Clean architecture | Easy to understand and modify |
| In-memory transport | Fast unit tests without network |
| Mock executor | Test without real processes |
| Typed messages | IDE autocomplete, fewer bugs |

## State Machines

### Process States

```
                    ┌──────────┐
                    │REGISTERED│
                    └────┬─────┘
                         │ start()
                    ┌────▼─────┐
             ┌──────│ STARTING │──────┐
             │      └────┬─────┘      │
             │           │            │
        fail │      ┌────▼─────┐      │ success
             │      │ RUNNING  │      │
             │      └────┬─────┘      │
             │           │            │
             │      stop │ crash      │
             │           │            │
        ┌────▼─────┐┌────▼─────┐┌─────▼────┐
        │  FAILED  ││   DEAD   ││ STOPPING │
        └──────────┘└──────────┘└────┬─────┘
                                     │
                                ┌────▼─────┐
                                │ STOPPED  │
                                └──────────┘
```

### Restart Coordination States

```
┌──────┐     ┌───────────┐     ┌──────────────┐     ┌────────────┐
│ IDLE │────►│ NOTIFYING │────►│ AWAITING_ACK │────►│ RESTARTING │
└──────┘     └───────────┘     └──────────────┘     └─────┬──────┘
    ▲                                │                    │
    │                           timeout                   │
    │                                │                    │
    │                          ┌─────▼─────┐              │
    │                          │  FAILED   │              │
    │                          └─────┬─────┘              │
    │                                │                    │
    │         ┌──────┐               │                    │
    └─────────│ DONE │◄──────────────┴────────────────────┘
              └──────┘
```

## Recommended Diagrams

### For Understanding the System

| Purpose | Diagram | File |
|---------|---------|------|
| **Big picture** | System Overview | `overview.puml` |
| **All features** | Use Cases | `usecases.puml` |
| **How layers connect** | Layered Architecture | `architecture_layered.puml` |

### For Understanding Behavior

| Purpose | Diagram | File |
|---------|---------|------|
| **Restart flow** | Restart Sequence | `sequence_restart_flow.puml` |
| **Restart states** | State Machine | `state_restart.puml` |
| **Basic operations** | Basic Sequence | `sequence_basic.puml` |

### For Understanding Code

| Purpose | Diagram | File |
|---------|---------|------|
| **Core classes** | Core Class Diagram | `class_core.puml` |
| **Transport classes** | Transport Class Diagram | `class_transport.puml` |
| **Runtime classes** | Runtime Class Diagram | `class_runtime.puml` |
| **All components** | Component Diagram | `component.puml` |

### Recommended Combinations

**For Presentations (High-Level):**
1. `overview.puml` - What is ProcessHub
2. `usecases.puml` - What can it do
3. `architecture_layered.puml` - How it's organized

**For Technical Documentation:**
1. `component.puml` - Component relationships
2. `class_core.puml` - Core implementation
3. `sequence_restart_flow.puml` - Key behavior
4. `state_restart.puml` - State machine

**For Onboarding Developers:**
1. `architecture_layered.puml` - Layer structure
2. `sequence_basic.puml` - Basic flow
3. `class_core.puml` + `class_transport.puml` - Main classes

## Design Principles

### 1. Separation of Core Logic

Core business logic (`ProcessHubCore`) has **zero I/O dependencies**:
- No socket calls
- No file operations
- No subprocess calls

This makes it:
- Testable with simple unit tests
- Portable to any transport
- Easy to reason about

### 2. Single Lock Per Data Structure

Each registry has exactly one lock:
- `ConnectionRegistry._lock`
- `ProcessRegistry._lock`
- `RestartStateMachine._lock`

This prevents:
- Deadlocks (no lock ordering issues)
- Complex synchronization bugs

### 3. Immutable State Snapshots

UI receives **immutable copies** of state:
```python
snapshot = core.get_state_snapshot()  # Returns frozen dataclass
# UI can read snapshot without locks
# Concurrent updates don't affect UI rendering
```

### 4. Typed Protocol Messages

All messages are **dataclasses with explicit fields**:
```python
@dataclass
class ProcessStartRequest(MessageBase):
    panel_id: str
    process_list: list[str]
    timeout_per_process: float = 20.0
```

Benefits:
- IDE autocomplete
- Runtime type checking
- Self-documenting API

## Summary

ProcessHub provides:

1. **Centralized Control** - One hub manages all processes
2. **Shared Ownership** - Multiple clients can use same process
3. **Coordinated Recovery** - Graceful handling of crashes
4. **Clean Architecture** - Maintainable, testable code
5. **Flexible Deployment** - Multiple transport options
6. **Real-time Visibility** - Web dashboard and API

It's ideal for:
- Test automation with shared resources
- HIL/SIL testing environments
- Distributed systems requiring process coordination
- Any scenario where multiple clients share processes
