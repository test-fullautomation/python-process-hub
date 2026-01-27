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
# File: integration.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Logging server integration for process hub.
#   Provides integration with centralized logging servers (Fluentbit, Telegraf).
#   Mirrors functionality of ProcessControl.init_logging_server from ta-framework.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Logging server integration.

This module provides integration with centralized logging servers,
mirroring the functionality of ProcessControl.init_logging_server
from the original ta-framework implementation.

The design is pluggable:

- Define a protocol for logging servers

- Support Fluentbit, Telegraf, or custom implementations

- Integrate with ProcessHubServer via composition
"""

from __future__ import annotations

import logging
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Protocol, Type

logger = logging.getLogger(__name__)


# ============================================================================
# Types
# ============================================================================


class LoggingServerType(Enum):
    """
Supported logging server types.
    """

    FLUENTBIT = "fluentbit"
    TELEGRAF = "telegraf"
    CUSTOM = "custom"


@dataclass
class LoggingConfig:
    """
Logging configuration for a process.

This is passed to the process executor to add logging arguments.
    """

    enabled: bool = False
    config_dir: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    extra_args: dict[str, Any] = field(default_factory=dict)

    def to_command_args(self, taf_path: Optional[str] = None) -> list[str]:
        """
Convert to command line arguments.

Matches the original format:

    --variable TAF_PATH:{taf_path}
    
    --variable central_logging_conf:{config_dir}
    
    --variable central_logging_host:{host}
    
    --variable central_logging_port:{port}
        """
        if not self.enabled:
            return []

        args = []
        if taf_path:
            args.append(f"--variable TAF_PATH:{taf_path}")
        if self.config_dir:
            args.append(f"--variable central_logging_conf:{self.config_dir}")
        if self.host:
            args.append(f"--variable central_logging_host:{self.host}")
        if self.port:
            args.append(f"--variable central_logging_port:{self.port}")

        for key, value in self.extra_args.items():
            args.append(f"--variable {key}:{value}")

        return args

    def to_dict(self) -> dict:
        """
Convert to dict for process config.
        """
        return {
            "central_log": self.enabled,
            "logging_config_dir": self.config_dir,
            "logging_host": self.host,
            "logging_port": self.port,
            **self.extra_args,
        }


# ============================================================================
# Logging Server Protocol
# ============================================================================


class LoggingServerProtocol(Protocol):
    """
Protocol for logging server implementations.

Any logging server (Fluentbit, Telegraf, custom) must implement
these methods to work with LoggingIntegration.
    """

    @property
    def hot_cfg_dir(self) -> str:
        """
Get the hot configuration directory.
        """
        ...

    @property
    def hot_lock_cfg_path(self) -> str:
        """
Get the hot lock configuration file path.
        """
        ...

    def allocate(self, count: int) -> tuple[str, list[int]]:
        """
Allocate logging ports.

Args:

    count: Number of ports to allocate

Returns:

    Tuple of (host, list of ports)
        """
        ...

    def deallocate(self) -> None:
        """
Deallocate/cleanup the logging server.
        """
        ...


class LoggingServerBase(ABC):
    """
Abstract base class for logging servers.

Provides common functionality and defines the interface.
Subclasses must implement allocate() and deallocate().
    """

    def __init__(
        self,
        uuid: int,
        src_dir: str,
        hot_dir: str,
        influx_dir: str,
        ctrl_dir: str,
    ):
        """
Initialize logging server.

Args:

    uuid: Unique identifier (typically process ID)
    
    src_dir: Source directory for logging configs
    
    hot_dir: Hot reload directory for configs
    
    influx_dir: InfluxDB directory
    
    ctrl_dir: Control directory
        """
        self.uuid = uuid
        self.src_dir = src_dir
        self.hot_dir = hot_dir
        self.influx_dir = influx_dir
        self.ctrl_dir = ctrl_dir

        # These should be set by subclasses
        self._hot_cfg_dir: Optional[str] = None
        self._hot_lock_cfg_path: Optional[str] = None
        self._host: str = "localhost"
        self._allocated_ports: list[int] = []

    @property
    def hot_cfg_dir(self) -> str:
        return self._hot_cfg_dir or ""

    @property
    def hot_lock_cfg_path(self) -> str:
        return self._hot_lock_cfg_path or ""

    @abstractmethod
    def allocate(self, count: int) -> tuple[str, list[int]]:
        """
