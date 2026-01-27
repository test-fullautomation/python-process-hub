#!/usr/bin/env python
"""
Simple test script to verify ZMQ communication between server and client.

Run this script to test if basic ZMQ pub/sub is working.
"""

import logging
import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ProcessHub.transport.zmq_transport import ZmqTransport

logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for verbose output
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Test topics
TEST_REQUEST = "TEST_REQUEST"
TEST_RESPONSE = "TEST_RESPONSE"

# Flags to track message receipt
server_received = threading.Event()
client_received = threading.Event()


def run_server():
    """Run a simple server that echoes messages."""
    logger.info("=== Starting Server ===")

    # Create server transport (with broker)
    transport = ZmqTransport(
        start_broker=True,
        xpub_port=5555,
        xsub_port=5556,
    )

    # Register handler for requests
    def on_request(data):
        logger.info("[SERVER] Received request: %s", data)
        server_received.set()

        # Send response back
        response = {"status": "ok", "echo": data}
        logger.info("[SERVER] Sending response: %s", response)
        transport.send(TEST_RESPONSE, response)

    transport.register_handler(TEST_REQUEST, on_request)

    # Start transport
    transport.start()
    logger.info("[SERVER] Transport started, listening...")

    # Wait for test to complete
    time.sleep(10)

    transport.stop()
    logger.info("[SERVER] Stopped")


def run_client():
    """Run a simple client that sends a request and waits for response."""
    # Give server time to start
    time.sleep(1)

    logger.info("=== Starting Client ===")

    # Create client transport (no broker)
    transport = ZmqTransport(
        start_broker=False,
        xpub_port=5555,
        xsub_port=5556,
    )

    # Register handler for responses
    def on_response(data):
        logger.info("[CLIENT] Received response: %s", data)
        client_received.set()

    transport.register_handler(TEST_RESPONSE, on_response)

    # Start transport
    transport.start()
    logger.info("[CLIENT] Transport started")

    # Give subscription time to propagate
    time.sleep(0.5)

    # Send request
    request = {"message": "Hello from client!", "timestamp": time.time()}
    logger.info("[CLIENT] Sending request: %s", request)
    transport.send(TEST_REQUEST, request)

    # Wait for response
    logger.info("[CLIENT] Waiting for response...")
    if client_received.wait(timeout=5.0):
        logger.info("[CLIENT] Response received successfully!")
    else:
        logger.error("[CLIENT] Timeout waiting for response!")

    transport.stop()
    logger.info("[CLIENT] Stopped")


def main():
    """Run the test."""
    logger.info("=" * 60)
    logger.info("ZMQ Communication Test")
    logger.info("=" * 60)

    # Start server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Run client in main thread
    run_client()

    # Check results
    logger.info("")
    logger.info("=" * 60)
    logger.info("Results:")
    logger.info("  Server received request: %s", server_received.is_set())
    logger.info("  Client received response: %s", client_received.is_set())

    if server_received.is_set() and client_received.is_set():
        logger.info("SUCCESS: ZMQ communication is working!")
    else:
        logger.error("FAILURE: Communication problem detected")
        if not server_received.is_set():
            logger.error("  - Server did not receive the request")
        if not client_received.is_set():
            logger.error("  - Client did not receive the response")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
