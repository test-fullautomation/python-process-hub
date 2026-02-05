# **************************************************************************************************************
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
# **************************************************************************************************************

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from testutils.process_helpers import create_test_core, register_panel, start_processes, stop_processes

def test():
    core, executor = create_test_core()
    register_panel(core, "panel_A")
    register_panel(core, "panel_B")
    start_processes(core, "panel_A", ["worker_1"])
    start_processes(core, "panel_B", ["worker_1"])
    msgs = stop_processes(core, "panel_A", ["worker_1"], force=True)
    payload = msgs[0].payload
    return f"Process 'worker_1' force stopped: stopped={payload.stopped}, still_in_use={payload.still_in_use}, failed={payload.failed}"
