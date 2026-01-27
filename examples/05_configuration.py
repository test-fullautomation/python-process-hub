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
# File: 05_configuration.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Example demonstrating configuration loading and validation.
#   Shows how to load process configurations from JSON files,
#   use environment variable expansion, and validate schemas.
#
# Usage:
#   python 05_configuration.py
#
# *******************************************************************************
"""
Configuration Loading Example.

This example demonstrates:
1. Loading process configurations from JSON files
2. Environment variable expansion in configs
3. Using configuration schemas for validation
4. Creating server/client from configuration
"""

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

# Add ProcessHub to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from ProcessHub.config import (
    JsonConfigLoader,
    ProcessConfigLoader,
    ProcessConfig,
    ServerConfig,
    ClientConfig,
    TransportConfig,
    expand_vars,
    fully_expand_vars,
    validate_process_config,
    validate_server_config,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def demo_environment_expansion():
    """Demonstrate environment variable expansion."""
    logger.info("=" * 60)
    logger.info("Environment Variable Expansion")
    logger.info("=" * 60)

    # Set some test environment variables
    os.environ["MY_PROJECT_PATH"] = "/home/user/project"
    os.environ["MY_PYTHON"] = "python3.10"

    # Different expansion formats
    examples = [
        "${MY_PROJECT_PATH}/scripts/main.py",  # Bash style
        "$MY_PROJECT_PATH/scripts/main.py",     # Simple bash style
        "%MY_PROJECT_PATH%\\scripts\\main.py",  # Windows style
    ]

    for example in examples:
        expanded = expand_vars(example)
        logger.info("  %s", example)
        logger.info("    -> %s", expanded)

    # Nested expansion
    os.environ["BASE_PATH"] = "${MY_PROJECT_PATH}/base"
    nested = "${BASE_PATH}/config.json"
    expanded = fully_expand_vars(nested)
    logger.info("\nNested expansion:")
    logger.info("  %s", nested)
    logger.info("    -> %s", expanded)
    logger.info("")


def demo_json_config_loader():
    """Demonstrate JSON configuration loading."""
    logger.info("=" * 60)
    logger.info("JSON Configuration Loading")
    logger.info("=" * 60)

    # Create a sample config file
    sample_config = {
        "system_manager": {
            "process_name": "SystemManager",
            "script": "${MY_PROJECT_PATH}/scripts/system_manager.py",
            "args": ["--config", "${MY_PROJECT_PATH}/config/system.json"],
            "wait_time": 2.0,
            "central_log": True,
        },
        "data_processor": {
            "process_name": "DataProcessor",
            "script": "${MY_PROJECT_PATH}/scripts/data_processor.py",
            "args": ["--workers", "4"],
            "wait_time": 1.5,
            "dependencies": ["system_manager"],
        },
        "web_server": {
            "process_name": "WebServer",
            "script": "${MY_PROJECT_PATH}/scripts/web_server.py",
            "args": ["--port", "2507"],
            "wait_time": 3.0,
            "dependencies": ["system_manager", "data_processor"],
        },
    }

    # Write to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(sample_config, f, indent=2)
        config_path = f.name

    try:
        # Load with environment expansion
        loader = JsonConfigLoader(expand_env=True)
        config = loader.load(config_path)

        logger.info("Loaded configuration:")
        for name, proc_config in config.items():
            logger.info("  Process: %s", name)
            logger.info("    Script: %s", proc_config["script"])
            logger.info("    Args: %s", proc_config["args"])
            logger.info("")

    finally:
        os.unlink(config_path)


def demo_process_config_loader():
    """Demonstrate ProcessConfigLoader for high-level loading."""
    logger.info("=" * 60)
    logger.info("Process Config Loader")
    logger.info("=" * 60)

    # Sample configuration
    config = {
        "worker_1": {
            "process_name": "Worker1",
            "script": "/path/to/worker.py",
            "args": ["--id", "1"],
            "wait_time": 1.0,
        },
        "worker_2": {
            "process_name": "Worker2",
            "script": "/path/to/worker.py",
            "args": ["--id", "2"],
            "wait_time": 1.0,
        },
    }

    # Use ProcessConfigLoader
    loader = ProcessConfigLoader()
    loader.load_dict(config)

    logger.info("Loaded %d processes:", len(loader.get_process_names()))
    for name in loader.get_process_names():
        logger.info("  - %s", name)

    # Get executor config for a process
    exec_config = loader.get_executor_config("worker_1")
    logger.info("\nExecutor config for 'worker_1':")
    for key, value in exec_config.items():
        logger.info("  %s: %s", key, value)
    logger.info("")


