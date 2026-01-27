"""Unit tests for ZMQ transport."""

import time
import pytest
from dataclasses import dataclass
from typing import Any, List
from unittest.mock import MagicMock

# Skip all tests if pyzmq is not available
pytest.importorskip("zmq", reason="pyzmq not installed")

from ProcessHub.transport.zmq_transport import (
    ZmqBroker,
    ZmqAsyncClient,
    ZmqTransport,
    HAS_ZMQ,
)


# Use dynamic ports to avoid conflicts with other tests or services
# Each test class uses a different port range
def get_ports(base: int) -> tuple[int, int]:
    """Get XPUB and XSUB ports from a base port."""
    return base, base + 1


class TestZmqBroker:
    """Tests for ZmqBroker."""

    def test_start_stop_lifecycle(self):
        """Test broker start/stop lifecycle."""
        xpub_port, xsub_port = get_ports(15550)
        broker = ZmqBroker(xpub_port=xpub_port, xsub_port=xsub_port)

        assert not broker._running

        broker.start()

        assert broker._running
        assert broker._thread is not None
        assert broker._thread.is_alive()

        broker.stop()

        assert not broker._running

    def test_start_is_idempotent(self):
        """Test that multiple start calls are safe."""
        xpub_port, xsub_port = get_ports(15552)
        broker = ZmqBroker(xpub_port=xpub_port, xsub_port=xsub_port)

        broker.start()
        thread1 = broker._thread

        broker.start()  # Should do nothing
        thread2 = broker._thread

        assert thread1 is thread2

        broker.stop()

    def test_stop_is_idempotent(self):
        """Test that multiple stop calls are safe."""
        xpub_port, xsub_port = get_ports(15554)
        broker = ZmqBroker(xpub_port=xpub_port, xsub_port=xsub_port)

        broker.start()
        broker.stop()
        broker.stop()  # Should not raise

    def test_endpoint_properties(self):
        """Test endpoint property accessors."""
        xpub_port, xsub_port = get_ports(15556)
        broker = ZmqBroker(xpub_port=xpub_port, xsub_port=xsub_port)

        assert broker.xpub_endpoint == f"tcp://localhost:{xpub_port}"
        assert broker.xsub_endpoint == f"tcp://localhost:{xsub_port}"

    def test_custom_bind_address(self):
        """Test broker with custom bind address."""
        xpub_port, xsub_port = get_ports(15558)
        broker = ZmqBroker(
            xpub_port=xpub_port,
            xsub_port=xsub_port,
            bind_address="tcp://127.0.0.1",
        )

        broker.start()
        assert broker._running
        broker.stop()


class TestZmqAsyncClient:
    """Tests for ZmqAsyncClient."""

    @pytest.fixture
    def broker(self):
        """Create and start a broker for testing."""
        xpub_port, xsub_port = get_ports(15560)
        broker = ZmqBroker(xpub_port=xpub_port, xsub_port=xsub_port)
        broker.start()
        time.sleep(0.1)  # Let broker bind
        yield broker, xpub_port, xsub_port
        broker.stop()

    def test_start_stop_lifecycle(self, broker):
        """Test client start/stop lifecycle."""
        broker_instance, xpub_port, xsub_port = broker

        client = ZmqAsyncClient(
            sub_endpoint=f"tcp://localhost:{xpub_port}",
            pub_endpoint=f"tcp://localhost:{xsub_port}",
        )

        assert not client._running

        client.start()

        assert client._running
        assert client._loop is not None

        client.stop()

        assert not client._running

    def test_register_topic_before_start(self, broker):
        """Test registering a topic before starting."""
        broker_instance, xpub_port, xsub_port = broker

        client = ZmqAsyncClient(
            sub_endpoint=f"tcp://localhost:{xpub_port}",
            pub_endpoint=f"tcp://localhost:{xsub_port}",
        )

        handler = MagicMock()
        client.register_topic("TEST_TOPIC", handler)

        assert "TEST_TOPIC" in client._handlers
        assert "TEST_TOPIC" in client._subscribed_topics

        client.start()
        time.sleep(0.1)
        client.stop()

    def test_register_topic_after_start(self, broker):
        """Test registering a topic after starting."""
        broker_instance, xpub_port, xsub_port = broker

        client = ZmqAsyncClient(
            sub_endpoint=f"tcp://localhost:{xpub_port}",
            pub_endpoint=f"tcp://localhost:{xsub_port}",
        )

        client.start()
        time.sleep(0.1)

        handler = MagicMock()
        client.register_topic("LATE_TOPIC", handler)

        assert "LATE_TOPIC" in client._handlers

        client.stop()

    def test_send_message_not_started(self):
        """Test that send returns False when not started."""
        client = ZmqAsyncClient()

        result = client.send_message("TOPIC", {"data": "test"})

        assert result is False

    def test_send_message_async_not_started(self):
        """Test that async send does nothing when not started."""
        client = ZmqAsyncClient()

        # Should not raise
        client.send_message_async("TOPIC", {"data": "test"})


