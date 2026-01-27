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
# File: zmq_transport.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   ZMQ transport implementation for process hub.
#   Provides a ZeroMQ-based transport wrapping the ZMQ PUB/SUB pattern.
#   Requires: pyzmq (pip install pyzmq)
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
ZMQ transport implementation.

This module provides a ZeroMQ-based transport for the process hub,
wrapping the ZMQ PUB/SUB pattern for message passing.

Requires: pyzmq

    pip install pyzmq

Usage:

    from ProcessHub.transport.zmq_transport import ZmqTransport

    # Server (starts broker)
    
    transport = ZmqTransport(start_broker=True)
    
    transport.register_handler("TOPIC", my_handler)
    
    transport.start()

    # Client (connects to existing broker)
    
    transport = ZmqTransport(start_broker=False)
    
    transport.start()
    
    transport.send("TOPIC", {"data": "value"})
"""

from __future__ import annotations

import asyncio
import logging
import pickle
import threading
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Callable, Optional

from .base import TransportBase

logger = logging.getLogger(__name__)


# ============================================================================
# TCP Keepalive Configuration
# ============================================================================


@dataclass
class TcpKeepaliveConfig:
    """
TCP keepalive configuration for ZMQ sockets.

TCP keepalive helps detect dead connections when the server crashes
without sending a proper shutdown notification.

Usage:

    # Default: detect dead connection in ~25 seconds
    config = TcpKeepaliveConfig()

    # Faster detection: ~13 seconds
    config = TcpKeepaliveConfig(idle=5, interval=2, count=4)

    # Disable keepalive
    config = TcpKeepaliveConfig(enabled=False)

Attributes:

    enabled: Enable TCP keepalive (default: True)

    idle: Time in seconds before sending first probe (default: 10)

    interval: Time in seconds between probes (default: 5)

    count: Number of failed probes before connection is dead (default: 3)

Detection time = idle + (interval * count)
Default: 10 + (5 * 3) = 25 seconds
    """

    enabled: bool = True
    idle: int = 10      # Seconds before first probe
    interval: int = 5   # Seconds between probes
    count: int = 3      # Failed probes before dead

    def detection_time(self) -> float:
        """
Calculate the maximum time to detect a dead connection.

**Returns:**

  / *Type*: float /

  Detection time in seconds.
        """
        if not self.enabled:
            return float("inf")
        return self.idle + (self.interval * self.count)

# Try to import zmq
try:
    import zmq
    import zmq.asyncio

    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False
    logger.warning("pyzmq not installed. Install with: pip install pyzmq")


# ============================================================================
# ZMQ Broker
# ============================================================================


class ZmqBroker:
    """
ZeroMQ XPUB/XSUB broker (proxy).

Routes messages between publishers and subscribers.

Runs in a background thread.

Usage:

    broker = ZmqBroker()
    
    broker.start()
    
    # ... use transport ...
    
    broker.stop()
    """

    def __init__(
        self,
        xpub_port: int = 5555,
        xsub_port: int = 5556,
        bind_address: str = "tcp://*",
    ):
        """
Initialize broker.

Args:

    xpub_port: Port for XPUB socket (subscribers connect here)
    
    xsub_port: Port for XSUB socket (publishers connect here)
    
    bind_address: Address to bind to
        """
        if not HAS_ZMQ:
            raise ImportError("pyzmq is required for ZmqBroker")

        self._xpub_port = xpub_port
        self._xsub_port = xsub_port
        self._bind_address = bind_address

        self._context: Optional[zmq.Context] = None
        self._xpub: Optional[zmq.Socket] = None
        self._xsub: Optional[zmq.Socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def xpub_endpoint(self) -> str:
        """
Get the XPUB endpoint for subscribers.
        """
        return f"tcp://localhost:{self._xpub_port}"

    @property
    def xsub_endpoint(self) -> str:
        """
Get the XSUB endpoint for publishers.
        """
        return f"tcp://localhost:{self._xsub_port}"

    def start(self) -> None:
        """
