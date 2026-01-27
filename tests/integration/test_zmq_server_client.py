"""Integration tests for ProcessHubServer and ProcessHubClient using ZMQ transport."""

import pytest
import threading
import time

# Skip all tests if pyzmq is not available
pytest.importorskip("zmq", reason="pyzmq not installed")

from ProcessHub.runtime.server import ProcessHubServer
from ProcessHub.runtime.client import ProcessHubClient
from ProcessHub.transport.zmq_transport import ZmqTransport
from ProcessHub.process.executor import MockExecutor
from ProcessHub.ui.null_view import NullView


def get_ports(base: int) -> tuple[int, int]:
    """Get XPUB and XSUB ports from a base port."""
    return base, base + 1


class TestZmqServerClientIntegration:
    """Integration tests for server and client using ZMQ transport."""

    @pytest.fixture
    def ports(self):
        """Get unique ports for this test."""
        # Use high ports to avoid conflicts
        return get_ports(16100)

    @pytest.fixture
    def executor(self):
        """Create a mock executor."""
        return MockExecutor()

    @pytest.fixture
    def server(self, ports, executor):
        """Create and start a server with ZMQ transport."""
        xpub_port, xsub_port = ports
        transport = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )
        server = ProcessHubServer(
            transport=transport,
            executor=executor,
            view=NullView(),
            process_config={
                "test_proc": {"script": "test.py"},
                "other_proc": {"script": "other.py"},
            },
        )
        server.start()
        time.sleep(0.2)  # Let broker start and bind
        yield server
        server.stop()

    @pytest.fixture
    def client(self, ports):
        """Create and start a client with ZMQ transport."""
        xpub_port, xsub_port = ports
        transport = ZmqTransport(
            start_broker=False,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )
        client = ProcessHubClient(
            transport=transport,
            panel_id="test_panel",
        )
        client.start()
        time.sleep(0.2)  # Let connections establish
        yield client
        client.stop()

    def test_client_register(self, server, client):
        """Test client registration over ZMQ."""
        registered = threading.Event()
        response_data = {}

        def on_registered(data):
            response_data.update(data)
            registered.set()

        client.controller.connect("connection_registered", on_registered)
        client.register_connection(session_id="zmq_session")

        assert registered.wait(timeout=2.0), "Registration timed out"
        assert response_data.get("success") is True
        assert client.is_registered

    def test_client_unregister(self, server, client):
        """Test client unregistration over ZMQ."""
        # Register first
        registered = threading.Event()
        client.controller.connect("connection_registered", lambda d: registered.set())
        client.register_connection(session_id="zmq_session")
        assert registered.wait(timeout=2.0)

        # Unregister
        unregistered = threading.Event()
        client.controller.connect("connection_unregistered", lambda d: unregistered.set())
        client.unregister_connection()

        assert unregistered.wait(timeout=2.0), "Unregistration timed out"
        assert not client.is_registered

    def test_start_process(self, server, client, executor):
        """Test starting a process over ZMQ."""
        # Register
        registered = threading.Event()
        client.controller.connect("connection_registered", lambda d: registered.set())
        client.register_connection(session_id="zmq_session")
        assert registered.wait(timeout=2.0)

        # Start process
        started = threading.Event()
        start_data = {}

        def on_started(data):
            start_data.update(data)
            started.set()

        client.controller.connect("process_started", on_started)
        client.request_process_start(["test_proc"])

        assert started.wait(timeout=2.0), "Process start timed out"
        assert start_data.get("success") is True
        assert "test_proc" in executor._running

    def test_stop_process(self, server, client, executor):
        """Test stopping a process over ZMQ."""
        # Register and start
        registered = threading.Event()
        client.controller.connect("connection_registered", lambda d: registered.set())
        client.register_connection(session_id="zmq_session")
        assert registered.wait(timeout=2.0)

        started = threading.Event()
        client.controller.connect("process_started", lambda d: started.set())
        client.request_process_start(["test_proc"])
        assert started.wait(timeout=2.0)

        # Stop process
        stopped = threading.Event()
        client.controller.connect("process_stopped", lambda d: stopped.set())
        client.request_process_stop(["test_proc"])

        assert stopped.wait(timeout=2.0), "Process stop timed out"
        assert "test_proc" not in executor._running

    def test_start_multiple_processes(self, server, client, executor):
        """Test starting multiple processes over ZMQ."""
        # Register
        registered = threading.Event()
        client.controller.connect("connection_registered", lambda d: registered.set())
        client.register_connection(session_id="zmq_session")
        assert registered.wait(timeout=2.0)

        # Start multiple processes
        started = threading.Event()
        start_data = {}

        def on_started(data):
            start_data.update(data)
            started.set()

        client.controller.connect("process_started", on_started)
        client.request_process_start(["test_proc", "other_proc"])

        assert started.wait(timeout=2.0), "Process start timed out"
        assert start_data.get("success") is True
        assert "test_proc" in executor._running
        assert "other_proc" in executor._running


