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
# File: client_controller.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   ClientController - callback handler registry for client events.
#   Maps action names to user-provided handlers.
#   Decouples message arrival from application logic.
#
# Original author:
#   Nguyen Tan Phat (MS/EMC51)
#
# Original file:
#   ta-framework-tsb/ta_framework/project/process_hub/client_controller.py
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
ClientController - callback handler registry for client events.

This is a simple dispatcher that maps action names to user-provided handlers.
It decouples message arrival from application logic.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Callable, Optional, Union

logger = logging.getLogger(__name__)


class ClientEvent(Enum):
   """
Enumeration of client events for type-safe event handling.

Use these enum values instead of strings to avoid typos and get IDE autocomplete.

Usage::

   from ProcessHub.runtime import ClientEvent

   # Register with enum (recommended)
   client.controller.connect(ClientEvent.PROCESS_STARTED, on_started)

   # Or use string (backward compatible)
   client.controller.connect("process_started", on_started)
   """

   CONNECTION_REGISTERED = "connection_registered"
   CONNECTION_UNREGISTERED = "connection_unregistered"
   CONNECTION_INFO = "connection_info"
   PROCESS_STARTED = "process_started"
   PROCESS_STOPPED = "process_stopped"
   PROCESS_KILLED = "process_killed"
   PROCESS_RESTARTED = "process_restarted"
   RESTART_FAILED = "restart_failed"
   SERVER_TIMEOUT = "server_timeout"
   SERVER_SHUTDOWN = "server_shutdown"


