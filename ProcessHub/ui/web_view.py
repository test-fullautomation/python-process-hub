#  Copyright 2020-2026 Robert Bosch GmbH
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# *******************************************************************************
#
# File: web_view.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Web-based view for Process Hub dashboard using FastAPI.
#   Provides a browser-accessible UI for monitoring processes and connections.
#
# History:
#
# 20.01.2026 / V 1.3.0 / Nguyen Huynh Tri Cuong
# - Refactored HTML, CSS, and JavaScript into separate static files
#
# 20.01.2026 / V 1.2.0 / Nguyen Huynh Tri Cuong
# - Added Admin API for process control (start/stop/restart)
#
# 19.01.2026 / V 1.1.0 / Nguyen Huynh Tri Cuong
# - Added console log view with save file option
#
# 16.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version with FastAPI
#
# *******************************************************************************
"""
Web-based view for Process Hub dashboard.

This module provides a web UI for monitoring the Process Hub:

- Real-time process status display

- Connection monitoring

- Restart state visualization

- Auto-generated API documentation at /docs

Requires: fastapi, uvicorn

    pip install fastapi uvicorn

Usage:

    from ProcessHub.ui.web_view import WebView

    view = WebView(host="0.0.0.0", port=2507)

    server = ProcessHubServer(transport=transport, view=view)

    server.run()

    # Open browser to http://localhost:2507

    # API docs at http://localhost:2507/docs
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from ..core.models import HubStateSnapshot, ProcessState
from .base import HubViewBase

logger = logging.getLogger(__name__)

# Path to static files directory
STATIC_DIR = Path(__file__).parent / "static"

# Try to import FastAPI and uvicorn
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
    import uvicorn

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    logger.warning(
        "FastAPI not installed. Install with: pip install fastapi uvicorn"
    )




# Pydantic models for API responses
if HAS_FASTAPI:

    class ConnectionInfo(BaseModel):
        """
Connection information model.
        """
        panel_id: str
        session_id: str
        connected_at: Optional[str] = None

    class ProcessInfo(BaseModel):
        """
Process information model.
        """
        name: str
        state: str
        pid: Optional[int] = None
        requesters: list[str] = []

    class RestartInfo(BaseModel):
        """
Restart state information model.
        """
        phase: str
        killed_processes: list[str] = []
        pending_panels: list[str] = []

    class HubState(BaseModel):
        """
Complete hub state model.
        """
        connections: list[ConnectionInfo] = []
        processes: list[ProcessInfo] = []
        restart: RestartInfo

    class LogEntry(BaseModel):
        """
Log entry model.
        """
        timestamp: str
        level: str
        logger_name: str
        message: str

    class LogResponse(BaseModel):
        """
Log response model.
        """
        logs: list[LogEntry] = []
        total: int = 0
        loggers: list[str] = []

    # Admin API models
    class AdminProcessRequest(BaseModel):
        """
Admin process control request.
        """
        process_names: list[str]

    class AdminProcessResponse(BaseModel):
        """
Admin process control response.
        """
        success: bool
        message: str
        results: dict[str, bool] = {}

    # Config API models
    class ProcessConfigItem(BaseModel):
        """
Single process configuration.
        """
        script: str
        args: list[str] = []
        wait_time: float = 2.0
        process_name: Optional[str] = None
        env: dict[str, str] = {}

    class ProcessConfigRequest(BaseModel):
        """
Request to add a process configuration.
        """
        name: str
        config: "ProcessConfigItem"

    class ProcessConfigResponse(BaseModel):
        """
Response for config operations.
        """
        success: bool
        message: str

    class AllConfigsResponse(BaseModel):
        """
Response containing all process configurations.
        """
        configs: dict[str, dict] = {}
        config_enabled: bool = False


class WebViewLogHandler(logging.Handler):
    """
Custom logging handler that captures logs to a deque buffer.

Used by WebView to display logs in the console view.
    """

    def __init__(self, buffer: deque, lock: threading.Lock, max_entries: int = 1000):
        """
Initialize the log handler.

