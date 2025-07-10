import anyio
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
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp import InitializeResult
from mcp.types import EmptyResult, CallToolResult, ListToolsResult
import pytest
import httpx
import uvicorn
from fastapi_mcp import FastApiMCP


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
    mcp.mount()

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
async def test_raw_sse_connection(http_client: httpx.AsyncClient) -> None:
    """Test the SSE connection establishment simply with an HTTP client."""
    async with anyio.create_task_group():

        async def connection_test() -> None:
            async with http_client.stream("GET", "/mcp") as response:
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

                line_number = 0
                async for line in response.aiter_lines():
                    if line_number == 0:
                        assert line == "event: endpoint"
                    elif line_number == 1:
                        assert line.startswith("data: /mcp/messages/?session_id=")
                    else:
                        return
                    line_number += 1

        # Add timeout to prevent test from hanging if it fails
        with anyio.fail_after(3):
            await connection_test()


@pytest.mark.anyio
async def test_sse_basic_connection(server: str) -> None:
    async with sse_client(server + "/mcp") as streams:
        async with ClientSession(*streams) as session:
            # Test initialization
            result = await session.initialize()
            assert isinstance(result, InitializeResult)
            assert result.serverInfo.name == SERVER_NAME

            # Test ping
            ping_result = await session.send_ping()
            assert isinstance(ping_result, EmptyResult)


@pytest.mark.anyio
async def test_sse_tool_call(server: str) -> None:
    async with sse_client(server + "/mcp") as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()

            tools_list_result = await session.list_tools()
            assert isinstance(tools_list_result, ListToolsResult)
            assert len(tools_list_result.tools) > 0

            tool_call_result = await session.call_tool("get_item", {"item_id": 1})
            assert isinstance(tool_call_result, CallToolResult)
            assert not tool_call_result.isError
            assert tool_call_result.content is not None
            assert len(tool_call_result.content) > 0
