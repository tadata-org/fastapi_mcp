from pydantic import HttpUrl
from typing_extensions import Annotated, Doc
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
import httpx
from typing import Optional, Dict, Any
import logging
import json
import base64
import binascii
from urllib.parse import urlencode

from fastapi_mcp.types import (
    ClientRegistrationRequest,
    ClientRegistrationResponse,
    AuthConfig,
    OAuthMetadata,
    OAuthMetadataDict,
    OAuthMetadataResponse,
    StrHttpUrl,
)


logger = logging.getLogger(__name__)


async def discover_oauth_endpoints(metadata_url: str) -> OAuthMetadataResponse:
    """
    Fetch OAuth metadata and extract endpoint URLs for auto-discovery.

    Args:
        metadata_url: The OAuth provider's metadata endpoint URL

    Returns:
        OAuthMetadataResponse with populated endpoint URLs from OAuth metadata
    """
    try:
        async with httpx.AsyncClient() as client:
            logger.debug(f"Discovering OAuth endpoints from {metadata_url}")
            response = await client.get(metadata_url)

            if response.status_code != 200:
                logger.error(f"Failed to fetch OAuth metadata: {response.status_code}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to fetch OAuth metadata from {metadata_url}",
                )

            metadata = response.json()

            # Extract common endpoint URLs and create typed response
            endpoints = OAuthMetadataResponse(
                authorization_endpoint=HttpUrl(metadata.get("authorization_endpoint")),
                token_endpoint=HttpUrl(metadata.get("token_endpoint")),
                userinfo_endpoint=HttpUrl(metadata.get("userinfo_endpoint")),
                issuer=HttpUrl(metadata.get("issuer")),
            )

            logger.debug(f"Discovered endpoints: {endpoints}")
            return endpoints

    except httpx.RequestError as e:
        logger.error(f"Network error fetching OAuth metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Network error communicating with OAuth provider"
        )
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Invalid OAuth metadata format: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid OAuth metadata format")


def encode_oauth_state(client_redirect_uri: str, original_state: Optional[str] = None) -> str:
    """
    Encode client callback details into the OAuth state parameter.

    This allows the callback proxy to know where to forward the authorization
    result after receiving it from the external OAuth provider.

    Args:
        client_redirect_uri: The original client's callback URL
        original_state: The original state parameter from the client (optional)

    Returns:
        Base64-encoded JSON string containing the client details
    """
    state_data = {
        "client_redirect_uri": client_redirect_uri,
        "original_state": original_state,
    }

    state_json = json.dumps(state_data, separators=(",", ":"))
    encoded_state = base64.urlsafe_b64encode(state_json.encode("utf-8")).decode("ascii")

    return encoded_state


