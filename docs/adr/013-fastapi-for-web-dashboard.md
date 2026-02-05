# ADR-013: FastAPI for Web Dashboard

## Status

Accepted

## Date

2026-01-15

## Author

Nguyen Huynh Tri Cuong (MS/EMC51)

## Reviewer

- Nguyen Huynh Tri Cuong (MS/EMC51)

## History

| Date | Version | Description |
|------|---------|-------------|
| 2026-01-15 | 1.0 | Initial version |

## Context

ProcessHub requires a web-based dashboard for:
- Real-time monitoring of connections, processes, and restart state
- REST API for programmatic access
- Admin controls for starting/stopping processes remotely
- Configuration management via browser

The web framework must:
1. Support asynchronous operations (ProcessHub uses threading)
2. Provide automatic API documentation
3. Be lightweight with minimal dependencies
4. Run embedded within the ProcessHub server (not standalone)
5. Support modern Python type hints
6. Have good performance for real-time updates

### Current Python Web Framework Landscape

| Framework | Async | Auto Docs | Type Hints | Performance | Dependencies |
|-----------|-------|-----------|------------|-------------|--------------|
| Flask | Partial | No | Limited | Medium | Minimal |
| Django | Partial | Optional | Limited | Medium | Heavy |
| FastAPI | Native | Yes (OpenAPI) | Native | High | Minimal |
| Tornado | Native | No | Limited | High | Minimal |
| Starlette | Native | No | Native | High | Minimal |

## Decision

**Use FastAPI** for the web dashboard implementation.

FastAPI is a modern, high-performance web framework built on Starlette and Pydantic, with native support for:
- Async/await patterns
- Automatic OpenAPI (Swagger) documentation
- Type validation via Pydantic models
- Dependency injection

### Architecture

```
ProcessHubServer
       │
       ├── ProcessHubCore (business logic)
       │
       └── WebView (HubView implementation)
                │
                ├── FastAPI Application
                │      ├── /api/state
                │      ├── /api/connections
                │      ├── /api/processes
                │      ├── /api/logs
                │      └── /api/admin/*
                │
                └── Uvicorn Server (embedded)
```

### Implementation Pattern

```python
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import threading

class WebView(HubViewBase):
    def __init__(self, host: str = "127.0.0.1", port: int = 2507):
        self.app = FastAPI(title="ProcessHub API")
        self._setup_routes()
        self._server_thread = None

    def _setup_routes(self):
        @self.app.get("/api/state")
        async def get_state() -> HubStateResponse:
            return self._get_hub_state()

        @self.app.post("/api/admin/processes/{name}/start")
        async def start_process(name: str) -> AdminResponse:
            return self._start_process(name)

    def start(self):
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        self._server_thread = threading.Thread(target=server.run)
        self._server_thread.start()
```

### API Documentation

FastAPI automatically generates:
- **Swagger UI** at `/docs` - Interactive API explorer
- **ReDoc** at `/redoc` - Alternative documentation style
- **OpenAPI JSON** at `/openapi.json` - Machine-readable spec

```python
@app.get("/api/processes", response_model=List[ProcessInfo])
async def get_processes():
    """
    Get all managed processes.

    Returns a list of processes with their current state, PID, and owners.
    """
    return hub_core.get_processes()
```

### Type Safety with Pydantic

```python
from pydantic import BaseModel
from typing import List, Optional

class ProcessInfo(BaseModel):
    name: str
    state: str
    pid: Optional[int]
    requesters: List[str]

class HubStateResponse(BaseModel):
    connections: List[ConnectionInfo]
    processes: List[ProcessInfo]
    restart: RestartInfo
```

## Consequences

### Positive

- **Automatic API Documentation**: Swagger UI generated from code, always up-to-date
- **Type Validation**: Pydantic validates request/response data automatically
- **Modern Python**: Native async/await and type hints support
- **High Performance**: Built on Starlette, one of the fastest Python frameworks
- **Developer Experience**: IDE autocomplete, type checking, clear error messages
- **Standards Compliant**: OpenAPI 3.0, JSON Schema
- **Easy Testing**: TestClient for unit tests without running server

### Negative

- **Additional Dependency**: Requires `fastapi` and `uvicorn` packages
- **Learning Curve**: Developers unfamiliar with FastAPI need onboarding
- **Async Complexity**: Mixing sync ProcessHub code with async FastAPI requires care

### Neutral

- **Optional Component**: WebView is optional; users can use ConsoleView or NullView
- **Uvicorn Dependency**: Could use other ASGI servers, but Uvicorn is recommended

## Alternatives Considered

### 1. Flask (Rejected)

Traditional micro-framework with large ecosystem.

Rejected because:
- No native async support (requires Flask-Async extensions)
- No automatic API documentation (requires Flask-RESTX or Flasgger)
- No built-in request/response validation
- Older design patterns, less modern Python support

### 2. Django REST Framework (Rejected)

Full-featured framework with excellent REST support.

Rejected because:
- Heavy dependency footprint (full Django required)
- Overkill for embedded dashboard (designed for standalone apps)
- No native async support until Django 4.1+
- Complex setup for simple API use case

### 3. Tornado (Rejected)

Async framework with built-in HTTP server.

Rejected because:
- No automatic API documentation
- Less modern API compared to FastAPI
- Smaller community and ecosystem
- More verbose code for equivalent functionality

### 4. Starlette (Deferred)

Lightweight ASGI framework (FastAPI's foundation).

Deferred because:
- Missing automatic documentation generation
- No built-in Pydantic integration
- Would require more boilerplate code
- FastAPI provides better developer experience with minimal overhead

### 5. Plain HTTP Server (Rejected)

Python's built-in `http.server` module.

Rejected because:
- No REST framework features
- No automatic documentation
- No request validation
- Would require building everything from scratch

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Starlette Framework](https://www.starlette.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [OpenAPI Specification](https://swagger.io/specification/)
- [Uvicorn ASGI Server](https://www.uvicorn.org/)
- Source: `ProcessHub/ui/web_view.py`
