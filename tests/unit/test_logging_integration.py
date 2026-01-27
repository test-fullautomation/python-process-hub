"""Unit tests for LoggingIntegration."""

import os
import pytest
from ProcessHub.logging.integration import (
    LoggingIntegration,
    LoggingServerType,
    LoggingConfig,
    MockLoggingServer,
    LoggingAwareExecutor,
)
from ProcessHub.process.executor import MockExecutor


class TestLoggingConfig:
    """Tests for LoggingConfig."""

    def test_disabled_config(self):
        """Test disabled logging config."""
        config = LoggingConfig(enabled=False)
        assert not config.enabled
        assert config.to_command_args() == []
        assert config.to_dict()["central_log"] is False

    def test_enabled_config(self):
        """Test enabled logging config with all fields."""
        config = LoggingConfig(
            enabled=True,
            config_dir="fluentbit",
            host="localhost",
            port=24000,
        )
        assert config.enabled
        assert config.host == "localhost"
        assert config.port == 24000

    def test_to_command_args(self):
        """Test conversion to command line arguments."""
        config = LoggingConfig(
            enabled=True,
            config_dir="fluentbit",
            host="localhost",
            port=24000,
        )

        args = config.to_command_args(taf_path="/path/to/taf")

        assert "--variable TAF_PATH:/path/to/taf" in args
        assert "--variable central_logging_conf:fluentbit" in args
        assert "--variable central_logging_host:localhost" in args
        assert "--variable central_logging_port:24000" in args

    def test_to_command_args_with_extra(self):
        """Test extra args are included."""
        config = LoggingConfig(
            enabled=True,
            config_dir="telegraf",
            host="192.168.1.1",
            port=25000,
            extra_args={"custom_key": "custom_value"},
        )

        args = config.to_command_args()

        assert "--variable custom_key:custom_value" in args

    def test_to_dict(self):
        """Test conversion to dict."""
        config = LoggingConfig(
            enabled=True,
            config_dir="fluentbit",
            host="localhost",
            port=24000,
        )

        d = config.to_dict()

        assert d["central_log"] is True
        assert d["logging_config_dir"] == "fluentbit"
        assert d["logging_host"] == "localhost"
        assert d["logging_port"] == 24000


class TestMockLoggingServer:
    """Tests for MockLoggingServer."""

    def test_allocate_single_port(self):
        """Test allocating a single port."""
        server = MockLoggingServer(uuid=12345, base_port=24000)

        host, ports = server.allocate(1)

        assert host == "localhost"
        assert len(ports) == 1
        assert ports[0] == 24000

    def test_allocate_multiple_ports(self):
        """Test allocating multiple ports."""
        server = MockLoggingServer(uuid=12345, base_port=24000)

        host, ports = server.allocate(3)

        assert len(ports) == 3
        assert ports == [24000, 24001, 24002]

    def test_sequential_allocations(self):
        """Test sequential port allocations."""
        server = MockLoggingServer(uuid=12345, base_port=24000)

        _, ports1 = server.allocate(2)
        _, ports2 = server.allocate(2)

        assert ports1 == [24000, 24001]
        assert ports2 == [24002, 24003]

    def test_deallocate_resets(self):
        """Test deallocate resets port counter."""
        server = MockLoggingServer(uuid=12345, base_port=24000)

        server.allocate(5)
        server.deallocate()
        _, ports = server.allocate(1)

        assert ports[0] == 24000

    def test_hot_cfg_dir(self):
        """Test hot config dir path."""
        server = MockLoggingServer(uuid=12345, hot_dir="/path/to/hot")

        assert "mock_12345" in server.hot_cfg_dir


