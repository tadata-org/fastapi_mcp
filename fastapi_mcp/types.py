import time
from typing import Any, Dict, Annotated, Union, Optional, Sequence, Literal, List
from typing_extensions import Doc
from pydantic import (
    BaseModel,
    ConfigDict,
    HttpUrl,
    field_validator,
    model_validator,
)
from pydantic.main import IncEx
from fastapi import params


StrHttpUrl = Annotated[Union[str, HttpUrl], HttpUrl]


class BaseType(BaseModel):
    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)


class HTTPRequestInfo(BaseType):
    method: str
    path: str
    headers: Dict[str, str]
    cookies: Dict[str, str]
    query_params: Dict[str, str]
    body: Any


class OAuthMetadata(BaseType):
    """OAuth 2.0 Server Metadata according to RFC 8414"""

    issuer: Annotated[
        StrHttpUrl,
        Doc(
            """
            The authorization server's issuer identifier, which is a URL that uses the https scheme.
            """
        ),
    ]

    authorization_endpoint: Annotated[
        Optional[StrHttpUrl],
        Doc(
            """
            URL of the authorization server's authorization endpoint.
            """
        ),
    ] = None

    token_endpoint: Annotated[
        StrHttpUrl,
        Doc(
            """
            URL of the authorization server's token endpoint.
            """
        ),
    ]

    scopes_supported: Annotated[
        List[str],
        Doc(
            """
            List of OAuth 2.0 scopes that the authorization server supports.
            """
        ),
    ] = ["openid", "profile", "email"]

    response_types_supported: Annotated[
        List[str],
        Doc(
            """
            List of the OAuth 2.0 response_type values that the authorization server supports.
            """
        ),
    ] = ["code"]

    grant_types_supported: Annotated[
        List[str],
        Doc(
            """
            List of the OAuth 2.0 grant type values that the authorization server supports.
            """
        ),
    ] = ["authorization_code", "client_credentials"]

    token_endpoint_auth_methods_supported: Annotated[
        List[str],
        Doc(
            """
            List of client authentication methods supported by the token endpoint.
            """
        ),
    ] = ["none"]

    code_challenge_methods_supported: Annotated[
        List[str],
        Doc(
            """
            List of PKCE code challenge methods supported by the authorization server.
            """
        ),
    ] = ["S256"]

    registration_endpoint: Annotated[
        Optional[StrHttpUrl],
        Doc(
            """
            URL of the authorization server's client registration endpoint.
            """
        ),
    ] = None

    @field_validator(
        "scopes_supported",
        "response_types_supported",
        "grant_types_supported",
        "token_endpoint_auth_methods_supported",
        "code_challenge_methods_supported",
    )
    @classmethod
    def validate_non_empty_lists(cls, v, info):
        if not v:
            raise ValueError(f"{info.field_name} cannot be empty")

        return v

    @model_validator(mode="after")
    def validate_endpoints_for_grant_types(self):
        if "authorization_code" in self.grant_types_supported and not self.authorization_endpoint:
            raise ValueError("authorization_endpoint is required when authorization_code grant type is supported")
        return self

    def model_dump(
        self,
        *,
        mode: Literal["json", "python"] | str = "python",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: Any | None = None,
        by_alias: bool = False,
        exclude_unset: bool = True,
        exclude_defaults: bool = False,
        exclude_none: bool = True,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = True,
        serialize_as_any: bool = False,
    ) -> dict[str, Any]:
        # Always exclude unset and None fields, since clients don't take it well when
        # OAuth metadata fields are present but empty.
        exclude_unset = True
        exclude_none = True
        return super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
            serialize_as_any=serialize_as_any,
        )


OAuthMetadataDict = Annotated[Union[Dict[str, Any], OAuthMetadata], OAuthMetadata]


