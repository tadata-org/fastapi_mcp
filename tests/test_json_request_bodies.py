"""Exercise generated MCP arguments against actual in-process FastAPI endpoints."""

import copy
import json
from typing import Optional

import httpx
import pytest
from fastapi import Body, FastAPI, Query, Request
from jsonschema import Draft202012Validator
from mcp.shared.memory import create_connected_server_and_client_session
from pydantic import BaseModel, RootModel

from fastapi_mcp import FastApiMCP


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete", "get"])
@pytest.mark.parametrize(
    "annotation,value",
    [
        (list[int], [1, 2]),
        (list[int], []),
        (str, "café"),
        (str, ""),
        (int, 0),
        (float, 1.5),
        (bool, False),
        (dict[str, int], {"count": 2}),
        (RootModel[list[int]], [3, 4]),
        (list[int] | str, "choice"),
    ],
)
async def test_json_body_reaches_endpoint(method, annotation, value):
    app = FastAPI()

    async def endpoint(request: Request, value=Body(...)):
        return {"body": json.loads(await request.body()), "content_type": request.headers["content-type"]}

    endpoint.__annotations__["value"] = annotation
    app.add_api_route("/body", endpoint, methods=[method.upper()], operation_id="body")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        mcp = FastApiMCP(app, http_client=client)
        tool = next(t for t in mcp.tools if t.name == "body")
        original = copy.deepcopy(app.openapi())
        body_schema = original["paths"]["/body"][method]["requestBody"]["content"]["application/json"]["schema"]
        if "$ref" in body_schema:
            body_schema = original["components"]["schemas"][body_schema["$ref"].rsplit("/", 1)[1]]
        assert tool.inputSchema["properties"]["payload"] == body_schema
        assert "payload" in tool.inputSchema["required"]
        arguments = {"payload": value}
        before = copy.deepcopy(arguments)
        Draft202012Validator(tool.inputSchema).validate(arguments)
        result = await mcp._execute_api_tool(client, "body", arguments, mcp.operation_map)
        assert json.loads(result[0].text) == {"body": value, "content_type": "application/json"}
        assert arguments == before
        assert app.openapi() == original


@pytest.mark.parametrize("arguments,expected", [({}, ""), ({"payload": None}, "null"), ({"payload": ""}, '""')])
async def test_optional_body_distinguishes_omission_from_null(arguments, expected):
    app = FastAPI()

    @app.post("/optional", operation_id="optional")
    async def endpoint(request: Request, value: Optional[str] = Body(None)):
        return {"raw": (await request.body()).decode()}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        mcp = FastApiMCP(app, http_client=client)
        tool = next(t for t in mcp.tools if t.name == "optional")
        assert "payload" not in tool.inputSchema.get("required", [])
        Draft202012Validator(tool.inputSchema).validate(arguments)
        result = await mcp._execute_api_tool(client, "optional", arguments, mcp.operation_map)
        assert json.loads(result[0].text) == {"raw": expected}


async def test_payload_argument_avoids_routing_names():
    app = FastAPI()

    @app.post("/items/{payload}", operation_id="items")
    async def endpoint(payload: int, value: list[int] = Body(...), payload_1: str = Query(...)):
        return {"path": payload, "query": payload_1, "body": value}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        mcp = FastApiMCP(app, http_client=client)
        tool = next(t for t in mcp.tools if t.name == "items")
        arguments = {"payload": 42, "payload_1": "route", "payload_2": [7]}
        Draft202012Validator(tool.inputSchema).validate(arguments)
        result = await mcp._execute_api_tool(client, "items", arguments, mcp.operation_map)
        assert json.loads(result[0].text) == {"path": 42, "query": "route", "body": [7]}


async def test_existing_object_body_keeps_flat_arguments():
    class Item(BaseModel):
        name: str

    app = FastAPI()

    @app.post("/items", operation_id="items")
    async def endpoint(item: Item):
        return item

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        mcp = FastApiMCP(app, http_client=client)
        tool = next(t for t in mcp.tools if t.name == "items")
        assert set(tool.inputSchema["properties"]) == {"name"}
        result = await mcp._execute_api_tool(client, "items", {"name": "unchanged"}, mcp.operation_map)
        assert json.loads(result[0].text) == {"name": "unchanged"}


async def test_mcp_call_validates_the_complete_array_body():
    app = FastAPI()
    calls = []

    @app.post("/bulk", operation_id="bulk")
    async def endpoint(values: list[int] = Body(..., min_length=1)):
        calls.append(values)
        return {"total": sum(values)}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        mcp = FastApiMCP(app, http_client=client)
        async with create_connected_server_and_client_session(mcp.server) as session:
            tools = await session.list_tools()
            schema = next(t.inputSchema for t in tools.tools if t.name == "bulk")
            assert schema["properties"]["payload"]["minItems"] == 1
            result = await session.call_tool("bulk", {"payload": [2, 3]})
            assert not result.isError
            assert json.loads(result.content[0].text) == {"total": 5}
            for arguments in ({}, {"payload": "invalid"}, {"payload": []}):
                invalid = await session.call_tool("bulk", arguments)
                assert invalid.isError
            assert calls == [[2, 3]]
