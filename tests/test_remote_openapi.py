import pytest
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP


@pytest.mark.asyncio
def test_fetch_openapi_from_remote(monkeypatch):
    app = FastAPI()
    remote_openapi = {"openapi": "3.0.0", "info": {"title": "Remote", "version": "1.0.0"}, "paths": {}}

    class MockAsyncClient:
        async def get(self, url):
            class Resp:
                def raise_for_status(self):
                    pass

                def json(self):
                    return remote_openapi

            return Resp()

    client = MockAsyncClient()
    mcp = FastApiMCP(app, http_client=client, fetch_openapi_from_remote=True)
    # The openapi schema should be fetched from remote
    assert mcp.tools is not None
    assert mcp.operation_map is not None
    # The schema should match what the mock returned
    assert mcp.operation_map == {}  # since paths is empty
