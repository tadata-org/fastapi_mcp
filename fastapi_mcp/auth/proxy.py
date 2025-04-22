from typing_extensions import Annotated, Doc
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
import httpx
from typing import Optional
import logging
from urllib.parse import urlencode

from fastapi_mcp.types import (
    ClientRegistrationRequest,
    ClientRegistrationResponse,
    AuthConfig,
    OAuthMetadata,
    OAuthMetadataDict,
    StrHttpUrl,
)


logger = logging.getLogger(__name__)


def setup_oauth_custom_metadata(
    app: Annotated[FastAPI, Doc("The FastAPI app instance")],
    auth_config: Annotated[AuthConfig, Doc("The AuthConfig used")],
    metadata: Annotated[OAuthMetadataDict, Doc("The custom metadata specified in AuthConfig")],
    include_in_schema: Annotated[bool, Doc("Whether to include the metadata endpoint in your OpenAPI docs")] = False,
):
    """
    Just serve the custom metadata provided to AuthConfig under the path specified in `metadata_path`.
    """

    auth_config = AuthConfig.model_validate(auth_config)
    metadata = OAuthMetadata.model_validate(metadata)

    @app.get(
        auth_config.metadata_path,
        response_model=OAuthMetadata,
        response_model_exclude_unset=True,
        response_model_exclude_none=True,
        include_in_schema=include_in_schema,
        operation_id="oauth_custom_metadata",
    )
    async def oauth_metadata_proxy():
        return metadata


def setup_oauth_metadata_proxy(
    app: Annotated[FastAPI, Doc("The FastAPI app instance")],
    metadata_url: Annotated[
        str,
        Doc(
            """
            The URL of the OAuth provider's metadata endpoint that you want to proxy.
            """
        ),
    ],
    path: Annotated[
        str,
        Doc(
            """
            The path to mount the OAuth metadata endpoint at.

            Clients will usually expect this to be /.well-known/oauth-authorization-server
            """
        ),
    ] = "/.well-known/oauth-authorization-server",
    authorize_path: Annotated[
        str,
        Doc(
            """
            The path to mount the authorize endpoint at.

            Clients will usually expect this to be /oauth/authorize
            """
        ),
    ] = "/oauth/authorize",
    register_path: Annotated[
        Optional[str],
        Doc(
            """
            The path to mount the register endpoint at.

            Clients will usually expect this to be /oauth/register
            """
        ),
    ] = None,
    include_in_schema: Annotated[bool, Doc("Whether to include the metadata endpoint in your OpenAPI docs")] = False,
):
    """
    Proxy for your OAuth provider's Metadata endpoint, just adding our (fake) registration endpoint.
    """

    @app.get(
        path,
        response_model=OAuthMetadata,
        response_model_exclude_unset=True,
        response_model_exclude_none=True,
        include_in_schema=include_in_schema,
        operation_id="oauth_metadata_proxy",
    )
    async def oauth_metadata_proxy(request: Request):
        base_url = str(request.base_url).rstrip("/")

        # Fetch your OAuth provider's OpenID Connect metadata
        async with httpx.AsyncClient() as client:
            response = await client.get(metadata_url)
            if response.status_code != 200:
                logger.error(
                    f"Failed to fetch OAuth metadata from {metadata_url}: {response.status_code}. Response: {response.text}"
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to fetch OAuth metadata",
                )

            oauth_metadata = response.json()

        # Override the registration endpoint if provided
        if register_path:
            oauth_metadata["registration_endpoint"] = f"{base_url}{register_path}"

        # Replace your OAuth provider's authorize endpoint with our proxy
        oauth_metadata["authorization_endpoint"] = f"{base_url}{authorize_path}"

        return OAuthMetadata.model_validate(oauth_metadata)


