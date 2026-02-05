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
# test_06_RestartCoordination_BADCASE.py
#
# Nguyen Huynh Tri Cuong (MS/EMC51)
#
# 05.02.2026 - 18:25:28
#
# --------------------------------------------------------------------------------------------------------------

import pytest
from pytestlibs.CExecute import CExecute

# --------------------------------------------------------------------------------------------------------------

class Test_RestartCoordination_BADCASE:

# --------------------------------------------------------------------------------------------------------------
   # Expected: Restart times out when panels do not acknowledge in time
   @pytest.mark.parametrize(
      "Description", ["Restart state machine timeout",]
   )
   def test_PHB_0017(self, Description):
      nReturn = CExecute.Execute("PHB_0017")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
