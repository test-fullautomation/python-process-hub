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
#   Process execution layer package.
#   Provides abstract process executor interface and implementations.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Process execution layer.

Provides abstract process executor interface and implementations:

- ProcessExecutor: Abstract interface

- SimpleExecutor: Basic cross-platform executor

- MockExecutor: For testing

- ProcessManager: High-level process lifecycle management


Platform-specific executors:

- WindowsExecutor: Windows-specific (cmd.exe, PowerShell)

- UnixExecutor: Unix/Linux/macOS (POSIX signals)
"""

from .executor import (
    ProcessExecutor,
    SimpleExecutor,
    MockExecutor,
    create_executor,
)
from .manager import ProcessManager

# Platform executors
from .platform.base import PlatformExecutor

try:
    from .platform.windows import WindowsExecutor
except ImportError:
    WindowsExecutor = None  # type: ignore

try:
    from .platform.unix import UnixExecutor
except ImportError:
    UnixExecutor = None  # type: ignore

__all__ = [
    # Core
    "ProcessExecutor",
    "SimpleExecutor",
    "MockExecutor",
    "create_executor",
    # Manager
    "ProcessManager",
    # Platform
    "PlatformExecutor",
    "WindowsExecutor",
    "UnixExecutor",
]
