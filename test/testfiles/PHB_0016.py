# Copyright (c) 2020-2026 Robert Bosch GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from testutils.process_helpers import create_test_core, register_panel, start_processes
from ProcessHub.core.hub_core import MessageType
from ProcessHub.core.models import ProcessRestartReady

def test():
    core, executor = create_test_core()
    register_panel(core, "panel_A")
    start_processes(core, "panel_A", ["worker_1"])
    # Kill the process
    executor.kill_process("worker_1")
    # Tick detects death
    msgs = core.tick()
    # Panel acknowledges restart
    ack = ProcessRestartReady(panel_id="panel_A")
    msgs = core.handle_restart_ready(ack)
    # Tick again to complete restart
    msgs = core.tick()
    # Check if process is running again
    snapshot = core.get_state_snapshot()
    proc_states = {p.name: p.state.name for p in snapshot.processes}
    if "worker_1" in proc_states and proc_states["worker_1"] == "RUNNING":
        return f"Full restart flow completed: process 'worker_1' restarted successfully"
    else:
        return f"Restart flow incomplete: states={proc_states}"