class TestZmqTransport:
    """Tests for ZmqTransport."""

    def test_start_with_broker(self):
        """Test starting transport with broker."""
        xpub_port, xsub_port = get_ports(15570)
        transport = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        assert not transport.is_started

        transport.start()

        assert transport.is_started
        assert transport._broker is not None
        assert transport._client is not None

        transport.stop()

        assert not transport.is_started

    def test_start_without_broker(self):
        """Test starting transport without broker (client only)."""
        # First start a broker separately
        xpub_port, xsub_port = get_ports(15572)
        broker = ZmqBroker(xpub_port=xpub_port, xsub_port=xsub_port)
        broker.start()
        time.sleep(0.1)

        try:
            transport = ZmqTransport(
                start_broker=False,
                xpub_port=xpub_port,
                xsub_port=xsub_port,
            )

            transport.start()

            assert transport.is_started
            assert transport._broker is None  # No broker created
            assert transport._client is not None

            transport.stop()
        finally:
            broker.stop()

    def test_register_handler_before_start(self):
        """Test registering handler before start."""
        xpub_port, xsub_port = get_ports(15574)
        transport = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        handler = MagicMock()
        transport.register_handler("MY_TOPIC", handler)

        assert "MY_TOPIC" in transport._handlers

        transport.start()
        time.sleep(0.1)
        transport.stop()

    def test_register_handler_after_start(self):
        """Test registering handler after start."""
        xpub_port, xsub_port = get_ports(15576)
        transport = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        transport.start()
        time.sleep(0.1)

        handler = MagicMock()
        transport.register_handler("LATE_TOPIC", handler)

        assert "LATE_TOPIC" in transport._handlers

        transport.stop()

    def test_register_handler_with_enum(self):
        """Test registering handler with enum topic."""
        from enum import Enum

        class MyTopic(Enum):
            TEST = "TEST_TOPIC"

        xpub_port, xsub_port = get_ports(15578)
        transport = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        handler = MagicMock()
        transport.register_handler(MyTopic.TEST, handler)

        assert "TEST_TOPIC" in transport._handlers

    def test_send_before_start_raises(self):
        """Test that send before start raises error."""
        xpub_port, xsub_port = get_ports(15580)
        transport = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        with pytest.raises(RuntimeError, match="not started"):
            transport.send("TOPIC", {"data": "test"})

    def test_send_async_before_start_raises(self):
        """Test that send_async before start raises error."""
        xpub_port, xsub_port = get_ports(15582)
        transport = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        with pytest.raises(RuntimeError, match="not started"):
            transport.send_async("TOPIC", {"data": "test"})

    def test_serialize_dataclass(self):
        """Test that dataclass messages are serialized to dict."""
        xpub_port, xsub_port = get_ports(15584)
        transport = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        @dataclass
        class TestMessage:
            name: str
            value: int

        message = TestMessage(name="test", value=42)
        result = transport._serialize(message)

        assert result == {"name": "test", "value": 42}

    def test_serialize_dict(self):
        """Test that dict messages pass through unchanged."""
        xpub_port, xsub_port = get_ports(15586)
        transport = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        message = {"name": "test", "value": 42}
        result = transport._serialize(message)

        assert result == message

    def test_start_is_idempotent(self):
        """Test that multiple start calls are safe."""
        xpub_port, xsub_port = get_ports(15588)
        transport = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        transport.start()
        client1 = transport._client

        transport.start()  # Should do nothing
        client2 = transport._client

        assert client1 is client2

        transport.stop()

    def test_stop_is_idempotent(self):
        """Test that multiple stop calls are safe."""
        xpub_port, xsub_port = get_ports(15590)
        transport = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        transport.start()
        transport.stop()
        transport.stop()  # Should not raise


