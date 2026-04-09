"""Integration tests for streamable HTTP transport in stateless mode.

Stateless mode (``mount_http(stateless=True)``) is required for multi-replica
deployments behind a load balancer: without sticky-session routing on the
``Mcp-Session-Id`` header, stateful sessions break the moment a follow-up
request lands on a different replica.

These tests mirror the stateful tests in ``test_http_real_transport.py`` but
mount the server with ``stateless=True`` and assert the stateless invariants:

1. ``initialize`` responses must NOT carry an ``mcp-session-id`` header.
2. ``tools/list`` and ``tools/call`` must succeed without prior ``initialize``
   and without any session header plumbing.
"""

import atexit
import multiprocessing
import os
import signal
import socket
import sys
import threading
import time
from typing import AsyncGenerator, Generator

import coverage
import httpx
import mcp.types as types
import pytest
import uvicorn
from fastapi import FastAPI

from fastapi_mcp import FastApiMCP


HOST = "127.0.0.1"
SERVER_NAME = "Test MCP Server (stateless)"


def run_stateless_server(server_port: int, fastapi_app: FastAPI) -> None:
    # Initialize coverage for subprocesses
    cov = None
    if "COVERAGE_PROCESS_START" in os.environ:
        cov = coverage.Coverage(source=["fastapi_mcp"])
        cov.start()

        def cleanup():
            if cov:
                cov.stop()
                cov.save()

        atexit.register(cleanup)

        def handle_signal(signum, frame):
            cleanup()
            sys.exit(0)

        signal.signal(signal.SIGTERM, handle_signal)

        def periodic_save():
            while True:
                time.sleep(1.0)
                if cov:
                    cov.save()

        save_thread = threading.Thread(target=periodic_save)
        save_thread.daemon = True
        save_thread.start()

    # Configure the server in stateless mode
    mcp = FastApiMCP(
        fastapi_app,
        name=SERVER_NAME,
        description="Test description",
    )
    mcp.mount_http(stateless=True)

    server = uvicorn.Server(config=uvicorn.Config(app=fastapi_app, host=HOST, port=server_port, log_level="error"))
    server.run()

    while not server.started:
        time.sleep(0.5)

    if cov:
        cov.stop()
        cov.save()


@pytest.fixture(params=["simple_fastapi_app", "simple_fastapi_app_with_root_path"])
def stateless_server(request: pytest.FixtureRequest) -> Generator[str, None, None]:
    coverage_rc = os.path.abspath(".coveragerc")
    os.environ["COVERAGE_PROCESS_START"] = coverage_rc

    with socket.socket() as s:
        s.bind((HOST, 0))
        server_port = s.getsockname()[1]

    ctx = multiprocessing.get_context("fork")

    fastapi_app = request.getfixturevalue(request.param)
    proc = ctx.Process(
        target=run_stateless_server,
        kwargs={"server_port": server_port, "fastapi_app": fastapi_app},
        daemon=True,
    )
    proc.start()

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

    yield f"http://{HOST}:{server_port}{fastapi_app.root_path}"

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
async def stateless_http_client(stateless_server: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(base_url=stateless_server) as client:
        yield client


@pytest.mark.anyio
async def test_stateless_initialize_has_no_session_header(
    stateless_http_client: httpx.AsyncClient, stateless_server: str
) -> None:
    """Stateless initialize must not return an mcp-session-id header."""
    response = await stateless_http_client.post(
        "/mcp",
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

    assert response.status_code == 200
    result = response.json()
    assert result["result"]["serverInfo"]["name"] == SERVER_NAME

    # The invariant: stateless transport must not emit a session id.
    assert "mcp-session-id" not in {k.lower() for k in response.headers.keys()}, (
        f"Stateless transport leaked mcp-session-id header: {dict(response.headers)}"
    )


@pytest.mark.anyio
async def test_stateless_tools_list_without_session(
    stateless_http_client: httpx.AsyncClient, stateless_server: str
) -> None:
    """tools/list must succeed in stateless mode without prior initialize or session header."""
    response = await stateless_http_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 2,
        },
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 2
    assert "error" not in result, f"tools/list returned an error: {result}"
    assert "tools" in result["result"]
    tool_names = [tool["name"] for tool in result["result"]["tools"]]
    assert "get_item" in tool_names
    assert "list_items" in tool_names


@pytest.mark.anyio
async def test_stateless_call_tool_without_session(
    stateless_http_client: httpx.AsyncClient, stateless_server: str
) -> None:
    """tools/call must succeed in stateless mode without prior initialize or session header."""
    response = await stateless_http_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 3,
            "params": {
                "name": "get_item",
                "arguments": {"item_id": 1},
            },
        },
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 3
    assert result["result"]["isError"] is False
    content = result["result"]["content"][0]
    assert content["type"] == "text"
    assert "Item 1" in content["text"]
