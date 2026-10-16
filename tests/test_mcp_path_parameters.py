import json

import httpx
import pytest
from fastapi import FastAPI
from mcp.types import TextContent

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
