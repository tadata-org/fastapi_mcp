import logging

from fastapi import Request, Response, HTTPException
from mcp.server.streamable_http import StreamableHTTPServerTransport
from mcp.server.transport_security import TransportSecuritySettings

logger = logging.getLogger(__name__)


class FastApiStreamableHttpTransport(StreamableHTTPServerTransport):
    def __init__(
        self,
        mcp_session_id: str | None = None,
        is_json_response_enabled: bool = True,  # Default to JSON for HTTP transport
        event_store=None,
        security_settings: TransportSecuritySettings | None = None,
    ):
        super().__init__(
            mcp_session_id=mcp_session_id,
            is_json_response_enabled=is_json_response_enabled,
            event_store=event_store,
            security_settings=security_settings,
        )
        logger.debug(f"FastApiStreamableHttpTransport initialized with session_id: {mcp_session_id}")

    async def handle_fastapi_request(self, request: Request) -> Response:
        """
        The approach here is different from FastApiSseTransport.
        In FastApiSseTransport, we reimplement the SSE transport logic to have a more FastAPI-native transport.
        It proved to be less bug-prone since it avoids deconstructing and reconstructing raw ASGI objects.

        But, we took a different approach here because StreamableHTTPServerTransport handles more complexity,
        and multiple request methods (GET/POST/DELETE), so we want to leverage that logic and avoid reimplementing.

        We still ensure it works natively with FastAPI by capturing the ASGI response from the SDK and converting
        it to a FastAPI Response.
        """
        logger.debug(f"Handling FastAPI request: {request.method} {request.url.path}")

        # Capture the response from the SDK's handle_request method
        response_started = False
        response_status = 200
        response_headers = []
        response_body = b""

        async def capture_send(message):
            nonlocal response_started, response_status, response_headers, response_body

            if message["type"] == "http.response.start":
                response_started = True
                response_status = message["status"]
                response_headers = message.get("headers", [])
            elif message["type"] == "http.response.body":
                response_body += message.get("body", b"")

        try:
            # Delegate to the SDK's handle_request method with ASGI interface
            await self.handle_request(request.scope, request.receive, capture_send)

            # Convert the captured ASGI response to a FastAPI Response
            headers_dict = {name.decode(): value.decode() for name, value in response_headers}

            return Response(
                content=response_body,
                status_code=response_status,
                headers=headers_dict,
            )

        except Exception as e:
            logger.exception(f"Error in StreamableHTTPServerTransport: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
