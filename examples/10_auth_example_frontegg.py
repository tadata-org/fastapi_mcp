from fastapi import FastAPI, Depends
import httpx
from pydantic_settings import BaseSettings
import logging

from frontegg.fastapi import frontegg
from frontegg.fastapi.secure_access import User, FronteggSecurity

from fastapi_mcp import FastApiMCP, AuthConfig

from examples.shared.setup import setup_logging


setup_logging()
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    For this to work, you need an .env file in the root of the project with the following variables:
    MCP_BASE_URL=http://localhost:8179
    FRONTEGG_DOMAIN=your-tenant.frontegg.com
    FRONTEGG_CLIENT_ID=your-client-id
    FRONTEGG_CLIENT_SECRET=your-client-secret
    """

    mcp_base_url: str = "http://localhost:8000"  # app base url, e.g. "http://localhost:8179"
    frontegg_domain: str  # frontegg domain, e.g. "your-tenant.frontegg.com"
    frontegg_client_id: str
    frontegg_client_secret: str

    @property
    def frontegg_jwks_url(self) -> str:
        return f"https://{self.frontegg_domain}/.well-known/jwks.json"

    @property
    def frontegg_oauth_metadata_url(self) -> str:
        return f"https://{self.frontegg_domain}/.well-known/openid-configuration"

    class Config:
        env_file = ".env"


settings = Settings()  # type: ignore


async def lifespan(app: FastAPI):
    await frontegg.init_app(
        settings.frontegg_client_id,
        settings.frontegg_client_secret,
        options=dict(auth_url=settings.frontegg_oauth_metadata_url),
    )

    yield


app = FastAPI(lifespan=lifespan)


@app.get("/.well-known/oauth-authorization-server", include_in_schema=False)
async def oauth_authorization_server():  # type: ignore
    """
    This endpoint is used to get the metadata for the OAuth authorization server.
    It is required by the MCP protocol to get the authorization endpoint.

    authorization_endpoint: The endpoint to use to authorize the user,
        this app is using the proxy to authorize the user.
    code_challenge_methods_supported: The methods to use to challenge the user,
        mcp-remote is using S256 so we need to support it.
    """

    # Get metadata from openid-configuration endpoint
    response = await httpx.AsyncClient().get(settings.frontegg_oauth_metadata_url)
    metadata = response.json()

    # Patch the authorize_url to use the proxy
    metadata["authorization_endpoint"] = f"{settings.mcp_base_url}/oauth/authorize"

    # Indicate registration endpoint in /oauth/register
    metadata["registration_endpoint"] = f"{settings.mcp_base_url}/oauth/register"

    # Add PKCE support
    metadata["code_challenge_methods_supported"] = ["S256"]
    return metadata


@app.get("/api/public", operation_id="public")
async def public():
    return {"message": "This is a public route"}


@app.get("/api/protected", operation_id="protected")
async def protected(user: User = Depends(FronteggSecurity())):
    return {"message": f"Hello, {user.name}!", "user_id": user.id}


# Set up FastAPI-MCP with Auth0 auth
mcp = FastApiMCP(
    app,
    name="MCP With Frontegg",
    description="Example of FastAPI-MCP with Frontegg authentication",
    auth_config=AuthConfig(
        issuer=f"https://{settings.frontegg_domain}/",
        authorize_url=f"https://{settings.frontegg_domain}/oauth/authorize",
        oauth_metadata_url=settings.frontegg_oauth_metadata_url,
        client_id=settings.frontegg_client_id,
        client_secret=settings.frontegg_client_secret,
        dependencies=[Depends(FronteggSecurity())],
        setup_proxies=True,
    ),
)

# Mount the MCP server
mcp.mount()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
