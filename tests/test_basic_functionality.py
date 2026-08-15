from importlib.metadata import version as pkg_version

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from mcp.server.lowlevel.server import Server
from packaging.version import Version

from fastapi_mcp import FastApiMCP

# FastAPI >= 0.137.0 stopped flattening `include_router()`'d sub-routes into
# `app.routes`; it now records each inclusion as a `_IncludedRouter` object carrying
# `.original_router` / `.include_context.prefix` instead. `_resolve_router_include_prefix`
# uses that metadata when available (see fastapi_mcp/server.py), which is strictly more
# capable than the path-diffing fallback used on older FastAPI: it can resolve a router's
# prefix even when the router has no routes of its own, and it can't be confused by two
# routers sharing the same endpoint function. A few of the tests below only hold on one
# side of that boundary; they say so explicitly rather than silently skip.
FASTAPI_HAS_INCLUDED_ROUTER_METADATA = Version(pkg_version("fastapi")) >= Version("0.137.0")


def _mcp_endpoint_exists(app: FastAPI, path: str) -> bool:
    """
    Whether an MCP streamable-HTTP endpoint is actually reachable at `path`.

    Deliberately goes through a real request/response cycle instead of inspecting
    `app.routes` -- FastAPI's internal route-table representation is not a stable
    contract (see FASTAPI_HAS_INCLUDED_ROUTER_METADATA above), so asserting on it
    directly is what let the fastapi>=0.137 regression slip through review previously.
    """
    client = TestClient(app)
    response = client.post(
        path,
        json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        },
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
    )
    return response.status_code != 404


def test_create_mcp_server(simple_fastapi_app: FastAPI):
    """Test creating an MCP server without mounting it."""
    mcp = FastApiMCP(
        simple_fastapi_app,
        name="Test MCP Server",
        description="Test description",
    )

    # Verify the MCP server was created correctly
    assert mcp.name == "Test MCP Server"
    assert mcp.description == "Test description"
    assert isinstance(mcp.server, Server)
    assert len(mcp.tools) > 0, "Should have extracted tools from the app"
    assert len(mcp.operation_map) > 0, "Should have operation mapping"

    # Check that the operation map contains all expected operations from simple_app
    expected_operations = ["list_items", "get_item", "create_item", "update_item", "delete_item", "raise_error"]
    for op in expected_operations:
        assert op in mcp.operation_map, f"Operation {op} not found in operation map"


def test_default_values(simple_fastapi_app: FastAPI):
    """Test that default values are used when not explicitly provided."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Verify default values
    assert mcp.name == simple_fastapi_app.title
    assert mcp.description == simple_fastapi_app.description

    # Mount with default path
    mcp.mount()

    # Check that the MCP server was properly mounted
    # Look for a route that includes our mount path in its pattern
    route_found = any("/mcp" in str(route) for route in simple_fastapi_app.routes)
    assert route_found, "MCP server mount point not found in app routes"


def test_normalize_paths(simple_fastapi_app: FastAPI):
    """Test that mount paths are normalized correctly."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Test with path without leading slash
    mount_path = "test-mcp"
    mcp.mount(mount_path=mount_path)

    # Check that the route was added with a normalized path
    route_found = any("/test-mcp" in str(route) for route in simple_fastapi_app.routes)
    assert route_found, "Normalized mount path not found in app routes"

    # Create a new MCP server
    mcp2 = FastApiMCP(simple_fastapi_app)

    # Test with path with trailing slash
    mount_path = "/test-mcp2/"
    mcp2.mount(mount_path=mount_path)

    # Check that the route was added with a normalized path
    route_found = any("/test-mcp2" in str(route) for route in simple_fastapi_app.routes)
    assert route_found, "Normalized mount path not found in app routes"


def test_mount_router_with_include_router_prefix(simple_fastapi_app: FastAPI):
    """
    Regression test for https://github.com/tadata-org/fastapi_mcp/issues/204.

    When an APIRouter is created without a `prefix` and is instead given one via
    `app.include_router(router, prefix=...)`, the MCP server should still be mounted
    at the router's effective path, not at the app root.
    """
    other_router = APIRouter()  # No prefix on the constructor

    @other_router.get("/ping", operation_id="ping")
    async def ping() -> dict:
        return {"ping": "pong"}

    simple_fastapi_app.include_router(other_router, prefix="/other/route")

    mcp = FastApiMCP(simple_fastapi_app)
    mcp.mount_http(other_router)

    assert _mcp_endpoint_exists(simple_fastapi_app, "/other/route/mcp"), "Expected MCP endpoint not reachable"
    assert not _mcp_endpoint_exists(
        simple_fastapi_app, "/mcp"
    ), "MCP endpoint should not be mounted at the app root"