Allocate logging ports.
        """
        pass

    @abstractmethod
    def deallocate(self) -> None:
        """
Deallocate/cleanup.
        """
        pass


# ============================================================================
# Mock Logging Server (for testing)
# ============================================================================


class MockLoggingServer(LoggingServerBase):
    """
Mock logging server for testing.

Simulates port allocation without actually starting any services.
    """

    def __init__(self, uuid: int = 0, base_port: int = 24000, **kwargs):
        super().__init__(
            uuid=uuid,
            src_dir=kwargs.get("src_dir", ""),
            hot_dir=kwargs.get("hot_dir", ""),
            influx_dir=kwargs.get("influx_dir", ""),
            ctrl_dir=kwargs.get("ctrl_dir", ""),
        )
        self._base_port = base_port
        self._next_port = base_port
        self._hot_cfg_dir = os.path.join(self.hot_dir, f"mock_{uuid}")
        self._hot_lock_cfg_path = os.path.join(self._hot_cfg_dir, "lock.cfg")

    def allocate(self, count: int) -> tuple[str, list[int]]:
        """
Allocate mock ports.
        """
        ports = list(range(self._next_port, self._next_port + count))
        self._next_port += count
        self._allocated_ports.extend(ports)
        logger.debug("Mock allocated ports: %s", ports)
        return self._host, ports

    def deallocate(self) -> None:
        """
Deallocate mock resources.
        """
        self._allocated_ports.clear()
        self._next_port = self._base_port
        logger.debug("Mock deallocated all ports")


# ============================================================================
# Logging Integration
# ============================================================================


class LoggingIntegration:
    """
Logging server integration manager.

This class manages the lifecycle of a logging server and provides
methods to get logging configuration for processes.

Mirrors the functionality of ProcessControl.init_logging_server()
from the original implementation.

Usage:

    # Initialize
    
    logging = LoggingIntegration(
    
        server_type=LoggingServerType.FLUENTBIT,
        
        paths={"src_dir": ..., "hot_dir": ..., ...}
        
    )
    
    logging.start()

    # Get config for a process
    
    config = logging.get_process_logging_config("my_process")

    # Use in process start
    
    if config.enabled:
    
        extra_args = config.to_command_args(taf_path="/path/to/taf")

    # Cleanup
    
    logging.stop()

With custom server factory:

    def my_factory(uuid, paths):
    
        return MyCustomLoggingServer(uuid=uuid, **paths)

    logging = LoggingIntegration(
    
        server_type=LoggingServerType.CUSTOM,
        
        server_factory=my_factory,
        
    )
    """

    def __init__(
        self,
        server_type: LoggingServerType = LoggingServerType.FLUENTBIT,
        paths: Optional[dict[str, str]] = None,
        server_factory: Optional[Callable[[int, dict], LoggingServerProtocol]] = None,
        uuid: Optional[int] = None,
        taf_path: Optional[str] = None,
    ):
        """
Initialize logging integration.

Args:

    server_type: Type of logging server to use
    
    paths: Dictionary of paths:
    
        - src_dir: Source directory for logging configs
        
        - hot_dir: Hot reload directory
        
        - influx_dir: InfluxDB directory
        
        - ctrl_dir: Control directory
        
    server_factory: Custom factory function for CUSTOM type
    
    uuid: Unique identifier (defaults to current PID)
    
    taf_path: TAF_PATH for command line arguments
        """
        self._server_type = server_type
        self._paths = paths or {}
        self._server_factory = server_factory
        self._uuid = uuid or os.getpid()
        self._taf_path = taf_path or os.environ.get("TAF_PATH", "")

        self._server: Optional[LoggingServerProtocol] = None
        self._config_dir: Optional[str] = None
        self._started = False

    @property
    def server(self) -> Optional[LoggingServerProtocol]:
        """
