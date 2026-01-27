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
# File: client.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   ProcessHubClient - client for connecting to ProcessHubServer.
#   Provides client API for registering/unregistering connections,
#   starting/stopping processes, and handling restart notifications.
#
# Original author:
#   Nguyen Tan Phat (MS/EMC51)
#
# Original file:
#   ta-framework-tsb/ta_framework/project/process_hub/process_hub_client.py
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
ProcessHubClient - client for connecting to ProcessHubServer.

This module provides a client API for:

- Registering/unregistering connections

- Starting/stopping processes

- Handling restart notifications
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import asdict
from enum import Enum
from typing import Any, Callable, Optional

from ..core.models import (
    ConnectionInfoRequest,
    ProcessRestartReady,
    ProcessStartRequest,
    ProcessStopRequest,
    RegisterConnectionRequest,
    UnregisterConnectionRequest,
)
from ..transport.base import TransportBase
from .client_controller import ClientController
from .server import Topics

logger = logging.getLogger(__name__)


class ProcessHubClient:
    """
Process Hub Client for connecting to ProcessHubServer.

Usage:

    from ProcessHub.runtime.client import ProcessHubClient
    
    from ProcessHub.transport.zmq_transport import ZmqTransport

    transport = ZmqTransport(start_broker=False)
    
    client = ProcessHubClient(
    
        transport=transport,
        
        panel_id="my_panel",
        
    )

    # Connect handlers
    
    client.controller.connect("process_started", on_started)
    
    client.controller.connect("process_killed", on_killed)

    # Start client
    
    client.start()

    # Register with server
    
    client.register_connection(session_id="my_session")

    # Request processes
    
    client.request_process_start(["system_manager", "edge_compute"])

    # Handle restart (when on_killed is called)
    
    client.notify_restart_ready()

    # Cleanup
    
    client.unregister_connection()
    
    client.stop()
    """

    def __init__(
        self,
        transport: TransportBase,
        panel_id: Optional[str] = None,
        default_timeout: float = 30.0,
    ):
        """
Initialize the client.

**Arguments:**

* ``transport``

  / *Condition*: required / *Type*: TransportBase /

  Transport implementation for communicating with the server.

* ``panel_id``

  / *Condition*: optional / *Type*: Optional[str] / *Default*: None /

  Panel identifier. Auto-generated if None.

* ``default_timeout``

  / *Condition*: optional / *Type*: float / *Default*: 30.0 /

  Default timeout for requests in seconds.
        """
        self._transport = transport
        self._panel_id = panel_id or self._generate_panel_id()
        self._default_timeout = default_timeout

        self._is_registered = False
        self._running = False

        # Timeout handling
        self._wait_event = threading.Event()
        self._timeout_thread: Optional[threading.Thread] = None

        # Registration synchronization
        self._registration_event = threading.Event()
        self._registration_error: Optional[str] = None

        # Callback controller
        self.controller = ClientController()

        # Register response handlers
        self._register_handlers()

    def _generate_panel_id(self) -> str:
        """
Generate a unique panel ID.
        """
        return f"panel_{uuid.uuid4().hex[:8]}"

    def _register_handlers(self) -> None:
        """
Register response handlers with transport.
        """
        handlers = {
            Topics.REGISTER_RESPONSE: self._on_register_response,
            Topics.UNREGISTER_RESPONSE: self._on_unregister_response,
            Topics.CONNECTION_INFO_RESPONSE: self._on_connection_info_response,
            Topics.START_RESPONSE: self._on_start_response,
            Topics.STOP_RESPONSE: self._on_stop_response,
            Topics.RESTART_NOTIFY: self._on_restart_notify,
            Topics.RESTART_DONE: self._on_restart_done,
            Topics.SHUTDOWN_NOTIFY: self._on_shutdown_notify,
        }

        for topic, handler in handlers.items():
            self._transport.register_handler(topic.value, handler)

    # ========================================================================
    # Lifecycle
    # ========================================================================

    def start(self) -> None:
        """
Start the client (transport only).
        """
        logger.info("Starting ProcessHubClient (panel_id=%s)", self._panel_id)
        self._transport.start()
        self._running = True

    def stop(self) -> None:
        """
Stop the client.
        """
        logger.info("Stopping ProcessHubClient")
        self._running = False

        # Cancel any pending timeout
        self._wait_event.set()

        self._transport.stop()

    @property
    def panel_id(self) -> str:
        """
Get the panel ID.
        """
        return self._panel_id

    @property
    def is_registered(self) -> bool:
        """
Check if client is registered with server.
        """
        return self._is_registered

    @property
    def is_running(self) -> bool:
        """
Check if client is running.
        """
        return self._running

    # ========================================================================
    # Timeout Handling
    # ========================================================================

    def _start_timeout_watcher(
        self, timeout: float, operation: str
    ) -> None:
        """
Start a timeout watcher thread.

If no response arrives within timeout, calls on_server_timeout.
        """
        self._wait_event.clear()

        def _watcher():
            happened = self._wait_event.wait(timeout=timeout)
            if not happened:
                logger.warning(
                    "Timeout waiting for %s (%.1fs)", operation, timeout
                )
                try:
                    self.controller.on_server_timeout(
                        f"Server response timeout for '{operation}' after {timeout}s"
                    )
                except Exception:
                    logger.exception("Error in timeout handler")

        self._timeout_thread = threading.Thread(
            target=_watcher,
            daemon=True,
            name=f"timeout-{operation}",
        )
        self._timeout_thread.start()

    def _cancel_timeout(self) -> None:
        """
Cancel pending timeout watcher.
        """
        self._wait_event.set()

    # ========================================================================
    # Request Decorators
    # ========================================================================

    def _check_registered(func: Callable) -> Callable:  # noqa: N805
        """
Decorator to check if client is registered.
        """

        def wrapper(self: ProcessHubClient, *args: Any, **kwargs: Any) -> Any:
            if not self._is_registered:
                logger.error(
                    "Cannot call %s: not registered with server",
                    func.__name__,
                )
                raise RuntimeError(
                    "Not registered with server. Call register_connection() first."
                )
            return func(self, *args, **kwargs)

        return wrapper

    def _check_response_panel(self, data: dict) -> bool:
        """
Check if response is for this panel.
        """
        response_panel = data.get("panel_id", "")
        if response_panel != self._panel_id:
            return False
        self._cancel_timeout()
        return True

    # ========================================================================
    # Connection Management
    # ========================================================================

    def register_connection(
        self,
        session_id: str,
        timeout: Optional[float] = None,
    ) -> None:
        """
Register connection with the server.

Args:

    session_id: Session identifier (groups related panels)
    
    timeout: Request timeout (uses default if None)
        """
        timeout = timeout or self._default_timeout

        req = RegisterConnectionRequest(
            panel_id=self._panel_id,
            session_id=session_id,
        )

        logger.info(
            "Registering connection (panel=%s, session=%s)",
            self._panel_id,
            session_id,
        )

        self._registration_event.clear()
        self._registration_error = None
        self._start_timeout_watcher(timeout, "register_connection")
        self._transport.send(Topics.REGISTER_REQUEST.value, asdict(req))

    def wait_for_registration(self, timeout: Optional[float] = None) -> bool:
        """
Wait for registration to complete.

Call this after register_connection() to block until the server responds.

Args:

    timeout: Maximum time to wait (uses default_timeout if None)

Returns:

    True if registered successfully, False if timed out or failed.

Raises:

    RuntimeError: If registration failed with an error from server.
        """
        timeout = timeout or self._default_timeout

        if self._is_registered:
            return True

        # Wait for registration response
        got_response = self._registration_event.wait(timeout=timeout)

        if not got_response:
            logger.error("Registration timed out after %.1fs", timeout)
            return False

        if self._registration_error:
            raise RuntimeError(f"Registration failed: {self._registration_error}")

        return self._is_registered

    def _on_register_response(self, data: Any) -> None:
        """
Handle register connection response.
        """
        d = self._deserialize(data)
        if not self._check_response_panel(d):
            return

        self._is_registered = d.get("success", True)
        if not self._is_registered:
            self._registration_error = d.get("message", "Registration failed")
        else:
            self._registration_error = None

        logger.info(
            "Registration %s: %s",
            "successful" if self._is_registered else "failed",
            d.get("message", ""),
        )

        # Signal that registration response was received
        self._registration_event.set()

        self.controller.on_connection_registered(d)

    @_check_registered
    def unregister_connection(self, timeout: Optional[float] = None) -> None:
        """
Unregister connection from the server.

Args:

    timeout: Request timeout
        """
        timeout = timeout or self._default_timeout

        req = UnregisterConnectionRequest(panel_id=self._panel_id)

        logger.info("Unregistering connection (panel=%s)", self._panel_id)

        self._start_timeout_watcher(timeout, "unregister_connection")
        self._transport.send(Topics.UNREGISTER_REQUEST.value, asdict(req))

    def _on_unregister_response(self, data: Any) -> None:
        """
Handle unregister connection response.
        """
        d = self._deserialize(data)
        if not self._check_response_panel(d):
            return

        self._is_registered = False
        logger.info("Unregistered from server")

        self.controller.on_connection_unregistered(d)

    @_check_registered
    def request_connection_info(self, timeout: Optional[float] = None) -> None:
        """
Request connection info from server.

Args:

    timeout: Request timeout
        """
        timeout = timeout or self._default_timeout

        req = ConnectionInfoRequest(panel_id=self._panel_id)

        logger.debug("Requesting connection info")

        self._start_timeout_watcher(timeout, "connection_info")
        self._transport.send(Topics.CONNECTION_INFO_REQUEST.value, asdict(req))

    def _on_connection_info_response(self, data: Any) -> None:
        """
Handle connection info response.
        """
        d = self._deserialize(data)
        if not self._check_response_panel(d):
            return

        self.controller.on_connection_info(d.get("connections", {}))

    # ========================================================================
    # Process Control
    # ========================================================================

    @_check_registered
    def request_process_start(
        self,
        process_list: list[str] | str,
        timeout_per_process: float = 20.0,
    ) -> None:
        """
Request to start process(es).

Args:

    process_list: Process name(s) to start
    
    timeout_per_process: Timeout per process (total = N * timeout)
        """
        if isinstance(process_list, str):
            process_list = [process_list]

        total_timeout = timeout_per_process * len(process_list)

        req = ProcessStartRequest(
            panel_id=self._panel_id,
            process_list=process_list,
            timeout_per_process=timeout_per_process,
        )

        logger.info("Requesting process start: %s", process_list)

        self._start_timeout_watcher(total_timeout, "process_start")
        self._transport.send(Topics.START_REQUEST.value, asdict(req))

    def _on_start_response(self, data: Any) -> None:
        """
Handle process start response.
        """
        d = self._deserialize(data)
        if not self._check_response_panel(d):
            return

        success = d.get("success", False)
        if success:
            logger.info("Process start successful")
        else:
            logger.error(
                "Process start failed: %s (failed: %s)",
                d.get("error_message", ""),
                d.get("failed_processes", []),
            )

        self.controller.on_process_started(d)

    @_check_registered
    def request_process_stop(
        self,
        process_list: list[str] | str,
        force: bool = False,
        timeout_per_process: float = 10.0,
    ) -> None:
        """
Request to stop process(es).

Args:

    process_list: Process name(s) to stop
    
    force: Force stop even if other panels need the process
    
    timeout_per_process: Timeout per process
        """
        if isinstance(process_list, str):
            process_list = [process_list]

        total_timeout = timeout_per_process * len(process_list)

        req = ProcessStopRequest(
            panel_id=self._panel_id,
            process_list=process_list,
            force=force,
        )

        logger.info("Requesting process stop: %s (force=%s)", process_list, force)

        self._start_timeout_watcher(total_timeout, "process_stop")
        self._transport.send(Topics.STOP_REQUEST.value, asdict(req))

    def _on_stop_response(self, data: Any) -> None:
        """
Handle process stop response.
        """
        d = self._deserialize(data)
        if not self._check_response_panel(d):
            return

        logger.info("Process stop completed: %s", d.get("message", ""))

        self.controller.on_process_stopped(d)

    # ========================================================================
    # Restart Handling
    # ========================================================================

    def _on_restart_notify(self, data: Any) -> None:
        """
Handle restart notification from server.
        """
        d = self._deserialize(data)
        if not self._check_response_panel(d):
            return

        killed = d.get("killed_processes", [])
        logger.warning("Received restart notification: %s", killed)

        self.controller.on_process_killed(killed)

    @_check_registered
    def notify_restart_ready(self, timeout: float = 150.0) -> None:
        """
Notify server that this panel is ready for restart.

Call this after receiving on_process_killed callback
and completing any necessary cleanup.

Args:

    timeout: Timeout waiting for restart completion
        """
        req = ProcessRestartReady(panel_id=self._panel_id)

        logger.info("Notifying server: ready for restart")

        self._start_timeout_watcher(timeout, "restart_ready")
        self._transport.send(Topics.RESTART_READY.value, asdict(req))

    def _on_restart_done(self, data: Any) -> None:
        """
Handle restart completion notification.
        """
        d = self._deserialize(data)
        if not self._check_response_panel(d):
            return

        success = d.get("success", False)
        if success:
            logger.info("Restart completed successfully")
            self.controller.on_process_restarted(d)
        else:
            logger.error(
                "Restart failed: %s",
                d.get("failed_processes", []),
            )
            self.controller.on_restart_failed(d)

    # ========================================================================
    # Server Shutdown Handling
    # ========================================================================

    def _on_shutdown_notify(self, data: Any) -> None:
        """
Handle server shutdown/reset notification.

This is called when the server is shutting down or resetting.
The client should clean up its state.
        """
        d = self._deserialize(data)
        if not self._check_response_panel(d):
            return

        reason = d.get("reason", "unknown")
        message = d.get("message", "")
        logger.warning(
            "Received server %s notification: %s",
            reason,
            message,
        )

        # Mark as unregistered since server is clearing connections
        self._is_registered = False

        self.controller.on_server_shutdown(d)

    # ========================================================================
    # Utilities
    # ========================================================================

    def _deserialize(self, data: Any) -> dict:
        """
Deserialize incoming data to dict.
        """
        if hasattr(data, "data"):
            # Handle DictMsg wrapper
            return data.data
        if isinstance(data, dict):
            return data
        return {"data": data}
