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
# File: null_view.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Null view for headless operation.
#   Use this when running process hub without a UI.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Null view for headless operation.

Use this when running process hub without a UI,
such as in embedded mode or background service.
"""

from __future__ import annotations

from ..core.models import HubStateSnapshot
from .base import HubViewBase


class NullView(HubViewBase):
    """
No-op view for headless/embedded use.

Does nothing on render - useful for:

- Running as background service

- Embedding in other applications

- Unit testing without console output
    """

    def render(self, snapshot: HubStateSnapshot) -> None:
        """
No-op render.
        """
        pass
