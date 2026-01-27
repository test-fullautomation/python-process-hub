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
# File: 09_logging_integration.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Example demonstrating the logging server integration.
#   Shows how to integrate centralized logging (Fluentbit, Telegraf) with Process Hub.
#
# Usage:
#   python 09_logging_integration.py
#
# *******************************************************************************
"""
Logging Integration Example.

This example demonstrates how to:
1. Configure LoggingIntegration with different server types
2. Use MockLoggingServer for testing
3. Create a custom logging server
4. Integrate logging with ProcessHubServer

The logging integration supports:
- Fluentbit (if ta_framework is installed)
- Telegraf (if ta_framework is installed)
- Custom logging servers
- Mock server for testing
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

# Add ProcessHub to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from ProcessHub.logging.integration import (
    LoggingConfig,
    LoggingIntegration,
    LoggingServerBase,
    LoggingServerType,
    MockLoggingServer,
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def example_basic_logging_config():
    """
    Example 1: Basic LoggingConfig usage.

    LoggingConfig is a dataclass that holds logging settings for a process.
    It can convert settings to command-line arguments.
    """
    print("\n" + "=" * 60)
    print("Example 1: Basic LoggingConfig")
    print("=" * 60)

    # Create a logging config
    config = LoggingConfig(
        enabled=True,
        config_dir="/path/to/logging/config",
        host="localhost",
        port=24224,
        extra_args={"log_level": "debug"},
    )

    # Convert to command line arguments
    args = config.to_command_args(taf_path="/opt/taf")
    print("Command line arguments:")
    for arg in args:
        print(f"  {arg}")

    # Convert to dict for process config
    config_dict = config.to_dict()
    print("\nAs dict:")
    for key, value in config_dict.items():
        print(f"  {key}: {value}")


def example_mock_logging_server():
    """
    Example 2: Using MockLoggingServer for testing.

    MockLoggingServer simulates port allocation without starting real services.
    Useful for unit tests and local development.
    """
    print("\n" + "=" * 60)
    print("Example 2: MockLoggingServer")
    print("=" * 60)

    # Create a mock logging server
    mock_server = MockLoggingServer(
        uuid=12345,
        base_port=24000,
        hot_dir="/tmp/logging",
    )

    print(f"Hot config dir: {mock_server.hot_cfg_dir}")
    print(f"Hot lock config path: {mock_server.hot_lock_cfg_path}")

    # Allocate ports for processes
    host, ports = mock_server.allocate(3)
    print(f"\nAllocated 3 ports on {host}: {ports}")

    # Allocate more ports
    host, more_ports = mock_server.allocate(2)
    print(f"Allocated 2 more ports on {host}: {more_ports}")

    # Deallocate
    mock_server.deallocate()
    print("\nDeallocated all ports")


def example_logging_integration():
    """
    Example 3: Using LoggingIntegration.

    LoggingIntegration manages the lifecycle of a logging server
    and provides methods to get logging configuration for processes.
    """
    print("\n" + "=" * 60)
    print("Example 3: LoggingIntegration")
    print("=" * 60)

    # Create temporary directories for the example
    with tempfile.TemporaryDirectory() as temp_dir:
        paths = {
            "src_dir": os.path.join(temp_dir, "src"),
            "hot_dir": os.path.join(temp_dir, "hot"),
            "influx_dir": os.path.join(temp_dir, "influx"),
            "ctrl_dir": os.path.join(temp_dir, "ctrl"),
        }

        # Create directories
        for path in paths.values():
            os.makedirs(path, exist_ok=True)

        # Initialize logging integration
        # Using FLUENTBIT type will fall back to MockLoggingServer
        # if ta_framework is not installed
        logging_integration = LoggingIntegration(
            server_type=LoggingServerType.FLUENTBIT,
            paths=paths,
            taf_path="/opt/taf",
        )

        # Start the logging server
        logging_integration.start()
        print(f"Logging server started: {logging_integration.is_started}")
        print(f"Config dir: {logging_integration.config_dir}")

        # Define process configurations
        process_configs = {
            "system_manager": {
                "script": "python",
                "args": ["-c", "print('system_manager')"],
                "central_log": True,  # Enable central logging for this process
            },
            "edge_compute": {
                "script": "python",
                "args": ["-c", "print('edge_compute')"],
                "central_log": False,  # Disable central logging
            },
            "data_processor": {
                "script": "python",
                "args": ["-c", "print('data_processor')"],
                "central_log": True,
            },
        }

        # Get logging config for each process
        print("\nProcess logging configurations:")
        for name, config in process_configs.items():
            log_config = logging_integration.get_process_logging_config(name, config)
            print(f"\n  {name}:")
            print(f"    enabled: {log_config.enabled}")
            if log_config.enabled:
                print(f"    host: {log_config.host}")
                print(f"    port: {log_config.port}")
                print(f"    config_dir: {log_config.config_dir}")

        # Enhance process config with logging settings
        print("\nEnhanced process config for system_manager:")
        enhanced = logging_integration.enhance_process_config(
            "system_manager",
            process_configs["system_manager"],
        )
        for key, value in enhanced.items():
            print(f"  {key}: {value}")

        # Stop the logging server
        logging_integration.stop()
        print("\nLogging server stopped")


def example_custom_logging_server():
    """
    Example 4: Creating a custom logging server.

    You can create your own logging server by extending LoggingServerBase
    or implementing LoggingServerProtocol.
    """
    print("\n" + "=" * 60)
    print("Example 4: Custom Logging Server")
    print("=" * 60)

    class MyCustomLoggingServer(LoggingServerBase):
        """Custom logging server implementation."""

        def __init__(self, uuid: int, **kwargs):
            super().__init__(
                uuid=uuid,
                src_dir=kwargs.get("src_dir", ""),
                hot_dir=kwargs.get("hot_dir", ""),
                influx_dir=kwargs.get("influx_dir", ""),
                ctrl_dir=kwargs.get("ctrl_dir", ""),
            )
            self._hot_cfg_dir = os.path.join(self.hot_dir, f"custom_{uuid}")
            self._hot_lock_cfg_path = os.path.join(self._hot_cfg_dir, "custom.lock")
            self._port_counter = 30000

        def allocate(self, count: int) -> tuple[str, list[int]]:
            """Allocate ports using custom logic."""
            ports = []
            for _ in range(count):
                # Custom port allocation logic
                ports.append(self._port_counter)
                self._port_counter += 1
                self._allocated_ports.append(ports[-1])

            logger.info("Custom server allocated ports: %s", ports)
            return "custom-host.local", ports

        def deallocate(self) -> None:
            """Custom cleanup logic."""
            logger.info("Custom server deallocating %d ports", len(self._allocated_ports))
            self._allocated_ports.clear()

    # Factory function for custom server
    def custom_server_factory(uuid: int, paths: dict) -> MyCustomLoggingServer:
        return MyCustomLoggingServer(uuid=uuid, **paths)

    # Create temporary directories
    with tempfile.TemporaryDirectory() as temp_dir:
        paths = {
            "src_dir": os.path.join(temp_dir, "src"),
            "hot_dir": os.path.join(temp_dir, "hot"),
            "influx_dir": os.path.join(temp_dir, "influx"),
            "ctrl_dir": os.path.join(temp_dir, "ctrl"),
        }

        for path in paths.values():
            os.makedirs(path, exist_ok=True)

        # Use custom logging server
        logging_integration = LoggingIntegration(
            server_type=LoggingServerType.CUSTOM,
            paths=paths,
            server_factory=custom_server_factory,
        )

        logging_integration.start()
        print(f"Custom server started: {logging_integration.is_started}")

        # Allocate some ports
        process_config = {"central_log": True}
        log_config = logging_integration.get_process_logging_config(
            "my_process", process_config
        )
        print(f"\nAllocated for my_process:")
        print(f"  host: {log_config.host}")
        print(f"  port: {log_config.port}")

        logging_integration.stop()
        print("\nCustom server stopped")


def example_integration_with_server():
    """
    Example 5: Integrating logging with ProcessHubServer.

    Shows how to use LoggingAwareExecutor to automatically add
    logging configuration when starting processes.
    """
    print("\n" + "=" * 60)
    print("Example 5: Integration with ProcessHubServer")
    print("=" * 60)

    from ProcessHub.logging.integration import LoggingAwareExecutor
    from ProcessHub.process import MockExecutor

    # Create temporary directories
    with tempfile.TemporaryDirectory() as temp_dir:
        paths = {
            "src_dir": os.path.join(temp_dir, "src"),
            "hot_dir": os.path.join(temp_dir, "hot"),
            "influx_dir": os.path.join(temp_dir, "influx"),
            "ctrl_dir": os.path.join(temp_dir, "ctrl"),
        }

        for path in paths.values():
            os.makedirs(path, exist_ok=True)

        # Process configurations
        process_configs = {
            "system_manager": {
                "script": "python",
                "args": ["-c", "import time; time.sleep(3600)"],
                "central_log": True,
            },
            "worker": {
                "script": "python",
                "args": ["-c", "import time; time.sleep(3600)"],
                "central_log": False,
            },
        }

        # Initialize logging integration
        logging_integration = LoggingIntegration(
            server_type=LoggingServerType.FLUENTBIT,
            paths=paths,
            taf_path="/opt/taf",
        )
        logging_integration.start()

        # Create base executor
        base_executor = MockExecutor(process_configs)

        # Wrap with logging-aware executor
        logging_executor = LoggingAwareExecutor(
            executor=base_executor,
            logging_integration=logging_integration,
            process_configs=process_configs,
        )

        # Now when starting a process, logging config is automatically added
        print("Starting system_manager with logging executor...")
        success, msg, pid = logging_executor.start("system_manager", {})
        print(f"  success: {success}")
        print(f"  message: {msg}")
        print(f"  pid: {pid}")

        print("\nStarting worker with logging executor...")
        success, msg, pid = logging_executor.start("worker", {})
        print(f"  success: {success}")
        print(f"  message: {msg}")
        print(f"  pid: {pid}")

        # Stop processes
        logging_executor.stop("system_manager")
        logging_executor.stop("worker")

        # Cleanup
        logging_integration.stop()
        print("\nLogging integration stopped")


def main():
    """Run all examples."""
    print("=" * 60)
    print("Process Hub Logging Integration Examples")
    print("=" * 60)

    example_basic_logging_config()
    example_mock_logging_server()
    example_logging_integration()
    example_custom_logging_server()
    example_integration_with_server()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
