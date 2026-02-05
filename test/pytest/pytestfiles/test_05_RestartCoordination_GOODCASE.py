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
# test_05_RestartCoordination_GOODCASE.py
#
# Nguyen Huynh Tri Cuong (MS/EMC51)
#
# 05.02.2026 - 18:25:28
#
# --------------------------------------------------------------------------------------------------------------

import pytest
from pytestlibs.CExecute import CExecute

# --------------------------------------------------------------------------------------------------------------

class Test_RestartCoordination_GOODCASE:

# --------------------------------------------------------------------------------------------------------------
   # Expected: Dead process detected and restart notification sent
   @pytest.mark.parametrize(
      "Description", ["Detect killed process via health check tick",]
   )
   def test_PHB_0015(self, Description):
      nReturn = CExecute.Execute("PHB_0015")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
   # Expected: Complete restart cycle executed successfully
   @pytest.mark.parametrize(
      "Description", ["Full restart flow: detect, notify, acknowledge, restart",]
   )
   def test_PHB_0016(self, Description):
      nReturn = CExecute.Execute("PHB_0016")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