Args:

    buffer: Deque to store log entries

    lock: Lock for thread-safe access

    max_entries: Maximum number of entries to keep
        """
        super().__init__()
        self._buffer = buffer
        self._lock = lock
        self._max_entries = max_entries

    def emit(self, record: logging.LogRecord) -> None:
        """
Emit a log record to the buffer.
        """
        try:
            entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger_name": record.name,
                "message": self.format(record),
            }
            with self._lock:
                self._buffer.append(entry)
                # Trim if exceeds max entries
                while len(self._buffer) > self._max_entries:
                    self._buffer.popleft()
        except Exception:
            self.handleError(record)


class WebView(HubViewBase):
    """
Web-based view for Process Hub using FastAPI.

Provides a browser-accessible dashboard for monitoring processes.

Includes auto-generated API documentation at /docs.

Usage:

    view = WebView(host="0.0.0.0", port=2507)

    server = ProcessHubServer(transport=transport, view=view)

    server.run()

    # Dashboard: http://localhost:2507

    # API docs: http://localhost:2507/docs
    """

    # Type aliases for admin callbacks
    ProcessStartCallback = Callable[[list[str]], dict[str, bool]]
    ProcessStopCallback = Callable[[list[str], bool], dict[str, bool]]
    GetAvailableProcessesCallback = Callable[[], list[str]]
    GetProcessConfigCallback = Callable[[], dict[str, dict]]
    AddProcessConfigCallback = Callable[[str, dict], tuple[bool, str]]
    UpdateProcessConfigCallback = Callable[[str, dict], tuple[bool, str]]
    RemoveProcessConfigCallback = Callable[[str], tuple[bool, str]]
    ResetHubCallback = Callable[[], tuple[bool, str]]

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 2507,
        title: str = "Process Hub API",
        on_process_start: Optional[ProcessStartCallback] = None,
        on_process_stop: Optional[ProcessStopCallback] = None,
        get_available_processes: Optional[GetAvailableProcessesCallback] = None,
        get_process_config: Optional[GetProcessConfigCallback] = None,
        add_process_config: Optional[AddProcessConfigCallback] = None,
        update_process_config: Optional[UpdateProcessConfigCallback] = None,
        remove_process_config: Optional[RemoveProcessConfigCallback] = None,
        reset_hub: Optional[ResetHubCallback] = None,
    ):
        """
Initialize web view.

**Arguments:**

* ``host``

  / *Condition*: optional / *Type*: str / *Default*: "127.0.0.1" /

  Host address to bind to. Use "0.0.0.0" for all interfaces.

* ``port``

  / *Condition*: optional / *Type*: int / *Default*: 2507 /

  Port number for the web server.

* ``title``

  / *Condition*: optional / *Type*: str / *Default*: "Process Hub API" /

  Title for the API documentation.

* ``on_process_start``

  / *Condition*: optional / *Type*: Callable / *Default*: None /

  Callback for starting processes. Signature: (process_names: list[str]) -> dict[str, bool]
  Returns dict mapping process name to success status.

* ``on_process_stop``

  / *Condition*: optional / *Type*: Callable / *Default*: None /

  Callback for stopping processes. Signature: (process_names: list[str], force: bool) -> dict[str, bool]
  Returns dict mapping process name to success status.

* ``get_available_processes``

  / *Condition*: optional / *Type*: Callable / *Default*: None /

  Callback to get list of available process names for autocomplete.
  Signature: () -> list[str]

* ``get_process_config``

  / *Condition*: optional / *Type*: Callable / *Default*: None /

  Callback to get all process configurations.
  Signature: () -> dict[str, dict]

* ``add_process_config``

  / *Condition*: optional / *Type*: Callable / *Default*: None /

  Callback to add a new process configuration.
  Signature: (name: str, config: dict) -> tuple[bool, str]

* ``update_process_config``

  / *Condition*: optional / *Type*: Callable / *Default*: None /

  Callback to update an existing process configuration.
  Signature: (name: str, config: dict) -> tuple[bool, str]