class TestZmqTransportIntegration:
    """Integration tests for ZMQ transport with multiple transports."""

    def test_two_transports_communicate(self):
        """Test that two transports can communicate through a broker."""
        xpub_port, xsub_port = get_ports(15600)

        # Server transport (with broker)
        server = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        # Client transport (without broker)
        client = ZmqTransport(
            start_broker=False,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        # Track received messages
        server_received: List[Any] = []
        client_received: List[Any] = []

        server.register_handler("FROM_CLIENT", lambda msg: server_received.append(msg))
        client.register_handler("FROM_SERVER", lambda msg: client_received.append(msg))

        # Start both
        server.start()
        time.sleep(0.1)  # Let broker start

        client.start()
        time.sleep(0.2)  # Let connections establish

        # Send messages
        client.send("FROM_CLIENT", {"source": "client", "id": 1})
        server.send("FROM_SERVER", {"source": "server", "id": 2})

        # Wait for delivery
        time.sleep(0.3)

        # Verify
        assert len(server_received) == 1
        assert server_received[0]["source"] == "client"

        assert len(client_received) == 1
        assert client_received[0]["source"] == "server"

        # Cleanup
        client.stop()
        server.stop()

    def test_multiple_clients(self):
        """Test multiple clients receiving same broadcast."""
        xpub_port, xsub_port = get_ports(15610)

        # Server with broker
        server = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        # Two clients
        client1 = ZmqTransport(
            start_broker=False,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )
        client2 = ZmqTransport(
            start_broker=False,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        # Track received
        client1_received: List[Any] = []
        client2_received: List[Any] = []

        client1.register_handler("BROADCAST", lambda msg: client1_received.append(msg))
        client2.register_handler("BROADCAST", lambda msg: client2_received.append(msg))

        # Start all
        server.start()
        time.sleep(0.1)

        client1.start()
        client2.start()
        time.sleep(0.2)

        # Server broadcasts
        server.send("BROADCAST", {"message": "hello all"})

        # Wait for delivery
        time.sleep(0.3)

        # Both clients should receive
        assert len(client1_received) == 1
        assert len(client2_received) == 1
        assert client1_received[0]["message"] == "hello all"
        assert client2_received[0]["message"] == "hello all"

        # Cleanup
        client1.stop()
        client2.stop()
        server.stop()

    def test_topic_filtering(self):
        """Test that clients only receive subscribed topics."""
        xpub_port, xsub_port = get_ports(15620)

        server = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        client = ZmqTransport(
            start_broker=False,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        subscribed_received: List[Any] = []

        # Only subscribe to TOPIC_A
        client.register_handler("TOPIC_A", lambda msg: subscribed_received.append(msg))

        server.start()
        time.sleep(0.1)

        client.start()
        time.sleep(0.2)

        # Send to both topics
        server.send("TOPIC_A", {"topic": "A"})
        server.send("TOPIC_B", {"topic": "B"})  # Client not subscribed

        time.sleep(0.3)

        # Should only receive TOPIC_A
        assert len(subscribed_received) == 1
        assert subscribed_received[0]["topic"] == "A"

        client.stop()
        server.stop()

    def test_dataclass_message_roundtrip(self):
        """Test sending dataclass messages through the transport."""
        xpub_port, xsub_port = get_ports(15630)

        @dataclass
        class RequestMessage:
            action: str
            params: dict

        server = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        client = ZmqTransport(
            start_broker=False,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )

        received: List[Any] = []
        server.register_handler("REQUEST", lambda msg: received.append(msg))

        server.start()
        time.sleep(0.1)

        client.start()
        time.sleep(0.2)

        # Send dataclass message
        message = RequestMessage(action="start", params={"name": "process1"})
        client.send("REQUEST", message)

        time.sleep(0.3)

        # Should receive as dict (serialized)
        assert len(received) == 1
        assert received[0]["action"] == "start"
        assert received[0]["params"]["name"] == "process1"

        client.stop()
        server.stop()
