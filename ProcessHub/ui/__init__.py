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
#   UI layer package - decoupled views for hub state.
#   Provides pluggable view implementations.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""UI layer - decoupled views for hub state."""

from .base import HubView, HubViewBase
from .console_view import ConsoleView
from .null_view import NullView

# WebView requires fastapi and uvicorn (optional dependency)
try:
    from .web_view import WebView
    __all__ = ["HubView", "HubViewBase", "ConsoleView", "NullView", "WebView"]
except ImportError:
    __all__ = ["HubView", "HubViewBase", "ConsoleView", "NullView"]