class TestLoggingIntegration:
    """Tests for LoggingIntegration."""

    @pytest.fixture
    def mock_paths(self, tmp_path):
        """Create temporary paths for testing."""
        return {
            "src_dir": str(tmp_path / "src"),
            "hot_dir": str(tmp_path / "hot"),
            "influx_dir": str(tmp_path / "influx"),
            "ctrl_dir": str(tmp_path / "ctrl"),
        }

    @pytest.fixture
    def mock_server_factory(self, mock_paths):
        """Create a mock server factory for testing."""
        def factory(uuid, paths):
            return MockLoggingServer(uuid=uuid, base_port=24000, **paths)
        return factory

    def test_start_stop_lifecycle(self, mock_paths, mock_server_factory):
        """Test start/stop lifecycle."""
        integration = LoggingIntegration(
            server_type=LoggingServerType.CUSTOM,
            paths=mock_paths,
            server_factory=mock_server_factory,
        )

        assert not integration.is_started
        assert integration.server is None

        integration.start()

        assert integration.is_started
        assert integration.server is not None

        integration.stop()

        assert not integration.is_started

    def test_creates_ctrl_dir(self, mock_paths, mock_server_factory):
        """Test that control directory is created."""
        integration = LoggingIntegration(
            server_type=LoggingServerType.CUSTOM,
            paths=mock_paths,
            server_factory=mock_server_factory,
        )

        integration.start()

        assert os.path.exists(mock_paths["ctrl_dir"])

        integration.stop()

    def test_get_process_logging_config_disabled(self, mock_paths, mock_server_factory):
        """Test getting config for process without central_log."""
        integration = LoggingIntegration(
            server_type=LoggingServerType.CUSTOM,
            paths=mock_paths,
            server_factory=mock_server_factory,
        )
        integration.start()

        config = integration.get_process_logging_config(
            "my_process",
            process_config={"central_log": False},
        )

        assert not config.enabled
        integration.stop()

    def test_get_process_logging_config_enabled(self, mock_paths, mock_server_factory):
        """Test getting config for process with central_log."""
        integration = LoggingIntegration(
            server_type=LoggingServerType.CUSTOM,
            paths=mock_paths,
            server_factory=mock_server_factory,
        )
        integration.start()

        config = integration.get_process_logging_config(
            "my_process",
            process_config={"central_log": True},
        )

        assert config.enabled
        assert config.host is not None
        assert config.port is not None

        integration.stop()

    def test_enhance_process_config(self, mock_paths, mock_server_factory):
        """Test enhancing process config with logging settings."""
        integration = LoggingIntegration(
            server_type=LoggingServerType.CUSTOM,
            paths=mock_paths,
            taf_path="/path/to/taf",
            server_factory=mock_server_factory,
        )
        integration.start()

        original_config = {
            "script": "test.py",
            "args": ["--arg1"],
            "central_log": True,
        }

        enhanced = integration.enhance_process_config("my_process", original_config)

        # Original fields preserved
        assert enhanced["script"] == "test.py"
        assert enhanced["args"] == ["--arg1"]

        # Logging fields added
        assert "logging_host" in enhanced
        assert "logging_port" in enhanced
        assert enhanced["taf_path"] == "/path/to/taf"

        integration.stop()

    def test_custom_server_factory(self, mock_paths):
        """Test using custom server factory."""
        custom_server = MockLoggingServer(uuid=99999, base_port=30000, **mock_paths)

        def factory(uuid, paths):
            return custom_server

        integration = LoggingIntegration(
            server_type=LoggingServerType.CUSTOM,
            paths=mock_paths,
            server_factory=factory,
        )
        integration.start()

        assert integration.server is custom_server

        _, ports = integration.server.allocate(1)
        assert ports[0] == 30000

        integration.stop()

    def test_custom_without_factory_raises(self, mock_paths):
        """Test that CUSTOM type without factory raises error."""
        integration = LoggingIntegration(
            server_type=LoggingServerType.CUSTOM,
            paths=mock_paths,
            server_factory=None,
        )

        with pytest.raises(ValueError, match="server_factory"):
            integration.start()


class TestLoggingAwareExecutor:
    """Tests for LoggingAwareExecutor."""

    @pytest.fixture
    def mock_paths(self, tmp_path):
        return {
            "src_dir": str(tmp_path / "src"),
            "hot_dir": str(tmp_path / "hot"),
            "influx_dir": str(tmp_path / "influx"),
            "ctrl_dir": str(tmp_path / "ctrl"),
        }

    @pytest.fixture
    def mock_server_factory(self, mock_paths):
        """Create a mock server factory for testing."""
        def factory(uuid, paths):
            return MockLoggingServer(uuid=uuid, base_port=24000, **paths)
        return factory

    def test_wraps_executor(self, mock_paths, mock_server_factory):
        """Test that it wraps an executor."""
        base_executor = MockExecutor()
        logging_integration = LoggingIntegration(
            server_type=LoggingServerType.CUSTOM,
            paths=mock_paths,
            server_factory=mock_server_factory,
        )
        logging_integration.start()

        process_configs = {
            "my_process": {"script": "test.py", "central_log": True}
        }

        executor = LoggingAwareExecutor(
            executor=base_executor,
            logging_integration=logging_integration,
            process_configs=process_configs,
        )

        # Start a process
        success, msg, pid = executor.start("my_process", {})

        assert success
        assert executor.is_running("my_process")

        # Stop the process
        executor.stop("my_process")
        assert not executor.is_running("my_process")

        logging_integration.stop()
