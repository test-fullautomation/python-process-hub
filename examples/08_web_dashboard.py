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
# File: 08_web_dashboard.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Example demonstrating the WebView dashboard.
#   Shows how to run the Process Hub with a web-based UI.
#
# Usage:
#   1. Install dependencies: pip install fastapi uvicorn
#   2. Run this script: python 08_web_dashboard.py
#   3. Open browser to http://localhost:2507 (API docs at /docs)
#   4. Run a client in another terminal: python 02_basic_client.py
#
# *******************************************************************************
"""
Web Dashboard Example.

This example demonstrates how to:
1. Create a ProcessHubServer with WebView
2. Access the dashboard via web browser
3. Monitor processes and connections in real-time

Requirements:
    pip install fastapi uvicorn

The dashboard provides:
- Real-time process status display
- Connection monitoring
- Restart state visualization
- Automatic refresh every second
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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Reduce noise from uvicorn
logging.getLogger("uvicorn").setLevel(logging.WARNING)


def main():
    """Run the Process Hub Server with WebView."""
    # Check if FastAPI is available
    try:
        from ProcessHub.ui import WebView
    except ImportError:
        logger.error("FastAPI is required for WebView. Install with: pip install fastapi uvicorn")
        sys.exit(1)

    logger.info("Starting Process Hub Server with Web Dashboard...")

    # Create ZMQ transport with broker
    transport = ZmqTransport(
        start_broker=True,
        xpub_port=5555,
        xsub_port=5556,
    )

    # Create a simple executor for process management
    executor = SimpleExecutor(stop_timeout=5.0)

    # Create WebView for browser-based dashboard
    view = WebView(
        host="127.0.0.1",  # Use "0.0.0.0" to allow external access
        port=2507,
    )

    # Start the web view server
    view.start()

    # Define process configurations
    python_exe = sys.executable
    process_config = {
        "example_process": {
            "script": python_exe,
            "args": ["-c", "import time; print('example_process running'); time.sleep(3600)"],
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
    }

    # Create server
    server = ProcessHubServer(
        transport=transport,
        executor=executor,
        view=view,
        process_config=process_config,
        refresh_interval=0.5,
        restart_timeout=30.0,
    )

    logger.info("=" * 60)
    logger.info("Web Dashboard available at: %s", view.url)
    logger.info("API Documentation at: %s", view.docs_url)
    logger.info("ZMQ Server listening on ports 5555 (XPUB) and 5556 (XSUB)")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Open your browser to: %s", view.url)
    logger.info("")
    logger.info("Then run a client in another terminal:")
    logger.info("  python 02_basic_client.py")
    logger.info("")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)

    # Run the server (blocks until Ctrl+C)
    server.run()

    # Stop the web view
    view.stop()

    logger.info("Server stopped")


if __name__ == "__main__":
    main()
