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
# *******************************************************************************
#
# File: 10_admin_dashboard.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Example demonstrating the WebView with Admin API enabled.
#   Shows how to start/stop processes directly from the web dashboard.
#
# Usage:
#   1. Install dependencies: pip install fastapi uvicorn
#   2. Run this script: python 10_admin_dashboard.py
#   3. Open browser to http://localhost:2507
#   4. Use the Start/Stop/Kill buttons in the Processes table
#
# *******************************************************************************
"""
Admin Dashboard Example.:

This example demonstrates how to:
1. Create a ProcessHubServer with WebView and Admin API enabled
2. Define admin callbacks for process control
3. Start/stop processes directly from the web dashboard

Requirements:
    pip install fastapi uvicorn

The admin dashboard provides:
- Inline Start/Stop/Kill buttons next to each process
- Admin Controls section for starting new processes
- Real-time process status updates
- Console log viewer

Admin API endpoints:
- GET  /api/admin/status - Check if admin is enabled
- POST /api/admin/processes/start - Start multiple processes
- POST /api/admin/processes/stop - Stop multiple processes
- POST /api/admin/processes/{name}/start - Start a single process
- POST /api/admin/processes/{name}/stop - Stop a single process
"""

import logging
import sys
from pathlib import Path

# Add ProcessHub to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from ProcessHub.runtime import ProcessHubServer
from ProcessHub.transport import ZmqTransport
from ProcessHub.process import SimpleExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Reduce noise from uvicorn
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def main():
    """Run the Process Hub Server with Admin Dashboard."""
    # Check if FastAPI is available
    try:
        from ProcessHub.ui import WebView
    except ImportError:
        logger.error(
            "FastAPI is required for WebView. Install with: pip install fastapi uvicorn"
        )
        sys.exit(1)

    logger.info("Starting Process Hub Server with Admin Dashboard...")

    # Create ZMQ transport with broker
    transport = ZmqTransport(
        start_broker=True,
        xpub_port=5555,
        xsub_port=5556,
    )

    # Create a simple executor for process management
    executor = SimpleExecutor(stop_timeout=5.0)

    # Define process configurations
    python_exe = sys.executable
    process_config = {
        "example_process": {
            "script": python_exe,
            "args": [
                "-c",
                "import time; print('example_process running'); time.sleep(3600)",
            ],
            "wait_time": 1.0,
            "process_name": "example_process",
        },
        "worker_1": {
            "script": python_exe,
            "args": ["-c", "import time; print('Worker 1 running'); time.sleep(3600)"],
            "wait_time": 1.0,
            "process_name": "worker_1",
        },
        "worker_2": {
            "script": python_exe,
            "args": ["-c", "import time; print('Worker 2 running'); time.sleep(3600)"],
            "wait_time": 1.0,
            "process_name": "worker_2",
        },
        "long_running_task": {
            "script": python_exe,
            "args": [
                "-c",
                "import time; print('Long running task started'); time.sleep(3600)",
            ],
            "wait_time": 1.0,
            "process_name": "long_running_task",
        },
    }

    # =========================================================================
    # Define admin callbacks for process control
    # =========================================================================

    # Holder for server reference (will be set after server creation)
    # Used by admin callbacks to register/unregister processes
    server_holder = [None]

    def on_process_start(process_names: list[str]) -> dict[str, bool]:
        """
        Admin callback to start processes.

        Args:
            process_names: List of process names to start

        Returns:
            Dict mapping process name to success status
        """
        server = server_holder[0]
        results = {}

        for name in process_names:
            config = process_config.get(name, {})
            if not config:
                logger.warning("No config found for process: %s", name)
                results[name] = False
                continue

            logger.info("Admin starting process: %s", name)
            success, msg, pid = executor.start(name, config)
            results[name] = success

            if success:
                # Register the process in the server so it shows on dashboard
                if server and pid:
                    server.register_admin_process(name, pid)

                if "already running" in msg:
                    logger.info("Process %s is already running (PID %s)", name, pid)
                else:
                    logger.info("Process %s started with PID %s", name, pid)
            else:
                logger.error("Failed to start %s: %s", name, msg)

        return results

    def on_process_stop(process_names: list[str], force: bool) -> dict[str, bool]:
        """
        Admin callback to stop processes.

        Args:
            process_names: List of process names to stop
            force: If True, force kill the process

        Returns:
            Dict mapping process name to success status
        """
        server = server_holder[0]
        results = {}

        for name in process_names:
            logger.info("Admin stopping process: %s (force=%s)", name, force)
            success, msg = executor.stop(name, force=force)
            results[name] = success

            if success:
                # Unregister the process from the server
                if server:
                    server.unregister_admin_process(name)

                if "already stopped" in msg or "not running" in msg:
                    logger.info("Process %s was already stopped", name)
                else:
                    logger.info("Process %s stopped", name)
            else:
                logger.error("Failed to stop %s: %s", name, msg)

        return results

    def get_available_processes() -> list[str]:
        """
        Return list of available process names for autocomplete.

        Returns:
            List of process names from process_config
        """
        return list(process_config.keys())

    def get_process_config() -> dict[str, dict]:
        """
        Return all process configurations.

        Returns:
            Dict mapping process name to config dict
        """
        return process_config.copy()

    def add_process_config(name: str, config: dict) -> tuple[bool, str]:
        """
        Add a new process configuration.

        Args:
            name: Process name
            config: Process configuration dict

        Returns:
            Tuple of (success, message)
        """
        if name in process_config:
            return False, f"Process '{name}' already exists"

        # Validate required fields
        if not config.get("script"):
            return False, "Script path is required"

        process_config[name] = config
        logger.info("Added process config: %s", name)
        return True, f"Configuration '{name}' added successfully"

    def remove_process_config(name: str) -> tuple[bool, str]:
        """
        Remove a process configuration.

        Args:
            name: Process name to remove

        Returns:
            Tuple of (success, message)
        """
        if name not in process_config:
            return False, f"Process '{name}' not found"

        # Check if process is running
        if executor.is_running(name):
            return False, f"Cannot remove '{name}': process is running"

        del process_config[name]
        logger.info("Removed process config: %s", name)
        return True, f"Configuration '{name}' removed successfully"

    def update_process_config(name: str, config: dict) -> tuple[bool, str]:
        """
        Update an existing process configuration.

        Args:
            name: Process name to update
            config: New process configuration dict

        Returns:
            Tuple of (success, message)
        """
        if name not in process_config:
            return False, f"Process '{name}' not found"

        # Validate required fields
        if not config.get("script"):
            return False, "Script path is required"

        process_config[name] = config
        logger.info("Updated process config: %s", name)
        return True, f"Configuration '{name}' updated successfully"

    # =========================================================================
    # Create WebView with admin callbacks enabled
    # =========================================================================

    def reset_hub() -> tuple[bool, str]:
        """
        Reset the hub by removing all connections and stopping all processes.

        This uses the server's built-in reset method which:
        - Stops all managed processes
        - Clears all connections from the registry
        - Resets the restart state machine

        Returns:
            Tuple of (success, message)
        """
        server = server_holder[0]
        if server is None:
            return False, "Server not initialized"

        try:
            return server.reset()
        except Exception as e:
            logger.exception("Error resetting hub")
            return False, f"Error resetting hub: {str(e)}"

    view = WebView(
        host="127.0.0.1",  # Use "0.0.0.0" to allow external access
        port=2508,
        title="Process Hub Admin",
        on_process_start=on_process_start,  # Enable admin start
        on_process_stop=on_process_stop,  # Enable admin stop
        get_available_processes=get_available_processes,  # Enable autocomplete
        get_process_config=get_process_config,  # Enable config viewing
        add_process_config=add_process_config,  # Enable adding configs
        update_process_config=update_process_config,  # Enable updating configs
        remove_process_config=remove_process_config,  # Enable removing configs
        reset_hub=reset_hub,  # Enable hub reset
    )

    # Start the web view server
    view.start()

    # Create server
    server = ProcessHubServer(
        transport=transport,
        executor=executor,
        view=view,
        process_config=process_config,
        refresh_interval=0.5,
        restart_timeout=30.0,
    )

    # Set server reference for admin callbacks (start, stop, reset)
    server_holder[0] = server

    print()
    print("=" * 70)
    print("  ADMIN DASHBOARD")
    print("=" * 70)
    print()
    print(f"  Dashboard URL:    {view.url}")
    print(f"  API Docs:         {view.docs_url}")
    print(f"  Admin API:        ENABLED")
    print()
    print("  Available processes:")
    for name in process_config:
        print(f"    - {name}")
    print()
    print("  How to use:")
    print("    1. Open the dashboard in your browser")
    print("    2. Use the Start/Stop/Kill buttons in the Processes table")
    print("    3. Or use the Admin Controls section to start new processes")
    print()
    print("  Admin API endpoints:")
    print("    GET  /api/admin/status")
    print("    POST /api/admin/processes/{name}/start")
    print("    POST /api/admin/processes/{name}/stop?force=false")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 70)
    print()

    # Run the server (blocks until Ctrl+C)
    try:
        server.run()
    except KeyboardInterrupt:
        pass

    # Stop the web view
    view.stop()

    logger.info("Server stopped")


if __name__ == "__main__":
    main()