def test_mount_empty_router_with_include_router_prefix(simple_fastapi_app: FastAPI):
    """
    The literal repro from https://github.com/tadata-org/fastapi_mcp/issues/204: a router
    used purely as a mount point, with zero routes of its own.

    On FastAPI >= 0.137, `_resolve_router_include_prefix` can recover the prefix from
    FastAPI's own include-time metadata (`_IncludedRouter`) even though there is nothing
    to diff paths against, so this now resolves correctly. On FastAPI < 0.137 there is no
    such metadata and no routes to diff, so there is genuinely no information available to
    recover the prefix from -- this is a documented limitation, not a bug in the fix.
    """
    empty_router = APIRouter()  # zero routes: a pure mount point, as in the issue

    simple_fastapi_app.include_router(empty_router, prefix="/empty")

    mcp = FastApiMCP(simple_fastapi_app)
    mcp.mount_http(empty_router)

    if FASTAPI_HAS_INCLUDED_ROUTER_METADATA:
        assert _mcp_endpoint_exists(simple_fastapi_app, "/empty/mcp"), "Expected MCP endpoint not reachable"
        assert not _mcp_endpoint_exists(
            simple_fastapi_app, "/mcp"
        ), "MCP endpoint should not be mounted at the app root"
    else:
        assert _mcp_endpoint_exists(simple_fastapi_app, "/mcp"), (
            "Known limitation on fastapi < 0.137: a router with no routes of its own "
            "carries no recoverable prefix information, so mounting safely falls back "
            "to the app root instead of guessing."
        )


def test_resolve_prefix_with_endpoint_shared_across_routers(simple_fastapi_app: FastAPI):
    """
    Regression test: reusing the same endpoint function on two different routers is
    legitimate FastAPI, but `endpoint is router_endpoint` identity alone can't tell the
    two registrations apart. Picking the wrong router's prefix is worse than the
    pre-fix behavior (mounting a router's MCP endpoint under an unrelated router's
    prefix), so this must never happen -- either resolve correctly, or fall back safely.
    """

    async def ping() -> dict:
        return {"ping": "pong"}

    router_a = APIRouter()
    router_a.add_api_route("/ping", ping, methods=["GET"])
    router_b = APIRouter()
    router_b.add_api_route("/ping", ping, methods=["GET"])

    simple_fastapi_app.include_router(router_a, prefix="/alpha")
    simple_fastapi_app.include_router(router_b, prefix="/beta")

    mcp = FastApiMCP(simple_fastapi_app)
    resolved = mcp._resolve_router_include_prefix(router_b)

    assert resolved != "/alpha", "Must never resolve to the other router's prefix"
    if FASTAPI_HAS_INCLUDED_ROUTER_METADATA:
        assert resolved == "/beta", "Should resolve exactly via include-time identity metadata"
    else:
        assert resolved == "", (
            "Known limitation on fastapi < 0.137: path-diffing alone cannot disambiguate "
            "two routers sharing the same endpoint function, so this must fall back to "
            "the safe empty prefix rather than guess."
        )


def test_resolve_prefix_with_router_included_at_multiple_prefixes(simple_fastapi_app: FastAPI):
    """
    A router included more than once under different prefixes is unusual but legal.
    There is no single correct prefix to pick from `mount_http`/`mount_sse`'s signature
    alone, so resolution must not silently pick the first one -- it should fall back to
    the safe empty prefix instead.
    """
    router = APIRouter()

    @router.get("/x", operation_id="shared_x")
    async def x() -> dict:
        return {}

    simple_fastapi_app.include_router(router, prefix="/one")
    simple_fastapi_app.include_router(router, prefix="/two")

    mcp = FastApiMCP(simple_fastapi_app)
    resolved = mcp._resolve_router_include_prefix(router)

    assert resolved == "", "Ambiguous multi-prefix inclusion must fall back to the safe empty prefix"
