import time
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Annotated, Union, Optional, Sequence, Literal, List, Callable
from typing_extensions import Doc
from pydantic import (
    BaseModel,
    ConfigDict,
    HttpUrl,
    field_validator,
    model_validator,
    Field,
)
from pydantic.main import IncEx
from fastapi import params
from enum import Enum


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


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
    API_ONLY = "api_only"


class Permission(str, Enum):
    READ_TOOLS = "read:tools"
    CALL_TOOLS = "call:tools"
    MANAGE_USERS = "manage:users"
    MANAGE_API_KEYS = "manage:api_keys"
    VIEW_LOGS = "view:logs"
    VIEW_METRICS = "view:metrics"
    ADMIN_ALL = "admin:all"


class User(BaseType):
    id: str
    username: str
    email: Optional[str] = None
    role: UserRole = UserRole.USER
    permissions: List[Permission] = []
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None

    def has_permission(self, permission: Permission) -> bool:
        if self.role == UserRole.ADMIN or Permission.ADMIN_ALL in self.permissions:
            return True
        return permission in self.permissions

    def has_role(self, role: UserRole) -> bool:
        role_hierarchy = {UserRole.GUEST: 0, UserRole.USER: 1, UserRole.API_ONLY: 1, UserRole.ADMIN: 2}
        return role_hierarchy.get(self.role, 0) >= role_hierarchy.get(role, 0)


class UserCreate(BaseType):
    username: str
    email: Optional[str] = None
    role: UserRole = UserRole.USER
    permissions: List[Permission] = []
    password: Optional[str] = None


class UserUpdate(BaseType):
    email: Optional[str] = None
    role: Optional[UserRole] = None
    permissions: Optional[List[Permission]] = None
    is_active: Optional[bool] = None


class ApiKeyStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    REVOKED = "revoked"


class ApiKey(BaseType):
    id: str
    key: str
    name: str
    description: Optional[str] = None
    user_id: str
    status: ApiKeyStatus = ApiKeyStatus.ACTIVE
    permissions: List[Permission] = []
    rate_limit: Optional[int] = None
    rate_limit_window: int = 60
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    usage_count: int = 0

    @classmethod
    def generate_key(cls, prefix: str = "mcp") -> str:
        return f"{prefix}_{secrets.token_urlsafe(32)}"

    def is_valid(self) -> bool:
        if self.status != ApiKeyStatus.ACTIVE:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True


class ApiKeyCreate(BaseType):
    name: str
    description: Optional[str] = None
    permissions: List[Permission] = []
    rate_limit: Optional[int] = None
    rate_limit_window: int = 60
    expires_in_days: Optional[int] = None


class ApiKeyUpdate(BaseType):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ApiKeyStatus] = None
    permissions: Optional[List[Permission]] = None
    rate_limit: Optional[int] = None
    rate_limit_window: Optional[int] = None


class RateLimitConfig(BaseType):
    enabled: bool = True
    default_limit: int = 100
    default_window: int = 60
    user_limit: Optional[int] = None
    api_key_limit: Optional[int] = None
    global_limit: Optional[int] = None

    def get_effective_limit(self, api_key: Optional[ApiKey] = None) -> int:
        if api_key and api_key.rate_limit:
            return api_key.rate_limit
        if api_key and self.api_key_limit:
            return self.api_key_limit
        if self.user_limit:
            return self.user_limit
        return self.default_limit


class CallStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    UNAUTHORIZED = "unauthorized"


class CallLog(BaseType):
    id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tool_name: str
    user_id: Optional[str] = None
    api_key_id: Optional[str] = None
    status: CallStatus
    duration_ms: float
    request_method: str
    request_path: str
    request_headers: Dict[str, str] = {}
    request_body: Optional[str] = None
    response_status: int
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None


class MonitorData(BaseType):
    total_calls: int = 0
    success_calls: int = 0
    error_calls: int = 0
    rate_limited_calls: int = 0
    total_users: int = 0
    active_api_keys: int = 0
    uptime_seconds: float = 0
    avg_response_time_ms: float = 0
    p99_response_time_ms: float = 0
    requests_per_second: float = 0
    top_tools: List[Dict[str, Any]] = []
    recent_errors: List[Dict[str, Any]] = []
    active_users: List[Dict[str, Any]] = []


class PanelConfig(BaseType):
    enabled: bool = True
    mount_path: str = "/mcp-panel"
    title: str = "FastAPI MCP Panel"
    enable_testing: bool = True
    enable_monitoring: bool = True
    enable_api_keys: bool = True
    enable_users: bool = False
    enable_logs: bool = True
    logo_url: Optional[str] = None
    theme: Literal["light", "dark", "auto"] = "auto"


class SecurityConfig(BaseType):
    enabled: bool = True
    require_auth: bool = False
    require_api_key: bool = False
    allow_guest_access: bool = False
    session_timeout_minutes: int = 60
    jwt_secret: Optional[str] = None
    password_hash_rounds: int = 12


class ExtendedAuthConfig(AuthConfig):
    security: Optional[SecurityConfig] = None
    rate_limit: Optional[RateLimitConfig] = None
    panel: Optional[PanelConfig] = None