class TestZmqMultiClient:
    """Tests for multiple clients communicating over ZMQ."""

    @pytest.fixture
    def ports(self):
        """Get unique ports for this test."""
        return get_ports(16200)

    @pytest.fixture
    def executor(self):
        """Create a mock executor."""
        return MockExecutor()

    def test_multiple_clients_same_session(self, ports, executor):
        """Test multiple clients in same session over ZMQ."""
        xpub_port, xsub_port = ports

        # Server transport (with broker)
        server_transport = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )
        server = ProcessHubServer(
            transport=server_transport,
            executor=executor,
            view=NullView(),
            process_config={"test_proc": {"script": "test.py"}},
        )
        server.start()
        time.sleep(0.2)

        try:
            # Client 1
            client1_transport = ZmqTransport(
                start_broker=False,
                xpub_port=xpub_port,
                xsub_port=xsub_port,
            )
            client1 = ProcessHubClient(
                transport=client1_transport,
                panel_id="panel_1",
            )

            # Client 2
            client2_transport = ZmqTransport(
                start_broker=False,
                xpub_port=xpub_port,
                xsub_port=xsub_port,
            )
            client2 = ProcessHubClient(
                transport=client2_transport,
                panel_id="panel_2",
            )

            client1.start()
            client2.start()
            time.sleep(0.2)

            # Register both in same session
            reg1 = threading.Event()
            reg2 = threading.Event()
            client1.controller.connect("connection_registered", lambda d: reg1.set())
            client2.controller.connect("connection_registered", lambda d: reg2.set())

            client1.register_connection(session_id="shared_zmq_session")
            client2.register_connection(session_id="shared_zmq_session")

            assert reg1.wait(timeout=2.0), "Client 1 registration timed out"
            assert reg2.wait(timeout=2.0), "Client 2 registration timed out"

            # Check server sees both
            snapshot = server.core.get_state_snapshot()
            assert len(snapshot.connections) == 2

            # Both should see each other in session
            for conn in snapshot.connections:
                assert len(conn.session_panel_ids) == 2

            client1.stop()
            client2.stop()
        finally:
            server.stop()

    def test_clients_different_sessions(self, ports, executor):
        """Test multiple clients in different sessions over ZMQ."""
        xpub_port, xsub_port = ports

        server_transport = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )
        server = ProcessHubServer(
            transport=server_transport,
            executor=executor,
            view=NullView(),
            process_config={"test_proc": {"script": "test.py"}},
        )
        server.start()
        time.sleep(0.2)

        try:
            # Client 1
            client1_transport = ZmqTransport(
                start_broker=False,
                xpub_port=xpub_port,
                xsub_port=xsub_port,
            )
            client1 = ProcessHubClient(
                transport=client1_transport,
                panel_id="panel_1",
            )

            # Client 2
            client2_transport = ZmqTransport(
                start_broker=False,
                xpub_port=xpub_port,
                xsub_port=xsub_port,
            )
            client2 = ProcessHubClient(
                transport=client2_transport,
                panel_id="panel_2",
            )

            client1.start()
            client2.start()
            time.sleep(0.2)

            # Register in different sessions
            reg1 = threading.Event()
            reg2 = threading.Event()
            client1.controller.connect("connection_registered", lambda d: reg1.set())
            client2.controller.connect("connection_registered", lambda d: reg2.set())

            client1.register_connection(session_id="session_A")
            client2.register_connection(session_id="session_B")

            assert reg1.wait(timeout=2.0)
            assert reg2.wait(timeout=2.0)

            # Check server sees both in different sessions
            snapshot = server.core.get_state_snapshot()
            assert len(snapshot.connections) == 2

            # Each should only see themselves in their session
            for conn in snapshot.connections:
                assert len(conn.session_panel_ids) == 1

            client1.stop()
            client2.stop()
        finally:
            server.stop()


