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
# File: web_api.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / February 2026.
#
# Description:
#   Optional REST API and web dashboard for fleet orchestrator.
#   Requires FastAPI and uvicorn (install via: pip install fastapi uvicorn).
#
# History:
#
# 06.02.2026 / V 1.1.0 / Nguyen Huynh Tri Cuong
# - Initial fleet orchestrator implementation
#
# *******************************************************************************
"""
Optional REST API and web dashboard for fleet orchestrator.

Provides:
- REST API endpoints for fleet status, hub details, and command routing
- HTML dashboard for fleet monitoring
- Swagger/OpenAPI documentation at /docs

Requires FastAPI and uvicorn:
    pip install fastapi uvicorn
"""

from __future__ import annotations

import logging
import threading
from dataclasses import asdict
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .orchestrator import FleetOrchestrator

logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models for API
# ============================================================================


class CommandRequest(BaseModel):
    """Request body for fleet command endpoint."""

    hub_id: str
    action: str
    params: dict = {}


class CommandResponse(BaseModel):
    """Response body for fleet command endpoint."""

    command_id: str
    hub_id: str
    action: str


class ProcessActionRequest(BaseModel):
    """Request body for hub process start/stop endpoints."""

    process_list: list[str]
    panel_id: str = "fleet"
    force: bool = False


# ============================================================================
# Fleet Web API
# ============================================================================


