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
SERVER_NAME = "Test Stateless MCP Server"


def run_server(server_port: int, fastapi_app: FastAPI, stateless: bool = False) -> None:
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
    mcp.mount_http(stateless=stateless)

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


@pytest.fixture(params=[False, True])
def stateless_mode(request: pytest.FixtureRequest) -> bool:
    return request.param


@pytest.fixture(params=["simple_fastapi_app"])
def server(request: pytest.FixtureRequest, stateless_mode: bool) -> Generator[str, None, None]:
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
        kwargs={"server_port": server_port, "fastapi_app": fastapi_app, "stateless": stateless_mode},
        daemon=True,
    )
    proc.start()

    # Wait for server to start
    time.sleep(2)

    # Return the server URL
    yield f"http://{HOST}:{server_port}{fastapi_app.root_path}"

    # Clean up
    proc.terminate()
    proc.join(timeout=5)
    if proc.is_alive():
        proc.kill()
        proc.join()


@pytest.fixture()
async def http_client(server: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(base_url=server) as client:
        yield client


@pytest.mark.anyio
async def test_stateless_initialize_request(http_client: httpx.AsyncClient, server: str, stateless_mode: bool) -> None:
    """Test that initialize request works in both stateless and stateful modes."""
    mcp_path = "/mcp"

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

    # Check session ID behavior
    session_id = response.headers.get("mcp-session-id")
    if stateless_mode:
        # In stateless mode, session ID should be None or empty
        assert session_id is None or session_id == ""
    else:
        # In stateful mode, session ID should be present
        assert session_id is not None


@pytest.mark.anyio
async def test_stateless_list_tools(http_client: httpx.AsyncClient, server: str, stateless_mode: bool) -> None:
    """Test tool listing in both stateless and stateful modes."""
    mcp_path = "/mcp"

    # Initialize the connection
    init_response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {
                "protocolVersion": types.LATEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        },
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
    )
    assert init_response.status_code == 200

    # Extract session ID from the initialize response
    session_id = init_response.headers.get("mcp-session-id")

    # Send initialized notification
    initialized_response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **({"mcp-session-id": session_id} if not stateless_mode else {}),
        },
    )
    assert initialized_response.status_code == 202

    # List tools
    response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 2,
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **({"mcp-session-id": session_id} if not stateless_mode else {}),
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 2
    assert "result" in result
    assert "tools" in result["result"]
    assert len(result["result"]["tools"]) > 0

    # Verify we have the expected tools from the simple FastAPI app
    tool_names = [tool["name"] for tool in result["result"]["tools"]]
    assert "get_item" in tool_names
    assert "list_items" in tool_names


@pytest.mark.anyio
async def test_stateless_call_tool(http_client: httpx.AsyncClient, server: str, stateless_mode: bool) -> None:
    """Test tool calling in both stateless and stateful modes."""
    mcp_path = "/mcp"

    # Initialize the connection
    init_response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {
                "protocolVersion": types.LATEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        },
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
    )
    assert init_response.status_code == 200

    # Extract session ID from the initialize response
    session_id = init_response.headers.get("mcp-session-id")

    # Send initialized notification
    initialized_response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **({"mcp-session-id": session_id} if not stateless_mode else {}),
        },
    )
    assert initialized_response.status_code == 202

    # Call a tool
    response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 3,
            "params": {
                "name": "get_item",
                "arguments": {"item_id": 1},
            },
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **({"mcp-session-id": session_id} if not stateless_mode else {}),
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 3
    assert "result" in result
    assert "content" in result["result"]


@pytest.mark.anyio
async def test_stateless_ignores_session_header(
    http_client: httpx.AsyncClient, server: str, stateless_mode: bool
) -> None:
    """Test that stateless mode ignores mcp-session-id header even when provided."""
    mcp_path = "/mcp"

    if not stateless_mode:
        pytest.skip("Skipping test for stateful mode")

    # Initialize the connection
    init_response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {
                "protocolVersion": types.LATEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        },
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
    )
    assert init_response.status_code == 200

    # Send initialized notification with a fake session ID
    fake_session_id = "fake-session-id-12345"
    initialized_response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "mcp-session-id": fake_session_id,  # Use fake session ID
        },
    )
    assert initialized_response.status_code == 202

    # List tools with fake session ID
    response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 2,
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "mcp-session-id": fake_session_id,  # Use fake session ID
        },
    )

    # Should work regardless of the session ID in stateless mode
    assert response.status_code == 200
    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 2
    assert "result" in result
    assert "tools" in result["result"]
