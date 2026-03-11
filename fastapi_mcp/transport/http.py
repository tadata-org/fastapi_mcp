import logging
import asyncio
from typing import Any, List, MutableMapping, Tuple

from fastapi import Request, Response, HTTPException
from mcp.server.lowlevel.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager, EventStore
from mcp.server.transport_security import TransportSecuritySettings

ACCEPT_JSON = b"application/json"
ACCEPT_SSE = b"text/event-stream"

logger = logging.getLogger(__name__)


class FastApiHttpSessionManager:
    """
    FastAPI-native wrapper around StreamableHTTPSessionManager
    """

    def __init__(
        self,
        mcp_server: Server,
        event_store: EventStore | None = None,
        json_response: bool = True,  # Default to JSON for HTTP transport
        security_settings: TransportSecuritySettings | None = None,
    ):
        self.mcp_server = mcp_server
        self.event_store = event_store
        self.json_response = json_response
        self.security_settings = security_settings
        self._session_manager: StreamableHTTPSessionManager | None = None
        self._manager_task: asyncio.Task | None = None
        self._manager_started = False
        self._startup_lock = asyncio.Lock()

    async def _ensure_session_manager_started(self) -> None:
        """
        Ensure the session manager is started.

        This is called lazily on the first request to start the session manager
        if it hasn't been started yet.
        """
        if self._manager_started:
            return

        async with self._startup_lock:
            if self._manager_started:
                return

            logger.debug("Starting StreamableHTTP session manager")

            # Create the session manager
            # Note: We don't use stateless=True because we want to support sessions
            # but sessions are optional as per the MCP spec
            self._session_manager = StreamableHTTPSessionManager(
                app=self.mcp_server,
                event_store=self.event_store,
                json_response=self.json_response,
                stateless=False,  # Always support sessions, but they're optional
                security_settings=self.security_settings,
            )

            # Start the session manager in a background task
            async def run_session_manager():
                try:
                    async with self._session_manager.run():
                        logger.info("StreamableHTTP session manager is running")
                        # Keep running until cancelled
                        await asyncio.Event().wait()
                except asyncio.CancelledError:
                    logger.info("StreamableHTTP session manager is shutting down")
                    raise
                except Exception:
                    logger.exception("Error in StreamableHTTP session manager")
                    raise

            self._manager_task = asyncio.create_task(run_session_manager())
            self._manager_started = True

            # Give the session manager a moment to initialize
            await asyncio.sleep(0.1)

    def _ensure_accept_headers(self, scope: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        """
        Ensure the ASGI scope's Accept header includes text/event-stream.

        The upstream MCP StreamableHTTPSessionManager requires both application/json
        and text/event-stream in the Accept header, even when json_response=True.
        Clients that only send Accept: application/json (e.g., Google Gemini CLI)
        would be rejected. This method adds text/event-stream to the Accept header
        when it is missing, so standard HTTP JSON-RPC clients work out of the box.
        """
        headers: List[Tuple[bytes, bytes]] = list(scope.get("headers", []))
        accept_idx = None
        has_sse = False

        for i, (name, value) in enumerate(headers):
            if name.lower() == b"accept":
                accept_idx = i
                accept_types = [t.strip() for t in value.split(b",")]
                has_sse = any(t.startswith(ACCEPT_SSE) for t in accept_types)
                break

        if has_sse:
            return scope

        # Build a new scope with the updated Accept header (immutable approach)
        new_scope = dict(scope)
        if accept_idx is not None:
            new_headers = list(headers)
            existing_value = new_headers[accept_idx][1]
            new_headers[accept_idx] = (b"accept", existing_value + b", " + ACCEPT_SSE)
            new_scope["headers"] = new_headers
        else:
            new_headers = list(headers)
            new_headers.append((b"accept", ACCEPT_JSON + b", " + ACCEPT_SSE))
            new_scope["headers"] = new_headers

        return new_scope

    async def handle_fastapi_request(self, request: Request) -> Response:
        """
        Handle a FastAPI request by delegating to the session manager.

        This converts FastAPI's Request/Response to ASGI scope/receive/send
        and then converts the result back to a FastAPI Response.
        """
        # Ensure session manager is started
        await self._ensure_session_manager_started()

        if not self._session_manager:
            raise HTTPException(status_code=500, detail="Session manager not initialized")

        logger.debug(f"Handling FastAPI request: {request.method} {request.url.path}")

        # Ensure Accept header includes text/event-stream for upstream compatibility.
        # The upstream MCP library requires both application/json and text/event-stream,
        # but standard HTTP JSON-RPC clients only send application/json.
        scope = self._ensure_accept_headers(request.scope)

        # Capture the response from the session manager
        response_started = False
        response_status = 200
        response_headers: List[Tuple[bytes, bytes]] = []
        response_body = b""

        async def send_callback(message: MutableMapping[str, Any]) -> None:
            nonlocal response_started, response_status, response_headers, response_body

            if message["type"] == "http.response.start":
                response_started = True
                response_status = message["status"]
                response_headers = message.get("headers", [])
            elif message["type"] == "http.response.body":
                response_body += message.get("body", b"")

        try:
            # Delegate to the session manager's handle_request method
            await self._session_manager.handle_request(scope, request.receive, send_callback)

            # Convert the captured ASGI response to a FastAPI Response
            headers_dict = {name.decode(): value.decode() for name, value in response_headers}

            return Response(
                content=response_body,
                status_code=response_status,
                headers=headers_dict,
            )

        except Exception:
            logger.exception("Error in StreamableHTTPSessionManager")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def shutdown(self) -> None:
        """Clean up the session manager and background task."""
        if self._manager_task and not self._manager_task.done():
            self._manager_task.cancel()
            try:
                await self._manager_task
            except asyncio.CancelledError:
                pass
        self._manager_started = False
