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
#   Platform-specific process execution package.
#   Provides platform-specific executor implementations.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Platform-specific process execution.

Provides platform-specific executor implementations:

- PlatformExecutor: Abstract base class

- WindowsExecutor: Windows-specific (cmd.exe, PowerShell)

- UnixExecutor: Unix/Linux/macOS (POSIX signals)
"""

import sys

from .base import PlatformExecutor

__all__ = ["PlatformExecutor"]

# Platform-specific imports
if sys.platform == "win32":
    try:
        from .windows import WindowsExecutor
 
        __all__.append("WindowsExecutor")
    except ImportError:
        WindowsExecutor = None  # type: ignore
else:
    try:
        from .unix import UnixExecutor

        __all__.append("UnixExecutor")
    except ImportError:
        UnixExecutor = None  # type: ignore


def get_platform_executor() -> PlatformExecutor:
    """
    Get the appropriate executor for the current platform.

    Returns:
        Platform-specific executor instance
    """
    if sys.platform == "win32":
        from .windows import WindowsExecutor

        return WindowsExecutor()
    else:
        from .unix import UnixExecutor

        return UnixExecutor()
