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
# test_04_ConnectionManagement_GOODCASE.py
#
# Nguyen Huynh Tri Cuong (MS/EMC51)
#
# 05.02.2026 - 18:25:28
#
# --------------------------------------------------------------------------------------------------------------

import pytest
from pytestlibs.CExecute import CExecute

# --------------------------------------------------------------------------------------------------------------

class Test_ConnectionManagement_GOODCASE:

# --------------------------------------------------------------------------------------------------------------
   # Expected: Connection registered successfully with correct panel_id
   @pytest.mark.parametrize(
      "Description", ["Register a client connection",]
   )
   def test_PHB_0012(self, Description):
      nReturn = CExecute.Execute("PHB_0012")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
   # Expected: All panels registered and session_panel_ids updated correctly
   @pytest.mark.parametrize(
      "Description", ["Register multiple connections in the same session",]
   )
   def test_PHB_0013(self, Description):
      nReturn = CExecute.Execute("PHB_0013")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
   # Expected: Connection removed and orphaned processes stopped
   @pytest.mark.parametrize(
      "Description", ["Unregister connection with orphan process cleanup",]
   )
   def test_PHB_0014(self, Description):
      nReturn = CExecute.Execute("PHB_0014")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
