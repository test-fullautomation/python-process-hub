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
# File: __init__.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Configuration loading and schemas package.
#   Provides utilities for loading process configuration from various sources
#   and typed schemas for validation.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Configuration loading and schemas.

Provides utilities for loading process configuration from various sources
and typed schemas for validation.

Loader classes:

- JsonConfigLoader: Load from JSON files with env var expansion

- JsonPreprocessorLoader: Compatibility with ta-framework's JsonPreprocessor

- ProcessConfigLoader: High-level process configuration loader

Schema classes:

- ProcessConfig: Single process configuration

- ProcessesConfig: Collection of processes

- ServerConfig: Server configuration

- ClientConfig: Client configuration

- TransportConfig: Transport configuration

- LoggingServerConfig: Logging server configuration
"""

from .loader import (
    expand_vars,
    fully_expand_vars,
    expand_and_quote,
    ConfigLoader,
    JsonConfigLoader,
    JsonPreprocessorLoader,
    ProcessConfigLoader,
    compute_restart_sequence,
)

from .schemas import (
    ProcessConfig,
    ProcessesConfig,
    ServerConfig,
    ClientConfig,
    TransportConfig,
    LoggingServerConfig,
    validate_process_config,
    validate_server_config,
    validate_client_config,
)

__all__ = [
    # Loader utilities
    "expand_vars",
    "fully_expand_vars",
    "expand_and_quote",
    # Loaders
    "ConfigLoader",
    "JsonConfigLoader",
    "JsonPreprocessorLoader",
    "ProcessConfigLoader",
    "compute_restart_sequence",
    # Schemas
    "ProcessConfig",
    "ProcessesConfig",
    "ServerConfig",
    "ClientConfig",
    "TransportConfig",
    "LoggingServerConfig",
    # Validation
    "validate_process_config",
    "validate_server_config",
    "validate_client_config",
]
