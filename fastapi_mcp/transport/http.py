import logging
import json

from fastapi import Request, Response, HTTPException
from mcp.server.streamable_http import StreamableHTTPServerTransport
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import JSONRPCMessage
from pydantic import ValidationError
from fastapi_mcp.types import HTTPRequestInfo

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
        FastAPI-native request handler that adapts the SDK's handle_request method.

        The approach here is necessarily different from FastApiSseTransport.
        In FastApiSseTransport, we reimplement the SSE transport logic to have a more FastAPI-native transport.
        It proved to be less bug-prone since it avoids deconstructing and reconstructing raw ASGI objects.

        But, we took a different approach here because StreamableHTTPServerTransport handles more complexity,
        and multiple request methods (GET/POST/DELETE), so we want to leverage that logic and avoid reimplementing.

        So we use an enhanced adapter pattern: intercept and enhance POST requests for HTTPRequestInfo injection,
        while delegating the complex protocol handling to the SDK.
        """
        logger.debug(f"Handling FastAPI request: {request.method} {request.url.path}")

        if request.method == "POST":
            return await self._handle_post_with_injection(request)
        else:
            # For GET and DELETE requests, delegate directly to SDK since they don't need injection
            return await self._delegate_to_sdk(request)

    async def _handle_post_with_injection(self, request: Request) -> Response:
        """
        Handle POST requests with HTTPRequestInfo injection.

        This mirrors the approach in FastApiSseTransport.handle_fastapi_post_message()
        to ensure consistency in how we handle authentication context and header forwarding.

        The injection happens at the JSON-RPC message level, just like in SSE transport,
        so that the downstream tool handlers receive the same request context regardless
        of transport type.
        """
        try:
            # Read and parse the request body first, just like SSE transport does
            body = await request.body()
            logger.debug(f"Received JSON: {body.decode()}")

            try:
                raw_message = json.loads(body)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")
                raise HTTPException(status_code=400, detail=f"Parse error: {str(e)}")

            try:
                message = JSONRPCMessage.model_validate(raw_message)
            except ValidationError as e:
                logger.error(f"Failed to validate message: {e}")
                raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")

            # HACK to inject the HTTP request info into the MCP message,
            # so we can use it for auth.
            # It is then used in our custom `LowlevelMCPServer.call_tool()` decorator.
            if hasattr(message.root, "params") and message.root.params is not None:
                message.root.params["_http_request_info"] = HTTPRequestInfo(
                    method=request.method,
                    path=request.url.path,
                    headers=dict(request.headers),
                    cookies=request.cookies,
                    query_params=dict(request.query_params),
                    body=body.decode(),
                ).model_dump(mode="json")
                logger.debug("Injected HTTPRequestInfo into message for auth context")

            modified_body = message.model_dump_json(by_alias=True, exclude_none=True).encode()
            modified_request = self._create_modified_request(request, modified_body)

            # Delegate to SDK with the modified request
            return await self._delegate_to_sdk(modified_request)

        except HTTPException:
            # Re-raise FastAPI HTTPExceptions directly for proper error handling
            raise
        except Exception:
            logger.exception("Error processing POST request")
            raise HTTPException(status_code=500, detail="Internal server error")

    def _create_modified_request(self, original_request: Request, modified_body: bytes) -> Request:
        """
        Create a new Request object with modified body content.

        This is necessary because we need to inject HTTPRequestInfo into the JSON-RPC message
        before passing it to the SDK, but Request objects are immutable.
        """

        # Create a new receive callable that returns our modified body
        async def modified_receive():
            return {
                "type": "http.request",
                "body": modified_body,
                "more_body": False,
            }

        # Create new request with modified receive
        return Request(original_request.scope, modified_receive)

    async def _delegate_to_sdk(self, request: Request) -> Response:
        """
        Delegate request handling to the underlying StreamableHTTPServerTransport.

        This captures the ASGI response from the SDK and converts it to a FastAPI Response,
        maintaining the adapter pattern while providing FastAPI-native integration.
        """
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