* ``remove_process_config``

  / *Condition*: optional / *Type*: Callable / *Default*: None /

  Callback to remove a process configuration.
  Signature: (name: str) -> tuple[bool, str]

* ``reset_hub``

  / *Condition*: optional / *Type*: Callable / *Default*: None /

  Callback to reset the hub (remove all connections and stop all processes).
  Signature: () -> tuple[bool, str]
        """
        if not HAS_FASTAPI:
            raise ImportError(
                "FastAPI is required for WebView. "
                "Install with: pip install fastapi uvicorn"
            )

        self._host = host
        self._port = port
        self._title = title

        self._app: Optional[FastAPI] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # Current state (updated by render())
        self._current_state: Optional[HubStateSnapshot] = None
        self._state_lock = threading.Lock()

        # Log buffer for console view
        self._log_buffer: deque = deque(maxlen=1000)
        self._log_lock = threading.Lock()
        self._log_handler: Optional[WebViewLogHandler] = None

        # Admin callbacks for process control
        self._on_process_start = on_process_start
        self._on_process_stop = on_process_stop
        self._get_available_processes = get_available_processes
        self._get_process_config = get_process_config
        self._add_process_config = add_process_config
        self._update_process_config = update_process_config
        self._remove_process_config = remove_process_config
        self._reset_hub = reset_hub

        self._setup_app()
        self._setup_log_handler()

    def _setup_app(self) -> None:
        """
Set up the FastAPI application.
        """
        self._app = FastAPI(
            title=self._title,
            description="Process Hub monitoring and management API",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc",
        )

        # Mount static files directory for CSS, JS, etc.
        if STATIC_DIR.exists():
            self._app.mount(
                "/static",
                StaticFiles(directory=str(STATIC_DIR)),
                name="static"
            )

        @self._app.get("/", response_class=HTMLResponse, include_in_schema=False)
        async def index():
            """
Serve the dashboard page.
            """
            index_file = STATIC_DIR / "index.html"
            if index_file.exists():
                return FileResponse(str(index_file), media_type="text/html")
            else:
                return HTMLResponse(
                    content="<h1>Dashboard not found</h1><p>Static files missing.</p>",
                    status_code=404
                )

        @self._app.get(
            "/api/state",
            response_model=HubState,
            summary="Get current hub state",
            description="Returns the current state of all connections, processes, and restart status.",
        )
        async def get_state():
            """
Return current state as JSON.
            """
            with self._state_lock:
                if self._current_state is None:
                    return HubState(
                        connections=[],
                        processes=[],
                        restart=RestartInfo(phase="idle"),
                    )

                return self._state_to_model(self._current_state)

        @self._app.get(
            "/api/connections",
            response_model=list[ConnectionInfo],
            summary="Get all connections",
            description="Returns a list of all connected panels.",
        )
        async def get_connections():
            """
Return connections list.
            """
            with self._state_lock:
                if self._current_state is None:
                    return []
                return [
                    ConnectionInfo(
                        panel_id=c.panel_id,
                        session_id=c.session_id,
                        connected_at=datetime.fromtimestamp(c.connected_at).isoformat()
                        if c.connected_at
                        else None,
                    )
                    for c in self._current_state.connections
                ]

        @self._app.get(
            "/api/processes",
            response_model=list[ProcessInfo],
            summary="Get all processes",
            description="Returns a list of all managed processes.",
        )
        async def get_processes():
            """Return processes list."""
            with self._state_lock:
                if self._current_state is None:
                    return []
                return [
                    ProcessInfo(
                        name=p.name,
                        state=p.state.value if hasattr(p.state, "value") else str(p.state),
                        pid=p.pid,
                        requesters=list(p.requesters) if p.requesters else [],
                    )
                    for p in self._current_state.processes
                ]

        @self._app.get(
            "/api/restart",
            response_model=RestartInfo,
            summary="Get restart status",
            description="Returns the current restart coordination state.",
        )
        async def get_restart():
            """
