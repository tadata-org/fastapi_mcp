"""
FastAPI-MCP: Automatic MCP server generator for FastAPI applications.

Created by Tadata Inc. (https://github.com/tadata-org)
"""

try:
    from importlib.metadata import version

    __version__ = version("fastapi-mcp")
except Exception:  # pragma: no cover
    # Fallback for local development
    __version__ = "0.0.0.dev0"  # pragma: no cover

from .server import FastApiMCP
from .types import (
    AuthConfig,
    OAuthMetadata,
    ExtendedAuthConfig,
    PanelConfig,
    RateLimitConfig,
    SecurityConfig,
    UserRole,
    Permission,
    User,
    UserCreate,
    UserUpdate,
    ApiKeyStatus,
    ApiKey,
    ApiKeyCreate,
    ApiKeyUpdate,
    CallStatus,
    CallLog,
    MonitorData,
)


__all__ = [
    "FastApiMCP",
    "AuthConfig",
    "OAuthMetadata",
    "ExtendedAuthConfig",
    "PanelConfig",
    "RateLimitConfig",
    "SecurityConfig",
    "UserRole",
    "Permission",
    "User",
    "UserCreate",
    "UserUpdate",
    "ApiKeyStatus",
    "ApiKey",
    "ApiKeyCreate",
    "ApiKeyUpdate",
    "CallStatus",
    "CallLog",
    "MonitorData",
]
