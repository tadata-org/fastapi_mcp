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


@pytest.mark.anyio
async def test_http_list_tools(http_client: httpx.AsyncClient, server: str) -> None:
    """Test tool listing via HTTP POST with JSON response."""
    mcp_path = "/mcp"

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
    assert session_id is not None, "Server should return a session ID"

    initialized_response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "mcp-session-id": session_id,
        },
    )
    assert initialized_response.status_code == 202

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
            "mcp-session-id": session_id,
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
async def test_http_call_tool(http_client: httpx.AsyncClient, server: str) -> None:
    """Test tool calling via HTTP POST with JSON response."""
    mcp_path = "/mcp"

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
    assert session_id is not None, "Server should return a session ID"

    initialized_response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "mcp-session-id": session_id,
        },
    )
    assert initialized_response.status_code == 202

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
            "mcp-session-id": session_id,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 3
    assert "result" in result
    assert result["result"]["isError"] is False
    assert "content" in result["result"]
    assert len(result["result"]["content"]) > 0

    # Verify the response contains expected item data
    content = result["result"]["content"][0]
    assert content["type"] == "text"
    assert "Item 1" in content["text"]  # Should contain the item name


@pytest.mark.anyio
async def test_http_ping(http_client: httpx.AsyncClient, server: str) -> None:
    """Test ping functionality via HTTP POST."""
    mcp_path = "/mcp"

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
    assert session_id is not None, "Server should return a session ID"

    initialized_response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "mcp-session-id": session_id,
        },
    )
    assert initialized_response.status_code == 202

    response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "ping",
            "id": 4,
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "mcp-session-id": session_id,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 4
    assert "result" in result


@pytest.mark.anyio
async def test_http_error_handling(http_client: httpx.AsyncClient, server: str) -> None:
    """Test error handling for invalid requests."""
    mcp_path = "/mcp"

    response = await http_client.post(
        mcp_path,
        content="invalid json",
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
    )

    assert response.status_code == 400
    result = response.json()
    assert "error" in result
    assert result["error"]["code"] == -32700  # Parse error


@pytest.mark.anyio
async def test_http_invalid_method(http_client: httpx.AsyncClient, server: str) -> None:
    """Test error handling for invalid methods."""
    mcp_path = "/mcp"

    # First initialize to get a session ID
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
    assert session_id is not None, "Server should return a session ID"

    response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "invalid/method",
            "id": 5,
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "mcp-session-id": session_id,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 5
    assert "error" in result
    assert result["error"]["code"] == -32602  # Invalid request parameters


@pytest.mark.anyio
async def test_http_notification_handling(http_client: httpx.AsyncClient, server: str) -> None:
    """Test that notifications return 202 Accepted without response body."""
    mcp_path = "/mcp"

    # First initialize to get a session ID
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
    assert session_id is not None, "Server should return a session ID"

    response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "notifications/cancelled",
            "params": {"requestId": "test-123"},
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "mcp-session-id": session_id,
        },
    )

    assert response.status_code == 202
    # Notifications should return empty body
    assert response.content == b"" or response.text == "null"


@pytest.mark.anyio
async def test_http_accept_json_only(http_client: httpx.AsyncClient, server: str) -> None:
    """Test that HTTP transport accepts requests with only Accept: application/json.

    Standard HTTP JSON-RPC clients (e.g., Google Gemini CLI) only send
    Accept: application/json. The HTTP transport should handle this
    without returning a 406 Not Acceptable error.

    See: https://github.com/tadata-org/fastapi_mcp/issues/233
    """
    mcp_path = "/mcp"

    # Send request with only application/json Accept header (no text/event-stream)
    response = await http_client.post(
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
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )

    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}. "
        f"HTTP transport should accept requests with only Accept: application/json. "
        f"Response: {response.text}"
    )

    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 1
    assert "result" in result
    assert result["result"]["serverInfo"]["name"] == SERVER_NAME


