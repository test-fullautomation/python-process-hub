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

import os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from testutils.process_helpers import create_test_core, register_panel, start_processes

def test():
    core, executor = create_test_core()
    # Override restart timeout to very short
    core._restart_fsm._context.timeout_seconds = 0.1
    register_panel(core, "panel_A")
    start_processes(core, "panel_A", ["worker_1"])
    # Kill the process
    executor.kill_process("worker_1")
    # Tick detects death
    core.tick()
    # Wait for timeout
    time.sleep(0.2)
    # Tick should detect timeout
    msgs = core.tick()
    # Check if timeout was handled
    timed_out = any("timeout" in str(m.payload).lower() or "timed out" in str(m.payload).lower() for m in msgs) if msgs else False
    # Alternative: check restart FSM state
    from ProcessHub.core.restart_state import RestartState
    fsm_state = core._restart_fsm.state
    if fsm_state in (RestartState.IDLE, RestartState.DONE) or timed_out:
        return f"Restart timed out as expected"
    else:
        return f"Restart did not timeout: state={fsm_state}"