def decode_oauth_state(encoded_state: str) -> Dict[str, Any]:
    """
    Decode the OAuth state parameter to extract client callback details.

    Args:
        encoded_state: Base64-encoded state parameter

    Returns:
        Dictionary containing client_redirect_uri and original_state
    """
    try:
        decoded_bytes = base64.urlsafe_b64decode(encoded_state.encode("ascii"))
        state_json = decoded_bytes.decode("utf-8")
        state_data = json.loads(state_json)

        if not isinstance(state_data, dict) or "client_redirect_uri" not in state_data:
            raise ValueError("Invalid state parameter structure")

        return state_data

    except (json.JSONDecodeError, binascii.Error, UnicodeDecodeError) as e:
        logger.error(f"Failed to decode OAuth state parameter: {e}")
        raise ValueError("Invalid or corrupted state parameter") from e


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
    token_url_override: Annotated[
        Optional[str],
        Doc(
            """
            Override for the token endpoint URL in metadata.

            If provided, this URL will be used in metadata instead of the one from
            the external OAuth provider's metadata.
            """
        ),
    ] = None,
    user_info_url_override: Annotated[
        Optional[str],
        Doc(
            """
            Override for the user info endpoint URL in metadata.

            If provided, this URL will be used in metadata instead of the one from
            the external OAuth provider's metadata.
            """
        ),
    ] = None,
    include_in_schema: Annotated[bool, Doc("Whether to include the metadata endpoint in your OpenAPI docs")] = False,
):
    """
    Proxy for your OAuth provider's Metadata endpoint, just adding our (fake) registration endpoint.
    Explicitly configured endpoints take precedence over fetched ones.
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

        metadata = response.json()

        metadata["issuer"] = HttpUrl(metadata["issuer"])

        # Override with our fake registration endpoint
        if register_path:
            metadata["registration_endpoint"] = HttpUrl(f"{base_url}{register_path}")

        # Override with our proxy authorize endpoint
        metadata["authorization_endpoint"] = HttpUrl(f"{base_url}{authorize_path}")

        # Prefer explicitly configured endpoints over fetched ones
        if token_url_override:
            metadata["token_endpoint"] = HttpUrl(token_url_override)
        if user_info_url_override:
            metadata["userinfo_endpoint"] = HttpUrl(user_info_url_override)

        return OAuthMetadata.model_validate(metadata)


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
    callback_path: Annotated[str, Doc("The path where the OAuth callback endpoint is mounted")] = "/oauth/callback",
    include_in_schema: Annotated[bool, Doc("Whether to include the authorize endpoint in your OpenAPI docs")] = False,
):
    """
    Proxy for your OAuth provider's authorize endpoint that logs the requested scopes and adds
    default scopes and the audience parameter if not provided.

    This proxy uses the server's callback URL instead of the client's redirect_uri, and encodes
    the original client details in the state parameter so the callback proxy knows where to
    forward the authorization result.
    """

    @app.get(
        path,
        include_in_schema=include_in_schema,
    )
    async def oauth_authorize_proxy(
        request: Request,
        response_type: str = "code",
        client_id: Optional[str] = client_id,
        redirect_uri: Optional[str] = None,
        scope: str = "",
        state: Optional[str] = None,
        code_challenge: Optional[str] = None,
        code_challenge_method: Optional[str] = None,
        audience: Optional[str] = audience,
    ):
        # Validate that client provided a redirect_uri
        if not redirect_uri:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="redirect_uri parameter is required")

        if not scope:
            logger.warning("Client didn't provide any scopes! Using default scopes.")
            scope = default_scope
            logger.debug(f"Default scope: {scope}")

        scopes = scope.split()
        logger.debug(f"Scopes passed: {scopes}")
        for required_scope in default_scope.split():
            if required_scope not in scopes:
                scopes.append(required_scope)

        # Encode the client's callback details in the state parameter
        base_url = str(request.base_url).rstrip("/")
        server_callback_uri = f"{base_url}{callback_path}"

        # Encode client details into state parameter for callback proxy
        encoded_state = encode_oauth_state(client_redirect_uri=redirect_uri, original_state=state)

        logger.debug(f"Using server callback URL: {server_callback_uri}")
        logger.debug(f"Original client redirect URI: {redirect_uri}")

        params = {
            "response_type": response_type,
            "client_id": client_id,
            "redirect_uri": server_callback_uri,  # Use server's callback URL
            "scope": " ".join(scopes),
            "audience": audience,
            "state": encoded_state,  # Use encoded state with client details
        }

        if code_challenge:
            params["code_challenge"] = code_challenge
        if code_challenge_method:
            params["code_challenge_method"] = code_challenge_method

        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        auth_url = f"{authorize_url}?{urlencode(params)}"

        return RedirectResponse(url=auth_url)


def setup_oauth_callback_proxy(
    app: Annotated[FastAPI, Doc("The FastAPI app instance")],
    client_id: Annotated[str, Doc("The client ID of the OAuth application")],
    client_secret: Annotated[str, Doc("The client secret of the OAuth application")],
    token_url: Annotated[StrHttpUrl, Doc("The URL of the OAuth provider's token endpoint")],
    user_info_url: Annotated[
        Optional[StrHttpUrl], Doc("Optional URL of the OAuth provider's user info endpoint")
    ] = None,
    path: Annotated[str, Doc("The path to mount the callback endpoint at")] = "/oauth/callback",
    include_in_schema: Annotated[bool, Doc("Whether to include the callback endpoint in your OpenAPI docs")] = False,
):
    """
    OAuth callback proxy that receives authorization codes from external OAuth providers
    and forwards the access tokens to the original MCP client callbacks.

    This enables remote MCP servers to support arbitrary clients without requiring each
    client's redirect URI to be pre-registered with the OAuth provider - only the server's
    callback URL needs to be registered.
    """

    @app.get(path, include_in_schema=include_in_schema, operation_id="oauth_callback_proxy")
    async def oauth_callback_proxy(
        request: Request,
        code: Optional[str] = None,
        state: Optional[str] = None,
        error: Optional[str] = None,
        error_description: Optional[str] = None,
    ):
        if error:
            error_msg = error_description or error
            logger.error(f"OAuth provider returned error: {error} - {error_msg}")

            # If we have a state, try to decode it to forward the error to the client
            if state:
                try:
                    client_details = decode_oauth_state(state)
                    client_redirect_uri = client_details["client_redirect_uri"]
                    original_state = client_details.get("original_state")

                    # Forward error to client
                    error_params = {
                        "error": error,
                        "error_description": error_description,
                    }
                    if original_state:
                        error_params["state"] = original_state

                    error_url = f"{client_redirect_uri}?{urlencode(error_params)}"
                    return RedirectResponse(url=error_url)
                except ValueError as e:
                    logger.error(f"Failed to decode state parameter: {e}")

            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"OAuth error: {error_msg}")

        if not code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization code is required")

        if not state:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="State parameter is required")

        try:
            client_details = decode_oauth_state(state)
            client_redirect_uri = client_details["client_redirect_uri"]
            original_state = client_details.get("original_state")

            logger.debug(f"Decoded client redirect URI: {client_redirect_uri}")

        except ValueError as e:
            logger.error(f"Invalid state parameter: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state parameter")

        try:
            base_url = str(request.base_url).rstrip("/")
            server_callback_uri = f"{base_url}{path}"

            async with httpx.AsyncClient() as client:
                token_data = {
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": server_callback_uri,
                }

                logger.debug(f"Exchanging code for token with {token_url}")

                response = await client.post(
                    str(token_url), data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"}
                )

                if response.status_code != 200:
                    logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Failed to exchange authorization code for token",
                    )

                token_response = response.json()
                access_token = token_response.get("access_token")

                if not access_token:
                    logger.error(f"No access token in response: {token_response}")
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid token response from OAuth provider"
                    )

                logger.debug("Successfully obtained access token")

                # Optionally fetch user information
                user_info = None
                if user_info_url:
                    try:
                        logger.debug(f"Fetching user info from {user_info_url}")
                        user_response = await client.get(
                            str(user_info_url), headers={"Authorization": f"Bearer {access_token}"}
                        )

                        if user_response.status_code == 200:
                            user_info = user_response.json()
                            logger.debug("Successfully fetched user info")
                        else:
                            logger.warning(f"Failed to fetch user info: {user_response.status_code}")

                    except Exception as e:
                        logger.warning(f"Error fetching user info: {e}")

        except httpx.RequestError as e:
            logger.error(f"Network error during token exchange: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail="Network error communicating with OAuth provider"
            )

        try:
            callback_params = {
                "access_token": access_token,
                "token_type": token_response.get("token_type", "Bearer"),
            }

            if "expires_in" in token_response:
                callback_params["expires_in"] = token_response["expires_in"]
            if "refresh_token" in token_response:
                callback_params["refresh_token"] = token_response["refresh_token"]
            if "scope" in token_response:
                callback_params["scope"] = token_response["scope"]

            if user_info:
                callback_params["user_info"] = json.dumps(user_info)

            # Restore original state if it existed
            if original_state:
                callback_params["state"] = original_state

            # Construct the final callback URL
            client_callback_url = f"{client_redirect_uri}?{urlencode(callback_params)}"

            logger.debug(f"Forwarding token to client callback: {client_redirect_uri}")

            return RedirectResponse(url=client_callback_url)

        except Exception as e:
            logger.error(f"Error forwarding to client callback: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to forward authorization result to client",
            )


def setup_oauth_protected_resource_metadata(
    app: Annotated[
        FastAPI,
        Doc("The FastAPI app instance"),
    ],
    auth_config: Annotated[
        AuthConfig,
        Doc("The auth configuration containing authorization server details"),
    ],
    path: Annotated[
        str, Doc("The path to mount the protected resource metadata endpoint at")
    ] = "/.well-known/oauth-protected-resource",
    include_in_schema: Annotated[
        bool,
        Doc("Whether to include the metadata endpoint in your OpenAPI docs"),
    ] = False,
):
    """
    OAuth 2.0 Protected Resource Metadata endpoint according to RFC 9728.

    This endpoint provides metadata about the MCP server as an OAuth 2.1 resource server.
    This allows the MCP server to act purely as a resource server, without being an authorization server.
    """

    @app.get(
        path,
        response_model=Dict[str, Any],
        include_in_schema=include_in_schema,
        operation_id="oauth_protected_resource_metadata",
    )
    async def oauth_protected_resource_metadata(request: Request):
        base_url = str(request.base_url).rstrip("/")

        scopes_supported = ["openid", "profile", "email"]  # Default fallback
        if auth_config.default_scope:
            scopes_supported = auth_config.default_scope.split()

        metadata = {
            "resource": base_url,
            "authorization_servers": [str(auth_config.issuer)],
            "scopes_supported": scopes_supported,
            "bearer_methods_supported": ["header"],
            "resource_documentation": f"{base_url}/docs",
        }

        if auth_config.audience:
            metadata["audience"] = [auth_config.audience]

        return metadata


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
