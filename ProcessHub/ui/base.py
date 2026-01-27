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
# File: base.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Abstract view interface for process hub.
#   Implements improvement 3.6: Pluggable views (console, web, null).
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Abstract view interface.

This module implements improvement 3.6:

- Define abstract interface for hub state observers

- Allow pluggable views (console, web, null)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from ..core.models import HubStateSnapshot


class HubView(Protocol):
    """
Protocol for hub state observers.

Improvement 3.6: Expose get_state() on core, have independent loop poll/observe.

This protocol allows different view implementations:

- ConsoleView: ASCII table in terminal

- NullView: No-op for headless/embedded use

- WebView: Future web-based UI

- MetricsView: Push to monitoring systems
    """

    def on_state_changed(self, snapshot: HubStateSnapshot) -> None:
        """
Called when hub state changes.

This is for push-based updates. Views can use this to
trigger re-renders or update internal state.
        """
        ...

    def render(self, snapshot: HubStateSnapshot) -> None:
        """
Render current state.

This is for pull-based updates. The server loop calls
this periodically with the latest snapshot.
        """
        ...


class HubViewBase(ABC):
    """
Base class for hub views.

Provides default implementation where on_state_changed
simply calls render.
    """

    @abstractmethod
    def render(self, snapshot: HubStateSnapshot) -> None:
        """
Render current state to output.
        """
        pass

    def on_state_changed(self, snapshot: HubStateSnapshot) -> None:
        """
Default: just render.
        """
        self.render(snapshot)
