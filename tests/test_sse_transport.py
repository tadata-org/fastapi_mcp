import anyio
import multiprocessing
import socket
import time
from typing import AsyncGenerator, Generator
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp import InitializeResult
from mcp.types import EmptyResult, CallToolResult, ListToolsResult
import pytest
import httpx
import uvicorn
from fastapi_mcp import FastApiMCP

from .fixtures.simple_app import make_simple_fastapi_app


HOST = "127.0.0.1"
SERVER_NAME = "Test MCP Server"


@pytest.fixture
def server_port() -> int:
    with socket.socket() as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


@pytest.fixture
def server_url(server_port: int) -> str:
    return f"http://{HOST}:{server_port}"


def run_server(server_port: int) -> None:
    fastapi = make_simple_fastapi_app()
    mcp = FastApiMCP(
        fastapi,
        name=SERVER_NAME,
        description="Test description",
    )
    mcp.mount()

    server = uvicorn.Server(config=uvicorn.Config(app=fastapi, host=HOST, port=server_port, log_level="error"))
    server.run()

    # Give server time to start
    while not server.started:
        time.sleep(0.5)


@pytest.fixture()
def server(server_port: int) -> Generator[None, None, None]:
    proc = multiprocessing.Process(target=run_server, kwargs={"server_port": server_port}, daemon=True)
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

    yield

    # Signal the server to stop
    proc.kill()
    proc.join(timeout=2)
    if proc.is_alive():
        raise RuntimeError("server process failed to terminate")


@pytest.fixture()
async def http_client(server: None, server_url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(base_url=server_url) as client:
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
async def test_sse_basic_connection(server: None, server_url: str) -> None:
    async with sse_client(server_url + "/mcp") as streams:
        async with ClientSession(*streams) as session:
            # Test initialization
            result = await session.initialize()
            assert isinstance(result, InitializeResult)
            assert result.serverInfo.name == SERVER_NAME

            # Test ping
            ping_result = await session.send_ping()
            assert isinstance(ping_result, EmptyResult)


@pytest.mark.anyio
async def test_sse_tool_call(server: None, server_url: str) -> None:
    async with sse_client(server_url + "/mcp") as streams:
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
