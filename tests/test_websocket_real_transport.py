import atexit
import multiprocessing
import os
import signal
import socket
import sys
import threading
import time
from typing import Generator

import coverage
import pytest
import uvicorn
from mcp import InitializeResult
from mcp.client.session import ClientSession
from mcp.client.websocket import websocket_client
from mcp.types import EmptyResult, CallToolResult, ListToolsResult

from fastapi_mcp import FastApiMCP
from .fixtures.simple_app import make_simple_fastapi_app

HOST = "127.0.0.1"
SERVER_NAME = "Test MCP WebSocket Server"


@pytest.fixture
def server_port() -> int:
    with socket.socket() as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


@pytest.fixture
def server_url(server_port: int) -> str:
    return f"http://{HOST}:{server_port}"


@pytest.fixture
def websocket_url(server_port: int) -> str:
    return f"ws://{HOST}:{server_port}/mcp"


def run_websocket_server(server_port: int) -> None:
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

    # Configure the server with WebSocket transport
    fastapi = make_simple_fastapi_app()
    mcp = FastApiMCP(
        fastapi,
        name=SERVER_NAME,
        description="Test WebSocket description",
    )
    mcp.mount(transport="websocket")

    # Start the server
    server = uvicorn.Server(config=uvicorn.Config(app=fastapi, host=HOST, port=server_port, log_level="error"))
    server.run()

    # Give server time to start
    while not server.started:
        time.sleep(0.5)

    # Ensure coverage is saved if exiting the normal way
    if cov:
        cov.stop()
        cov.save()


@pytest.fixture()
def websocket_server(server_port: int) -> Generator[None, None, None]:
    # Ensure COVERAGE_PROCESS_START is set in the environment for subprocesses
    coverage_rc = os.path.abspath(".coveragerc")
    if os.path.exists(coverage_rc):
        os.environ["COVERAGE_PROCESS_START"] = coverage_rc

    # Start server process
    process = multiprocessing.Process(target=run_websocket_server, args=(server_port,))
    process.start()

    # Wait for server to be ready
    time.sleep(2)

    yield

    # Clean up
    process.terminate()
    process.join(timeout=5)
    if process.is_alive():
        process.kill()
        process.join()


@pytest.mark.anyio
async def test_websocket_basic_connection(websocket_server: None, websocket_url: str) -> None:
    """Test basic WebSocket connection to MCP server."""
    async with websocket_client(websocket_url) as streams:
        async with ClientSession(*streams) as session:
            # Test initialization
            result = await session.initialize()
            assert isinstance(result, InitializeResult)
            assert result.serverInfo.name == SERVER_NAME

            # Test ping
            ping_result = await session.send_ping()
            assert isinstance(ping_result, EmptyResult)


@pytest.mark.anyio
async def test_websocket_tool_listing(websocket_server: None, websocket_url: str) -> None:
    """Test listing tools via WebSocket connection."""
    async with websocket_client(websocket_url) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()

            # List tools
            tools_result = await session.list_tools()
            assert isinstance(tools_result, ListToolsResult)
            assert len(tools_result.tools) > 0

            # Check for expected tools from simple app
            tool_names = [tool.name for tool in tools_result.tools]
            expected_operations = ["list_items", "get_item", "create_item", "update_item", "delete_item"]
            for op in expected_operations:
                assert op in tool_names


@pytest.mark.anyio
async def test_websocket_tool_call(websocket_server: None, websocket_url: str) -> None:
    """Test calling a tool via WebSocket connection."""
    async with websocket_client(websocket_url) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()

            # Call a tool
            result = await session.call_tool("get_item", {"item_id": 1})
            assert isinstance(result, CallToolResult)
            assert not result.isError
            assert len(result.content) > 0


@pytest.mark.anyio
async def test_websocket_error_handling(websocket_server: None, websocket_url: str) -> None:
    """Test error handling via WebSocket connection."""
    async with websocket_client(websocket_url) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()

            # Call tool with invalid parameters to trigger an error
            result = await session.call_tool("get_item", {})  # Missing required item_id
            assert isinstance(result, CallToolResult)
            assert result.isError
            assert len(result.content) > 0


@pytest.mark.anyio
async def test_websocket_complex_tool_call(websocket_server: None, websocket_url: str) -> None:
    """Test calling a tool with complex parameters via WebSocket."""
    async with websocket_client(websocket_url) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()

            # Create a new item
            test_item = {
                "id": 999,
                "name": "WebSocket Test Item",
                "description": "An item created via WebSocket",
                "price": 19.99,
                "tags": ["websocket", "test"],
            }

            result = await session.call_tool("create_item", test_item)
            assert isinstance(result, CallToolResult)
            assert not result.isError
            assert len(result.content) > 0
