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
#   Runtime components package - server, client, and transport wiring.
#   Wires together the core logic with transport and UI layers.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Runtime components - server, client, and transport wiring.

This module provides the runtime components that wire together
the core logic with transport and UI layers.
"""

from .server import ProcessHubServer, Topics
from .client import ProcessHubClient
from .client_controller import ClientController, ClientEvent

__all__ = [
    "ProcessHubServer",
    "ProcessHubClient",
    "ClientController",
    "ClientEvent",
    "Topics",
]
