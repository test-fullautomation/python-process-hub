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
# File: schemas.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Configuration schemas using dataclasses.
#   Defines typed configuration schemas for process definitions,
#   server configuration, and client configuration.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Configuration schemas using dataclasses.

This module defines typed configuration schemas for:

- Process definitions

- Server configuration

- Client configuration

These can optionally be used with Pydantic for validation
if pydantic is installed, otherwise they work as plain dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

# Try to use pydantic for validation
try:
    from pydantic.dataclasses import dataclass as pydantic_dataclass
    from pydantic import Field, validator

    HAS_PYDANTIC = True
    # Use pydantic dataclass for validation
    config_dataclass = pydantic_dataclass
except ImportError:
    HAS_PYDANTIC = False
    # Fall back to standard dataclass
    config_dataclass = dataclass
    Field = field  # type: ignore


# ============================================================================
# Process Configuration
# ============================================================================


@config_dataclass
class ProcessConfig:
    """
Configuration for a single process.

Attributes:

    process_name: Display name / window title

    script: Path to script or executable

    args: Command line arguments

    wait_time: Time to wait after starting (seconds)

    exec_type: Execution type ("python" or "external")

    central_log: Whether to use central logging

    dependencies: List of dependent process names

    env: Additional environment variables

    working_dir: Working directory for process

    enable: Whether the process is enabled for ProcessHub

    description: Brief description of what the process does

    mandatory: Whether the process is mandatory for testing

    warning_on_deselect: Warning message when deselecting the process
    """

    process_name: str
    script: str
    args: List[str] = field(default_factory=list)
    wait_time: float = 2.0
    exec_type: Literal["python", "external"] = "python"
    central_log: bool = False
    dependencies: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    working_dir: Optional[str] = None
    enable: bool = True
    description: str = ""
    mandatory: bool = False
    warning_on_deselect: str = ""

    def to_executor_config(self) -> dict:
        """
Convert to executor configuration dict.
        """
        return {
            "script": self.script,
            "args": self.args,
            "wait_time": self.wait_time,
            "process_name": self.process_name,
            "central_log": self.central_log,
            "env": self.env,
            "working_dir": self.working_dir,
            "enable": self.enable,
            "description": self.description,
            "mandatory": self.mandatory,
            "warning_on_deselect": self.warning_on_deselect,
        }


@config_dataclass
class ProcessesConfig:
    """
Collection of process configurations.

Attributes:

    processes: Dict of process name to configuration
    """

    processes: Dict[str, ProcessConfig] = field(default_factory=dict)

    def get(self, name: str) -> Optional[ProcessConfig]:
        """
Get process configuration by name.
        """
        return self.processes.get(name)

    def names(self) -> List[str]:
        """
Get all process names.
        """
        return list(self.processes.keys())

    @classmethod
    def from_dict(cls, data: Dict[str, dict]) -> "ProcessesConfig":
        """
Create from raw dict (e.g., loaded from JSON).
        """
        processes = {}
        for name, config in data.items():
            # Handle both "process_name" and using key as name
            if "process_name" not in config:
                config["process_name"] = name
            processes[name] = ProcessConfig(**config)
        return cls(processes=processes)


# ============================================================================
# Server Configuration
# ============================================================================


@config_dataclass
class TransportConfig:
    """
Transport configuration.

Attributes:

    type: Transport type ("zmq" or "inmemory")
    
    start_broker: Whether to start broker (ZMQ only)
    
    xpub_port: XPUB port for subscribers
    
    xsub_port: XSUB port for publishers
    
    bind_address: Address to bind to
    
    connect_address: Address to connect to
    """

    type: Literal["zmq", "inmemory"] = "zmq"
    start_broker: bool = True
    xpub_port: int = 5555
    xsub_port: int = 5556
    bind_address: str = "tcp://*"
    connect_address: str = "tcp://localhost"