Return restart state.
            """
            with self._state_lock:
                if self._current_state is None:
                    return RestartInfo(phase="idle")
                return RestartInfo(
                    phase=self._current_state.restart_state,
                    killed_processes=list(self._current_state.killed_processes)
                    if self._current_state.killed_processes
                    else [],
                    pending_panels=list(self._current_state.pending_panels)
                    if self._current_state.pending_panels
                    else [],
                )

        @self._app.get(
            "/api/health",
            summary="Health check",
            description="Returns server health status.",
        )
        async def health_check():
            """
Health check endpoint.
            """
            return {"status": "healthy", "running": self._running}

        @self._app.get(
            "/api/logs",
            response_model=LogResponse,
            summary="Get logs",
            description="Returns console logs. Use 'limit' to restrict number of entries. "
                        "Use 'logger_filter' for exact match or 'logger_prefix' for prefix matching.",
        )
        async def get_logs(
            limit: int = 100,
            offset: int = 0,
            logger_filter: Optional[str] = None,
            logger_prefix: Optional[str] = None,
            logger_exclude: Optional[str] = None,
            level_filter: Optional[str] = None,
        ):
            """
Return logs from buffer with optional filtering.

Args:
    limit: Maximum number of logs to return
    offset: Number of logs to skip
    logger_filter: Comma-separated logger names to include (exact match)
    logger_prefix: Comma-separated prefixes to include (prefix match)
    logger_exclude: Comma-separated prefixes to exclude
    level_filter: Comma-separated log levels to include (empty = all)
            """
            with self._log_lock:
                logs_list = list(self._log_buffer)

                # Get unique logger names before filtering
                unique_loggers = sorted(set(log["logger_name"] for log in logs_list))

                # Apply logger exclusion filter first (prefix match)
                if logger_exclude:
                    exclude_prefixes = [
                        f.strip() for f in logger_exclude.split(",") if f.strip()
                    ]
                    if exclude_prefixes:
                        logs_list = [
                            log for log in logs_list
                            if not any(
                                log["logger_name"].startswith(prefix)
                                for prefix in exclude_prefixes
                            )
                        ]

                # Apply logger prefix filter (takes precedence over exact match)
                if logger_prefix:
                    filter_prefixes = [
                        f.strip() for f in logger_prefix.split(",") if f.strip()
                    ]
                    if filter_prefixes:
                        logs_list = [
                            log for log in logs_list
                            if any(
                                log["logger_name"].startswith(prefix)
                                for prefix in filter_prefixes
                            )
                        ]
                # Apply exact logger filter if no prefix filter
                elif logger_filter:
                    filter_loggers = [
                        f.strip() for f in logger_filter.split(",") if f.strip()
                    ]
                    if filter_loggers:
                        logs_list = [
                            log for log in logs_list
                            if log["logger_name"] in filter_loggers
                        ]

                # Apply level filter if provided
                if level_filter:
                    filter_levels = [
                        f.strip().upper() for f in level_filter.split(",") if f.strip()
                    ]
                    if filter_levels:
                        logs_list = [
                            log for log in logs_list
                            if log["level"].upper() in filter_levels
                        ]

                total = len(logs_list)
                # Apply offset and limit
                logs_list = logs_list[offset:offset + limit] if offset < total else []

            return LogResponse(
                logs=[LogEntry(**log) for log in logs_list],
                total=total,
                loggers=unique_loggers,
            )

        @self._app.get(
            "/api/logs/download",
            summary="Download logs",
            description="Download logs as a text file.",
        )
        async def download_logs():
            """
Download logs as text file.
            """
            from fastapi.responses import PlainTextResponse
            with self._log_lock:
                logs_list = list(self._log_buffer)

            # Format logs as text
            lines = []
            for log in logs_list:
                lines.append(
                    f"[{log['timestamp']}] [{log['level']}] {log['logger_name']}: {log['message']}"
                )
            content = "\n".join(lines)

            filename = f"processhub_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            return PlainTextResponse(
                content=content,
                media_type="text/plain",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}"
                },
            )

        @self._app.delete(
            "/api/logs",
            summary="Clear logs",
            description="Clear all logs from the buffer.",
        )
        async def clear_logs():
            """
