import json
import httpx
from typing import Dict, Optional, Any, List, Union, Literal, Sequence
from typing_extensions import Annotated, Doc

from fastapi import FastAPI, Request, APIRouter, params
from fastapi.openapi.utils import get_openapi
from mcp.server.lowlevel.server import Server
import mcp.types as types

from fastapi_mcp.openapi.convert import convert_openapi_to_mcp_tools
from fastapi_mcp.transport.sse import FastApiSseTransport
from fastapi_mcp.transport.http import FastApiHttpSessionManager
from fastapi_mcp.types import HTTPRequestInfo, AuthConfig

import logging


logger = logging.getLogger(__name__)


class FastApiMCP:
    """
    Create an MCP server from a FastAPI app.
    """

    def __init__(
        self,
        fastapi: Annotated[
            FastAPI,
            Doc("The FastAPI application to create an MCP server from"),
        ],
        name: Annotated[
            Optional[str],
            Doc("Name for the MCP server (defaults to app.title)"),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc("Description for the MCP server (defaults to app.description)"),
        ] = None,
        describe_all_responses: Annotated[
            bool,
            Doc("Whether to include all possible response schemas in tool descriptions"),
        ] = False,
        describe_full_response_schema: Annotated[
            bool,
            Doc("Whether to include full json schema for responses in tool descriptions"),
        ] = False,
        http_client: Annotated[
            Optional[httpx.AsyncClient],
            Doc(
                """
                Optional custom HTTP client to use for API calls to the FastAPI app.
                Has to be an instance of `httpx.AsyncClient`.
                """
            ),
        ] = None,
        include_operations: Annotated[
            Optional[List[str]],
            Doc("List of operation IDs to include as MCP tools. Cannot be used with exclude_operations."),
        ] = None,
        exclude_operations: Annotated[
            Optional[List[str]],
            Doc("List of operation IDs to exclude from MCP tools. Cannot be used with include_operations."),
        ] = None,
        include_tags: Annotated[
            Optional[List[str]],
            Doc("List of tags to include as MCP tools. Cannot be used with exclude_tags."),
        ] = None,
        exclude_tags: Annotated[
            Optional[List[str]],
            Doc("List of tags to exclude from MCP tools. Cannot be used with include_tags."),
        ] = None,
        auth_config: Annotated[
            Optional[AuthConfig],
            Doc("Configuration for MCP authentication"),
        ] = None,
        headers: Annotated[
            List[str],
            Doc(
                """
                List of HTTP header names to forward from the incoming MCP request into each tool invocation.
                Only headers in this allowlist will be forwarded. Defaults to ['authorization'].
                """
            ),
        ] = ["authorization"],
    ):
        # Validate operation and tag filtering options
        if include_operations is not None and exclude_operations is not None:
            raise ValueError("Cannot specify both include_operations and exclude_operations")

        if include_tags is not None and exclude_tags is not None:
            raise ValueError("Cannot specify both include_tags and exclude_tags")

        self.operation_map: Dict[str, Dict[str, Any]]
        self.tools: List[types.Tool]
        self.server: Server

        self.fastapi = fastapi
        self.name = name or self.fastapi.title or "FastAPI MCP"
        self.description = description or self.fastapi.description

        self._base_url = "http://apiserver"
        self._describe_all_responses = describe_all_responses
        self._describe_full_response_schema = describe_full_response_schema
        self._include_operations = include_operations
        self._exclude_operations = exclude_operations
        self._include_tags = include_tags
        self._exclude_tags = exclude_tags
        self._auth_config = auth_config

        if self._auth_config:
            self._auth_config = self._auth_config.model_validate(self._auth_config)

        self._http_client = http_client or httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.fastapi, raise_app_exceptions=False),
            base_url=self._base_url,
            timeout=10.0,
        )

        self._forward_headers = {h.lower() for h in headers}
        self._http_transport: FastApiHttpSessionManager | None = None  # Store reference to HTTP transport for cleanup

        self.setup_server()

    def setup_server(self) -> None:
        openapi_schema = get_openapi(
            title=self.fastapi.title,
            version=self.fastapi.version,
            openapi_version=self.fastapi.openapi_version,
            description=self.fastapi.description,
            routes=self.fastapi.routes,
        )

        all_tools, self.operation_map = convert_openapi_to_mcp_tools(
            openapi_schema,
            describe_all_responses=self._describe_all_responses,
            describe_full_response_schema=self._describe_full_response_schema,
        )

        # Filter tools based on operation IDs and tags
        self.tools = self._filter_tools(all_tools, openapi_schema)

        mcp_server: Server = Server(self.name, self.description)

        @mcp_server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            return self.tools

        @mcp_server.call_tool()
        async def handle_call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> List[Union[types.TextContent, types.ImageContent, types.EmbeddedResource]]:
            # Extract HTTP request info from MCP context
            http_request_info = None
            try:
                # Access the MCP server's request context to get the original HTTP Request
                request_context = mcp_server.request_context

                if request_context and hasattr(request_context, "request"):
                    http_request = request_context.request

                    if http_request and hasattr(http_request, "method"):
                        http_request_info = HTTPRequestInfo(
                            method=http_request.method,
                            path=http_request.url.path,
                            headers=dict(http_request.headers),
                            cookies=http_request.cookies,
                            query_params=dict(http_request.query_params),
                            body=None,
                        )
                        logger.debug(
                            f"Extracted HTTP request info from context: {http_request_info.method} {http_request_info.path}"
                        )
            except (LookupError, AttributeError) as e:
                logger.error(f"Could not extract HTTP request info from context: {e}")

            return await self._execute_api_tool(
                client=self._http_client,
                tool_name=name,
                arguments=arguments,
                operation_map=self.operation_map,
                http_request_info=http_request_info,
            )

        self.server = mcp_server

    def _register_mcp_connection_endpoint_sse(
        self,
        router: FastAPI | APIRouter,
        transport: FastApiSseTransport,
        mount_path: str,
        dependencies: Optional[Sequence[params.Depends]],
    ):
        @router.get(mount_path, include_in_schema=False, operation_id="mcp_connection", dependencies=dependencies)
        async def handle_mcp_connection(request: Request):
            async with transport.connect_sse(request.scope, request.receive, request._send) as (reader, writer):
                await self.server.run(
                    reader,
                    writer,
                    self.server.create_initialization_options(notification_options=None, experimental_capabilities={}),
                    raise_exceptions=False,
                )

    def _register_mcp_messages_endpoint_sse(
        self,
        router: FastAPI | APIRouter,
        transport: FastApiSseTransport,
        mount_path: str,
        dependencies: Optional[Sequence[params.Depends]],
    ):
        @router.post(
            f"{mount_path}/messages/",
            include_in_schema=False,
            operation_id="mcp_messages",
            dependencies=dependencies,
        )
        async def handle_post_message(request: Request):
            return await transport.handle_fastapi_post_message(request)

    def _register_mcp_endpoints_sse(
        self,
        router: FastAPI | APIRouter,
        transport: FastApiSseTransport,
        mount_path: str,
        dependencies: Optional[Sequence[params.Depends]],
    ):
        self._register_mcp_connection_endpoint_sse(router, transport, mount_path, dependencies)
        self._register_mcp_messages_endpoint_sse(router, transport, mount_path, dependencies)

    def _register_mcp_http_endpoint(
        self,
        router: FastAPI | APIRouter,
        transport: FastApiHttpSessionManager,
        mount_path: str,
        dependencies: Optional[Sequence[params.Depends]],
    ):
        @router.api_route(
            mount_path,
            methods=["GET", "POST", "DELETE"],
            include_in_schema=False,
            operation_id="mcp_http",
            dependencies=dependencies,
        )
        async def handle_mcp_streamable_http(request: Request):
            return await transport.handle_fastapi_request(request)

    def _register_mcp_endpoints_http(
        self,
        router: FastAPI | APIRouter,
        transport: FastApiHttpSessionManager,
        mount_path: str,
        dependencies: Optional[Sequence[params.Depends]],
    ):
        self._register_mcp_http_endpoint(router, transport, mount_path, dependencies)

    def _setup_auth_2025_03_26(self):
        from fastapi_mcp.auth.proxy import (
            setup_oauth_custom_metadata,
            setup_oauth_metadata_proxy,
            setup_oauth_authorize_proxy,
            setup_oauth_fake_dynamic_register_endpoint,
        )

        if self._auth_config:
            if self._auth_config.custom_oauth_metadata:
                setup_oauth_custom_metadata(
                    app=self.fastapi,
                    auth_config=self._auth_config,
                    metadata=self._auth_config.custom_oauth_metadata,
                )

            elif self._auth_config.setup_proxies:
                assert self._auth_config.client_id is not None

                metadata_url = self._auth_config.oauth_metadata_url
                if not metadata_url:
                    metadata_url = f"{self._auth_config.issuer}{self._auth_config.metadata_path}"

                setup_oauth_metadata_proxy(
                    app=self.fastapi,
                    metadata_url=metadata_url,
                    path=self._auth_config.metadata_path,
                    register_path="/oauth/register" if self._auth_config.setup_fake_dynamic_registration else None,
                )
                setup_oauth_authorize_proxy(
                    app=self.fastapi,
                    client_id=self._auth_config.client_id,
                    authorize_url=self._auth_config.authorize_url,
                    audience=self._auth_config.audience,
                    default_scope=self._auth_config.default_scope,
                )
                if self._auth_config.setup_fake_dynamic_registration:
                    assert self._auth_config.client_secret is not None
                    setup_oauth_fake_dynamic_register_endpoint(
                        app=self.fastapi,
                        client_id=self._auth_config.client_id,
                        client_secret=self._auth_config.client_secret,
                    )

    def _setup_auth(self):
        if self._auth_config:
            if self._auth_config.version == "2025-03-26":
                self._setup_auth_2025_03_26()
            else:
                raise ValueError(
                    f"Unsupported MCP spec version: {self._auth_config.version}. Please check your AuthConfig."
                )
        else:
            logger.info("No auth config provided, skipping auth setup")

    def _resolve_include_prefix_from_metadata(self, router: APIRouter) -> List[str]:
        """
        Resolve the `include_router(router, prefix=...)` prefix using FastAPI's own
        include-time bookkeeping (FastAPI >= 0.137, Starlette's `_IncludedRouter`).

        Since FastAPI 0.137.0, `app.include_router()` no longer flattens a sub-router's
        routes into `app.routes`; instead it appends one `_IncludedRouter` object per
        `include_router()` call that carries `.original_router` (the router instance
        that was included) and `.include_context.prefix` (the prefix it was included
        under). Matching on `.original_router is router` identity is exact -- unlike
        diffing paths, it works even when `router` has zero routes of its own, and it
        cannot be confused by two different routers sharing the same endpoint function.

        Returns one prefix string per matching inclusion (usually zero or one; more
        than one means `router` was `include_router`-ed more than once under different
        prefixes). Returns an empty list on FastAPI < 0.137, where `app.routes` has no
        such per-inclusion record at all.
        """
        prefixes = []
        for app_route in self.fastapi.routes:
            if getattr(app_route, "original_router", None) is not router:
                continue
            include_context = getattr(app_route, "include_context", None)
            prefix = getattr(include_context, "prefix", None)
            if prefix is not None:
                prefixes.append(prefix)
        return prefixes

    def _resolve_include_prefix_by_diff(self, router: APIRouter) -> List[str]:
        """
        Resolve the `include_router(router, prefix=...)` prefix by diffing `router`'s
        own routes against their counterparts on `self.fastapi.routes` (same endpoint
        function, same HTTP methods, path ending in the router's own route path).

        Fallback for FastAPI < 0.137, where `app.include_router()` flattens sub-routes
        directly into `app.routes` and there is no other way to recover the prefix.

        Requires *every* route defined on `router` to agree on the same candidate
        prefix before accepting it -- an endpoint function reused across two different
        routers (or a router included more than once under different prefixes) can
        otherwise make an unrelated prefix look like a valid match. Returns a list of
        the distinct candidate prefixes found: empty if none of `router`'s routes could
        be matched at all, or more than one entry if there is a genuine ambiguity.
        """
        own_routes = [r for r in router.routes if getattr(r, "path", None) and getattr(r, "endpoint", None) is not None]
        if not own_routes:
            return []

        per_route_candidates = []
        for router_route in own_routes:
            router_path: str = getattr(router_route, "path")
            router_endpoint = getattr(router_route, "endpoint")
            router_methods = getattr(router_route, "methods", None)
            matches = set()
            for app_route in self.fastapi.routes:
                app_path = getattr(app_route, "path", None)
                if not app_path or not app_path.endswith(router_path):
                    continue
                if getattr(app_route, "endpoint", None) is not router_endpoint:
                    continue
                if router_methods is not None and getattr(app_route, "methods", None) != router_methods:
                    continue
                matches.add(app_path[: -len(router_path)])
            if not matches:
                return []
            per_route_candidates.append(matches)

        return sorted(set.intersection(*per_route_candidates))

    def _resolve_router_include_prefix(self, router: APIRouter) -> str:
        """
        Resolve the prefix under which `router` was actually mounted onto `self.fastapi`.

        When a router is included via `app.include_router(router, prefix="/x")` without
        setting `prefix` on the `APIRouter()` constructor itself, that prefix is only
        reflected on `self.fastapi`'s route table -- the router object's own `.prefix`
        attribute stays empty. Tries the exact, identity-based resolution first
        (FastAPI >= 0.137) and falls back to diffing route paths (FastAPI < 0.137).

        Returns an empty string, and logs a warning, if no prefix could be resolved
        unambiguously -- e.g. the router hasn't been included into the app yet, or (on
        FastAPI < 0.137 only) it has no routes of its own to diff against. This
        preserves the previous behavior of relying solely on `router.prefix` rather
        than risk mounting under the wrong prefix.
        """
        prefixes = self._resolve_include_prefix_from_metadata(router)
        if not prefixes:
            prefixes = self._resolve_include_prefix_by_diff(router)

        if not prefixes:
            logger.warning(
                f"Could not determine the prefix that {router!r} was included under. "
                "Mounting at the router's own prefix; if this router was included via "
                "`app.include_router(router, prefix=...)`, make sure `include_router` is "
                "called before `mount_http`/`mount_sse`, or set `prefix` on the "
                "`APIRouter()` constructor directly."
            )
            return ""

        unique_prefixes = sorted(set(prefixes))
        if len(unique_prefixes) > 1:
            logger.warning(
                f"{router!r} appears to be included in the app under multiple different "
                f"prefixes {unique_prefixes}. Could not unambiguously resolve where its "
                "MCP endpoint should be mounted, so falling back to the router's own "
                "prefix rather than guessing."
            )
            return ""

        return unique_prefixes[0]

    def mount_http(
        self,
        router: Annotated[
            Optional[FastAPI | APIRouter],
            Doc(
                """
                The FastAPI app or APIRouter to mount the MCP server to. If not provided, the MCP
                server will be mounted to the FastAPI app.
                """
            ),
        ] = None,
        mount_path: Annotated[
            str,
            Doc(
                """
                Path where the MCP server will be mounted.
                Mount path is appended to the root path of FastAPI router, or to the prefix of APIRouter.
                Defaults to '/mcp'.
                """
            ),
        ] = "/mcp",
    ) -> None:
        """
        Mount the MCP server with HTTP transport to **any** FastAPI app or APIRouter.

        There is no requirement that the FastAPI app or APIRouter is the same as the one that the MCP
        server was created from.

        If `router` is an `APIRouter`, it must already be included into the app (via
        `app.include_router(router, ...)`) *before* calling this method -- the effective
        mount path is resolved from the app's current route table at call time and is
        not re-evaluated if the router is included afterwards.
        """
        # Normalize mount path
        if not mount_path.startswith("/"):
            mount_path = f"/{mount_path}"
        if mount_path.endswith("/"):
            mount_path = mount_path[:-1]

        if not router:
            router = self.fastapi

        assert isinstance(router, (FastAPI, APIRouter)), f"Invalid router type: {type(router)}"

        include_prefix = self._resolve_router_include_prefix(router) if isinstance(router, APIRouter) else ""
        full_mount_path = mount_path if isinstance(router, FastAPI) else include_prefix + router.prefix + mount_path

        http_transport = FastApiHttpSessionManager(mcp_server=self.server)
        dependencies = self._auth_config.dependencies if self._auth_config else None

        self._register_mcp_endpoints_http(router, http_transport, mount_path, dependencies)
        self._setup_auth()
        self._http_transport = http_transport  # Store reference

        # HACK: If we got a router and not a FastAPI instance, we need to re-include the router so that
        # FastAPI will pick up the new routes we added. The problem with this approach is that we assume
        # that the router is a sub-router of self.fastapi, which may not always be the case.
        #
        # TODO: Find a better way to do this.
        if isinstance(router, APIRouter):
            self.fastapi.include_router(router, prefix=include_prefix)

        logger.info(f"MCP HTTP server listening at {full_mount_path}")

    def mount_sse(
        self,
        router: Annotated[
            Optional[FastAPI | APIRouter],
            Doc(
                """
                The FastAPI app or APIRouter to mount the MCP server to. If not provided, the MCP
                server will be mounted to the FastAPI app.
                """
            ),
        ] = None,
        mount_path: Annotated[
            str,
            Doc(
                """
                Path where the MCP server will be mounted.
                Mount path is appended to the root path of FastAPI router, or to the prefix of APIRouter.
                Defaults to '/sse'.
                """
            ),
        ] = "/sse",
    ) -> None:
        """
        Mount the MCP server with SSE transport to **any** FastAPI app or APIRouter.

        There is no requirement that the FastAPI app or APIRouter is the same as the one that the MCP
        server was created from.

        If `router` is an `APIRouter`, it must already be included into the app (via
        `app.include_router(router, ...)`) *before* calling this method -- the effective
        mount path is resolved from the app's current route table at call time and is
        not re-evaluated if the router is included afterwards.
        """
        # Normalize mount path
        if not mount_path.startswith("/"):
            mount_path = f"/{mount_path}"
        if mount_path.endswith("/"):
            mount_path = mount_path[:-1]

        if not router:
            router = self.fastapi

        # Build the base path correctly for the SSE transport
        assert isinstance(router, (FastAPI, APIRouter)), f"Invalid router type: {type(router)}"
        include_prefix = self._resolve_router_include_prefix(router) if isinstance(router, APIRouter) else ""
        base_path = mount_path if isinstance(router, FastAPI) else include_prefix + router.prefix + mount_path
        messages_path = f"{base_path}/messages/"

        sse_transport = FastApiSseTransport(messages_path)
        dependencies = self._auth_config.dependencies if self._auth_config else None

        self._register_mcp_endpoints_sse(router, sse_transport, mount_path, dependencies)
        self._setup_auth()

        # HACK: If we got a router and not a FastAPI instance, we need to re-include the router so that
        # FastAPI will pick up the new routes we added. The problem with this approach is that we assume
        # that the router is a sub-router of self.fastapi, which may not always be the case.
        #
        # TODO: Find a better way to do this.
        if isinstance(router, APIRouter):
            self.fastapi.include_router(router, prefix=include_prefix)

        logger.info(f"MCP SSE server listening at {base_path}")

    def mount(
        self,
        router: Annotated[
            Optional[FastAPI | APIRouter],
            Doc(
                """
                The FastAPI app or APIRouter to mount the MCP server to. If not provided, the MCP
                server will be mounted to the FastAPI app.
                """
            ),
        ] = None,
        mount_path: Annotated[
            str,
            Doc(
                """
                Path where the MCP server will be mounted.
                Mount path is appended to the root path of FastAPI router, or to the prefix of APIRouter.
                Defaults to '/mcp'.
                """
            ),
        ] = "/mcp",
        transport: Annotated[
            Literal["sse"],
            Doc(
                """
                The transport type for the MCP server. Currently only 'sse' is supported.
                This parameter is deprecated.
                """
            ),
        ] = "sse",
    ) -> None:
        """
        [DEPRECATED] Mount the MCP server to **any** FastAPI app or APIRouter.

        This method is deprecated and will be removed in a future version.
        Use mount_http() for HTTP transport (recommended) or mount_sse() for SSE transport instead.

        For backwards compatibility, this method defaults to SSE transport.

        There is no requirement that the FastAPI app or APIRouter is the same as the one that the MCP
        server was created from.
        """
        import warnings

        warnings.warn(
            "mount() is deprecated and will be removed in a future version. "
            "Use mount_http() for HTTP transport (recommended) or mount_sse() for SSE transport instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        if transport == "sse":
            self.mount_sse(router, mount_path)
        else:  # pragma: no cover
            raise ValueError(  # pragma: no cover
                f"Unsupported transport: {transport}. Use mount_sse() or mount_http() instead."
            )

    async def _execute_api_tool(
        self,
        client: Annotated[httpx.AsyncClient, Doc("httpx client to use in API calls")],
        tool_name: Annotated[str, Doc("The name of the tool to execute")],
        arguments: Annotated[Dict[str, Any], Doc("The arguments for the tool")],
        operation_map: Annotated[Dict[str, Dict[str, Any]], Doc("A mapping from tool names to operation details")],
        http_request_info: Annotated[
            Optional[HTTPRequestInfo],
            Doc("HTTP request info to forward to the actual API call"),
        ] = None,
    ) -> List[Union[types.TextContent, types.ImageContent, types.EmbeddedResource]]:
        """
        Execute an MCP tool by making an HTTP request to the corresponding API endpoint.

        Returns:
            The result as MCP content types
        """
        if tool_name not in operation_map:
            raise Exception(f"Unknown tool: {tool_name}")

        operation = operation_map[tool_name]
        path: str = operation["path"]
        method: str = operation["method"]
        parameters: List[Dict[str, Any]] = operation.get("parameters", [])
        arguments = arguments.copy() if arguments else {}  # Deep copy arguments to avoid mutating the original

        for param in parameters:
            if param.get("in") == "path" and param.get("name") in arguments:
                param_name = param.get("name", None)
                if param_name is None:
                    raise ValueError(f"Parameter name is None for parameter: {param}")
                path = path.replace(f"{{{param_name}}}", str(arguments.pop(param_name)))

        query = {}
        for param in parameters:
            if param.get("in") == "query" and param.get("name") in arguments:
                param_name = param.get("name", None)
                if param_name is None:
                    raise ValueError(f"Parameter name is None for parameter: {param}")
                query[param_name] = arguments.pop(param_name)

        headers = {}
        for param in parameters:
            if param.get("in") == "header" and param.get("name") in arguments:
                param_name = param.get("name", None)
                if param_name is None:
                    raise ValueError(f"Parameter name is None for parameter: {param}")
                headers[param_name] = arguments.pop(param_name)

        # Forward headers that are in the allowlist
        if http_request_info and http_request_info.headers:
            for name, value in http_request_info.headers.items():
                # case-insensitive check for allowed headers
                if name.lower() in self._forward_headers:
                    headers[name] = value

        body = arguments if arguments else None

        try:
            logger.debug(f"Making {method.upper()} request to {path}")
            response = await self._request(client, method, path, query, headers, body)

            # TODO: Better typing for the AsyncClientProtocol. It should return a ResponseProtocol that has a json() method that returns a dict/list/etc.
            try:
                result = response.json()
                result_text = json.dumps(result, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                if hasattr(response, "text"):
                    result_text = response.text
                else:
                    result_text = response.content

            # If not raising an exception, the MCP server will return the result as a regular text response, without marking it as an error.
            # TODO: Use a raise_for_status() method on the response (it needs to also be implemented in the AsyncClientProtocol)
            if 400 <= response.status_code < 600:
                raise Exception(
                    f"Error calling {tool_name}. Status code: {response.status_code}. Response: {response.text}"
                )

            try:
                return [types.TextContent(type="text", text=result_text)]
            except ValueError:
                return [types.TextContent(type="text", text=result_text)]

        except Exception as e:
            logger.exception(f"Error calling {tool_name}")
            raise e

    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        query: Dict[str, Any],
        headers: Dict[str, str],
        body: Optional[Any],
    ) -> Any:
        if method.lower() == "get":
            return await client.get(path, params=query, headers=headers)
        elif method.lower() == "post":
            return await client.post(path, params=query, headers=headers, json=body)
        elif method.lower() == "put":
            return await client.put(path, params=query, headers=headers, json=body)
        elif method.lower() == "delete":
            return await client.delete(path, params=query, headers=headers)
        elif method.lower() == "patch":
            return await client.patch(path, params=query, headers=headers, json=body)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

    def _filter_tools(self, tools: List[types.Tool], openapi_schema: Dict[str, Any]) -> List[types.Tool]:
        """
        Filter tools based on operation IDs and tags.

        Args:
            tools: List of tools to filter
            openapi_schema: The OpenAPI schema

        Returns:
            Filtered list of tools
        """
        if (
            self._include_operations is None
            and self._exclude_operations is None
            and self._include_tags is None
            and self._exclude_tags is None
        ):
            return tools

        operations_by_tag: Dict[str, List[str]] = {}
        for path, path_item in openapi_schema.get("paths", {}).items():
            for method, operation in path_item.items():
                if method not in ["get", "post", "put", "delete", "patch"]:
                    continue

                operation_id = operation.get("operationId")
                if not operation_id:
                    continue

                tags = operation.get("tags", [])
                for tag in tags:
                    if tag not in operations_by_tag:
                        operations_by_tag[tag] = []
                    operations_by_tag[tag].append(operation_id)

        operations_to_include = set()

        if self._include_operations is not None:
            operations_to_include.update(self._include_operations)
        elif self._exclude_operations is not None:
            all_operations = {tool.name for tool in tools}
            operations_to_include.update(all_operations - set(self._exclude_operations))

        if self._include_tags is not None:
            for tag in self._include_tags:
                operations_to_include.update(operations_by_tag.get(tag, []))
        elif self._exclude_tags is not None:
            excluded_operations = set()
            for tag in self._exclude_tags:
                excluded_operations.update(operations_by_tag.get(tag, []))

            all_operations = {tool.name for tool in tools}
            operations_to_include.update(all_operations - excluded_operations)

        filtered_tools = [tool for tool in tools if tool.name in operations_to_include]

        if filtered_tools:
            filtered_operation_ids = {tool.name for tool in filtered_tools}
            self.operation_map = {
                op_id: details for op_id, details in self.operation_map.items() if op_id in filtered_operation_ids
            }

        return filtered_tools
