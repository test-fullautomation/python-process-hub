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
# File: topics.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / February 2026.
#
# Description:
#   Fleet message topics for EventBus routing.
#   All fleet topics use "FLEET_" prefix to avoid collision with local hub topics.
#
# History:
#
# 06.02.2026 / V 1.1.0 / Nguyen Huynh Tri Cuong
# - Initial fleet orchestrator implementation
#
# *******************************************************************************
"""
Fleet message topics for EventBus routing.

All fleet topics use ``FLEET_`` prefix to separate from local hub
topics (``PROCESS_*``, ``REGISTER_*``, ``SERVER_*``).

When used with EventBusTransport, the full routing key becomes:
``fleet.FLEET_HUB_ANNOUNCE``, ``fleet.FLEET_COMMAND``, etc.
"""

from __future__ import annotations

from enum import Enum


class FleetTopics(str, Enum):
    """
FleetTopics: Message topics for fleet protocol.

Used with transport.register_handler() and transport.send().
    """

    # Hub lifecycle
    HUB_ANNOUNCE = "FLEET_HUB_ANNOUNCE"
    HUB_REGISTERED = "FLEET_HUB_REGISTERED"
    HUB_DEREGISTER = "FLEET_HUB_DEREGISTER"

    # Status reporting
    HUB_STATUS_REPORT = "FLEET_HUB_STATUS_REPORT"
    FLEET_STATUS_REQUEST = "FLEET_STATUS_REQUEST"
    FLEET_STATUS_RESPONSE = "FLEET_STATUS_RESPONSE"

    # Command routing
    FLEET_COMMAND = "FLEET_COMMAND"
    FLEET_COMMAND_RESULT = "FLEET_COMMAND_RESULT"

    # Health notifications
    HUB_ONLINE = "FLEET_HUB_ONLINE"
    HUB_OFFLINE = "FLEET_HUB_OFFLINE"
