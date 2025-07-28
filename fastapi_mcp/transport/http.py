import logging
import anyio
from fastapi import Request, Response, HTTPException
from mcp.server.lowlevel.server import Server
from mcp.server.streamable_http import StreamableHTTPServerTransport
from mcp.server.transport_security import TransportSecuritySettings

logger = logging.getLogger(__name__)


class FastApiStreamableHttpTransport:
    """
    FastAPI wrapper for StreamableHTTPServerTransport using stateless mode.

    This creates a fresh transport instance for each request to avoid conflicts
    and follows the SDK's recommended stateless pattern.
    """

    def __init__(
        self,
        mcp_session_id: str | None = None,
        is_json_response_enabled: bool = True,  # Default to JSON for HTTP transport
        event_store=None,
        security_settings: TransportSecuritySettings | None = None,
        mcp_server: Server | None = None,
    ):
        logger.debug("FastApiStreamableHttpTransport initialized for stateless mode")
        self._mcp_server = mcp_server
        self._is_json_response_enabled = is_json_response_enabled
        self._event_store = event_store
        self._security_settings = security_settings

    async def handle_fastapi_request(self, request: Request, mcp_server: Server | None = None) -> Response:
        """
        Handle FastAPI request using stateless mode - creates a fresh transport for each request.

        This follows the SDK's stateless pattern from StreamableHTTPSessionManager to avoid
        409 Conflict errors that occur when multiple requests try to use the same transport instance.
        """
        logger.debug(f"Handling FastAPI request: {request.method} {request.url.path}")

        # Use the stored server if available, or the passed one
        server = self._mcp_server or mcp_server
        if not server:
            raise HTTPException(status_code=500, detail="No MCP server available")

        # Create a fresh transport for this request (stateless mode)
        http_transport = StreamableHTTPServerTransport(
            mcp_session_id=None,  # No session tracking in stateless mode
            is_json_response_enabled=self._is_json_response_enabled,
            event_store=None,  # No event store in stateless mode
            security_settings=self._security_settings,
        )

        # Start server in a background task
        async def run_stateless_server(*, task_status: anyio.abc.TaskStatus[None] = anyio.TASK_STATUS_IGNORED):
            async with http_transport.connect() as streams:
                read_stream, write_stream = streams
                task_status.started()
                try:
                    await server.run(
                        read_stream,
                        write_stream,
                        server.create_initialization_options(),
                        stateless=True,
                    )
                except Exception:
                    logger.exception("Stateless session crashed")

        # Start the server task
        async with anyio.create_task_group() as tg:
            await tg.start(run_stateless_server)

            # Capture the response from the SDK's handle_request method
            response_started = False
            response_status = 200
            response_headers = []
            response_body = b""

            async def send_callback(message):
                nonlocal response_started, response_status, response_headers, response_body

                if message["type"] == "http.response.start":
                    response_started = True
                    response_status = message["status"]
                    response_headers = message.get("headers", [])
                elif message["type"] == "http.response.body":
                    response_body += message.get("body", b"")

            try:
                # Delegate to the SDK's handle_request method with ASGI interface
                await http_transport.handle_request(request.scope, request.receive, send_callback)

                # Convert the captured ASGI response to a FastAPI Response
                headers_dict = {name.decode(): value.decode() for name, value in response_headers}

                return Response(
                    content=response_body,
                    status_code=response_status,
                    headers=headers_dict,
                )

            except Exception:
                logger.exception("Error in StreamableHTTPServerTransport")
                raise HTTPException(status_code=500, detail="Internal server error")
            finally:
                # Terminate the transport after the request is handled (stateless mode)
                await http_transport.terminate()
