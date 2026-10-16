import json
from collections.abc import Awaitable, Callable

import httpx
import pytest
from fastapi import FastAPI, Request
from mcp.types import TextContent
from starlette.responses import Response

from fastapi_mcp import FastApiMCP


@pytest.fixture
def path_app() -> FastAPI:
    app = FastAPI()
    excluded_calls: list[str] = []
    app.state.excluded_calls = excluded_calls

    @app.get("/files/{name}", operation_id="get_file")
    async def get_file(name: str, q: str = "none") -> dict[str, str]:
        return {"name": name, "q": q}

    @app.get("/files/{name}/versions/{version}", operation_id="get_version")
    async def get_version(name: str, version: str) -> dict[str, str]:
        return {"name": name, "version": version}

    @app.get("/admin", operation_id="admin")
    async def admin() -> dict[str, bool]:
        excluded_calls.append("admin")
        return {"admin": True}

    return app


@pytest.mark.parametrize(
    "name",
    ["plain", "report 2026.txt", "café.txt", "x?q=injected", "a#b", "100%done", "%2Fadmin", ".", ".."],
)
async def test_path_parameter_arrives_as_literal_data(path_app: FastAPI, name: str) -> None:
    mcp = FastApiMCP(path_app, include_operations=["get_file"])
    arguments = {"name": name, "q": "explicit"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=path_app), base_url="http://test") as client:
        result = await mcp._execute_api_tool(client, "get_file", arguments, mcp.operation_map)

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    assert json.loads(result[0].text) == {"name": name, "q": "explicit"}
    assert arguments == {"name": name, "q": "explicit"}


@pytest.mark.parametrize("name", ["../admin", "../../admin", "a/b", "/admin"])
async def test_path_parameter_cannot_reach_excluded_route(path_app: FastAPI, name: str) -> None:
    mcp = FastApiMCP(path_app, include_operations=["get_file"])
    assert [tool.name for tool in mcp.tools] == ["get_file"]

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=path_app), base_url="http://test") as client:
        with pytest.raises(Exception, match="Status code: 404"):
            await mcp._execute_api_tool(client, "get_file", {"name": name}, mcp.operation_map)
    assert path_app.state.excluded_calls == []


async def test_path_parameter_cannot_replace_another_placeholder(path_app: FastAPI) -> None:
    mcp = FastApiMCP(path_app, include_operations=["get_version"])

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=path_app), base_url="http://test") as client:
        result = await mcp._execute_api_tool(
            client, "get_version", {"name": "{version}", "version": "latest"}, mcp.operation_map
        )

    assert isinstance(result[0], TextContent)
    assert json.loads(result[0].text) == {"name": "{version}", "version": "latest"}


@pytest.mark.parametrize("name", ["docs/readme.txt", "folder name/café #100?.txt", "docs/%2Fadmin/readme.txt"])
async def test_path_converter_preserves_nested_names(name: str) -> None:
    app = FastAPI()
    raw_paths: list[bytes] = []

    @app.middleware("http")
    async def capture_path(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        raw_paths.append(request.scope["raw_path"])
        return await call_next(request)

    @app.get("/nested/{name:path}", operation_id="get_nested_file")
    async def get_nested_file(name: str, q: str = "none") -> dict[str, str]:
        return {"name": name, "q": q}

    mcp = FastApiMCP(app)
    arguments = {"name": name, "q": "explicit"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        result = await mcp._execute_api_tool(client, "get_nested_file", arguments, mcp.operation_map)

    assert isinstance(result[0], TextContent)
    assert json.loads(result[0].text) == {"name": name, "q": "explicit"}
    # ASGI decodes the escaped slash before FastAPI's path converter matches it.
    assert b"%2F" in raw_paths[0]
    assert arguments == {"name": name, "q": "explicit"}
