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

def test():
    core, executor = create_test_core()
    register_panel(core, "panel_A")
    start_processes(core, "panel_A", ["worker_1"])
    # Simulate process being killed externally
    executor.kill_process("worker_1")
    # Tick should detect the dead process
    msgs = core.tick()
    has_restart_notify = any(m.msg_type == MessageType.RESTART_NOTIFY for m in msgs)
    if has_restart_notify:
        return f"Dead process 'worker_1' detected, restart notification sent"
    else:
        return f"Dead process not detected"