Start the broker in a background thread.
        """
        if self._running:
            return

        self._context = zmq.Context()

        # XPUB socket - subscribers connect here
        self._xpub = self._context.socket(zmq.XPUB)
        self._xpub.bind(f"{self._bind_address}:{self._xpub_port}")

        # XSUB socket - publishers connect here
        self._xsub = self._context.socket(zmq.XSUB)
        self._xsub.bind(f"{self._bind_address}:{self._xsub_port}")

        self._running = True
        self._thread = threading.Thread(target=self._run_proxy, daemon=True)
        self._thread.start()

        logger.info(
            "ZMQ Broker started (XPUB=%d, XSUB=%d)",
            self._xpub_port,
            self._xsub_port,
        )

    def _run_proxy(self) -> None:
        """
Run the XPUB/XSUB proxy.
        """
        try:
            zmq.proxy(self._xpub, self._xsub)
        except zmq.ContextTerminated:
            pass  # Expected on shutdown
        except zmq.ZMQError:
            # Expected when sockets are closed during shutdown
            if self._running:
                logger.debug("Broker proxy interrupted")
        except Exception:
            # Only log unexpected errors if we're still supposed to be running
            if self._running:
                logger.exception("Broker proxy error")

    def stop(self) -> None:
        """
Stop the broker.
        """
        if not self._running:
            return

        self._running = False

        if self._xpub:
            self._xpub.close()
        if self._xsub:
            self._xsub.close()
        if self._context:
            self._context.term()

        logger.info("ZMQ Broker stopped")


# ============================================================================
# ZMQ Client (Async)
# ============================================================================


class ZmqAsyncClient:
    """
Async ZeroMQ PUB/SUB client.

Runs an asyncio event loop in a background thread for non-blocking I/O.
    """

    def __init__(
        self,
        sub_endpoint: str = "tcp://localhost:5555",
        pub_endpoint: str = "tcp://localhost:5556",
        keepalive: Optional[TcpKeepaliveConfig] = None,
    ):
        """
Initialize async client.