@config_dataclass
class LoggingServerConfig:
    """
Logging server configuration.

Attributes:

    type: Server type ("fluentbit", "telegraf", or "mock")
    
    src_dir: Source directory for configs
    
    hot_dir: Hot reload directory
    
    influx_dir: InfluxDB directory
    
    ctrl_dir: Control directory
    """

    type: Literal["fluentbit", "telegraf", "mock"] = "fluentbit"
    src_dir: str = ""
    hot_dir: str = ""
    influx_dir: str = ""
    ctrl_dir: str = ""


@config_dataclass
class ServerConfig:
    """
Process Hub Server configuration.

Attributes:
    transport: Transport configuration
    
    logging: Logging server configuration
    
    refresh_interval: Main loop refresh interval (seconds)
    
    restart_timeout: Restart coordination timeout (seconds)
    
    process_config_path: Path to process configuration file
    """

    transport: TransportConfig = field(default_factory=TransportConfig)
    logging: Optional[LoggingServerConfig] = None
    refresh_interval: float = 0.5
    restart_timeout: float = 300.0
    process_config_path: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "ServerConfig":
        """
Create from raw dict.
        """
        transport = TransportConfig(**data.get("transport", {}))
        logging = None
        if "logging" in data:
            logging = LoggingServerConfig(**data["logging"])
        return cls(
            transport=transport,
            logging=logging,
            refresh_interval=data.get("refresh_interval", 0.5),
            restart_timeout=data.get("restart_timeout", 300.0),
            process_config_path=data.get("process_config_path"),
        )


# ============================================================================
# Client Configuration
# ============================================================================


@config_dataclass
class ClientConfig:
    """
Process Hub Client configuration.

Attributes:

    transport: Transport configuration
    
    panel_id: Panel identifier (auto-generated if None)
    
    default_timeout: Default request timeout (seconds)
    
    auto_reconnect: Whether to auto-reconnect on disconnect
    
    reconnect_interval: Time between reconnect attempts (seconds)
    """

    transport: TransportConfig = field(default_factory=TransportConfig)
    panel_id: Optional[str] = None
    default_timeout: float = 30.0
    auto_reconnect: bool = True
    reconnect_interval: float = 5.0

    @classmethod
    def from_dict(cls, data: dict) -> "ClientConfig":
        """
Create from raw dict.
        """
        transport_data = data.get("transport", {})
        transport_data["start_broker"] = False  # Client never starts broker
        transport = TransportConfig(**transport_data)
        return cls(
            transport=transport,
            panel_id=data.get("panel_id"),
            default_timeout=data.get("default_timeout", 30.0),
            auto_reconnect=data.get("auto_reconnect", True),
            reconnect_interval=data.get("reconnect_interval", 5.0),
        )


# ============================================================================
# Validation Helpers
# ============================================================================


def validate_process_config(config: dict) -> ProcessConfig:
    """
Validate and create ProcessConfig from dict.

**Arguments:**

* ``config``

  / *Condition*: required / *Type*: dict /

  Raw configuration dict.

**Returns:**

  / *Type*: ProcessConfig /

  Validated ProcessConfig.

**Raises:**

* ``ValueError``: If validation fails.
    """
    required_fields = ["process_name", "script"]
    for field_name in required_fields:
        if field_name not in config:
            raise ValueError(f"Missing required field: {field_name}")

    return ProcessConfig(**config)


def validate_server_config(config: dict) -> ServerConfig:
    """
Validate and create ServerConfig from dict.

**Arguments:**

* ``config``

  / *Condition*: required / *Type*: dict /

  Raw configuration dict.

**Returns:**

  / *Type*: ServerConfig /

  Validated ServerConfig.
    """
    return ServerConfig.from_dict(config)


def validate_client_config(config: dict) -> ClientConfig:
    """
Validate and create ClientConfig from dict.

**Arguments:**

* ``config``

  / *Condition*: required / *Type*: dict /

  Raw configuration dict.

**Returns:**

  / *Type*: ClientConfig /

  Validated ClientConfig.
    """
    return ClientConfig.from_dict(config)