Get the logging server instance.
        """
        return self._server

    @property
    def config_dir(self) -> Optional[str]:
        """
Get the logging configuration directory.
        """
        return self._config_dir

    @property
    def is_started(self) -> bool:
        """
Check if logging server is started.
        """
        return self._started

    def start(self) -> None:
        """
Start the logging server.

Equivalent to ProcessControl.init_logging_server().
        """
        if self._started:
            logger.warning("Logging server already started")
            return

        logger.info("Starting logging server (type=%s)...", self._server_type.value)

        # Ensure control directory exists
        ctrl_dir = self._paths.get("ctrl_dir", "")
        if ctrl_dir:
            os.makedirs(ctrl_dir, exist_ok=True)

        # Create the logging server
        self._server = self._create_server()

        if self._server:
            self._config_dir = os.path.basename(self._paths.get("hot_dir", ""))
            self._started = True

            logger.info("Logging configuration directory: %s", self._config_dir)
            logger.info("Logging hot_cfg_dir: %s", self._server.hot_cfg_dir)
            logger.info("Logging hot_lock_cfg_path: %s", self._server.hot_lock_cfg_path)

    def stop(self) -> None:
        """
Stop the logging server and clean up.

Equivalent to ProcessControl.__del__() cleanup.
        """
        if not self._started:
            return

        logger.info("Stopping logging server...")

        if self._server:
            try:
                self._server.deallocate()
            except Exception as e:
                logger.warning("Error deallocating logging server: %s", e)

            self._clean_up_workspace()

        self._server = None
        self._started = False

    def get_process_logging_config(
        self,
        process_name: str,
        process_config: Optional[dict] = None,
    ) -> LoggingConfig:
        """
Get logging configuration for a process.

Args:

    process_name: Name of the process
    
    process_config: Process configuration dict (to check central_log flag)

Returns:

    LoggingConfig with allocated port if central_log is enabled
        """
        # Check if central logging is enabled for this process
        central_log = False
        if process_config:
            central_log = process_config.get("central_log", False)

        if not central_log or not self._server:
            return LoggingConfig(enabled=False)

        try:
            host, ports = self._server.allocate(1)
            return LoggingConfig(
                enabled=True,
                config_dir=self._config_dir,
                host=host,
                port=ports[0] if ports else None,
            )
        except Exception as e:
            logger.error("Failed to allocate logging port for %s: %s", process_name, e)
            return LoggingConfig(enabled=False)

    def enhance_process_config(
        self,
        process_name: str,
        process_config: dict,
    ) -> dict:
        """
Enhance process config with logging settings.

Args:

    process_name: Name of the process
    
    process_config: Original process configuration

Returns:

    Enhanced config with logging settings added
        """
        log_config = self.get_process_logging_config(process_name, process_config)

        if not log_config.enabled:
            return process_config

        # Create enhanced config
        enhanced = dict(process_config)
        enhanced.update(log_config.to_dict())
        enhanced["taf_path"] = self._taf_path

        return enhanced

    def _create_server(self) -> Optional[LoggingServerProtocol]:
        """
Create the logging server based on type.
        """
        if self._server_type == LoggingServerType.CUSTOM:
            if self._server_factory:
                return self._server_factory(self._uuid, self._paths)
            else:
                raise ValueError("Custom server type requires server_factory")

        elif self._server_type == LoggingServerType.FLUENTBIT:
            return self._create_fluentbit_server()

        elif self._server_type == LoggingServerType.TELEGRAF:
            return self._create_telegraf_server()

        else:
            logger.warning("Unknown server type: %s, using mock", self._server_type)
            return MockLoggingServer(uuid=self._uuid, **self._paths)

    def _create_fluentbit_server(self) -> Optional[LoggingServerProtocol]:
        """