def setup_oauth_authorize_proxy(
    app: Annotated[FastAPI, Doc("The FastAPI app instance")],
    client_id: Annotated[
        str,
        Doc(
            """
            In case the client doesn't specify a client ID, this will be used as the default client ID on the
            request to your OAuth provider.
            """
        ),
    ],
    authorize_url: Annotated[
        Optional[StrHttpUrl],
        Doc(
            """
            The URL of your OAuth provider's authorization endpoint.

            Usually this is something like `https://app.example.com/oauth/authorize`.
            """
        ),
    ],
    audience: Annotated[
        Optional[str],
        Doc(
            """
            Currently (2025-04-21), some Auth-supporting MCP clients (like `npx mcp-remote`) might not specify the
            audience when sending a request to your server.

            This may cause unexpected behavior from your OAuth provider, so this is a workaround.

            In case the client doesn't specify an audience, this will be used as the default audience on the
            request to your OAuth provider.
            """
        ),
    ] = None,
    default_scope: Annotated[
        str,
        Doc(
            """
            Currently (2025-04-21), some Auth-supporting MCP clients (like `npx mcp-remote`) might not specify the
            scope when sending a request to your server.

            This may cause unexpected behavior from your OAuth provider, so this is a workaround.

            Here is where you can optionally specify a default scope that will be sent to your OAuth provider in case
            the client doesn't specify it.
            """
        ),
    ] = "openid profile email",
    path: Annotated[str, Doc("The path to mount the authorize endpoint at")] = "/oauth/authorize",
    include_in_schema: Annotated[bool, Doc("Whether to include the authorize endpoint in your OpenAPI docs")] = False,
):
    """
    Proxy for your OAuth provider's authorize endpoint that logs the requested scopes and adds
    default scopes and the audience parameter if not provided.
    """

    @app.get(
        path,
        include_in_schema=include_in_schema,
    )
    async def oauth_authorize_proxy(
        response_type: str = "code",
        client_id: Optional[str] = client_id,
        redirect_uri: Optional[str] = None,
        scope: str = "",
        state: Optional[str] = None,
        code_challenge: Optional[str] = None,
        code_challenge_method: Optional[str] = None,
        audience: Optional[str] = audience,
    ):
        if not scope:
            logger.warning("Client didn't provide any scopes! Using default scopes.")
            scope = default_scope

        scopes = scope.split()
        for required_scope in default_scope.split():
            if required_scope not in scopes:
                scopes.append(required_scope)

        params = {
            "response_type": response_type,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "audience": audience,
        }

        if state:
            params["state"] = state
        if code_challenge:
            params["code_challenge"] = code_challenge
        if code_challenge_method:
            params["code_challenge_method"] = code_challenge_method

        auth_url = f"{authorize_url}?{urlencode(params)}"

        return RedirectResponse(url=auth_url)


def setup_oauth_fake_dynamic_register_endpoint(
    app: Annotated[FastAPI, Doc("The FastAPI app instance")],
    client_id: Annotated[str, Doc("The client ID of the pre-registered client")],
    client_secret: Annotated[str, Doc("The client secret of the pre-registered client")],
    path: Annotated[str, Doc("The path to mount the register endpoint at")] = "/oauth/register",
    include_in_schema: Annotated[bool, Doc("Whether to include the register endpoint in your OpenAPI docs")] = False,
):
    """
    A proxy for dynamic client registration endpoint.

    In MCP 2025-03-26 Spec, it is recommended to support OAuth Dynamic Client Registration (RFC 7591).
    Furthermore, `npx mcp-remote` which is the current de-facto client that supports MCP's up-to-date spec,
    requires this endpoint to be present.

    But, this is an overcomplication for most use cases.

    So instead of actually implementing dynamic client registration, we just echo back the pre-registered
    client ID and secret.

    Use this if you don't need dynamic client registration, or if your OAuth provider doesn't support it.
    """

    @app.post(
        path,
        response_model=ClientRegistrationResponse,
        include_in_schema=include_in_schema,
    )
    async def oauth_register_proxy(request: ClientRegistrationRequest) -> ClientRegistrationResponse:
        client_response = ClientRegistrationResponse(
            client_name=request.client_name or "MCP Server",  # Name doesn't really affect functionality
            client_id=client_id,
            client_secret=client_secret,
            redirect_uris=request.redirect_uris,  # Just echo back their requested URIs
            grant_types=request.grant_types or ["authorization_code"],
            token_endpoint_auth_method=request.token_endpoint_auth_method or "none",
        )
        return client_response