Clear log buffer.
            """
            with self._log_lock:
                self._log_buffer.clear()
            return {"status": "cleared"}

        # ====================================================================
        # Admin API endpoints (for development use)
        # ====================================================================

        @self._app.get(
            "/api/admin/status",
            summary="Admin API status",
            description="Check if admin API is enabled.",
            tags=["Admin"],
        )
        async def admin_status():
            """Check admin API availability."""
            return {
                "enabled": self._on_process_start is not None or self._on_process_stop is not None or self._reset_hub is not None,
                "start_enabled": self._on_process_start is not None,
                "stop_enabled": self._on_process_stop is not None,
                "reset_enabled": self._reset_hub is not None,
            }

        @self._app.get(
            "/api/admin/available-processes",
            summary="Get available processes",
            description="Returns list of process names available for starting.",
            tags=["Admin"],
        )
        async def get_available_processes():
            """Get list of available process names for autocomplete."""
            if self._get_available_processes is not None:
                try:
                    processes = self._get_available_processes()
                    return {"processes": processes}
                except Exception as e:
                    logger.exception("Error getting available processes")
                    return {"processes": [], "error": str(e)}

            # Fallback: return process names from current state
            with self._state_lock:
                if self._current_state is None:
                    return {"processes": []}
                return {
                    "processes": [p.name for p in self._current_state.processes]
                }

        @self._app.post(
            "/api/admin/processes/start",
            response_model=AdminProcessResponse,
            summary="Start processes",
            description="Start one or more processes by name. Requires admin callbacks to be configured.",
            tags=["Admin"],
        )
        async def admin_start_processes(request: AdminProcessRequest):
            """Start processes via admin API."""
            if self._on_process_start is None:
                return AdminProcessResponse(
                    success=False,
                    message="Admin start callback not configured",
                    results={},
                )

            try:
                results = self._on_process_start(request.process_names)
                all_success = all(results.values())
                return AdminProcessResponse(
                    success=all_success,
                    message="All processes started" if all_success else "Some processes failed to start",
                    results=results,
                )
            except Exception as e:
                logger.exception("Admin start error")
                return AdminProcessResponse(
                    success=False,
                    message=f"Error: {str(e)}",
                    results={},
                )

        @self._app.post(
            "/api/admin/processes/stop",
            response_model=AdminProcessResponse,
            summary="Stop processes",
            description="Stop one or more processes by name. Requires admin callbacks to be configured.",
            tags=["Admin"],
        )
        async def admin_stop_processes(request: AdminProcessRequest, force: bool = False):
            """Stop processes via admin API."""
            if self._on_process_stop is None:
                return AdminProcessResponse(
                    success=False,
                    message="Admin stop callback not configured",
                    results={},
                )

            try:
                results = self._on_process_stop(request.process_names, force)
                all_success = all(results.values())
                return AdminProcessResponse(
                    success=all_success,
                    message="All processes stopped" if all_success else "Some processes failed to stop",
                    results=results,
                )
            except Exception as e:
                logger.exception("Admin stop error")
                return AdminProcessResponse(
                    success=False,
                    message=f"Error: {str(e)}",
                    results={},
                )

        @self._app.post(
            "/api/admin/processes/{process_name}/start",
            response_model=AdminProcessResponse,
            summary="Start a single process",
            description="Start a process by name.",
            tags=["Admin"],
        )
        async def admin_start_process(process_name: str):
            """Start a single process."""
            if self._on_process_start is None:
                return AdminProcessResponse(
                    success=False,
                    message="Admin start callback not configured",
                    results={},
                )

            try:
                results = self._on_process_start([process_name])
                success = results.get(process_name, False)
                return AdminProcessResponse(
                    success=success,
                    message=f"Process {process_name} started" if success else f"Failed to start {process_name}",
                    results=results,
                )
            except Exception as e:
                logger.exception("Admin start error")
                return AdminProcessResponse(
                    success=False,
                    message=f"Error: {str(e)}",
                    results={},
                )

        @self._app.post(
            "/api/admin/processes/{process_name}/stop",
            response_model=AdminProcessResponse,
            summary="Stop a single process",
            description="Stop a process by name.",
            tags=["Admin"],
        )
        async def admin_stop_process(process_name: str, force: bool = False):
            """Stop a single process."""
            if self._on_process_stop is None:
                return AdminProcessResponse(
                    success=False,
                    message="Admin stop callback not configured",
                    results={},
                )

            try:
                results = self._on_process_stop([process_name], force)
                success = results.get(process_name, False)
                return AdminProcessResponse(
                    success=success,
                    message=f"Process {process_name} stopped" if success else f"Failed to stop {process_name}",
                    results=results,
                )
            except Exception as e:
                logger.exception("Admin stop error")
                return AdminProcessResponse(
                    success=False,
                    message=f"Error: {str(e)}",
                    results={},
                )

        @self._app.post(
            "/api/admin/reset",
            response_model=AdminProcessResponse,
            summary="Reset hub",
            description="Remove all connections and stop all processes to reset the hub to a fresh state.",
            tags=["Admin"],
        )
        async def admin_reset_hub():
            """Reset the hub to a fresh state."""
            if self._reset_hub is None:
                return AdminProcessResponse(
                    success=False,
                    message="Reset hub callback not configured",
                    results={},
                )

            try:
                success, message = self._reset_hub()
                return AdminProcessResponse(
                    success=success,
                    message=message,
                    results={},
                )
            except Exception as e:
                logger.exception("Admin reset hub error")
                return AdminProcessResponse(
                    success=False,
                    message=f"Error: {str(e)}",
                    results={},
                )

        # ====================================================================
        # Config API endpoints
        # ====================================================================

        @self._app.get(
            "/api/admin/config",
            response_model=AllConfigsResponse,
            summary="Get all process configurations",
            description="Returns all configured processes.",
            tags=["Config"],
        )
        async def get_all_configs():
            """Get all process configurations."""
            if self._get_process_config is None:
                return AllConfigsResponse(
                    configs={},
                    config_enabled=False,
                )

            try:
                configs = self._get_process_config()
                return AllConfigsResponse(
                    configs=configs,
                    config_enabled=True,
                )
            except Exception as e:
                logger.exception("Error getting configs")
                return AllConfigsResponse(
                    configs={},
                    config_enabled=True,
                )

        @self._app.post(
            "/api/admin/config",
            response_model=ProcessConfigResponse,
            summary="Add process configuration",
            description="Add a new process configuration.",
            tags=["Config"],
        )
        async def add_config(request: ProcessConfigRequest):
            """Add a new process configuration."""
            if self._add_process_config is None:
                return ProcessConfigResponse(
                    success=False,
                    message="Config management not enabled",
                )

            try:
                config_dict = request.config.model_dump()
                # Set process_name if not provided
                if not config_dict.get("process_name"):
                    config_dict["process_name"] = request.name

                success, message = self._add_process_config(request.name, config_dict)
                return ProcessConfigResponse(
                    success=success,
                    message=message,
                )
            except Exception as e:
                logger.exception("Error adding config")
                return ProcessConfigResponse(
                    success=False,
                    message=f"Error: {str(e)}",
                )

        @self._app.delete(
            "/api/admin/config/{name}",
            response_model=ProcessConfigResponse,
            summary="Remove process configuration",
            description="Remove a process configuration by name.",
            tags=["Config"],
        )
        async def remove_config(name: str):
            """Remove a process configuration."""
            if self._remove_process_config is None:
                return ProcessConfigResponse(
                    success=False,
                    message="Config management not enabled",
                )

            try:
                success, message = self._remove_process_config(name)
                return ProcessConfigResponse(
                    success=success,
                    message=message,
                )
            except Exception as e:
                logger.exception("Error removing config")
                return ProcessConfigResponse(
                    success=False,
                    message=f"Error: {str(e)}",
                )

        @self._app.put(
            "/api/admin/config/{name}",
            response_model=ProcessConfigResponse,
            summary="Update process configuration",
            description="Update an existing process configuration.",
            tags=["Config"],
        )
        async def update_config(name: str, request: ProcessConfigItem):
            """Update an existing process configuration."""
            if self._update_process_config is None:
                return ProcessConfigResponse(
                    success=False,
                    message="Config management not enabled",
                )

            try:
                config_dict = request.model_dump()
                # Set process_name if not provided
                if not config_dict.get("process_name"):
                    config_dict["process_name"] = name

                success, message = self._update_process_config(name, config_dict)
                return ProcessConfigResponse(
                    success=success,
                    message=message,
                )
            except Exception as e:
                logger.exception("Error updating config")
                return ProcessConfigResponse(
                    success=False,
                    message=f"Error: {str(e)}",
                )

    def _setup_log_handler(self) -> None:
        """
