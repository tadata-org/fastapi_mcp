import logging
from uuid import UUID
from typing import Union

from anyio.streams.memory import MemoryObjectSendStream
from fastapi import Request, Response, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from mcp.shared.message import SessionMessage, ServerMessageMetadata
from pydantic import ValidationError
from mcp.server.sse import SseServerTransport
from mcp.types import JSONRPCMessage, JSONRPCError, ErrorData


logger = logging.getLogger(__name__)

DEFAULT_MAX_BODY_BYTES = 1_000_000


class FastApiSseTransport(SseServerTransport):
    def __init__(self, endpoint: str, max_body_bytes: int = DEFAULT_MAX_BODY_BYTES):
        super().__init__(endpoint)

        max_body_bytes_int = int(max_body_bytes)
        if max_body_bytes_int <= 0:
            raise ValueError("max_body_bytes must be positive")

        self._max_body_bytes = max_body_bytes_int

    async def _read_body_with_limit(self, request: Request) -> bytes:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self._max_body_bytes:
                    raise HTTPException(status_code=413, detail="Payload too large")
            except ValueError:
                # Ignore invalid Content-Length and fall back to streaming limit.
                pass

        out = bytearray()
        async for chunk in request.stream():
            out.extend(chunk)
            if len(out) > self._max_body_bytes:
                raise HTTPException(status_code=413, detail="Payload too large")
        return bytes(out)

    async def handle_fastapi_post_message(self, request: Request) -> Response:
        """
        A reimplementation of the handle_post_message method of SseServerTransport
        that integrates better with FastAPI.

        A few good reasons for doing this:
        1. Avoid mounting a whole Starlette app and instead use a more FastAPI-native
           approach. Mounting has some known issues and limitations.
        2. Avoid re-constructing the scope, receive, and send from the request, as done
           in the original implementation.
        3. Use FastAPI's native response handling mechanisms and exception patterns to
           avoid unexpected rabbit holes.

        The combination of mounting a whole Starlette app and reconstructing the scope
        and send from the request proved to be especially error-prone for us when using
        tracing tools like Sentry, which had destructive effects on the request object
        when using the original implementation.
        """

        logger.debug("Handling POST message SSE")

        session_id_param = request.query_params.get("session_id")
        if session_id_param is None:
            logger.warning("Received request without session_id")
            raise HTTPException(status_code=400, detail="session_id is required")

        try:
            session_id = UUID(hex=session_id_param)
            logger.debug(f"Parsed session ID: {session_id}")
        except ValueError:
            logger.warning(f"Received invalid session ID: {session_id_param}")
            raise HTTPException(status_code=400, detail="Invalid session ID")

        writer = self._read_stream_writers.get(session_id)
        if not writer:
            logger.warning(f"Could not find session for ID: {session_id}")
            raise HTTPException(status_code=404, detail="Could not find session")

        body = await self._read_body_with_limit(request)
        logger.debug(f"Received JSON: {body.decode(errors='replace')}")

        try:
            message = JSONRPCMessage.model_validate_json(body)

            logger.debug(f"Validated client message: {message}")
        except ValidationError as err:
            logger.error(f"Failed to parse message: {err}")
            # Create background task to send error
            background_tasks = BackgroundTasks()
            background_tasks.add_task(self._send_message_safely, writer, err)
            response = JSONResponse(content={"error": "Could not parse message"}, status_code=400)
            response.background = background_tasks
            return response
        except Exception as e:
            logger.error(f"Error processing request body: {e}")
            raise HTTPException(status_code=400, detail="Invalid request body")

        # Create background task to send message with proper request context metadata
        background_tasks = BackgroundTasks()
        metadata = ServerMessageMetadata(request_context=request)
        session_message = SessionMessage(message, metadata=metadata)
        background_tasks.add_task(self._send_message_safely, writer, session_message)
        logger.debug("Accepting message, will send in background")

        # Return response with background task
        response = JSONResponse(content={"message": "Accepted"}, status_code=202)
        response.background = background_tasks
        return response

    async def _send_message_safely(
        self, writer: MemoryObjectSendStream[SessionMessage], message: Union[SessionMessage, ValidationError]
    ):
        """Send a message to the writer, avoiding ASGI race conditions"""

        try:
            logger.debug(f"Sending message to writer from background task: {message}")

            if isinstance(message, ValidationError):
                # Convert ValidationError to JSONRPCError
                error_data = ErrorData(
                    code=-32700,  # Parse error code in JSON-RPC
                    message="Parse error",
                    data={"validation_error": str(message)},
                )
                json_rpc_error = JSONRPCError(
                    jsonrpc="2.0",
                    id="unknown",  # We don't know the ID from the invalid request
                    error=error_data,
                )
                error_message = SessionMessage(JSONRPCMessage(root=json_rpc_error))
                await writer.send(error_message)
            else:
                await writer.send(message)
        except Exception as e:
            logger.error(f"Error sending message to writer: {e}")