class FleetWebAPI:
    """
REST API and web dashboard for fleet orchestrator.

Usage:

    from ProcessHub.fleet.web_api import FleetWebAPI

    web_api = FleetWebAPI(orchestrator=orchestrator, host="0.0.0.0", port=2510)
    web_api.start()
    # ...
    web_api.stop()
    """

    def __init__(
        self,
        orchestrator: FleetOrchestrator,
        host: str = "127.0.0.1",
        port: int = 2510,
        title: str = "ProcessHub Fleet Dashboard",
    ):
        """
Initialize the fleet web API.

**Arguments:**

* ``orchestrator``

  / *Condition*: required / *Type*: FleetOrchestrator /

  The fleet orchestrator to expose via REST.

* ``host``

  / *Condition*: optional / *Type*: str / *Default*: "127.0.0.1" /

  Host to bind the web server to.

* ``port``

  / *Condition*: optional / *Type*: int / *Default*: 2510 /

  Port for the web server.

* ``title``

  / *Condition*: optional / *Type*: str / *Default*: "ProcessHub Fleet Dashboard" /

  Dashboard title.
        """
        self._orchestrator = orchestrator
        self._host = host
        self._port = port
        self._title = title
        self._app = FastAPI(title=title)
        self._server_thread: Optional[threading.Thread] = None

        self._setup_routes()

    def _setup_routes(self) -> None:
        """Register all API routes."""
        app = self._app

        @app.get("/", response_class=HTMLResponse)
        async def dashboard():
            """Fleet monitoring dashboard."""
            return self._render_dashboard()

        @app.get("/api/fleet/status")
        async def fleet_status():
            """Get fleet-wide status."""
            snapshot = self._orchestrator.get_fleet_snapshot()
            return {
                "total_hubs": snapshot.total_hubs,
                "online_hubs": snapshot.online_hubs,
                "total_processes": snapshot.total_processes,
                "timestamp": snapshot.timestamp,
                "hubs": [asdict(h) for h in snapshot.hubs],
            }

        @app.get("/api/fleet/hubs")
        async def list_hubs():
            """List all registered hubs."""
            snapshot = self._orchestrator.get_fleet_snapshot()
            return {
                "total": snapshot.total_hubs,
                "hubs": [asdict(h) for h in snapshot.hubs],
            }

        @app.get("/api/fleet/hubs/{hub_id}")
        async def get_hub(hub_id: str):
            """Get details for a specific hub."""
            hub = self._orchestrator.get_hub_snapshot(hub_id)
            if hub is None:
                raise HTTPException(status_code=404, detail=f"Hub not found: {hub_id}")
            return asdict(hub)

        @app.post("/api/fleet/command", response_model=CommandResponse)
        async def send_command(request: CommandRequest):
            """Send a fleet command to a hub."""
            try:
                command_id = self._orchestrator.send_command(
                    hub_id=request.hub_id,
                    action=request.action,
                    params=request.params,
                )
                return CommandResponse(
                    command_id=command_id,
                    hub_id=request.hub_id,
                    action=request.action,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.post("/api/fleet/hubs/{hub_id}/start", response_model=CommandResponse)
        async def start_processes(hub_id: str, request: ProcessActionRequest):
            """Start processes on a hub."""
            try:
                command_id = self._orchestrator.send_command(
                    hub_id=hub_id,
                    action="start_process",
                    params={
                        "process_list": request.process_list,
                        "panel_id": request.panel_id,
                    },
                )
                return CommandResponse(
                    command_id=command_id,
                    hub_id=hub_id,
                    action="start_process",
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.post("/api/fleet/hubs/{hub_id}/stop", response_model=CommandResponse)
        async def stop_processes(hub_id: str, request: ProcessActionRequest):
            """Stop processes on a hub."""
            try:
                command_id = self._orchestrator.send_command(
                    hub_id=hub_id,
                    action="stop_process",
                    params={
                        "process_list": request.process_list,
                        "panel_id": request.panel_id,
                        "force": request.force,
                    },
                )
                return CommandResponse(
                    command_id=command_id,
                    hub_id=hub_id,
                    action="stop_process",
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.post("/api/fleet/hubs/{hub_id}/reset", response_model=CommandResponse)
        async def reset_hub(hub_id: str):
            """Reset a hub."""
            try:
                command_id = self._orchestrator.send_command(
                    hub_id=hub_id,
                    action="reset",
                )
                return CommandResponse(
                    command_id=command_id,
                    hub_id=hub_id,
                    action="reset",
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

    def start(self) -> None:
        """Start the web server in a background thread."""
        import uvicorn

        self._server_thread = threading.Thread(
            target=uvicorn.run,
            kwargs={
                "app": self._app,
                "host": self._host,
                "port": self._port,
                "log_level": "warning",
            },
            name="fleet-web-api",
            daemon=True,
        )
        self._server_thread.start()
        logger.info("Fleet web API started: http://%s:%d", self._host, self._port)

    def stop(self) -> None:
        """Stop the web server."""
        logger.info("Fleet web API stopped")

    def _render_dashboard(self) -> str:
        """Render the HTML fleet dashboard."""
        snapshot = self._orchestrator.get_fleet_snapshot()

        hub_rows = ""
        for hub in snapshot.hubs:
            status_class = {
                "online": "status-online",
                "degraded": "status-degraded",
                "offline": "status-offline",
            }.get(hub.status, "")

            processes_str = ", ".join(hub.processes) if hub.processes else "-"
            hub_rows += f"""
            <tr>
                <td><strong>{hub.hub_name}</strong></td>
                <td><code>{hub.hub_id}</code></td>
                <td>{hub.host}</td>
                <td><span class="{status_class}">{hub.status.upper()}</span></td>
                <td>{hub.process_count}</td>
                <td>{hub.connection_count}</td>
                <td>{processes_str}</td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{self._title}</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
               margin: 0; padding: 20px; background: #f5f5f5; }}
        h1 {{ color: #333; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                 min-width: 150px; }}
        .card h3 {{ margin: 0; color: #666; font-size: 14px; }}
        .card .value {{ font-size: 32px; font-weight: bold; color: #333; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px;
                 overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; color: #555; }}
        .status-online {{ color: #28a745; font-weight: bold; }}
        .status-degraded {{ color: #ffc107; font-weight: bold; }}
        .status-offline {{ color: #dc3545; font-weight: bold; }}
        code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 13px; }}
        .api-link {{ color: #007bff; text-decoration: none; }}
        .api-link:hover {{ text-decoration: underline; }}
        .footer {{ margin-top: 20px; color: #999; font-size: 13px; }}
    </style>
</head>
<body>
    <h1>{self._title}</h1>

    <div class="summary">
        <div class="card">
            <h3>Total Hubs</h3>
            <div class="value">{snapshot.total_hubs}</div>
        </div>
        <div class="card">
            <h3>Online Hubs</h3>
            <div class="value" style="color: #28a745">{snapshot.online_hubs}</div>
        </div>
        <div class="card">
            <h3>Total Processes</h3>
            <div class="value">{snapshot.total_processes}</div>
        </div>
    </div>

    <h2>Registered Hubs</h2>
    <table>
        <thead>
            <tr>
                <th>Name</th>
                <th>Hub ID</th>
                <th>Host</th>
                <th>Status</th>
                <th>Processes</th>
                <th>Connections</th>
                <th>Running Processes</th>
            </tr>
        </thead>
        <tbody>
            {hub_rows if hub_rows else '<tr><td colspan="7" style="text-align:center;color:#999">No hubs registered</td></tr>'}
        </tbody>
    </table>

    <div class="footer">
        <p>
            API: <a class="api-link" href="/api/fleet/status">/api/fleet/status</a> |
            <a class="api-link" href="/api/fleet/hubs">/api/fleet/hubs</a> |
            <a class="api-link" href="/docs">Swagger Docs</a>
        </p>
        <p>Auto-refreshes every 5 seconds.</p>
    </div>
</body>
</html>"""