Set up the logging handler to capture logs.
        """
        self._log_handler = WebViewLogHandler(
            buffer=self._log_buffer,
            lock=self._log_lock,
            max_entries=1000,
        )
        self._log_handler.setFormatter(
            logging.Formatter("%(message)s")
        )
        self._log_handler.setLevel(logging.DEBUG)

        # Attach to root logger to capture all logs
        root_logger = logging.getLogger()
        root_logger.addHandler(self._log_handler)

    def _state_to_model(self, snapshot: HubStateSnapshot) -> HubState:
        """
Convert snapshot to Pydantic model.
        """
        connections = [
            ConnectionInfo(
                panel_id=conn.panel_id,
                session_id=conn.session_id,
                connected_at=datetime.fromtimestamp(conn.connected_at).isoformat()
                if conn.connected_at
                else None,
            )
            for conn in snapshot.connections
        ]

        processes = [
            ProcessInfo(
                name=proc.name,
                state=proc.state.value if hasattr(proc.state, "value") else str(proc.state),
                pid=proc.pid,
                requesters=list(proc.requesters) if proc.requesters else [],
            )
            for proc in snapshot.processes
        ]

        restart = RestartInfo(
            phase=snapshot.restart_state,
            killed_processes=list(snapshot.killed_processes)
            if snapshot.killed_processes
            else [],
            pending_panels=list(snapshot.pending_panels)
            if snapshot.pending_panels
            else [],
        )

        return HubState(
            connections=connections,
            processes=processes,
            restart=restart,
        )

    def start(self) -> None:
        """
