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

def test():
    core, executor = create_test_core()
    register_panel(core, "panel_A")
    start_processes(core, "panel_A", ["worker_1", "worker_2"])
    snapshot = core.get_state_snapshot()
    count = len(snapshot.processes)
    all_have_state = all(hasattr(p, 'state') for p in snapshot.processes)
    all_have_requesters = all(hasattr(p, 'requesters') for p in snapshot.processes)
    if count == 2 and all_have_state and all_have_requesters:
        return f"Snapshot contains {count} processes with correct states and requesters"
    else:
        return f"Snapshot incomplete: count={count}, states={all_have_state}, requesters={all_have_requesters}"
