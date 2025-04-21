from fastapi import FastAPI, Depends, HTTPException, Request, status
from pydantic_settings import BaseSettings
from typing import Any
import logging

from fastapi_mcp import FastApiMCP, AuthConfig

from examples.shared.auth import fetch_jwks_public_key
from examples.shared.setup import setup_logging


setup_logging()
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    For this to work, you need an .env file in the root of the project with the following variables:
    AUTH0_DOMAIN=your-tenant.auth0.com
    AUTH0_AUDIENCE=https://your-tenant.auth0.com/api/v2/
    AUTH0_CLIENT_ID=your-client-id
    AUTH0_CLIENT_SECRET=your-client-secret
    """

    auth0_domain: str  # Auth0 domain, e.g. "your-tenant.auth0.com"
    auth0_audience: str  # Audience, e.g. "https://your-tenant.auth0.com/api/v2/"
    auth0_client_id: str
    auth0_client_secret: str

    @property
    def auth0_jwks_url(self):
        return f"https://{self.auth0_domain}/.well-known/jwks.json"

    @property
    def auth0_oauth_metadata_url(self):
        return f"https://{self.auth0_domain}/.well-known/openid-configuration"

    class Config:
        env_file = ".env"


settings = Settings()  # type: ignore


async def lifespan(app: FastAPI):
    app.state.jwks_public_key = await fetch_jwks_public_key(settings.auth0_jwks_url)
    logger.info(f"Auth0 client ID in settings: {settings.auth0_client_id}")
    logger.info(f"Auth0 domain in settings: {settings.auth0_domain}")
    logger.info(f"Auth0 audience in settings: {settings.auth0_audience}")
    yield


async def verify_auth(request: Request) -> dict[str, Any]:
    try:
        import jwt

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")

        token = auth_header.split(" ")[1]

        header = jwt.get_unverified_header(token)

        # Check if this is a JWE token (encrypted token)
        if header.get("alg") == "dir" and header.get("enc") == "A256GCM":
            raise ValueError(
                "Token is encrypted, offline validation not possible. "
                "This is usually due to not specifying the audience when requesting the token."
            )

        # Otherwise, it's a JWT, we can validate it offline
        if header.get("alg") in ["RS256", "HS256"]:
            claims = jwt.decode(
                token,
                app.state.jwks_public_key,
                algorithms=["RS256", "HS256"],
                audience=settings.auth0_audience,
                issuer=f"https://{settings.auth0_domain}/",
                options={"verify_signature": True},
            )
            return claims

    except Exception as e:
        logger.error(f"Auth error: {str(e)}")

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


async def get_current_user_id(claims: dict = Depends(verify_auth)) -> str:
    user_id = claims.get("sub")

    if not user_id:
        logger.error("No user ID found in token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return user_id


app = FastAPI(lifespan=lifespan)


@app.get("/api/public", operation_id="public")
async def public():
    return {"message": "This is a public route"}


@app.get("/api/protected", operation_id="protected")
async def protected(user_id: str = Depends(get_current_user_id)):
    return {"message": f"Hello, {user_id}!", "user_id": user_id}


# Set up FastAPI-MCP with Auth0 auth
mcp = FastApiMCP(
    app,
    name="MCP With Auth0",
    description="Example of FastAPI-MCP with Auth0 authentication",
    auth_config=AuthConfig(
        issuer=f"https://{settings.auth0_domain}/",
        authorize_url=f"https://{settings.auth0_domain}/authorize",
        oauth_metadata_url=settings.auth0_oauth_metadata_url,
        audience=settings.auth0_audience,
        client_id=settings.auth0_client_id,
        client_secret=settings.auth0_client_secret,
        dependencies=[Depends(verify_auth)],
        setup_proxies=True,
    ),
)

# Mount the MCP server
mcp.mount()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
