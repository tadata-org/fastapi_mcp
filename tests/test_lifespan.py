"""
Tests for lifespan context manager support with mount_http().

Regression tests for:
  https://github.com/tadata-org/fastapi_mcp/issues/256

When mount_http() is used, the FastAPI app's lifespan startup/shutdown events
must fire correctly and not be suppressed by the ASGI lifespan protocol.
"""

import asyncio
from contextlib import asynccontextmanager

import pytest
import httpx
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP
import mcp.types as types


# ---------------------------------------------------------------------------
# ASGI lifespan helper
# ---------------------------------------------------------------------------

@asynccontextmanager
async def run_asgi_lifespan(app: FastAPI):
    """
    Manually drive the ASGI lifespan protocol for an app in tests.

    httpx.ASGITransport only sends 'http' scoped requests — it never sends
    the 'lifespan' scope. This helper fills that gap by manually sending
    lifespan.startup / lifespan.shutdown events to the ASGI app, which is
    exactly what uvicorn does in production.
    """
    receive_q: asyncio.Queue = asyncio.Queue()
    send_q: asyncio.Queue = asyncio.Queue()

    async def receive():
        return await receive_q.get()

    async def send(message):
        await send_q.put(message)

    scope = {"type": "lifespan", "asgi": {"version": "3.0"}, "state": {}}
    lifespan_task = asyncio.create_task(app(scope, receive, send))

    # Trigger startup
    await receive_q.put({"type": "lifespan.startup"})
    startup_msg = await asyncio.wait_for(send_q.get(), timeout=5.0)
    assert startup_msg["type"] == "lifespan.startup.complete", (
        f"Expected lifespan.startup.complete, got: {startup_msg}"
    )

    try:
        yield
    finally:
        # Trigger shutdown
        await receive_q.put({"type": "lifespan.shutdown"})
        try:
            await asyncio.wait_for(send_q.get(), timeout=3.0)
        except asyncio.TimeoutError:
            pass

        # Clean up the background lifespan task
        if not lifespan_task.done():
            lifespan_task.cancel()
        try:
            await asyncio.wait_for(lifespan_task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lifespan_app():
    """Return (app, events) where events records startup/shutdown calls."""
    events: list[str] = []

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        events.append("startup")
        yield
        events.append("shutdown")

    app = FastAPI(title="Lifespan Test App", lifespan=lifespan)

    @app.get("/health", operation_id="health_check")
    async def health():
        return {"status": "healthy"}

    return app, events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_lifespan_startup_fires_with_mount_http():
    """on_startup events must run when mount_http() is used (issue #256)."""
    app, events = _make_lifespan_app()
    mcp = FastApiMCP(app)
    mcp.mount_http()

    async with run_asgi_lifespan(app):
        assert "startup" in events, "lifespan startup event was not triggered"

    assert "shutdown" in events, "lifespan shutdown event was not triggered"


@pytest.mark.anyio
async def test_lifespan_order():
    """startup must happen before shutdown and both must occur exactly once."""
    app, events = _make_lifespan_app()
    mcp = FastApiMCP(app)
    mcp.mount_http()

    async with run_asgi_lifespan(app):
        pass  # startup already done by now

    assert events == ["startup", "shutdown"], f"Unexpected event order: {events}"


@pytest.mark.anyio
async def test_lifespan_resource_available_during_request():
    """Resources initialised in the lifespan must be accessible during tool calls."""
    db_state: dict = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db_state["connected"] = True
        yield
        db_state["connected"] = False

    app = FastAPI(title="DB App", lifespan=lifespan)

    @app.get("/db-status", operation_id="db_status")
    async def db_status():
        return {"connected": db_state.get("connected", False)}

    mcp = FastApiMCP(app)
    mcp.mount_http()

    async with run_asgi_lifespan(app):
        assert db_state.get("connected") is True

        # Make an HTTP request while lifespan is active
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/db-status")
            assert response.status_code == 200
            assert response.json()["connected"] is True

    # After shutdown the resource must be cleaned up
    assert db_state.get("connected") is False


@pytest.mark.anyio
async def test_mcp_endpoint_reachable_after_lifespan_startup():
    """The /mcp endpoint must respond after lifespan startup completes."""
    app, events = _make_lifespan_app()
    mcp = FastApiMCP(app)
    mcp.mount_http()

    async with run_asgi_lifespan(app):
        assert "startup" in events

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
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
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
            )

            assert response.status_code == 200
            result = response.json()
            assert result["jsonrpc"] == "2.0"
            assert "result" in result

    assert "shutdown" in events


@pytest.mark.anyio
async def test_no_lifespan_still_works():
    """Apps without a lifespan context manager must continue to work fine."""
    app = FastAPI(title="No Lifespan App")

    @app.get("/ping", operation_id="ping")
    async def ping():
        return {"pong": True}

    mcp = FastApiMCP(app)
    mcp.mount_http()

    async with run_asgi_lifespan(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
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
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
            )
            assert response.status_code == 200


@pytest.mark.anyio
async def test_session_manager_starts_after_user_startup():
    """
    The MCP session manager must start AFTER the user's startup so that tools
    can access resources initialised in the lifespan.
    """
    order: list[str] = []

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        order.append("user_startup")
        yield
        order.append("user_shutdown")

    app = FastAPI(title="Order App", lifespan=lifespan)

    @app.get("/noop", operation_id="noop")
    async def noop():
        return {}

    mcp = FastApiMCP(app)
    mcp.mount_http()

    # Patch startup/shutdown to record order
    original_startup = mcp._http_transport.startup
    original_shutdown = mcp._http_transport.shutdown

    async def patched_startup():
        order.append("mcp_startup")
        await original_startup()

    async def patched_shutdown():
        order.append("mcp_shutdown")
        await original_shutdown()

    mcp._http_transport.startup = patched_startup
    mcp._http_transport.shutdown = patched_shutdown

    async with run_asgi_lifespan(app):
        pass

    # user startup must come before MCP startup
    assert order.index("user_startup") < order.index("mcp_startup"), (
        f"Expected user_startup before mcp_startup, got: {order}"
    )
    # MCP shutdown must come before user shutdown
    assert order.index("mcp_shutdown") < order.index("user_shutdown"), (
        f"Expected mcp_shutdown before user_shutdown, got: {order}"
    )
