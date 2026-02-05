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
# test_02_ProcessControl_GOODCASE.py
#
# Nguyen Huynh Tri Cuong (MS/EMC51)
#
# 05.02.2026 - 18:25:28
#
# --------------------------------------------------------------------------------------------------------------

import pytest
from pytestlibs.CExecute import CExecute

# --------------------------------------------------------------------------------------------------------------

class Test_ProcessControl_GOODCASE:

# --------------------------------------------------------------------------------------------------------------
   # Expected: Process started and response contains success
   @pytest.mark.parametrize(
      "Description", ["Start a single process successfully",]
   )
   def test_PHB_0006(self, Description):
      nReturn = CExecute.Execute("PHB_0006")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
   # Expected: All processes started and response contains success
   @pytest.mark.parametrize(
      "Description", ["Start multiple processes in a single request",]
   )
   def test_PHB_0007(self, Description):
      nReturn = CExecute.Execute("PHB_0007")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
   # Expected: Process actually stopped and removed from registry
   @pytest.mark.parametrize(
      "Description", ["Stop process when requester is the last one",]
   )
   def test_PHB_0008(self, Description):
      nReturn = CExecute.Execute("PHB_0008")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
   # Expected: Process keeps running, only requester removed
   @pytest.mark.parametrize(
      "Description", ["Stop shared process - other requesters still active",]
   )
   def test_PHB_0009(self, Description):
      nReturn = CExecute.Execute("PHB_0009")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
   # Expected: Process stopped regardless of other requesters
   @pytest.mark.parametrize(
      "Description", ["Force stop a shared process",]
   )
   def test_PHB_0010(self, Description):
      nReturn = CExecute.Execute("PHB_0010")
      assert nReturn == 0
# --------------------------------------------------------------------------------------------------------------
