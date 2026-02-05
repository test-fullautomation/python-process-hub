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
# test_03_ProcessControl_BADCASE.py
#
# Nguyen Huynh Tri Cuong (MS/EMC51)
#
# 05.02.2026 - 18:25:28
#
# --------------------------------------------------------------------------------------------------------------

import pytest
from pytestlibs.CExecute import CExecute

# --------------------------------------------------------------------------------------------------------------

class Test_ProcessControl_BADCASE:

# --------------------------------------------------------------------------------------------------------------
   # Expected: Start response indicates failure with error message
   @pytest.mark.parametrize(
      "Description", ["Start a process that fails to launch",]
   )
   def test_PHB_0011(self, Description):
      nReturn = CExecute.Execute("PHB_0011")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
