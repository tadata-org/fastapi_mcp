import logging
from contextlib import asynccontextmanager

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

import mcp.types as types
from mcp.shared.message import SessionMessage
from fastapi_mcp.types import HTTPRequestInfo

logger = logging.getLogger(__name__)


class FastApiWebSocketTransport:
    """
    WebSocket transport for FastAPI MCP that integrates with FastAPI's WebSocket support.

    This transport provides similar functionality to the SSE transport but uses WebSockets
    for bidirectional communication, which can be more efficient for interactive applications.
    """

    @asynccontextmanager
    async def connect_websocket(self, websocket: WebSocket):
        """
        Connect a WebSocket and return read/write streams for MCP communication.

        Args:
            websocket: FastAPI WebSocket instance

        Yields:
            tuple: (read_stream, write_stream) for MCP communication
        """
        await websocket.accept(subprotocol="mcp")

        read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
        read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]

        write_stream: MemoryObjectSendStream[SessionMessage]
        write_stream_reader: MemoryObjectReceiveStream[SessionMessage]

        read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
        write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

        async def ws_reader():
            """Read messages from WebSocket and send to read stream."""
            try:
                async with read_stream_writer:
                    while True:
                        try:
                            # Receive text message from WebSocket
                            raw_message = await websocket.receive_text()
                            logger.debug(f"Received WebSocket message: {raw_message}")

                            # Parse and validate JSON-RPC message
                            try:
                                client_message = types.JSONRPCMessage.model_validate_json(raw_message)

                                # HACK to inject HTTP request info into the MCP message,
                                # similar to what we do in SSE transport
                                if hasattr(client_message.root, "params") and client_message.root.params is not None:
                                    # For WebSocket, we have less HTTP context, but we can still provide some info
                                    client_message.root.params["_http_request_info"] = HTTPRequestInfo(
                                        method="WEBSOCKET",
                                        path=websocket.url.path,
                                        headers=dict(websocket.headers) if websocket.headers else {},
                                        cookies={},  # WebSocket doesn't have cookies in the same way
                                        query_params=dict(websocket.query_params) if websocket.query_params else {},
                                        body="",  # WebSocket doesn't have a body
                                    ).model_dump(mode="json")

                                session_message = SessionMessage(client_message)
                                await read_stream_writer.send(session_message)

                            except ValidationError as exc:
                                logger.error(f"Failed to parse WebSocket message: {exc}")
                                await read_stream_writer.send(exc)

                        except WebSocketDisconnect:
                            logger.debug("WebSocket disconnected")
                            break
                        except anyio.get_cancelled_exc_class():
                            logger.debug("WebSocket reader task cancelled")
                            break
                        except Exception as e:
                            logger.error(f"Error reading from WebSocket: {e}")
                            break

            except anyio.ClosedResourceError:
                logger.debug("Read stream closed")
            except anyio.get_cancelled_exc_class():
                logger.debug("WebSocket reader cancelled")
            except Exception as e:
                logger.error(f"Error in WebSocket reader: {e}")

        async def ws_writer():
            """Read messages from write stream and send to WebSocket."""
            try:
                async with write_stream_reader:
                    async for session_message in write_stream_reader:
                        try:
                            # Convert message to JSON and send via WebSocket
                            message_json = session_message.message.model_dump_json(by_alias=True, exclude_none=True)
                            logger.debug(f"Sending WebSocket message: {message_json}")
                            await websocket.send_text(message_json)

                        except WebSocketDisconnect:
                            logger.debug("WebSocket disconnected during send")
                            break
                        except anyio.get_cancelled_exc_class():
                            logger.debug("WebSocket writer task cancelled")
                            break
                        except Exception as e:
                            logger.error(f"Error sending WebSocket message: {e}")
                            break

            except anyio.ClosedResourceError:
                logger.debug("Write stream closed")
            except anyio.get_cancelled_exc_class():
                logger.debug("WebSocket writer cancelled")
            except Exception as e:
                logger.error(f"Error in WebSocket writer: {e}")

        async with anyio.create_task_group() as tg:
            tg.start_soon(ws_reader)
            tg.start_soon(ws_writer)
            try:
                yield (read_stream, write_stream)
            finally:
                # Cancel the task group when the context manager exits
                tg.cancel_scope.cancel()