Create Fluentbit server (if available).
        """
        try:
            # Try to import from ta_framework
            from ta_framework.project.logging.fluentbit import FluentbitServer

            return FluentbitServer(
                uuid=self._uuid,
                src_dir=self._paths.get("src_dir", ""),
                hot_dir=self._paths.get("hot_dir", ""),
                influx_dir=self._paths.get("influx_dir", ""),
                ctrl_dir=self._paths.get("ctrl_dir", ""),
            )
        except ImportError:
            logger.warning(
                "FluentbitServer not available, using mock. "
                "Install ta_framework or provide custom server_factory."
            )
            return MockLoggingServer(uuid=self._uuid, **self._paths)

    def _create_telegraf_server(self) -> Optional[LoggingServerProtocol]:
        """
Create Telegraf server (if available).
        """
        try:
            # Try to import from ta_framework
            from ta_framework.project.logging.telegraf import TelegrafServer

            return TelegrafServer(
                uuid=self._uuid,
                src_dir=self._paths.get("src_dir", ""),
                hot_dir=self._paths.get("hot_dir", ""),
                influx_dir=self._paths.get("influx_dir", ""),
                ctrl_dir=self._paths.get("ctrl_dir", ""),
            )
        except ImportError:
            logger.warning(
                "TelegrafServer not available, using mock. "
                "Install ta_framework or provide custom server_factory."
            )
            return MockLoggingServer(uuid=self._uuid, **self._paths)

    def _clean_up_workspace(self) -> None:
        """
Clean up workspace.

Equivalent to ProcessControl.clean_up_workspace().
        """
        if not self._server:
            return

        try:
            # Clean up hot config directory
            hot_cfg_dir = self._server.hot_cfg_dir
            if hot_cfg_dir and os.path.exists(hot_cfg_dir) and os.path.isdir(hot_cfg_dir):
                shutil.rmtree(hot_cfg_dir)
                logger.debug("Removed hot config dir: %s", hot_cfg_dir)

            # Clean up lock file
            hot_lock_cfg_path = self._server.hot_lock_cfg_path
            if hot_lock_cfg_path and os.path.exists(hot_lock_cfg_path):
                os.remove(hot_lock_cfg_path)
                logger.debug("Removed lock file: %s", hot_lock_cfg_path)

            # Clean up stats directory
            stats_dir = os.path.expandvars("${TAF_TEST_PATH}/stats")
            if os.path.exists(stats_dir) and os.path.isdir(stats_dir):
                for file in os.listdir(stats_dir):
                    if str(self._uuid) not in file:
                        continue
                    file_path = os.path.join(stats_dir, file)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        logger.warning("Failed to remove %s: %s", file_path, e)

        except Exception as e:
            logger.warning("Error during workspace cleanup: %s", e)


# ============================================================================
# Integration with ProcessHubServer
# ============================================================================


class LoggingAwareExecutor:
    """
Executor wrapper that adds logging configuration to process starts.

Wraps an existing executor and enhances process configs with logging.
    """

    def __init__(
        self,
        executor: Any,
        logging_integration: LoggingIntegration,
        process_configs: dict[str, dict],
    ):
        """
Initialize logging-aware executor.

Args:

    executor: Underlying process executor
    
    logging_integration: LoggingIntegration instance
    
    process_configs: Process configuration dict
        """
        self._executor = executor
        self._logging = logging_integration
        self._configs = process_configs

    def start(self, name: str, config: dict) -> tuple[bool, str, Optional[int]]:
        """
Start process with logging config.
        """
        # Get base config
        base_config = self._configs.get(name, {})
        base_config.update(config)

        # Enhance with logging
        enhanced_config = self._logging.enhance_process_config(name, base_config)

        return self._executor.start(name, enhanced_config)

    def stop(self, name: str, force: bool = False) -> bool:
        """
Stop process.
        """
        return self._executor.stop(name, force)

    def is_running(self, name: str) -> bool:
        """
Check if process is running.
        """
        return self._executor.is_running(name)