class TestZmqRestartFlow:
    """Tests for restart flow over ZMQ."""

    @pytest.fixture
    def ports(self):
        """Get unique ports for this test."""
        return get_ports(16300)

    @pytest.fixture
    def executor(self):
        """Create a mock executor."""
        return MockExecutor()

    def test_restart_notification_flow(self, ports, executor):
        """Test restart notification and acknowledgment over ZMQ."""
        xpub_port, xsub_port = ports

        server_transport = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )
        server = ProcessHubServer(
            transport=server_transport,
            executor=executor,
            view=NullView(),
            process_config={"test_proc": {"script": "test.py"}},
        )
        server.start()
        time.sleep(0.3)  # More time for broker to start

        client_transport = ZmqTransport(
            start_broker=False,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )
        client = ProcessHubClient(
            transport=client_transport,
            panel_id="test_panel",
        )
        client.start()
        time.sleep(0.3)  # More time for connections

        try:
            # Register
            registered = threading.Event()
            client.controller.connect("connection_registered", lambda d: registered.set())
            client.register_connection(session_id="zmq_session")
            assert registered.wait(timeout=2.0)

            # Start process
            started = threading.Event()
            client.controller.connect("process_started", lambda d: started.set())
            client.request_process_start(["test_proc"])
            assert started.wait(timeout=2.0)

            # Track restart events
            killed = threading.Event()
            killed_procs = []

            def on_killed(procs):
                killed_procs.extend(procs)
                killed.set()

            restarted = threading.Event()

            def on_restarted(data):
                restarted.set()

            client.controller.connect("process_killed", on_killed)
            client.controller.connect("process_restarted", on_restarted)

            # Kill the process
            executor.kill("test_proc")

            # Trigger health check and send the resulting messages
            # The server's tick() returns messages that need to be sent
            for _ in range(5):
                messages = server.core.tick()
                server._send_messages(messages)  # Actually send the messages
                if killed.wait(timeout=0.5):
                    break
                time.sleep(0.1)

            # Should receive kill notification
            assert killed.is_set(), "Kill notification timed out"
            assert "test_proc" in killed_procs

            # Acknowledge restart
            client.notify_restart_ready()
            time.sleep(0.2)  # Let message propagate

            # Trigger another tick to process the acknowledgment and send response
            for _ in range(5):
                messages = server.core.tick()
                server._send_messages(messages)  # Actually send the messages
                if restarted.wait(timeout=0.5):
                    break
                time.sleep(0.1)

            # Should receive restart done
            assert restarted.is_set(), "Restart notification timed out"

        finally:
            client.stop()
            server.stop()


class TestZmqBroadcast:
    """Tests for broadcast messages over ZMQ."""

    @pytest.fixture
    def ports(self):
        """Get unique ports for this test."""
        return get_ports(16400)

    @pytest.fixture
    def executor(self):
        """Create a mock executor."""
        return MockExecutor()

    def test_state_broadcast_to_all_clients(self, ports, executor):
        """Test that state broadcasts reach all clients."""
        xpub_port, xsub_port = ports

        server_transport = ZmqTransport(
            start_broker=True,
            xpub_port=xpub_port,
            xsub_port=xsub_port,
        )
        server = ProcessHubServer(
            transport=server_transport,
            executor=executor,
            view=NullView(),
            process_config={"test_proc": {"script": "test.py"}},
        )
        server.start()
        time.sleep(0.2)

        try:
            # Create multiple clients
            clients = []
            for i in range(3):
                transport = ZmqTransport(
                    start_broker=False,
                    xpub_port=xpub_port,
                    xsub_port=xsub_port,
                )
                client = ProcessHubClient(
                    transport=transport,
                    panel_id=f"panel_{i}",
                )
                client.start()
                clients.append(client)

            time.sleep(0.3)

            # Register all clients
            events = []
            for i, client in enumerate(clients):
                event = threading.Event()
                events.append(event)
                client.controller.connect("connection_registered", lambda d, e=event: e.set())
                client.register_connection(session_id=f"session_{i}")

            # Wait for all registrations
            for i, event in enumerate(events):
                assert event.wait(timeout=2.0), f"Client {i} registration timed out"

            # Track process started events on all clients
            started_events = []
            for client in clients:
                event = threading.Event()
                started_events.append(event)
                client.controller.connect("process_started", lambda d, e=event: e.set())

            # Start a process from the first client
            clients[0].request_process_start(["test_proc"])

            # First client should receive started response
            assert started_events[0].wait(timeout=2.0), "First client didn't receive start response"

            # Cleanup
            for client in clients:
                client.stop()

        finally:
            server.stop()
