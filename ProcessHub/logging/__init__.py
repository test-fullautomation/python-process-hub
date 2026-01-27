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
#   Logging server integration package for Process Hub.
#   Provides optional integration with centralized logging servers.
#
# History:
#
# 15.01.2026 / V 1.0.0 / Nguyen Huynh Tri Cuong
# - Initial version migrated from ta-framework-tsb process_hub
#
# *******************************************************************************
"""
Logging server integration for Process Hub.

This module provides optional integration with centralized logging servers
(Fluentbit, Telegraf, or custom implementations).

Usage:

    from ProcessHub.logging import LoggingIntegration, LoggingServerType

    # Initialize logging

    logging = LoggingIntegration(

        server_type=LoggingServerType.FLUENTBIT,

        paths={

            "src_dir": "/path/to/fluentbit",

            "hot_dir": "/path/to/logs/fluentbit",

            "influx_dir": "/path/to/influxdb",

            "ctrl_dir": "/path/to/control",

        }

    )

    logging.start()

    # Get config for a process

    log_config = logging.get_process_logging_config("my_process")

    # Cleanup

    logging.stop()
"""

from .integration import (
    LoggingIntegration,
    LoggingServerProtocol,
    LoggingServerType,
    LoggingConfig,
)

__all__ = [
    "LoggingIntegration",
    "LoggingServerProtocol",
    "LoggingServerType",
    "LoggingConfig",
]
