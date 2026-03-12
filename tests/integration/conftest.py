"""Pytest configuration for integration tests."""

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest


def is_server_available(host="localhost", port=4840, timeout=1.0):
    """Check if OPC UA server is available."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def wait_for_server(host="localhost", port=4840, timeout=10.0, check_interval=0.2):
    """
    Wait for OPC UA server to become available.

    Args:
        host: Server hostname
        port: Server port
        timeout: Maximum seconds to wait
        check_interval: Seconds between checks

    Returns:
        True if server became available, False if timeout
    """
    elapsed = 0.0
    while elapsed < timeout:
        if is_server_available(host, port, timeout=1.0):
            return True
        time.sleep(check_interval)
        elapsed += check_interval
    return False


@pytest.fixture(scope="session")
def opcua_test_server():
    """
    Start OPC UA replay server for integration tests.

    Automatically starts the server with test data, waits for it to be ready,
    yields to tests, then cleanly shuts down.

    Yields:
        dict with server info (endpoint, api_base, process)
    """
    # Check if server is already running
    if is_server_available():
        # Use existing server
        print("\n⚠ OPC UA server already running on localhost:4840 - using existing server")
        yield {
            "endpoint": "opc.tcp://localhost:4840/",
            "api_base": "http://localhost:8080",
            "process": None,
            "using_existing": True,
        }
        return

    # Start new server
    fixtures_dir = Path(__file__).parent / "fixtures"
    test_data = fixtures_dir / "test-data.csv"

    if not test_data.exists():
        pytest.fail(f"Test data not found: {test_data}")

    print(f"\n🚀 Starting OPC UA test server with {test_data.name}...")

    try:
        # Start server process
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "opc_replay.server",
                "--data",
                str(test_data),
                "--ts-col",
                "TS",
                "--auto-nodeset",
                "--loop",
                "--speed",
                "10",
                "--api-port",
                "8080",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=Path(__file__).parent.parent.parent,  # workspace root
        )

        # Wait for server to be ready
        print("   Waiting for server to be ready...", end="", flush=True)
        if not wait_for_server(timeout=10.0):
            # Server failed to start - capture output
            stdout, stderr = process.communicate(timeout=1.0)
            process.kill()
            pytest.fail(
                f"OPC UA server failed to start within 10s\n"
                f"stdout: {stdout.decode()}\n"
                f"stderr: {stderr.decode()}"
            )

        print(" ✓ Server ready")

        # Yield server info to tests
        yield {
            "endpoint": "opc.tcp://localhost:4840/",
            "api_base": "http://localhost:8080",
            "process": process,
            "using_existing": False,
        }

    finally:
        # Cleanup: stop server if we started it
        if process is not None and process.poll() is None:
            print("\n🛑 Stopping OPC UA test server...")
            process.terminate()
            try:
                process.wait(timeout=5.0)
                print("   ✓ Server stopped cleanly")
            except subprocess.TimeoutExpired:
                print("   ⚠ Server didn't stop gracefully, killing...")
                process.kill()
                process.wait()


@pytest.fixture(scope="session")
def opcua_server_available():
    """Fixture that checks if OPC UA server is available."""
    return is_server_available()


@pytest.fixture(scope="session")
def require_opcua_server(opcua_server_available):
    """Fixture that skips test if OPC UA server is not available."""
    if not opcua_server_available:
        pytest.skip("OPC UA server not available (requires server running on localhost:4840)")
