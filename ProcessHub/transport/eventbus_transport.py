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
# File: eventbus_transport.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   EventBus transport implementation for process hub.
#   Provides a RabbitMQ-based transport using EventBusClient.
#   Requires: EventBusClient package
#
# History:
#
# 22.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version
#
# *******************************************************************************
"""
EventBus transport implementation using RabbitMQ.

This module provides a RabbitMQ-based transport for the process hub,
using the EventBusClient library for message passing.

Requires: EventBusClient (https://github.com/test-fullautomation/python-rabbitmq-messagebus)

Usage::

   from ProcessHub.transport.eventbus_transport import EventBusTransport

   # With config file
   transport = EventBusTransport(config_path="config.jsonp")
   transport.register_handler("TOPIC", my_handler)
   transport.start()

   # With inline config
   transport = EventBusTransport(
      host="localhost",
      port=5672,
      exchange_name="process_hub",
   )
   transport.start()
   transport.send("TOPIC", {"data": "value"})
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Type

from .base import TransportBase

logger = logging.getLogger(__name__)

# Try to import EventBusClient
try:
   from EventBusClient.event_bus_client import EventBusClient
   from EventBusClient.message.dict_message import DictMessage
   from EventBusClient.message.base_message import BaseMessage

   HAS_EVENTBUS = True
except ImportError:
   HAS_EVENTBUS = False
   BaseMessage = object  # Fallback so class definition doesn't fail
   logger.warning(
      "EventBusClient not installed. "
      "Install from: https://github.com/test-fullautomation/python-rabbitmq-messagebus"
   )


# ============================================================================
# EventBus Configuration
# ============================================================================


@dataclass
class EventBusConfig:
   """
Configuration for EventBus transport.

Usage::

   # Minimal config
   config = EventBusConfig(host="localhost")

   # Full config
   config = EventBusConfig(
      host="rabbitmq.example.com",
      port=5672,
      exchange_name="process_hub",
      exchange_handler="TopicExchangeHandler",
      serializer="JsonSerializer",
      auto_reconnect=True,
   )

**Attributes:**

* ``host``

  / *Type*: str / *Default*: "localhost" /

  RabbitMQ server host.

* ``port``

  / *Type*: int / *Default*: 5672 /

  RabbitMQ server port.

* ``exchange_name``

  / *Type*: str / *Default*: "process_hub" /

  Exchange name for routing.

* ``exchange_handler``

  / *Type*: str / *Default*: "TopicExchangeHandler" /

  Exchange type handler class name.

* ``serializer``

  / *Type*: str / *Default*: "PickleSerializer" /

  Message serializer class name.

* ``auto_reconnect``

  / *Type*: bool / *Default*: True /

  Enable automatic reconnection on connection loss.

* ``qos_prefetch``

  / *Type*: int / *Default*: 10 /

  QoS prefetch count for message buffering.

* ``routing_key_prefix``

  / *Type*: str / *Default*: "processhub" /

  Prefix for all routing keys.
   """

   host: str = "localhost"
   port: int = 5672
   exchange_name: str = "process_hub"
   exchange_handler: str = "TopicExchangeHandler"
   serializer: str = "PickleSerializer"
   auto_reconnect: bool = True
   qos_prefetch: int = 10
   routing_key_prefix: str = "processhub"

   def to_dict(self) -> dict:
      """
Convert to EventBusClient config format.

**Returns:**

/ *Type*: dict /

Configuration dictionary compatible with EventBusClient.
      """
      return {
         "host": self.host,
         "port": self.port,
         "exchange_name": self.exchange_name,
         "exchange_handler": self.exchange_handler,
         "serializer": self.serializer,
         "auto_reconnect": self.auto_reconnect,
         "qos_prefetch": self.qos_prefetch,
      }


# ============================================================================
# ProcessHub Message (wraps dict for EventBusClient)
# ============================================================================


class ProcessHubMessage(BaseMessage):
   """
Message wrapper for ProcessHub data.

Wraps a dictionary payload for transport via EventBusClient.
   """

   def __init__(self, data: dict = None):
      """
Initialize message.

**Arguments:**

* ``data``

  / *Condition*: optional / *Type*: dict / *Default*: None /

  Dictionary payload to wrap.
      """
      self.data = data or {}

   @classmethod
   def from_data(cls, data: Any) -> "ProcessHubMessage":
      """
Create message from deserialized data.

**Arguments:**

* ``data``

  / *Condition*: required / *Type*: Any /

  Deserialized data from transport.

**Returns:**

/ *Type*: ProcessHubMessage /

ProcessHubMessage instance wrapping the data.
      """
      if isinstance(data, dict):
         return cls(data)
      elif isinstance(data, cls):
         return data
      else:
         return cls({"value": data})

   def get_value(self) -> dict:
      """
Get message payload.

**Returns:**

/ *Type*: dict /

