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
# File: inmemory_transport.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   In-memory transport for testing.
#   Provides a simple transport that delivers messages synchronously
#   within the same process. Useful for unit testing without ZMQ.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
In-memory transport for testing.

Provides a simple transport that delivers messages synchronously
within the same process. Useful for unit testing without ZMQ.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from enum import Enum
from typing import Any, Callable

from .base import TransportBase


class InMemoryTransport(TransportBase):
    """
In-memory transport for unit testing.

Messages are delivered synchronously within same process.

Provides test helpers to inspect sent messages.

Usage:

    transport = InMemoryTransport()
    
    transport.register_handler("TOPIC", my_handler)
    
    transport.start()

    transport.send("TOPIC", {"data": "value"})
    
    # my_handler is called synchronously

    # Test helper
    
    messages = transport.get_sent_messages("TOPIC")
    
    assert len(messages) == 1
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._sent_messages: list[tuple[str, Any, str | None]] = []
        self._lock = threading.Lock()
        self._started = False

    def start(self) -> None:
        """
Start the transport (no-op for in-memory).
        """
        self._started = True

    def stop(self) -> None:
        """
Stop the transport (no-op for in-memory).
        """
        self._started = False

    def register_handler(
        self, topic: str | Enum, handler: Callable[[Any], None]
    ) -> None:
        """
Register message handler for topic.
        """
        topic_str = topic.value if isinstance(topic, Enum) else str(topic)
        with self._lock:
            self._handlers[topic_str].append(handler)

    def send(
        self, topic: str | Enum, message: Any, target: str | None = None
    ) -> None:
        """
Send message synchronously

Stores message and invokes all registered handlers.
        """
        topic_str = topic.value if isinstance(topic, Enum) else str(topic)
        with self._lock:
            self._sent_messages.append((topic_str, message, target))
            handlers = self._handlers.get(topic_str, []).copy()

        # Invoke handlers outside lock to prevent deadlocks
        for handler in handlers:
            try:
                # Convert dataclass to dict if needed
                if hasattr(message, "__dataclass_fields__"):
                    from dataclasses import asdict

                    data = asdict(message)
                else:
                    data = message
                handler(data)
            except Exception as e:
                # Log but don't raise - mirrors async behavior
                print(f"Handler error for {topic_str}: {e}")

    def send_async(
        self, topic: str | Enum, message: Any, target: str | None = None
    ) -> None:
        """
Send message (same as send for in-memory).
        """
        self.send(topic, message, target)

    # ========================================================================
    # Test helpers
    # ========================================================================

    def get_sent_messages(
        self, topic: str | None = None
    ) -> list[tuple[str, Any, str | None]]:
        """
Get sent messages for testing.

**Arguments:**

* ``topic``

  / *Condition*: optional / *Type*: str / *Default*: None /

  Filter by topic (None for all).

**Returns:**

/ *Type*: list[tuple[str, Any, str | None]] /

List of (topic, message, target) tuples.
        """
        with self._lock:
            if topic:
                return [
                    (t, m, tgt)
                    for t, m, tgt in self._sent_messages
                    if t == topic
                ]
            return self._sent_messages.copy()

    def clear(self) -> None:
        """
Clear all sent messages and handlers.
        """
        with self._lock:
            self._sent_messages.clear()
            self._handlers.clear()

    def clear_messages(self) -> None:
        """
Clear sent messages only (keep handlers).
        """
        with self._lock:
            self._sent_messages.clear()

    def message_count(self, topic: str | None = None) -> int:
        """
Get count of sent messages.
        """
        return len(self.get_sent_messages(topic))
