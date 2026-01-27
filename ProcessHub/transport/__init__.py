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
#   Transport layer package - pluggable message transports.
#   Provides abstract transport interface and implementations.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Transport layer - pluggable message transports.

Provides abstract transport interface and implementations:

- TransportBase: Abstract interface

- InMemoryTransport: For testing

- ZmqTransport: For production (requires pyzmq)

- EventBusTransport: For RabbitMQ-based messaging (requires EventBusClient)
"""

from .base import TransportBase
from .inmemory_transport import InMemoryTransport

# ZMQ transport is optional (requires pyzmq)
try:
    from .zmq_transport import (
        ZmqTransport,
        ZmqBroker,
        ZmqAsyncClient,
        TcpKeepaliveConfig,
    )

    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False
    ZmqTransport = None  # type: ignore
    ZmqBroker = None  # type: ignore
    ZmqAsyncClient = None  # type: ignore
    TcpKeepaliveConfig = None  # type: ignore

# EventBus transport is optional (requires EventBusClient)
try:
    from .eventbus_transport import (
        EventBusTransport,
        EventBusConfig,
        ProcessHubMessage,
    )

    HAS_EVENTBUS = True
except ImportError:
    HAS_EVENTBUS = False
    EventBusTransport = None  # type: ignore
    EventBusConfig = None  # type: ignore
    ProcessHubMessage = None  # type: ignore

__all__ = [
    "TransportBase",
    "InMemoryTransport",
    # ZMQ
    "ZmqTransport",
    "ZmqBroker",
    "ZmqAsyncClient",
    "TcpKeepaliveConfig",
    "HAS_ZMQ",
    # EventBus
    "EventBusTransport",
    "EventBusConfig",
    "ProcessHubMessage",
    "HAS_EVENTBUS",
]
