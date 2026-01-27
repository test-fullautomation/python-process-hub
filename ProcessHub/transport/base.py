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
# File: base.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Abstract transport interface for process hub.
#   Allows ProcessHubCore to work with different transports (ZMQ, in-memory, HTTP).
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Abstract transport interface.

This module implements part of improvement 3.1:

- Abstract interface for message transport

- Allows ProcessHubCore to work with different transports

Benefits:

- ZMQ for production

- In-memory for testing

- HTTP/gRPC for future needs
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable


class TransportBase(ABC):
    """
    Abstract transport interface.

    Implementations must provide:

    - start/stop lifecycle methods

    - register_handler for receiving messages

    - send/send_async for sending messages

    Example implementation:

        class MyTransport(TransportBase):

            def start(self):

                self._client = create_client()

                self._client.connect()

            def stop(self):

                self._client.disconnect()

            def register_handler(self, topic, handler):

                self._client.subscribe(topic, handler)

            def send(self, topic, message, target=None):

                self._client.publish(topic, message)
    """

    @abstractmethod
    def start(self) -> None:
        """
Start the transport.

Should initialize connections, start background threads, etc.
Must be called before send() or register_handler().
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """
Stop the transport.

Should close connections, stop background threads, cleanup resources.
Should be idempotent (safe to call multiple times).
        """
        pass

    @abstractmethod
    def register_handler(
        self, topic: str | Enum, handler: Callable[[Any], None]
    ) -> None:
        """
Register message handler for topic.

Args:

    topic: Topic name (string or Enum)
    
    handler: Callable that receives deserialized message data
        """
        pass

    @abstractmethod
    def send(
        self, topic: str | Enum, message: Any, target: str | None = None
    ) -> None:
        """
Send message to topic (blocking).

Args:

    topic: Topic name
    
    message: Message data (will be serialized)
    
    target: Optional target panel ID (for directed messages)
        """
        pass

    @abstractmethod
    def send_async(
        self, topic: str | Enum, message: Any, target: str | None = None
    ) -> None:
        """
Send message asynchronously (non-blocking).

Same as send() but returns immediately.
        """
        pass