@pytest.mark.anyio
async def test_http_accept_json_only_then_list_tools(http_client: httpx.AsyncClient, server: str) -> None:
    """Test a full session (initialize + list tools) using only Accept: application/json.

    Verifies that clients sending only application/json can complete a full
    MCP session lifecycle without hitting 406 errors.
    """
    mcp_path = "/mcp"

    # Initialize with only application/json
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
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    assert init_response.status_code == 200

    session_id = init_response.headers.get("mcp-session-id")
    assert session_id is not None

    # Send initialized notification with only application/json
    notif_response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "mcp-session-id": session_id,
        },
    )
    assert notif_response.status_code == 202

    # List tools with only application/json
    tools_response = await http_client.post(
        mcp_path,
        json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 2,
        },
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "mcp-session-id": session_id,
        },
    )
    assert tools_response.status_code == 200
    result = tools_response.json()
    assert "result" in result
    assert "tools" in result["result"]
    assert len(result["result"]["tools"]) > 0


class TestEnsureAcceptHeaders:
    """Unit tests for FastApiHttpSessionManager._ensure_accept_headers."""

    def _make_manager(self):  # type: ignore[no-untyped-def]
        from fastapi_mcp.transport.http import FastApiHttpSessionManager
        from unittest.mock import MagicMock

        mock_server = MagicMock()
        return FastApiHttpSessionManager(mcp_server=mock_server)

    def test_already_has_sse_header(self) -> None:
        """When text/event-stream is already present, scope is returned unchanged."""
        manager = self._make_manager()
        scope = {
            "headers": [
                (b"accept", b"application/json, text/event-stream"),
                (b"content-type", b"application/json"),
            ]
        }
        result = manager._ensure_accept_headers(scope)
        assert result is scope  # Same object, no copy needed

    def test_json_only_gets_sse_appended(self) -> None:
        """When only application/json is present, text/event-stream is appended."""
        manager = self._make_manager()
        scope = {
            "headers": [
                (b"accept", b"application/json"),
                (b"content-type", b"application/json"),
            ]
        }
        result = manager._ensure_accept_headers(scope)
        assert result is not scope  # New scope created

        accept_header = None
        for name, value in result["headers"]:
            if name == b"accept":
                accept_header = value
                break

        assert accept_header is not None
        assert b"application/json" in accept_header
        assert b"text/event-stream" in accept_header

    def test_no_accept_header_adds_both(self) -> None:
        """When no Accept header exists, both types are added."""
        manager = self._make_manager()
        scope = {
            "headers": [
                (b"content-type", b"application/json"),
            ]
        }
        result = manager._ensure_accept_headers(scope)
        assert result is not scope

        accept_header = None
        for name, value in result["headers"]:
            if name == b"accept":
                accept_header = value
                break

        assert accept_header is not None
        assert b"application/json" in accept_header
        assert b"text/event-stream" in accept_header

    def test_wildcard_accept_gets_sse_appended(self) -> None:
        """When Accept is */* (no explicit text/event-stream), SSE is appended."""
        manager = self._make_manager()
        scope = {
            "headers": [
                (b"accept", b"*/*"),
            ]
        }
        result = manager._ensure_accept_headers(scope)
        assert result is not scope

        accept_header = None
        for name, value in result["headers"]:
            if name == b"accept":
                accept_header = value
                break

        assert accept_header is not None
        assert b"text/event-stream" in accept_header

    def test_original_scope_not_mutated(self) -> None:
        """Ensure the original scope's headers list is not mutated."""
        manager = self._make_manager()
        original_headers = [
            (b"accept", b"application/json"),
            (b"content-type", b"application/json"),
        ]
        scope = {"headers": original_headers}
        manager._ensure_accept_headers(scope)

        # Original headers should be untouched
        assert len(original_headers) == 2
        assert original_headers[0] == (b"accept", b"application/json")