class ClientController:
    """
Client controller for handling process hub events.

Register callbacks for various events, and they will be called
when the corresponding server response arrives.

Usage:

    controller = ClientController()

    def on_started(data):
    
        print(f"Processes started: {data}")

    controller.connect("process_started", on_started)

    # Later, when response arrives:
    
    controller.on_process_started(response_data)  # Calls on_started
    """

    # Available action names
    ACTIONS = [
        "connection_registered",
        "connection_unregistered",
        "connection_info",
        "process_started",
        "process_stopped",
        "process_killed",
        "process_restarted",
        "restart_failed",
        "server_timeout",
        "server_shutdown",
    ]

    def __init__(self):
        self._handlers: dict[str, Optional[Callable]] = {
            action: None for action in self.ACTIONS
        }

    def connect(self, action: Union[str, ClientEvent], handler: Callable) -> None:
        """
Connect an action to a handler.

**Arguments:**

* ``action``

  / *Condition*: required / *Type*: Union[str, ClientEvent] /

  Event name as string or ClientEvent enum value.

* ``handler``

  / *Condition*: required / *Type*: Callable /

  Callable to invoke when action occurs.

**Raises:**

* ``ValueError``: If action is unknown.

* ``TypeError``: If handler is not callable.
        """
        # Convert ClientEvent enum to string
        action_str = action.value if isinstance(action, ClientEvent) else str(action)

        if action_str not in self._handlers:
            raise ValueError(
                f"Unknown action '{action_str}'. Available: {self.ACTIONS}"
            )
        if not callable(handler):
            raise TypeError("Handler must be callable")

        self._handlers[action_str] = handler
        logger.debug("Connected handler for action: %s", action_str)

    def disconnect(self, action: Union[str, ClientEvent]) -> None:
        """
Disconnect a handler from an action.

**Arguments:**

* ``action``

  / *Condition*: required / *Type*: Union[str, ClientEvent] /

  Event name as string or ClientEvent enum value.
        """
        # Convert ClientEvent enum to string
        action_str = action.value if isinstance(action, ClientEvent) else str(action)

        if action_str in self._handlers:
            self._handlers[action_str] = None

    def _call_handler(self, action: str, *args: Any, **kwargs: Any) -> Any:
        """
Call the handler for an action.

Returns None if no handler is registered.
        """
        handler = self._handlers.get(action)
        if handler is None:
            logger.debug("No handler for action '%s'", action)
            return None

        try:
            return handler(*args, **kwargs)
        except Exception as e:
            logger.exception("Error in handler for '%s'", action)
            raise

    # ========================================================================
    # Event Methods (called by client when responses arrive)
    # ========================================================================

    def on_connection_registered(self, data: dict) -> Any:
        """
Called when connection registration response received.

**Arguments:**

* ``data``

  / *Condition*: required / *Type*: dict /

  Registration response data.

**Returns:**

/ *Type*: Any /

Handler return value or None.
        """
        return self._call_handler("connection_registered", data)

    def on_connection_unregistered(self, data: dict) -> Any:
        """
Called when connection unregistration response received.

**Arguments:**

* ``data``

  / *Condition*: required / *Type*: dict /

  Unregistration response data.

**Returns:**

/ *Type*: Any /

Handler return value or None.
        """
        return self._call_handler("connection_unregistered", data)

    def on_connection_info(self, connection_info: dict) -> Any:
        """
Called when connection info response received.

**Arguments:**

* ``connection_info``

  / *Condition*: required / *Type*: dict /

  Connection information data.

**Returns:**

/ *Type*: Any /

Handler return value or None.
        """
        return self._call_handler("connection_info", connection_info)

    def on_process_started(self, data: dict) -> Any:
        """
Called when process start response received.

**Arguments:**

* ``data``

  / *Condition*: required / *Type*: dict /

  Response data with keys: panel_id (str), success (bool),
  failed_processes (list), error_message (str).

**Returns:**

/ *Type*: Any /

Handler return value or None.
        """
        return self._call_handler("process_started", data)

    def on_process_stopped(self, data: dict) -> Any:
        """
Called when process stop response received.

**Arguments:**

* ``data``

  / *Condition*: required / *Type*: dict /

  Response data with keys: panel_id (str), success (bool), message (str).

**Returns:**

/ *Type*: Any /

Handler return value or None.
        """
        return self._call_handler("process_stopped", data)

    def on_process_killed(self, killed_processes: list[str]) -> Any:
        """
Called when process restart notification received.

This indicates processes have died and restart is needed.

**Arguments:**

* ``killed_processes``

  / *Condition*: required / *Type*: list[str] /

  List of dead process names.

**Returns:**

/ *Type*: Any /

Handler return value or None.
        """
        return self._call_handler("process_killed", killed_processes)

    def on_process_restarted(self, data: dict) -> Any:
        """
Called when process restart completed.

**Arguments:**

* ``data``

  / *Condition*: required / *Type*: dict /

  Response data with keys: panel_id (str), success (bool),
  failed_processes (list).

**Returns:**

/ *Type*: Any /

Handler return value or None.
        """
        return self._call_handler("process_restarted", data)

    def on_restart_failed(self, data: dict) -> Any:
        """
Called when restart failed (e.g., timeout, error).

**Arguments:**

* ``data``

  / *Condition*: required / *Type*: dict /

  Response data with keys: panel_id (str), success (False),
  failed_processes (list).

**Returns:**

/ *Type*: Any /

Handler return value or None.
        """
        return self._call_handler("restart_failed", data)

    def on_server_timeout(self, message: str) -> Any:
        """
Called when server response times out.

**Arguments:**

* ``message``

  / *Condition*: required / *Type*: str /

  Timeout error message.

**Returns:**

/ *Type*: Any /

Handler return value or None.
        """
        return self._call_handler("server_timeout", message)

    def on_server_shutdown(self, data: dict) -> Any:
        """
Called when server shutdown or reset notification received.

This indicates the server is shutting down or resetting.
The client should handle this by cleaning up state and potentially reconnecting.

**Arguments:**

* ``data``

  / *Condition*: required / *Type*: dict /

  Notification data with keys: panel_id (str), reason (str: "shutdown" or "reset"),
  message (str).

**Returns:**

/ *Type*: Any /

Handler return value or None.
        """
        return self._call_handler("server_shutdown", data)