Dictionary payload.
      """
      return self.data

   def __repr__(self) -> str:
      return f"ProcessHubMessage({self.data})"


# ============================================================================
# EventBus Transport (implements TransportBase)
# ============================================================================


class EventBusTransport(TransportBase):
   """
EventBus (RabbitMQ) transport implementation.

Uses EventBusClient for message passing with topic-based routing.

Usage::

   # With config file
   transport = EventBusTransport(config_path="config.jsonp")
   transport.register_handler("MY_TOPIC", my_handler)
   transport.start()
   transport.send("MY_TOPIC", {"key": "value"})
   transport.stop()

   # With inline config
   transport = EventBusTransport(
      host="localhost",
      port=5672,
      exchange_name="process_hub",
   )

   # With EventBusConfig
   config = EventBusConfig(host="rabbitmq.example.com")
   transport = EventBusTransport(config=config)
   """

   def __init__(
      self,
      config_path: Optional[str] = None,
      config: Optional[EventBusConfig] = None,
      host: Optional[str] = None,
      port: int = 5672,
      exchange_name: str = "process_hub",
      routing_key_prefix: str = "processhub",
      **kwargs,
   ):
      """
Initialize EventBus transport.

**Arguments:**

* ``config_path``

  / *Condition*: optional / *Type*: str / *Default*: None /

  Path to EventBusClient config file (config.jsonp).

* ``config``

  / *Condition*: optional / *Type*: EventBusConfig / *Default*: None /

  EventBusConfig instance with connection settings.

* ``host``

  / *Condition*: optional / *Type*: str / *Default*: None /

  RabbitMQ host (alternative to config).

* ``port``

  / *Condition*: optional / *Type*: int / *Default*: 5672 /

  RabbitMQ port.

* ``exchange_name``

  / *Condition*: optional / *Type*: str / *Default*: "process_hub" /

  Exchange name for routing.

* ``routing_key_prefix``

  / *Condition*: optional / *Type*: str / *Default*: "processhub" /

  Prefix for routing keys.

* ``**kwargs``

  / *Condition*: optional /

  Additional config options passed to EventBusConfig.
      """
      if not HAS_EVENTBUS:
         raise ImportError(
            "EventBusClient is required for EventBusTransport. "
            "Install from: https://github.com/test-fullautomation/python-rabbitmq-messagebus"
         )

      self._config_path = config_path

      # Build config from various sources
      if config:
         self._config = config
      elif host:
         self._config = EventBusConfig(
            host=host,
            port=port,
            exchange_name=exchange_name,
            routing_key_prefix=routing_key_prefix,
            **kwargs,
         )
      else:
         self._config = EventBusConfig(
            exchange_name=exchange_name,
            routing_key_prefix=routing_key_prefix,
            **kwargs,
         )

      self._client: Optional[EventBusClient] = None
      self._handlers: dict[str, Callable] = {}
      self._subscriptions: dict[str, Any] = {}  # topic -> SubscriptionCache
      self._started = False

   def _build_routing_key(self, topic: str) -> str:
      """
Build full routing key from topic.

**Arguments:**

* ``topic``

  / *Condition*: required / *Type*: str /

  Topic name (e.g., "PROCESS_START_REQUEST").

**Returns:**

/ *Type*: str /

Full routing key (e.g., "processhub.PROCESS_START_REQUEST").
      """
      prefix = self._config.routing_key_prefix
      if prefix:
         return f"{prefix}.{topic}"
      return topic

   def register_handler(
      self,
      topic: str | Enum,
      handler: Callable[[Any], None],
   ) -> None:
      """
Register a message handler for a topic.

**Arguments:**

* ``topic``

  / *Condition*: required / *Type*: str | Enum /

  Topic name (string or Enum).

* ``handler``

  / *Condition*: required / *Type*: Callable[[Any], None] /

  Callback function that receives message data (dict).
      """
      topic_str = topic.value if isinstance(topic, Enum) else str(topic)
      self._handlers[topic_str] = handler

      # If already started, subscribe now
      if self._client and self._started:
         self._subscribe_topic(topic_str, handler)

   def _subscribe_topic(self, topic: str, handler: Callable) -> None:
      """
Subscribe to a topic with the EventBusClient.

**Arguments:**

* ``topic``

  / *Condition*: required / *Type*: str /

  Topic name.

* ``handler``

  / *Condition*: required / *Type*: Callable /

  Callback function.
      """
      routing_key = self._build_routing_key(topic)

      def wrapped_callback(msg: ProcessHubMessage, headers: dict) -> None:
         """Unwrap message and call handler."""
         try:
            data = msg.get_value() if hasattr(msg, "get_value") else msg
            handler(data)
         except Exception as e:
            logger.exception("Handler error for topic %s: %s", topic, e)

      try:
         cache = self._client.on_sync(
            routing_key=routing_key,
            message_cls=ProcessHubMessage,
            callback=wrapped_callback,
            timeout=10.0,
         )
         self._subscriptions[topic] = cache
         logger.debug("Subscribed to routing key: %s", routing_key)
      except Exception as e:
         logger.error("Failed to subscribe to %s: %s", routing_key, e)

   def start(self) -> None:
      """
