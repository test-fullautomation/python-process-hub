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
# test_07_StateSnapshot_GOODCASE.py
#
# Nguyen Huynh Tri Cuong (MS/EMC51)
#
# 05.02.2026 - 18:25:28
#
# --------------------------------------------------------------------------------------------------------------

import pytest
from pytestlibs.CExecute import CExecute

# --------------------------------------------------------------------------------------------------------------

class Test_StateSnapshot_GOODCASE:

# --------------------------------------------------------------------------------------------------------------
   # Expected: Snapshot includes process names, states, and requesters
   @pytest.mark.parametrize(
      "Description", ["State snapshot contains all process information",]
   )
   def test_PHB_0018(self, Description):
      nReturn = CExecute.Execute("PHB_0018")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
   # Expected: Snapshot includes panel_ids, session_ids, and session groupings
   @pytest.mark.parametrize(
      "Description", ["State snapshot contains connection information",]
   )
   def test_PHB_0019(self, Description):
      nReturn = CExecute.Execute("PHB_0019")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
