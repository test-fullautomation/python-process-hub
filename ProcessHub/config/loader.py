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
# File: loader.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Configuration loader for process hub.
#   Provides utilities for loading and processing process configuration
#   from various sources (JSON, JSONP, dict).
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Configuration loader.

This module provides utilities for loading and processing
process configuration from various sources (JSON, JSONP, dict).

Replaces the dependency on JsonPreprocessor.CJsonPreprocessor
with a flexible, pluggable loader system.
"""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Optional, Union

logger = logging.getLogger(__name__)


# ============================================================================
# Variable Expansion
# ============================================================================


def expand_vars(value: str, env: Optional[dict] = None) -> str:
    """
Expand environment variables in a string.

Supports formats:

- ${VAR} or $VAR - standard env var

- %VAR% - Windows style

**Arguments:**

* ``value``

  / *Condition*: required / *Type*: str /

  String to expand.

* ``env``

  / *Condition*: optional / *Type*: dict / *Default*: None /

  Environment dict (uses os.environ if None).

**Returns:**

/ *Type*: str /

Expanded string.
    """
    if not isinstance(value, str):
        return value

    env = env or os.environ

    # Expand ${VAR} format
    def replace_braces(match):
        var_name = match.group(1)
        return env.get(var_name, match.group(0))

    value = re.sub(r'\$\{([^}]+)\}', replace_braces, value)

    # Expand $VAR format (word boundary)
    def replace_dollar(match):
        var_name = match.group(1)
        return env.get(var_name, match.group(0))

    value = re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', replace_dollar, value)

    # Expand %VAR% format (Windows)
    def replace_percent(match):
        var_name = match.group(1)
        return env.get(var_name, match.group(0))

    value = re.sub(r'%([^%]+)%', replace_percent, value)

    return value


def fully_expand_vars(value: str, env: Optional[dict] = None) -> str:
    """
Fully expand nested environment variables.

Expands repeatedly until no more changes occur.
    """
    if not isinstance(value, str):
        return value

    prev = None
    current = value
    max_iterations = 10

    for _ in range(max_iterations):
        prev = current
        current = expand_vars(current, env)
        if current == prev:
            break

    return current


def expand_and_quote(value: str, env: Optional[dict] = None) -> str:
    """
Expand variables and quote if contains spaces.

**Arguments:**

* ``value``

  / *Condition*: required / *Type*: str /

  String to process.

* ``env``

  / *Condition*: optional / *Type*: dict / *Default*: None /

  Environment dict.

**Returns:**

/ *Type*: str /

Expanded and possibly quoted string.
    """
    expanded = fully_expand_vars(value, env)

    if " " in expanded and not (
        expanded.startswith('"') and expanded.endswith('"')
    ):
        expanded = f'"{expanded}"'

    return expanded


# ============================================================================
# Config Loader Interface
# ============================================================================


class ConfigLoader(ABC):
    """Abstract configuration loader."""

    @abstractmethod
    def load(self, source: Union[str, Path, dict]) -> dict:
        """
Load configuration from source.

**Arguments:**

* ``source``

  / *Condition*: required / *Type*: Union[str, Path, dict] /

  File path, URL, or dict.

**Returns:**

/ *Type*: dict /

Configuration dict.
        """
        pass


class JsonConfigLoader(ConfigLoader):
    """
JSON configuration loader.

Loads configuration from JSON files with optional
environment variable expansion.
    """

    def __init__(
        self,
        expand_env: bool = True,
        env: Optional[dict] = None,
    ):
        """
Initialize loader.

**Arguments:**

* ``expand_env``

  / *Condition*: optional / *Type*: bool / *Default*: True /

  Whether to expand environment variables.

* ``env``

  / *Condition*: optional / *Type*: dict / *Default*: None /

  Environment dict (uses os.environ if None).
        """
        self._expand_env = expand_env
        self._env = env

    def load(self, source: Union[str, Path, dict]) -> dict:
        """
Load configuration from JSON file or dict.
        """
        if isinstance(source, dict):
            config = source
        else:
            path = Path(source)
            if not path.exists():
                raise FileNotFoundError(f"Config file not found: {path}")

            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)

        if self._expand_env:
            config = self._expand_config(config)

        return config

    def _expand_config(self, config: Any) -> Any:
        """
Recursively expand environment variables in config.
        """
        if isinstance(config, dict):
            return {k: self._expand_config(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._expand_config(v) for v in config]
        elif isinstance(config, str):
            return fully_expand_vars(config, self._env)
        else:
            return config


class JsonPreprocessorLoader(ConfigLoader):
    """
JSON Preprocessor loader (compatibility with ta-framework).

Uses JsonPreprocessor.CJsonPreprocessor if available,
falls back to standard JSON loading.
    """

    def __init__(self):
        self._preprocessor = None
        try:
            from JsonPreprocessor.CJsonPreprocessor import CJsonPreprocessor
            self._preprocessor = CJsonPreprocessor()
        except ImportError:
            logger.warning(
                "JsonPreprocessor not available, using standard JSON loader"
            )

    def load(self, source: Union[str, Path, dict]) -> dict:
        """