Start the transport.

Connects to RabbitMQ and subscribes to registered topics.
      """
      if self._started:
         return

      try:
         # Create client from config file or inline config
         if self._config_path:
            self._client = EventBusClient.from_config_sync(self._config_path)
         else:
            self._client = EventBusClient.from_config_sync(
               config_source=self._config.to_dict()
            )

         # Start background loop for async operations
         self._client.start_background_loop(loop_name="ProcessHubEventBus")

         # Connect to RabbitMQ
         self._client.connect_sync(
            host=self._config.host,
            port=self._config.port,
            timeout=30.0,
         )

         # Subscribe to all registered handlers
         for topic, handler in self._handlers.items():
            self._subscribe_topic(topic, handler)

         self._started = True
         logger.info(
            "EventBus Transport started (host=%s:%d, exchange=%s)",
            self._config.host,
            self._config.port,
            self._config.exchange_name,
         )

      except Exception as e:
         logger.exception("Failed to start EventBus transport")
         raise RuntimeError(f"EventBus transport start failed: {e}") from e

   def stop(self) -> None:
      """
Stop the transport.

Disconnects from RabbitMQ and cleans up resources.
      """
      if not self._started:
         return

      try:
         # Unsubscribe from all topics
         for topic in list(self._subscriptions.keys()):
            routing_key = self._build_routing_key(topic)
            try:
               self._client.off_sync(routing_key, timeout=5.0)
            except Exception as e:
               logger.debug("Error unsubscribing from %s: %s", routing_key, e)

         self._subscriptions.clear()

         # Close connection
         if self._client:
            self._client.close_sync(timeout=5.0)
            self._client.stop_background_loop(timeout=3.0)
            self._client = None

         self._started = False
         logger.info("EventBus Transport stopped")

      except Exception as e:
         logger.exception("Error stopping EventBus transport")

   def send(
      self,
      topic: str | Enum,
      message: Any,
      target: str | None = None,
   ) -> None:
      """
Send a message (blocking).

**Arguments:**

* ``topic``

  / *Condition*: required / *Type*: str | Enum /

  Topic name.

* ``message``

  / *Condition*: required / *Type*: Any /

  Message data (dict or dataclass).

* ``target``

  / *Condition*: optional / *Type*: str / *Default*: None /

  Optional target panel ID (included in message).
      """
      if not self._client or not self._started:
         raise RuntimeError("Transport not started")

      topic_str = topic.value if isinstance(topic, Enum) else str(topic)
      routing_key = self._build_routing_key(topic_str)
      payload = self._serialize(message)

      # Create ProcessHub message
      msg = ProcessHubMessage(payload)

      try:
         self._client.send_sync(
            routing_key=routing_key,
            message=msg,
            timeout=10.0,
         )
      except Exception as e:
         logger.error("Send error for %s: %s", routing_key, e)
         raise

   def send_async(
      self,
      topic: str | Enum,
      message: Any,
      target: str | None = None,
   ) -> None:
      """
Send a message (non-blocking).

**Arguments:**

* ``topic``

  / *Condition*: required / *Type*: str | Enum /

  Topic name.

* ``message``

  / *Condition*: required / *Type*: Any /

  Message data (dict or dataclass).

* ``target``

  / *Condition*: optional / *Type*: str / *Default*: None /

  Optional target panel ID (included in message).
      """
      if not self._client or not self._started:
         raise RuntimeError("Transport not started")

      topic_str = topic.value if isinstance(topic, Enum) else str(topic)
      routing_key = self._build_routing_key(topic_str)
      payload = self._serialize(message)

      # Create ProcessHub message
      msg = ProcessHubMessage(payload)

      try:
         # Use threadsafe=True for non-blocking send
         self._client.send_sync(
            routing_key=routing_key,
            message=msg,
            threadsafe=True,
            timeout=10.0,
         )
      except Exception as e:
         logger.error("Async send error for %s: %s", routing_key, e)

   def _serialize(self, message: Any) -> dict:
      """
Serialize message to dict format.

**Arguments:**

* ``message``

  / *Condition*: required / *Type*: Any /

  Message data (dict or dataclass).

**Returns:**

/ *Type*: dict /

Dictionary payload.
      """
      if hasattr(message, "__dataclass_fields__"):
         return asdict(message)
      elif isinstance(message, dict):
         return message
      else:
         return {"value": message}

   @property
   def is_started(self) -> bool:
      """
Check if transport is started.

**Returns:**

/ *Type*: bool /

True if transport is started, False otherwise.
      """
      return self._started

   @property
   def is_connected(self) -> bool:
      """
Check if connected to RabbitMQ.

**Returns:**

/ *Type*: bool /

True if connected, False otherwise.
      """
      if self._client:
         return self._client.is_connected()
      return False
