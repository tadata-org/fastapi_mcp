---
title: Transport
description: How to communicate with the FastAPI app
icon: car
---

FastAPI-MCP uses ASGI transport by default, which means it communicates directly with your FastAPI app without making HTTP requests. This is more efficient and doesn't require a base URL.

It's not even necessary that the FastAPI server will run.

If you need to specify a custom base URL or use a different transport method, you can provide your own `httpx.AsyncClient`:

```python {7-10, 14}
import httpx
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

app = FastAPI()

custom_client = httpx.AsyncClient(
    base_url="https://api.example.com",
    timeout=30.0
)

mcp = FastApiMCP(
    app,
    http_client=custom_client
)

mcp.mount()
```
