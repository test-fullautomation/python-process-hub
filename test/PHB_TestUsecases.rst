.. Copyright 2020-2026 Robert Bosch GmbH

.. Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

.. http://www.apache.org/licenses/LICENSE-2.0

.. Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

Test Use Cases
==============

* **Test PHB_0001**

  [ProcessRegistry / GOODCASE]

   **Register a new process in the registry**

   Expected: Process registered successfully with correct state

----

* **Test PHB_0002**

  [ProcessRegistry / GOODCASE]

   **Add a second requester to an existing process**

   Expected: Second requester added without re-registering the process

----

* **Test PHB_0003**

  [ProcessRegistry / GOODCASE]

   **Unregister last requester - process can be stopped**

   Expected: Unregister returns True indicating process can be stopped

----

* **Test PHB_0004**

  [ProcessRegistry / GOODCASE]

   **Unregister one requester while others remain**

   Expected: Unregister returns False indicating process should keep running

----

* **Test PHB_0005**

  [ProcessRegistry / GOODCASE]

   **Get state snapshot is immutable**

   Expected: Snapshot is a frozen copy that does not change when registry changes

----

* **Test PHB_0006**

  [ProcessControl / GOODCASE]

   **Start a single process successfully**

   Expected: Process started and response contains success

----

* **Test PHB_0007**

  [ProcessControl / GOODCASE]

   **Start multiple processes in a single request**

   Expected: All processes started and response contains success

----

* **Test PHB_0008**

  [ProcessControl / GOODCASE]

   **Stop process when requester is the last one**

   Expected: Process actually stopped and removed from registry

----

* **Test PHB_0009**

  [ProcessControl / GOODCASE]

   **Stop shared process - other requesters still active**

   Expected: Process keeps running, only requester removed

----

* **Test PHB_0010**

  [ProcessControl / GOODCASE]

   **Force stop a shared process**

   Expected: Process stopped regardless of other requesters

----

* **Test PHB_0011**

  [ProcessControl / BADCASE]

   **Start a process that fails to launch**

   Expected: Start response indicates failure with error message

----

* **Test PHB_0012**

  [ConnectionManagement / GOODCASE]

   **Register a client connection**

   Expected: Connection registered successfully with correct panel_id

----

* **Test PHB_0013**

  [ConnectionManagement / GOODCASE]

   **Register multiple connections in the same session**

   Expected: All panels registered and session_panel_ids updated correctly

----

* **Test PHB_0014**

  [ConnectionManagement / GOODCASE]

   **Unregister connection with orphan process cleanup**

   Expected: Connection removed and orphaned processes stopped

----

* **Test PHB_0015**

  [RestartCoordination / GOODCASE]

   **Detect killed process via health check tick**

   Expected: Dead process detected and restart notification sent

----

* **Test PHB_0016**

  [RestartCoordination / GOODCASE]

   **Full restart flow: detect, notify, acknowledge, restart**

   Expected: Complete restart cycle executed successfully

----

* **Test PHB_0017**

  [RestartCoordination / BADCASE]

   **Restart state machine timeout**

   Expected: Restart times out when panels do not acknowledge in time

   *Comment: Uses very short timeout (0.1s) to trigger timeout quickly*

----

* **Test PHB_0018**

  [StateSnapshot / GOODCASE]

   **State snapshot contains all process information**

   Expected: Snapshot includes process names, states, and requesters

----

* **Test PHB_0019**

  [StateSnapshot / GOODCASE]

   **State snapshot contains connection information**

   Expected: Snapshot includes panel_ids, session_ids, and session groupings

----

Generated: 05.02.2026 - 18:25:28

