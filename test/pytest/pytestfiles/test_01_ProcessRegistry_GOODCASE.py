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
# --------------------------------------------------------------------------------------------------------------
#
# test_01_ProcessRegistry_GOODCASE.py
#
# Nguyen Huynh Tri Cuong (MS/EMC51)
#
# 05.02.2026 - 18:25:28
#
# --------------------------------------------------------------------------------------------------------------

import pytest
from pytestlibs.CExecute import CExecute

# --------------------------------------------------------------------------------------------------------------

class Test_ProcessRegistry_GOODCASE:

# --------------------------------------------------------------------------------------------------------------
   # Expected: Process registered successfully with correct state
   @pytest.mark.parametrize(
      "Description", ["Register a new process in the registry",]
   )
   def test_PHB_0001(self, Description):
      nReturn = CExecute.Execute("PHB_0001")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
   # Expected: Second requester added without re-registering the process
   @pytest.mark.parametrize(
      "Description", ["Add a second requester to an existing process",]
   )
   def test_PHB_0002(self, Description):
      nReturn = CExecute.Execute("PHB_0002")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
   # Expected: Unregister returns True indicating process can be stopped
   @pytest.mark.parametrize(
      "Description", ["Unregister last requester - process can be stopped",]
   )
   def test_PHB_0003(self, Description):
      nReturn = CExecute.Execute("PHB_0003")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
   # Expected: Unregister returns False indicating process should keep running
   @pytest.mark.parametrize(
      "Description", ["Unregister one requester while others remain",]
   )
   def test_PHB_0004(self, Description):
      nReturn = CExecute.Execute("PHB_0004")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
   # Expected: Snapshot is a frozen copy that does not change when registry changes
   @pytest.mark.parametrize(
      "Description", ["Get state snapshot is immutable",]
   )
   def test_PHB_0005(self, Description):
      nReturn = CExecute.Execute("PHB_0005")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
