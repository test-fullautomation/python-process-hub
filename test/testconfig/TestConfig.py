# **************************************************************************************************************
#
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
#
# **************************************************************************************************************
#
# TestConfig.py
#
# Nguyen Huynh Tri Cuong (MS/EMC51)
# Derive from the component test of EventBusClient
#
# 05.02.2026
#
# --------------------------------------------------------------------------------------------------------------

listofdictUsecases = []

# the following keys are optional, all other keys are mandatory.
# dictUsecase['HINT']         = None
# dictUsecase['COMMENT']      = None
# dictUsecase['USERAWPATH']   = False # if True, 'TESTFILE' will not be normalized

# --------------------------------------------------------------------------------------------------------------

# If both 'EXPECTEDEXCEPTION' and 'EXPECTEDRETURN' are None, the check of values returned from ProcessHub is
# skipped and the test case result is UNKNOWN.

# --------------------------------------------------------------------------------------------------------------
#TM***
# ==============================================================================
# ProcessRegistry
# ==============================================================================
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0001"
dictUsecase['DESCRIPTION']       = "Register a new process in the registry"
dictUsecase['EXPECTATION']       = "Process registered successfully with correct state"
dictUsecase['SECTION']           = "ProcessRegistry"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0001.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Process 'worker_1' registered successfully with state RUNNING"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0002"
dictUsecase['DESCRIPTION']       = "Add a second requester to an existing process"
dictUsecase['EXPECTATION']       = "Second requester added without re-registering the process"
dictUsecase['SECTION']           = "ProcessRegistry"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0002.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Process 'worker_1' has 2 requesters: panel_A, panel_B"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0003"
dictUsecase['DESCRIPTION']       = "Unregister last requester - process can be stopped"
dictUsecase['EXPECTATION']       = "Unregister returns True indicating process can be stopped"
dictUsecase['SECTION']           = "ProcessRegistry"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0003.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Last requester removed: can_stop=True"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0004"
dictUsecase['DESCRIPTION']       = "Unregister one requester while others remain"
dictUsecase['EXPECTATION']       = "Unregister returns False indicating process should keep running"
dictUsecase['SECTION']           = "ProcessRegistry"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0004.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Requester removed, others remain: can_stop=False"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0005"
dictUsecase['DESCRIPTION']       = "Get state snapshot is immutable"
dictUsecase['EXPECTATION']       = "Snapshot is a frozen copy that does not change when registry changes"
dictUsecase['SECTION']           = "ProcessRegistry"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0005.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Snapshot is immutable: original count=1, snapshot count after add=1"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# ==============================================================================
# ProcessControl
# ==============================================================================
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0006"
dictUsecase['DESCRIPTION']       = "Start a single process successfully"
dictUsecase['EXPECTATION']       = "Process started and response contains success"
dictUsecase['SECTION']           = "ProcessControl"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0006.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Process 'worker_1' started successfully"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0007"
dictUsecase['DESCRIPTION']       = "Start multiple processes in a single request"
dictUsecase['EXPECTATION']       = "All processes started and response contains success"
dictUsecase['SECTION']           = "ProcessControl"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0007.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "All 3 processes started successfully: worker_1, worker_2, worker_3"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0008"
dictUsecase['DESCRIPTION']       = "Stop process when requester is the last one"
dictUsecase['EXPECTATION']       = "Process actually stopped and removed from registry"
dictUsecase['SECTION']           = "ProcessControl"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0008.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Process 'worker_1' stopped: stopped=['worker_1'], still_in_use=[], failed=[]"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0009"
dictUsecase['DESCRIPTION']       = "Stop shared process - other requesters still active"
dictUsecase['EXPECTATION']       = "Process keeps running, only requester removed"
dictUsecase['SECTION']           = "ProcessControl"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0009.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Process 'worker_1' still in use: stopped=[], still_in_use=['worker_1'], failed=[]"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0010"
dictUsecase['DESCRIPTION']       = "Force stop a shared process"
dictUsecase['EXPECTATION']       = "Process stopped regardless of other requesters"
dictUsecase['SECTION']           = "ProcessControl"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0010.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Process 'worker_1' force stopped: stopped=['worker_1'], still_in_use=[], failed=[]"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0011"
dictUsecase['DESCRIPTION']       = "Start a process that fails to launch"
dictUsecase['EXPECTATION']       = "Start response indicates failure with error message"
dictUsecase['SECTION']           = "ProcessControl"
dictUsecase['SUBSECTION']        = "BADCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0011.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Process 'bad_worker' failed to start: success=False"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# ==============================================================================
# ConnectionManagement
# ==============================================================================
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0012"
dictUsecase['DESCRIPTION']       = "Register a client connection"
dictUsecase['EXPECTATION']       = "Connection registered successfully with correct panel_id"
dictUsecase['SECTION']           = "ConnectionManagement"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0012.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Panel 'panel_A' registered successfully"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0013"
dictUsecase['DESCRIPTION']       = "Register multiple connections in the same session"
dictUsecase['EXPECTATION']       = "All panels registered and session_panel_ids updated correctly"
dictUsecase['SECTION']           = "ConnectionManagement"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0013.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Session has 2 panels: panel_A, panel_B"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0014"
dictUsecase['DESCRIPTION']       = "Unregister connection with orphan process cleanup"
dictUsecase['EXPECTATION']       = "Connection removed and orphaned processes stopped"
dictUsecase['SECTION']           = "ConnectionManagement"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0014.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Panel 'panel_A' unregistered, orphaned processes cleaned up"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# ==============================================================================
# RestartCoordination
# ==============================================================================
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0015"
dictUsecase['DESCRIPTION']       = "Detect killed process via health check tick"
dictUsecase['EXPECTATION']       = "Dead process detected and restart notification sent"
dictUsecase['SECTION']           = "RestartCoordination"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0015.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Dead process 'worker_1' detected, restart notification sent"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0016"
dictUsecase['DESCRIPTION']       = "Full restart flow: detect, notify, acknowledge, restart"
dictUsecase['EXPECTATION']       = "Complete restart cycle executed successfully"
dictUsecase['SECTION']           = "RestartCoordination"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0016.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Full restart flow completed: process 'worker_1' restarted successfully"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0017"
dictUsecase['DESCRIPTION']       = "Restart state machine timeout"
dictUsecase['EXPECTATION']       = "Restart times out when panels do not acknowledge in time"
dictUsecase['SECTION']           = "RestartCoordination"
dictUsecase['SUBSECTION']        = "BADCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = "Uses very short timeout (0.1s) to trigger timeout quickly"
dictUsecase['TESTFILE']          = r"PHB_0017.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Restart timed out as expected"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# ==============================================================================
# StateSnapshot
# ==============================================================================
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0018"
dictUsecase['DESCRIPTION']       = "State snapshot contains all process information"
dictUsecase['EXPECTATION']       = "Snapshot includes process names, states, and requesters"
dictUsecase['SECTION']           = "StateSnapshot"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0018.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Snapshot contains 2 processes with correct states and requesters"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# --------------------------------------------------------------------------------------------------------------
dictUsecase = {}
dictUsecase['TESTID']            = "PHB_0019"
dictUsecase['DESCRIPTION']       = "State snapshot contains connection information"
dictUsecase['EXPECTATION']       = "Snapshot includes panel_ids, session_ids, and session groupings"
dictUsecase['SECTION']           = "StateSnapshot"
dictUsecase['SUBSECTION']        = "GOODCASE"
dictUsecase['HINT']              = None
dictUsecase['COMMENT']           = None
dictUsecase['TESTFILE']          = r"PHB_0019.py"
dictUsecase['EXPECTEDEXCEPTION'] = None
dictUsecase['EXPECTEDRETURN']    = "Snapshot contains 2 connections in same session"
listofdictUsecases.append(dictUsecase)
del dictUsecase
# --------------------------------------------------------------------------------------------------------------
