"""
Compatibility layer for the mcp SDK's in-memory test helper.

mcp 1.x ships ``create_connected_server_and_client_session`` in
``mcp.shared.memory``. mcp 2.x removed it when the lowlevel server API was
redesigned, but the public ``create_client_server_memory_streams`` helper is
still there — so on 2.x we rebuild the exact same contract from it. Tests
import the helper from this module instead of from mcp directly, so the suite
runs unchanged under both major versions.
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import anyio

def tool_input_schema(tool: Any) -> Any:
    """Tool input schema (mcp 1.x: .inputSchema, mcp 2.x: .input_schema)."""
    schema = getattr(tool, "inputSchema", None)
    if schema is None:
        schema = tool.input_schema
    return schema


def call_result_is_error(result: Any) -> bool:
    """True when a CallToolResult flags an error (mcp 1.x: .isError, mcp 2.x: .is_error)."""
    value = getattr(result, "isError", None)
    if value is None:
        value = getattr(result, "is_error", False)
    return bool(value)


def jsonrpc_message_root(message: Any) -> Any:
    """Unwrapped value of a parsed JSONRPCMessage (mcp 1.x: .root, mcp 2.x: already unwrapped)."""
    return getattr(message, "root", message)


try:  # mcp 1.x
    from mcp.shared.memory import (  # type: ignore[attr-defined,no-redef]
        create_connected_server_and_client_session,
    )

except ImportError:  # mcp 2.x

    from mcp.client.session import ClientSession
    from mcp.shared.memory import create_client_server_memory_streams

    @asynccontextmanager
    async def create_connected_server_and_client_session(
        server: Any,
        read_timeout_seconds: Any = None,
        raise_exceptions: bool = False,
    ) -> AsyncGenerator[Any, None]:
        """Create a ClientSession connected to a running MCP server (mcp 2.x)."""
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            client_read, client_write = client_streams
            server_read, server_write = server_streams

            # Create a cancel scope for the server task
            async with anyio.create_task_group() as tg:

                async def run_server() -> None:
                    await server.run(
                        server_read,
                        server_write,
                        server.create_initialization_options(),
                        raise_exceptions=raise_exceptions,
                    )

                tg.start_soon(run_server)

                try:
                    async with ClientSession(
                        read_stream=client_read,
                        write_stream=client_write,
                        read_timeout_seconds=read_timeout_seconds,
                    ) as client_session:
                        await client_session.initialize()
                        yield client_session
                finally:
                    tg.cancel_scope.cancel()
