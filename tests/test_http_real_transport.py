import multiprocessing
import socket
import time
import os
import signal
import atexit
import sys
import threading
import coverage
from typing import AsyncGenerator, Generator
from fastapi import FastAPI
import pytest
import httpx
import uvicorn
from fastapi_mcp import FastApiMCP
import mcp.types as types


HOST = "127.0.0.1"
SERVER_NAME = "Test MCP Server"


def run_server(server_port: int, fastapi_app: FastAPI) -> None:
    # Initialize coverage for subprocesses
    cov = None
    if "COVERAGE_PROCESS_START" in os.environ:
        cov = coverage.Coverage(source=["fastapi_mcp"])
        cov.start()

        # Create a function to save coverage data at exit
        def cleanup():
            if cov:
                cov.stop()
                cov.save()

        # Register multiple cleanup mechanisms to ensure coverage data is saved
        atexit.register(cleanup)

        # Setup signal handler for clean termination
        def handle_signal(signum, frame):
            cleanup()
            sys.exit(0)

        signal.signal(signal.SIGTERM, handle_signal)

        # Backup thread to ensure coverage is written if process is terminated abruptly
        def periodic_save():
            while True:
                time.sleep(1.0)
                if cov:
                    cov.save()

        save_thread = threading.Thread(target=periodic_save)
        save_thread.daemon = True
        save_thread.start()

    # Configure the server
    mcp = FastApiMCP(
        fastapi_app,
        name=SERVER_NAME,
        description="Test description",
    )
    mcp.mount_http()

    # Start the server
    server = uvicorn.Server(config=uvicorn.Config(app=fastapi_app, host=HOST, port=server_port, log_level="error"))
    server.run()

    # Give server time to start
    while not server.started:
        time.sleep(0.5)

    # Ensure coverage is saved if exiting the normal way
    if cov:
        cov.stop()
        cov.save()


@pytest.fixture(params=["simple_fastapi_app", "simple_fastapi_app_with_root_path"])
def server(request: pytest.FixtureRequest) -> Generator[str, None, None]:
    # Ensure COVERAGE_PROCESS_START is set in the environment for subprocesses
    coverage_rc = os.path.abspath(".coveragerc")
    os.environ["COVERAGE_PROCESS_START"] = coverage_rc

    # Get a free port
    with socket.socket() as s:
        s.bind((HOST, 0))
        server_port = s.getsockname()[1]

    # Use fork method to avoid pickling issues
    ctx = multiprocessing.get_context("fork")

    # Run the server in a subprocess
    fastapi_app = request.getfixturevalue(request.param)
    proc = ctx.Process(
        target=run_server,
        kwargs={"server_port": server_port, "fastapi_app": fastapi_app},
        daemon=True,
    )
    proc.start()

    # Wait for server to be running
    max_attempts = 20
    attempt = 0
    while attempt < max_attempts:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((HOST, server_port))
                break
        except ConnectionRefusedError:
            time.sleep(0.1)
            attempt += 1
    else:
        raise RuntimeError(f"Server failed to start after {max_attempts} attempts")

    # Return the server URL
    yield f"http://{HOST}:{server_port}{fastapi_app.root_path}"

    # Signal the server to stop - added graceful shutdown before kill
    try:
        proc.terminate()
        proc.join(timeout=2)
    except (OSError, AttributeError):
        pass

    if proc.is_alive():
        proc.kill()
        proc.join(timeout=2)
        if proc.is_alive():
            raise RuntimeError("server process failed to terminate")


@pytest.fixture()
async def http_client(server: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(base_url=server) as client:
        yield client


@pytest.mark.anyio
async def test_http_initialize_request(http_client: httpx.AsyncClient, server: str) -> None:
    mcp_path = "/mcp"  # Always use absolute path since server already includes root_path

    response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {
                "protocolVersion": types.LATEST_PROTOCOL_VERSION,
                "capabilities": {
                    "sampling": None,
                    "elicitation": None,
                    "experimental": None,
                    "roots": None,
                },
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        },
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
    )

    assert response.status_code == 200

    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 1
    assert "result" in result
    assert result["result"]["serverInfo"]["name"] == SERVER_NAME