Args:

    sub_endpoint: Endpoint to subscribe to (broker's XPUB)

    pub_endpoint: Endpoint to publish to (broker's XSUB)

    keepalive: TCP keepalive configuration (default: enabled with 25s detection)
        """
        if not HAS_ZMQ:
            raise ImportError("pyzmq is required for ZmqAsyncClient")

        self._sub_endpoint = sub_endpoint
        self._pub_endpoint = pub_endpoint
        self._keepalive = keepalive or TcpKeepaliveConfig()

        self._context: Optional[zmq.asyncio.Context] = None
        self._pub_socket: Optional[zmq.asyncio.Socket] = None
        self._sub_socket: Optional[zmq.asyncio.Socket] = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._ready = threading.Event()  # Signals when sockets are ready

        self._handlers: dict[str, Callable] = {}
        self._subscribed_topics: set[str] = set()
        self._subscriber_task: Optional[asyncio.Task] = None

    def register_topic(
        self,
        topic: str,
        callback: Callable[[Any], None],
    ) -> None:
        """
Register a callback for a topic.

Args:

    topic: Topic string to subscribe to
    
    callback: Function to call when message received
        """
        self._handlers[topic] = callback
        self._subscribed_topics.add(topic)

        # If already running, subscribe now
        if self._sub_socket and self._running:
            asyncio.run_coroutine_threadsafe(
                self._subscribe(topic), self._loop
            )

    async def _subscribe(self, topic: str) -> None:
        """
Subscribe to a topic.
        """
        if self._sub_socket:
            self._sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)

    def _apply_keepalive(self, socket: zmq.Socket) -> None:
        """
Apply TCP keepalive settings to a socket.

Args:
    socket: ZMQ socket to configure
        """
        if not self._keepalive.enabled:
            socket.setsockopt(zmq.TCP_KEEPALIVE, 0)
            return

        socket.setsockopt(zmq.TCP_KEEPALIVE, 1)
        socket.setsockopt(zmq.TCP_KEEPALIVE_IDLE, self._keepalive.idle)
        socket.setsockopt(zmq.TCP_KEEPALIVE_INTVL, self._keepalive.interval)
        socket.setsockopt(zmq.TCP_KEEPALIVE_CNT, self._keepalive.count)

        logger.debug(
            "TCP keepalive configured: idle=%ds, interval=%ds, count=%d (detection: %.0fs)",
            self._keepalive.idle,
            self._keepalive.interval,
            self._keepalive.count,
            self._keepalive.detection_time(),
        )

    def start(self) -> None:
        """
Start the client in a background thread.
        """
        if self._running:
            return

        self._ready.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        # Wait for sockets to be ready (not just loop creation)
        if not self._ready.wait(timeout=5.0):
            logger.warning("ZMQ Client startup timeout - sockets may not be ready")
        else:
            logger.info("ZMQ Client started")

    def _run_loop(self) -> None:
        """
Run the asyncio event loop.
        """
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._async_main())
        except Exception as e:
            logger.exception("ZMQ client loop error")
        finally:
            self._loop.close()

    async def _async_main(self) -> None:
        """
Async main - setup sockets and run subscriber.
        """
        self._context = zmq.asyncio.Context()

        # Create SUB socket
        self._sub_socket = self._context.socket(zmq.SUB)
        self._apply_keepalive(self._sub_socket)
        self._sub_socket.connect(self._sub_endpoint)

        # Subscribe to all registered topics
        for topic in self._subscribed_topics:
            self._sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)
            logger.debug("Subscribed to topic: %s", topic)

        # Delay to let subscriptions propagate through broker
        # ZMQ subscriptions are async and need time to be established
        await asyncio.sleep(0.2)

        # Create PUB socket
        self._pub_socket = self._context.socket(zmq.PUB)
        self._apply_keepalive(self._pub_socket)
        self._pub_socket.connect(self._pub_endpoint)

        # Delay for PUB connection to establish
        await asyncio.sleep(0.1)

        # Start subscriber task
        self._subscriber_task = asyncio.create_task(self._subscriber_loop())

        # Signal that sockets are ready
        self._ready.set()
        logger.debug("ZMQ sockets ready")

        # Wait until stopped
        while self._running:
            await asyncio.sleep(0.1)

        # Cleanup
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass

        self._sub_socket.close()
        self._pub_socket.close()
        self._context.term()

    async def _subscriber_loop(self) -> None:
        """
Receive and dispatch messages.
        """
        while self._running:
            try:
                # Non-blocking receive with timeout
                if self._sub_socket.poll(100, zmq.POLLIN):
                    message = await self._sub_socket.recv_multipart()

                    if len(message) >= 2:
                        topic = message[0].decode("utf-8")
                        data = pickle.loads(message[1])

                        handler = self._handlers.get(topic)
                        if handler:
                            try:
                                handler(data)
                            except Exception as e:
                                logger.exception(
                                    "Handler error for topic %s", topic
                                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    logger.exception("Subscriber loop error")

    def send_message(
        self,
        topic: str,
        message: Any,
        timeout: float = 2.0,
    ) -> bool:
        """
Send a message (blocking).

Args:

    topic: Topic to publish to
    
    message: Message data
    
    timeout: Timeout in seconds

Returns:

    True if sent successfully
        """
        if not self._running or not self._loop:
            return False

        future = asyncio.run_coroutine_threadsafe(
            self._async_send(topic, message), self._loop
        )

        try:
            future.result(timeout=timeout)
            return True
        except Exception as e:
            logger.error("Send error: %s (%s)", e or "no details", type(e).__name__)
            return False

    def send_message_async(self, topic: str, message: Any) -> None:
        """
Send a message (non-blocking).

Args:
    topic: Topic to publish to
    message: Message data
        """
        if not self._running or not self._loop:
            return

        asyncio.run_coroutine_threadsafe(
            self._async_send(topic, message), self._loop
        )

    async def _async_send(self, topic: str, message: Any) -> None:
        """
Async send implementation.
        """
        if self._pub_socket:
            serialized = pickle.dumps(message, protocol=-1)
            await self._pub_socket.send_multipart(
                [topic.encode("utf-8"), serialized]
            )

    def stop(self) -> None:
        """
Stop the client.
        """
        if not self._running:
            return

        self._running = False

        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        logger.info("ZMQ Client stopped")


# ============================================================================
# ZMQ Transport (implements TransportBase)
# ============================================================================


class ZmqTransport(TransportBase):
    """
ZeroMQ transport implementation.

Wraps ZmqBroker and ZmqAsyncClient to implement the TransportBase interface.

Usage:

    # Server side (with broker)

    transport = ZmqTransport(start_broker=True)

    transport.register_handler("MY_TOPIC", my_handler)

    transport.start()

    transport.send("MY_TOPIC", {"key": "value"})

    transport.stop()

    # Client side (connect to existing broker)

    transport = ZmqTransport(start_broker=False)

    transport.register_handler("MY_TOPIC", my_handler)

    transport.start()

    # With custom keepalive (faster detection)

    transport = ZmqTransport(
        start_broker=False,
        keepalive=TcpKeepaliveConfig(idle=5, interval=2, count=4),
    )
    """

    def __init__(
        self,
        start_broker: bool = True,
        xpub_port: int = 5555,
        xsub_port: int = 5556,
        bind_address: str = "tcp://*",
        connect_address: str = "tcp://localhost",
        keepalive: Optional[TcpKeepaliveConfig] = None,
    ):
        """
Initialize ZMQ transport.

Args:

    start_broker: Whether to start the broker

    xpub_port: XPUB port (subscribers connect)

    xsub_port: XSUB port (publishers connect)

    bind_address: Address for broker to bind

    connect_address: Address for client to connect

    keepalive: TCP keepalive configuration for detecting dead connections.
               Default: enabled with 25 second detection time.
               Set to TcpKeepaliveConfig(enabled=False) to disable.
        """
        if not HAS_ZMQ:
            raise ImportError(
                "pyzmq is required for ZmqTransport. "
                "Install with: pip install pyzmq"
            )

        self._start_broker = start_broker
        self._xpub_port = xpub_port
        self._xsub_port = xsub_port
        self._bind_address = bind_address
        self._connect_address = connect_address
        self._keepalive = keepalive or TcpKeepaliveConfig()

        self._broker: Optional[ZmqBroker] = None
        self._client: Optional[ZmqAsyncClient] = None
        self._handlers: dict[str, Callable] = {}
        self._started = False

    def register_handler(
        self,
        topic: str | Enum,
        handler: Callable[[Any], None],
    ) -> None:
        """
Register a message handler for a topic.
        """
        topic_str = topic.value if isinstance(topic, Enum) else str(topic)
        self._handlers[topic_str] = handler

        # If already started, register with client
        if self._client:
            self._client.register_topic(topic_str, handler)

    def start(self) -> None:
        """
Start the transport.
        """
        if self._started:
            return

        # Start broker if requested
        if self._start_broker:
            self._broker = ZmqBroker(
                xpub_port=self._xpub_port,
                xsub_port=self._xsub_port,
                bind_address=self._bind_address,
            )
            self._broker.start()
            time.sleep(0.1)  # Give broker time to bind

        # Create and start client
        self._client = ZmqAsyncClient(
            sub_endpoint=f"{self._connect_address}:{self._xpub_port}",
            pub_endpoint=f"{self._connect_address}:{self._xsub_port}",
            keepalive=self._keepalive,
        )

        # Register all pending handlers
        for topic, handler in self._handlers.items():
            self._client.register_topic(topic, handler)

        self._client.start()
        self._started = True

        logger.info(
            "ZMQ Transport started (broker=%s, keepalive=%s, detection=%.0fs)",
            self._start_broker,
            self._keepalive.enabled,
            self._keepalive.detection_time(),
        )

    def stop(self) -> None:
        """
Stop the transport.
        """
        if not self._started:
            return

        if self._client:
            self._client.stop()
            self._client = None

        if self._broker:
            self._broker.stop()
            self._broker = None

        self._started = False
        logger.info("ZMQ Transport stopped")

    def send(
        self,
        topic: str | Enum,
        message: Any,
        target: str | None = None,
    ) -> None:
        """
Send a message (blocking).
        """
        if not self._client:
            raise RuntimeError("Transport not started")

        topic_str = topic.value if isinstance(topic, Enum) else str(topic)
        payload = self._serialize(message)
        self._client.send_message(topic_str, payload)

    def send_async(
        self,
        topic: str | Enum,
        message: Any,
        target: str | None = None,
    ) -> None:
        """
Send a message (non-blocking).
        """
        if not self._client:
            raise RuntimeError("Transport not started")

        topic_str = topic.value if isinstance(topic, Enum) else str(topic)
        payload = self._serialize(message)
        self._client.send_message_async(topic_str, payload)

    def _serialize(self, message: Any) -> Any:
        """
Serialize message to transport format.
        """
        # Convert dataclass to dict
        if hasattr(message, "__dataclass_fields__"):
            return asdict(message)
        return message

    @property
    def is_started(self) -> bool:
        """
Check if transport is started.
        """
        return self._started
