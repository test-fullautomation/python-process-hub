"""Pytest configuration and fixtures."""

import sys
from pathlib import Path

import pytest

# Add ProcessHub to path for imports
root_path = Path(__file__).parent.parent
sys.path.insert(0, str(root_path))


# ============================================================================
# Core Fixtures
# ============================================================================


@pytest.fixture
def process_registry():
    """Create a fresh ProcessRegistry."""
    from ProcessHub.core.process_registry import ProcessRegistry

    return ProcessRegistry()


@pytest.fixture
def restart_fsm():
    """Create a fresh RestartStateMachine."""
    from ProcessHub.core.restart_state import RestartStateMachine

    return RestartStateMachine()


# ============================================================================
# Transport Fixtures
# ============================================================================


@pytest.fixture
def inmemory_transport():
    """Create an InMemoryTransport for testing."""
    from ProcessHub.transport.inmemory_transport import InMemoryTransport

    transport = InMemoryTransport()
    yield transport
    transport.clear()


# ============================================================================
# Executor Fixtures
# ============================================================================


@pytest.fixture
def mock_executor():
    """Create a MockExecutor for testing."""
    from ProcessHub.process.executor import MockExecutor

    return MockExecutor()


# ============================================================================
# Hub Core Fixtures
# ============================================================================


@pytest.fixture
def hub_core(mock_executor):
    """Create a ProcessHubCore with mock executor."""
    from ProcessHub.core.hub_core import ProcessHubCore

    return ProcessHubCore(
        process_starter=lambda name: mock_executor.start(name, {}),
        process_stopper=mock_executor.stop,
        health_checker=lambda names: [n for n in names if not mock_executor.is_running(n)],
    )


# ============================================================================
# Server/Client Fixtures
# ============================================================================


@pytest.fixture
def server_client_pair(inmemory_transport, mock_executor):
    """Create a server and client pair for integration testing."""
    from ProcessHub.runtime.server import ProcessHubServer
    from ProcessHub.runtime.client import ProcessHubClient
    from ProcessHub.ui.null_view import NullView

    server = ProcessHubServer(
        transport=inmemory_transport,
        executor=mock_executor,
        view=NullView(),
    )
    server.start()

    client = ProcessHubClient(
        transport=inmemory_transport,
        panel_id="test_panel",
    )
    client.start()

    yield server, client

    client.stop()
    server.stop()