Load configuration using JsonPreprocessor or fallback.
        """
        if isinstance(source, dict):
            return source

        path = str(source)
        path = os.path.expandvars(path)

        if self._preprocessor:
            return self._preprocessor.jsonLoad(jFile=path)
        else:
            # Fallback to standard JSON
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)


# ============================================================================
# Process Config Loader
# ============================================================================


class ProcessConfigLoader:
    """
Process configuration loader.

Loads process definitions and provides utilities for
accessing process-specific configuration.

Usage:

    loader = ProcessConfigLoader()
    
    loader.load_file("${TAF_PATH}/project/processes/config.jsonp")
    

    config = loader.get_process_config("system_manager")
    
    args = loader.get_process_arguments("system_manager")
    """

    def __init__(
        self,
        loader: Optional[ConfigLoader] = None,
    ):
        """
Initialize loader.

**Arguments:**

* ``loader``

  / *Condition*: optional / *Type*: ConfigLoader / *Default*: None /

  Config loader to use (JsonPreprocessorLoader if None).
        """
        self._loader = loader or JsonPreprocessorLoader()
        self._config: dict = {}

    @property
    def config(self) -> dict:
        """
Get the full configuration dict.
        """
        return self._config

    def load_file(self, path: Union[str, Path]) -> dict:
        """
Load configuration from file.

**Arguments:**

* ``path``

  / *Condition*: required / *Type*: Union[str, Path] /

  Path to configuration file.

**Returns:**

  / *Type*: dict /

  Loaded configuration.
        """
        self._config = self._loader.load(path)
        logger.info("Loaded %d process configurations", len(self._config))
        return self._config

    def load_dict(self, config: dict) -> dict:
        """
Load configuration from dict.

**Arguments:**

* ``config``

  / *Condition*: required / *Type*: dict /

  Configuration dict.

**Returns:**

/ *Type*: dict /

The configuration.
        """
        self._config = config
        return self._config

    def get_process_names(self) -> list[str]:
        """
Get all process names.
        """
        return list(self._config.keys())

    def get_process_config(self, name: str) -> Optional[dict]:
        """
Get configuration for a specific process.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  Process name.

**Returns:**

/ *Type*: Optional[dict] /

Process configuration or None.
        """
        return self._config.get(name)

    def has_process(self, name: str) -> bool:
        """
Check if process is defined in config.
        """
        return name in self._config

    def get_process_arguments(
        self,
        name: str,
        logging_config: Optional[dict] = None,
    ) -> Optional[tuple]:
        """
Get process arguments for starting.

Mirrors ProcessControl.get_process_arguments().

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  Process name.

* ``logging_config``

  / *Condition*: optional / *Type*: dict / *Default*: None /

  Optional logging configuration dict with keys:
  config_dir, host, port.

**Returns:**

/ *Type*: Optional[tuple] /

Tuple of (name, script, args, logging_conf, logging_host, logging_port)
or None if process not found.
        """
        proc_config = self._config.get(name)
        if not proc_config:
            return None

        # Get script path
        script = proc_config.get("script", "")
        script = fully_expand_vars(script)

        # Get arguments
        args = proc_config.get("args", [])
        if isinstance(args, list):
            args = [expand_and_quote(arg) for arg in args]

        # Get logging config
        logging_conf = None
        logging_host = None
        logging_port = None

        if proc_config.get("central_log") and logging_config:
            logging_conf = logging_config.get("config_dir")
            logging_host = logging_config.get("host")
            logging_port = logging_config.get("port")

        return (name, script, args, logging_conf, logging_host, logging_port)

    def get_executor_config(self, name: str) -> dict:
        """
Get configuration formatted for executor.

**Arguments:**

* ``name``

  / *Condition*: required / *Type*: str /

  Process name.

**Returns:**

/ *Type*: dict /

Dict suitable for ProcessExecutor.start().
        """
        proc_config = self._config.get(name, {})

        return {
            "script": fully_expand_vars(proc_config.get("script", "")),
            "args": [expand_and_quote(a) for a in proc_config.get("args", [])],
            "wait_time": proc_config.get("wait_time", 2.0),
            "process_name": proc_config.get("process_name", name),
            "central_log": proc_config.get("central_log", False),
            "env": proc_config.get("env", {}),
            "enable": proc_config.get("enable", True),
            "description": proc_config.get("description", ""),
            "mandatory": proc_config.get("mandatory", False),
            "warning_on_deselect": proc_config.get("warning_on_deselect", ""),
        }


# ============================================================================
# Restart Sequence Computation
# ============================================================================


def compute_restart_sequence(
    config: dict,
    process_name: str,
) -> list[str]:
    """
Compute the restart sequence for a process.

Determines which processes need to be restarted based on
dependencies.

**Arguments:**

* ``config``

  / *Condition*: required / *Type*: dict /

  Process configuration dict.

* ``process_name``

  / *Condition*: required / *Type*: str /

  Name of process that died.

**Returns:**

/ *Type*: list[str] /

List of process names in restart order.
    """
    # Simple implementation - just return the process
    # Override with more complex logic if needed
    sequence = [process_name]

    # Check for dependencies
    proc_config = config.get(process_name, {})
    dependencies = proc_config.get("dependencies", [])

    for dep in dependencies:
        if dep not in sequence:
            sequence.insert(0, dep)

    return sequence