class AuthConfig(BaseType):
    version: Annotated[
        Literal["2025-03-26"],
        Doc(
            """
            The MCP spec version to use for setting up authorization.
            Currently only "2025-03-26" is supported.
            """
        ),
    ] = "2025-03-26"

    dependencies: Annotated[
        Optional[Sequence[params.Depends]],
        Doc(
            """
            FastAPI dependencies (using `Depends()`) that check for authentication or authorization
            and raise 401 or 403 errors if the request is not authenticated or authorized.

            This is necessary to trigger the client to start an OAuth flow.

            Example:
            ```python
            # Your authentication dependency
            async def authenticate_request(request: Request, token: str = Depends(oauth2_scheme)):
                payload = verify_token(request, token)
                if payload is None:
                    raise HTTPException(status_code=401, detail="Unauthorized")
                return payload

            # Usage with FastAPI-MCP
            mcp = FastApiMCP(
                app,
                auth_config=AuthConfig(dependencies=[Depends(authenticate_request)]),
            )
            ```
            """
        ),
    ] = None

    issuer: Annotated[
        Optional[str],
        Doc(
            """
            The issuer of the OAuth 2.0 server.
            Required if you don't provide `custom_oauth_metadata`.
            Usually it's either the base URL of your app, or the URL of the OAuth provider.
            For example, for Auth0, this would be `https://your-tenant.auth0.com`.
            """
        ),
    ] = None

    oauth_metadata_url: Annotated[
        Optional[StrHttpUrl],
        Doc(
            """
            The full URL of the OAuth provider's metadata endpoint.

            If not provided, FastAPI-MCP will attempt to guess based on the `issuer` and `metadata_path`.

            Only relevant if `setup_proxies` is `True`.

            If this URL is wrong, the metadata proxy will not work.
            """
        ),
    ] = None

    authorize_url: Annotated[
        Optional[StrHttpUrl],
        Doc(
            """
            The URL of your OAuth provider's authorization endpoint.

            Usually this is something like `https://app.example.com/oauth/authorize`.
            """
        ),
    ] = None

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
    ] = None

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
    ] = "openid profile email"

    client_id: Annotated[
        Optional[str],
        Doc(
            """
            In case the client doesn't specify a client ID, this will be used as the default client ID on the
            request to your OAuth provider.

            This is mandatory only if you set `setup_proxies` to `True`.
            """
        ),
    ] = None

    client_secret: Annotated[
        Optional[str],
        Doc(
            """
            The client secret to use for the client ID.

            This is mandatory only if you set `setup_proxies` to `True` and `setup_fake_dynamic_registration` to `True`.
            """
        ),
    ] = None

    custom_oauth_metadata: Annotated[
        Optional[OAuthMetadataDict],
        Doc(
            """
            Custom OAuth metadata to register.

            If your OAuth flow works with MCP out-of-the-box, you should just use this option to provide the
            metadata yourself.

            Otherwise, set `setup_proxies` to `True` to automatically setup MCP-compliant proxies around your
            OAuth provider's endpoints.
            """
        ),
    ] = None

    setup_proxies: Annotated[
        bool,
        Doc(
            """
            Whether to automatically setup MCP-compliant proxies around your original OAuth provider's endpoints.
            """
        ),
    ] = False

    setup_fake_dynamic_registration: Annotated[
        bool,
        Doc(
            """
            Whether to automatically setup a fake dynamic client registration endpoint.

            In MCP 2025-03-26 Spec, it is recommended to support OAuth Dynamic Client Registration (RFC 7591).
            Furthermore, `npx mcp-remote` which is the current de-facto client that supports MCP's up-to-date spec,
            requires this endpoint to be present.

            For most cases, a fake dynamic registration endpoint is enough, thus you should set this to `True`.

            This is only used if `setup_proxies` is also `True`.
            """
        ),
    ] = True

    metadata_path: Annotated[
        str,
        Doc(
            """
            The path to mount the OAuth metadata endpoint at.

            Clients will usually expect this to be /.well-known/oauth-authorization-server
            """
        ),
    ] = "/.well-known/oauth-authorization-server"

    @model_validator(mode="after")
    def validate_required_fields(self):
        if self.custom_oauth_metadata is None and self.issuer is None and not self.dependencies:
            raise ValueError("at least one of 'issuer', 'custom_oauth_metadata' or 'dependencies' is required")

        if self.setup_proxies:
            if self.client_id is None:
                raise ValueError("'client_id' is required when 'setup_proxies' is True")

            if self.setup_fake_dynamic_registration and not self.client_secret:
                raise ValueError("'client_secret' is required when 'setup_fake_dynamic_registration' is True")

        return self


class ClientRegistrationRequest(BaseType):
    redirect_uris: List[str]
    client_name: Optional[str] = None
    grant_types: Optional[List[str]] = ["authorization_code"]
    token_endpoint_auth_method: Optional[str] = "none"


class ClientRegistrationResponse(BaseType):
    client_id: str
    client_id_issued_at: int = int(time.time())
    client_secret: Optional[str] = None
    client_secret_expires_at: int = 0
    redirect_uris: List[str]
    grant_types: List[str]
    token_endpoint_auth_method: str
    client_name: str