def demo_typed_schemas():
    """Demonstrate typed configuration schemas."""
    logger.info("=" * 60)
    logger.info("Typed Configuration Schemas")
    logger.info("=" * 60)

    # Create ProcessConfig using dataclass
    process = ProcessConfig(
        process_name="MyProcess",
        script="/path/to/script.py",
        args=["--verbose"],
        wait_time=2.0,
        central_log=True,
        dependencies=["other_process"],
    )

    logger.info("ProcessConfig:")
    logger.info("  Name: %s", process.process_name)
    logger.info("  Script: %s", process.script)
    logger.info("  Args: %s", process.args)
    logger.info("  Wait time: %s", process.wait_time)
    logger.info("  Central log: %s", process.central_log)
    logger.info("  Dependencies: %s", process.dependencies)

    # Convert to executor config
    exec_config = process.to_executor_config()
    logger.info("\nAs executor config: %s", exec_config)

    # Create TransportConfig
    transport = TransportConfig(
        type="zmq",
        start_broker=True,
        xpub_port=5555,
        xsub_port=5556,
    )
    logger.info("\nTransportConfig:")
    logger.info("  Type: %s", transport.type)
    logger.info("  Start broker: %s", transport.start_broker)
    logger.info("  XPUB port: %s", transport.xpub_port)
    logger.info("  XSUB port: %s", transport.xsub_port)

    # Create ServerConfig
    server_config = ServerConfig(
        transport=transport,
        refresh_interval=0.5,
        restart_timeout=300.0,
    )
    logger.info("\nServerConfig:")
    logger.info("  Refresh interval: %s", server_config.refresh_interval)
    logger.info("  Restart timeout: %s", server_config.restart_timeout)
    logger.info("")


def demo_validation():
    """Demonstrate configuration validation."""
    logger.info("=" * 60)
    logger.info("Configuration Validation")
    logger.info("=" * 60)

    # Valid config
    valid_config = {
        "process_name": "TestProcess",
        "script": "/path/to/script.py",
        "args": [],
    }

    try:
        process = validate_process_config(valid_config)
        logger.info("Valid config created: %s", process.process_name)
    except ValueError as e:
        logger.error("Validation failed: %s", e)

    # Invalid config (missing required field)
    invalid_config = {
        "process_name": "TestProcess",
        # Missing 'script' field
    }

    try:
        process = validate_process_config(invalid_config)
        logger.info("Config created: %s", process.process_name)
    except ValueError as e:
        logger.info("Validation correctly failed: %s", e)

    # Server config from dict
    server_dict = {
        "transport": {
            "type": "zmq",
            "xpub_port": 5555,
            "xsub_port": 5556,
        },
        "refresh_interval": 1.0,
        "restart_timeout": 60.0,
    }

    server_config = validate_server_config(server_dict)
    logger.info("\nServer config validated:")
    logger.info("  Transport type: %s", server_config.transport.type)
    logger.info("  Refresh interval: %s", server_config.refresh_interval)
    logger.info("")


def demo_full_server_config():
    """Demonstrate complete server configuration."""
    logger.info("=" * 60)
    logger.info("Complete Server Configuration Example")
    logger.info("=" * 60)

    # This shows a complete configuration that could be loaded from JSON
    full_config = {
        "server": {
            "transport": {
                "type": "zmq",
                "start_broker": True,
                "xpub_port": 5555,
                "xsub_port": 5556,
                "bind_address": "tcp://*",
            },
            "refresh_interval": 0.5,
            "restart_timeout": 300.0,
            "logging": {
                "type": "fluentbit",
                "src_dir": "/opt/fluentbit/config",
                "hot_dir": "/var/log/fluentbit",
            },
        },
        "processes": {
            "system_manager": {
                "process_name": "SystemManager",
                "script": "/app/scripts/system_manager.py",
                "args": ["--config", "/app/config/system.json"],
                "wait_time": 2.0,
                "central_log": True,
            },
            "edge_compute": {
                "process_name": "EdgeCompute",
                "script": "/app/scripts/edge_compute.py",
                "args": [],
                "wait_time": 3.0,
                "dependencies": ["system_manager"],
            },
        },
    }

    logger.info("Full configuration structure:")
    logger.info(json.dumps(full_config, indent=2))
    logger.info("")

    # Parse it
    server_config = ServerConfig.from_dict(full_config["server"])
    logger.info("Parsed server config:")
    logger.info("  Transport: %s on ports %d/%d",
                server_config.transport.type,
                server_config.transport.xpub_port,
                server_config.transport.xsub_port)
    logger.info("  Refresh: %ss, Timeout: %ss",
                server_config.refresh_interval,
                server_config.restart_timeout)
    logger.info("")


def main():
    """Run all configuration examples."""
    demo_environment_expansion()
    demo_json_config_loader()
    demo_process_config_loader()
    demo_typed_schemas()
    demo_validation()
    demo_full_server_config()

    logger.info("=" * 60)
    logger.info("All configuration examples complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