Start the web server in a background thread.
        """
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_server,
            daemon=True,
        )
        self._thread.start()

        logger.info("WebView started at http://%s:%d", self._host, self._port)
        logger.info("API docs available at http://%s:%d/docs", self._host, self._port)

    def _run_server(self) -> None:
        """
Run the uvicorn server.
        """
        try:
            # Configure uvicorn with minimal logging
            config = uvicorn.Config(
                self._app,
                host=self._host,
                port=self._port,
                log_level="warning",
                access_log=False,
            )
            server = uvicorn.Server(config)
            server.run()
        except Exception as e:
            if self._running:
                logger.exception("WebView server error")

    def stop(self) -> None:
        """
Stop the web server.
        """
        self._running = False

        # Remove log handler from root logger
        if self._log_handler is not None:
            root_logger = logging.getLogger()
            root_logger.removeHandler(self._log_handler)
            self._log_handler = None

        logger.info("WebView stopped")

    def render(self, snapshot: HubStateSnapshot) -> None:
        """
Update the current state (called by server's main loop).

**Arguments:**

* ``snapshot``

  / *Condition*: required / *Type*: HubStateSnapshot /

  Current hub state snapshot.
        """
        with self._state_lock:
            self._current_state = snapshot

    @property
    def url(self) -> str:
        """
Get the dashboard URL.
        """
        return f"http://{self._host}:{self._port}"

    @property
    def docs_url(self) -> str:
        """
Get the API documentation URL.
        """
        return f"http://{self._host}:{self._port}/docs"
