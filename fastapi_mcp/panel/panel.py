import logging
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from typing_extensions import Annotated, Doc

from fastapi_mcp.types import (
    PanelConfig,
    ApiKeyCreate,
    ApiKeyUpdate,
    UserCreate,
    UserUpdate,
    CallStatus,
    Permission,
)
from fastapi_mcp.auth.user_manager import UserManager
from fastapi_mcp.auth.api_key_manager import ApiKeyManager
from fastapi_mcp.auth.rate_limiter import RateLimiter
from fastapi_mcp.monitoring.call_logger import CallLogger


logger = logging.getLogger(__name__)


class PanelRouter:
    """
    Modern web panel for FastAPI-MCP.
    
    Provides:
    - API testing interface
    - Real-time monitoring dashboard
    - API Key management
    - User management (if enabled)
    - Call logs viewer
    """

    def __init__(
        self,
        config: Annotated[
            PanelConfig,
            Doc("Panel configuration"),
        ],
        user_manager: Annotated[
            Optional[UserManager],
            Doc("User manager instance"),
        ] = None,
        api_key_manager: Annotated[
            Optional[ApiKeyManager],
            Doc("API Key manager instance"),
        ] = None,
        rate_limiter: Annotated[
            Optional[RateLimiter],
            Doc("Rate limiter instance"),
        ] = None,
        call_logger: Annotated[
            Optional[CallLogger],
            Doc("Call logger instance"),
        ] = None,
    ):
        self.config = config
        self.user_manager = user_manager
        self.api_key_manager = api_key_manager
        self.rate_limiter = rate_limiter
        self.call_logger = call_logger

        self.router = APIRouter()
        self._setup_routes()

    def _setup_routes(self):
        @self.router.get("/", response_class=HTMLResponse, include_in_schema=False)
        async def get_panel(request: Request):
            return HTMLResponse(content=self._get_index_html())

        @self.router.get("/api/config", include_in_schema=False)
        async def get_config():
            return JSONResponse(
                content={
                    "title": self.config.title,
                    "enable_testing": self.config.enable_testing,
                    "enable_monitoring": self.config.enable_monitoring,
                    "enable_api_keys": self.config.enable_api_keys,
                    "enable_users": self.config.enable_users,
                    "enable_logs": self.config.enable_logs,
                    "logo_url": self.config.logo_url,
                    "theme": self.config.theme,
                }
            )

        @self.router.get("/api/tools", include_in_schema=False)
        async def get_tools():
            return JSONResponse(content={"tools": []})

        if self.config.enable_monitoring:
            self._setup_monitoring_routes()

        if self.config.enable_logs:
            self._setup_logs_routes()

        if self.config.enable_api_keys:
            self._setup_api_keys_routes()

        if self.config.enable_users and self.user_manager:
            self._setup_users_routes()

    def _setup_monitoring_routes(self):
        @self.router.get("/api/monitoring", include_in_schema=False)
        async def get_monitoring():
            if not self.call_logger:
                raise HTTPException(status_code=501, detail="Monitoring not enabled")
            monitor_data = self.call_logger.get_monitor_data()
            return JSONResponse(content=monitor_data.model_dump())

        @self.router.get("/api/monitoring/stats", include_in_schema=False)
        async def get_stats():
            if not self.call_logger:
                raise HTTPException(status_code=501, detail="Monitoring not enabled")
            stats = self.call_logger.get_stats_summary()
            return JSONResponse(content=stats)

        @self.router.get("/api/monitoring/tools", include_in_schema=False)
        async def get_tool_stats(tool_name: Optional[str] = None):
            if not self.call_logger:
                raise HTTPException(status_code=501, detail="Monitoring not enabled")
            stats = self.call_logger.get_tool_statistics(tool_name)
            return JSONResponse(content=stats)

    def _setup_logs_routes(self):
        @self.router.get("/api/logs", include_in_schema=False)
        async def get_logs(
            tool_name: Optional[str] = None,
            user_id: Optional[str] = None,
            api_key_id: Optional[str] = None,
            status: Optional[str] = None,
            limit: int = 100,
            offset: int = 0,
        ):
            if not self.call_logger:
                raise HTTPException(status_code=501, detail="Logging not enabled")

            call_status = None
            if status:
                try:
                    call_status = CallStatus(status)
                except ValueError:
                    pass

            logs = self.call_logger.get_logs(
                tool_name=tool_name,
                user_id=user_id,
                api_key_id=api_key_id,
                status=call_status,
                limit=limit,
                offset=offset,
            )

            return JSONResponse(
                content={
                    "logs": [log.model_dump(mode="json") for log in logs],
                    "total": len(self.call_logger._logs) if self.call_logger else 0,
                    "limit": limit,
                    "offset": offset,
                }
            )

        @self.router.get("/api/logs/errors", include_in_schema=False)
        async def get_errors(tool_name: Optional[str] = None, limit: int = 100):
            if not self.call_logger:
                raise HTTPException(status_code=501, detail="Logging not enabled")

            errors = self.call_logger.get_errors(tool_name=tool_name, limit=limit)
            return JSONResponse(
                content={
                    "errors": [e.model_dump(mode="json") for e in errors],
                    "total": len(self.call_logger._errors) if self.call_logger else 0,
                }
            )

    def _setup_api_keys_routes(self):
        @self.router.get("/api/api-keys", include_in_schema=False)
        async def list_api_keys(user_id: Optional[str] = None):
            if not self.api_key_manager:
                raise HTTPException(status_code=501, detail="API Key management not enabled")

            keys = self.api_key_manager.list_api_keys(user_id=user_id)
            return JSONResponse(
                content={
                    "api_keys": [
                        {
                            "id": k.id,
                            "name": k.name,
                            "description": k.description,
                            "user_id": k.user_id,
                            "status": k.status.value,
                            "permissions": [p.value for p in k.permissions],
                            "rate_limit": k.rate_limit,
                            "rate_limit_window": k.rate_limit_window,
                            "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                            "created_at": k.created_at.isoformat(),
                            "usage_count": k.usage_count,
                        }
                        for k in keys
                    ]
                }
            )

        @self.router.post("/api/api-keys", include_in_schema=False)
        async def create_api_key(data: ApiKeyCreate, user_id: str = "default"):
            if not self.api_key_manager:
                raise HTTPException(status_code=501, detail="API Key management not enabled")

            api_key = self.api_key_manager.create_api_key(user_id=user_id, key_create=data)
            return JSONResponse(
                content={
                    "id": api_key.id,
                    "key": api_key.key,
                    "name": api_key.name,
                    "message": "Make sure to copy this key now - you won't be able to see it again!",
                },
                status_code=201,
            )

        @self.router.get("/api/api-keys/{api_key_id}", include_in_schema=False)
        async def get_api_key(api_key_id: str):
            if not self.api_key_manager:
                raise HTTPException(status_code=501, detail="API Key management not enabled")

            key = self.api_key_manager.get_api_key(api_key_id)
            if not key:
                raise HTTPException(status_code=404, detail="API Key not found")

            return JSONResponse(
                content={
                    "id": key.id,
                    "name": key.name,
                    "description": key.description,
                    "user_id": key.user_id,
                    "status": key.status.value,
                    "permissions": [p.value for p in key.permissions],
                    "rate_limit": key.rate_limit,
                    "rate_limit_window": key.rate_limit_window,
                    "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                    "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                    "created_at": key.created_at.isoformat(),
                    "usage_count": key.usage_count,
                }
            )

        @self.router.patch("/api/api-keys/{api_key_id}", include_in_schema=False)
        async def update_api_key(api_key_id: str, data: ApiKeyUpdate):
            if not self.api_key_manager:
                raise HTTPException(status_code=501, detail="API Key management not enabled")

            key = self.api_key_manager.update_api_key(api_key_id, data)
            if not key:
                raise HTTPException(status_code=404, detail="API Key not found")

            return JSONResponse(content={"message": "API Key updated"})

        @self.router.post("/api/api-keys/{api_key_id}/revoke", include_in_schema=False)
        async def revoke_api_key(api_key_id: str):
            if not self.api_key_manager:
                raise HTTPException(status_code=501, detail="API Key management not enabled")

            if not self.api_key_manager.revoke_api_key(api_key_id):
                raise HTTPException(status_code=404, detail="API Key not found")

            return JSONResponse(content={"message": "API Key revoked"})

        @self.router.post("/api/api-keys/{api_key_id}/rotate", include_in_schema=False)
        async def rotate_api_key(api_key_id: str):
            if not self.api_key_manager:
                raise HTTPException(status_code=501, detail="API Key management not enabled")

            key = self.api_key_manager.rotate_api_key(api_key_id)
            if not key:
                raise HTTPException(status_code=404, detail="API Key not found")

            return JSONResponse(
                content={
                    "id": key.id,
                    "key": key.key,
                    "message": "API Key rotated - make sure to copy the new key!",
                }
            )

        @self.router.delete("/api/api-keys/{api_key_id}", include_in_schema=False)
        async def delete_api_key(api_key_id: str):
            if not self.api_key_manager:
                raise HTTPException(status_code=501, detail="API Key management not enabled")

            if not self.api_key_manager.delete_api_key(api_key_id):
                raise HTTPException(status_code=404, detail="API Key not found")

            return JSONResponse(content={"message": "API Key deleted"}, status_code=204)

    def _setup_users_routes(self):
        @self.router.get("/api/users", include_in_schema=False)
        async def list_users():
            users = self.user_manager.list_users()
            return JSONResponse(
                content={
                    "users": [
                        {
                            "id": u.id,
                            "username": u.username,
                            "email": u.email,
                            "role": u.role.value,
                            "permissions": [p.value for p in u.permissions],
                            "is_active": u.is_active,
                            "created_at": u.created_at.isoformat(),
                            "last_login": u.last_login.isoformat() if u.last_login else None,
                        }
                        for u in users
                    ]
                }
            )

        @self.router.post("/api/users", include_in_schema=False)
        async def create_user(data: UserCreate):
            try:
                user = self.user_manager.create_user(data)
                return JSONResponse(
                    content={
                        "id": user.id,
                        "username": user.username,
                        "message": "User created",
                    },
                    status_code=201,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.router.get("/api/users/{user_id}", include_in_schema=False)
        async def get_user(user_id: str):
            user = self.user_manager.get_user(user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            return JSONResponse(
                content={
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role.value,
                    "permissions": [p.value for p in user.permissions],
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat(),
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                }
            )

        @self.router.patch("/api/users/{user_id}", include_in_schema=False)
        async def update_user(user_id: str, data: UserUpdate):
            user = self.user_manager.update_user(user_id, data)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            return JSONResponse(content={"message": "User updated"})

        @self.router.delete("/api/users/{user_id}", include_in_schema=False)
        async def delete_user(user_id: str):
            if not self.user_manager.delete_user(user_id):
                raise HTTPException(status_code=404, detail="User not found")

            return JSONResponse(content={"message": "User deleted"}, status_code=204)

    def _get_index_html(self) -> str:
        return _PANEL_HTML


_PANEL_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FastAPI MCP Panel</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        :root {
            --bg-primary: #ffffff;
            --bg-secondary: #f8fafc;
            --bg-tertiary: #f1f5f9;
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --border-color: #e2e8f0;
            --accent: #3b82f6;
            --accent-hover: #2563eb;
        }
        .dark {
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-tertiary: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --border-color: #334155;
            --accent: #60a5fa;
            --accent-hover: #3b82f6;
        }
        body { background-color: var(--bg-secondary); color: var(--text-primary); font-family: 'Inter', system-ui, sans-serif; }
        .card { background-color: var(--bg-primary); border: 1px solid var(--border-color); border-radius: 0.75rem; }
        .sidebar { background-color: var(--bg-primary); border-right: 1px solid var(--border-color); }
        .nav-item { color: var(--text-secondary); transition: all 0.2s; }
        .nav-item:hover, .nav-item.active { color: var(--accent); background-color: var(--bg-secondary); }
        .btn-primary { background-color: var(--accent); color: white; transition: background-color 0.2s; }
        .btn-primary:hover { background-color: var(--accent-hover); }
        .input-field { background-color: var(--bg-secondary); border: 1px solid var(--border-color); color: var(--text-primary); }
        .input-field:focus { border-color: var(--accent); outline: none; }
        .status-badge { display: inline-flex; align-items: center; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 500; }
        .status-success { background-color: rgba(16, 185, 129, 0.1); color: #10b981; }
        .status-error { background-color: rgba(239, 68, 68, 0.1); color: #ef4444; }
        .status-warning { background-color: rgba(245, 158, 11, 0.1); color: #f59e0b; }
        .status-info { background-color: rgba(59, 130, 246, 0.1); color: #3b82f6; }
        .table-header { background-color: var(--bg-secondary); color: var(--text-secondary); font-weight: 500; font-size: 0.75rem; text-transform: uppercase; }
        .table-row { border-bottom: 1px solid var(--border-color); transition: background-color 0.15s; }
        .table-row:hover { background-color: var(--bg-secondary); }
        .code-block { background-color: var(--bg-tertiary); border-radius: 0.5rem; font-family: monospace; font-size: 0.875rem; overflow-x: auto; }
        .metric-card { background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%); }
        .hidden { display: none !important; }
    </style>
</head>
<body class="min-h-screen">
    <div class="flex h-screen">
        <aside class="sidebar w-64 flex-shrink-0 flex flex-col">
            <div class="p-6 border-b" style="border-color: var(--border-color)">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg flex items-center justify-center" style="background: linear-gradient(135deg, #3b82f6, #8b5cf6)">
                        <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                        </svg>
                    </div>
                    <div>
                        <h1 class="font-bold text-lg" id="panel-title">FastAPI MCP</h1>
                        <p class="text-xs" style="color: var(--text-secondary)">Control Panel</p>
                    </div>
                </div>
            </div>
            <nav class="flex-1 p-4 space-y-1">
                <a href="#" class="nav-item active flex items-center gap-3 px-3 py-2 rounded-lg" data-view="dashboard">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"></path></svg>
                    Dashboard
                </a>
                <a href="#" class="nav-item flex items-center gap-3 px-3 py-2 rounded-lg" data-view="logs" id="nav-logs">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                    Call Logs
                </a>
                <a href="#" class="nav-item flex items-center gap-3 px-3 py-2 rounded-lg" data-view="api-keys" id="nav-api-keys">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path></svg>
                    API Keys
                </a>
                <a href="#" class="nav-item flex items-center gap-3 px-3 py-2 rounded-lg hidden" data-view="users" id="nav-users">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
                    Users
                </a>
            </nav>
            <div class="p-4 border-t" style="border-color: var(--border-color)">
                <div class="flex items-center justify-between">
                    <span class="text-sm" style="color: var(--text-secondary)">Theme</span>
                    <button id="theme-toggle" class="p-2 rounded-lg" style="background-color: var(--bg-secondary)">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path>
                        </svg>
                    </button>
                </div>
            </div>
        </aside>
        <main class="flex-1 overflow-auto">
            <div class="p-8">
                <div id="view-dashboard">
                    <div class="mb-8">
                        <h2 class="text-2xl font-bold mb-2">Dashboard</h2>
                        <p style="color: var(--text-secondary)">Overview of your MCP server activity</p>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                        <div class="card p-6 metric-card">
                            <div class="flex items-center justify-between mb-4">
                                <span style="color: var(--text-secondary)">Total Calls</span>
                                <div class="w-10 h-10 rounded-lg flex items-center justify-center" style="background-color: rgba(59, 130, 246, 0.1)">
                                    <svg class="w-5 h-5" style="color: var(--accent)" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
                                </div>
                            </div>
                            <div class="text-3xl font-bold" id="stat-total-calls">-</div>
                            <div class="text-sm mt-1" style="color: var(--text-secondary)"><span id="stat-success-rate">-</span> success rate</div>
                        </div>
                        <div class="card p-6 metric-card">
                            <div class="flex items-center justify-between mb-4">
                                <span style="color: var(--text-secondary)">Success</span>
                                <div class="w-10 h-10 rounded-lg flex items-center justify-center" style="background-color: rgba(16, 185, 129, 0.1)">
                                    <svg class="w-5 h-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                </div>
                            </div>
                            <div class="text-3xl font-bold text-emerald-500" id="stat-success">-</div>
                            <div class="text-sm mt-1" style="color: var(--text-secondary)">successful calls</div>
                        </div>
                        <div class="card p-6 metric-card">
                            <div class="flex items-center justify-between mb-4">
                                <span style="color: var(--text-secondary)">Errors</span>
                                <div class="w-10 h-10 rounded-lg flex items-center justify-center" style="background-color: rgba(239, 68, 68, 0.1)">
                                    <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                                </div>
                            </div>
                            <div class="text-3xl font-bold text-red-500" id="stat-errors">-</div>
                            <div class="text-sm mt-1" style="color: var(--text-secondary)"><span id="stat-error-rate">-</span> error rate</div>
                        </div>
                        <div class="card p-6 metric-card">
                            <div class="flex items-center justify-between mb-4">
                                <span style="color: var(--text-secondary)">Avg Response</span>
                                <div class="w-10 h-10 rounded-lg flex items-center justify-center" style="background-color: rgba(139, 92, 246, 0.1)">
                                    <svg class="w-5 h-5" style="color: #8b5cf6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                </div>
                            </div>
                            <div class="text-3xl font-bold" style="color: #8b5cf6"><span id="stat-avg-time">-</span><span class="text-lg">ms</span></div>
                            <div class="text-sm mt-1" style="color: var(--text-secondary)">P99: <span id="stat-p99">-</span>ms</div>
                        </div>
                    </div>
                    <div class="card p-6">
                        <h3 class="font-semibold mb-4">System Info</h3>
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
                            <div>
                                <div class="text-sm" style="color: var(--text-secondary)">Uptime</div>
                                <div class="font-semibold mt-1" id="stat-uptime">-</div>
                            </div>
                            <div>
                                <div class="text-sm" style="color: var(--text-secondary)">Req/Sec</div>
                                <div class="font-semibold mt-1" id="stat-rps">-</div>
                            </div>
                            <div>
                                <div class="text-sm" style="color: var(--text-secondary)">Active API Keys</div>
                                <div class="font-semibold mt-1" id="stat-api-keys">-</div>
                            </div>
                            <div>
                                <div class="text-sm" style="color: var(--text-secondary)">Rate Limited</div>
                                <div class="font-semibold mt-1" id="stat-rate-limited">-</div>
                            </div>
                        </div>
                    </div>
                </div>
                <div id="view-logs" class="hidden">
                    <div class="flex items-center justify-between mb-8">
                        <div>
                            <h2 class="text-2xl font-bold mb-2">Call Logs</h2>
                            <p style="color: var(--text-secondary)">View detailed call history</p>
                        </div>
                        <div class="flex items-center gap-3">
                            <select id="log-filter-status" class="input-field px-4 py-2 rounded-lg">
                                <option value="">All Status</option>
                                <option value="success">Success</option>
                                <option value="error">Error</option>
                                <option value="rate_limited">Rate Limited</option>
                            </select>
                            <button id="refresh-logs" class="btn-primary px-4 py-2 rounded-lg flex items-center gap-2">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                                Refresh
                            </button>
                        </div>
                    </div>
                    <div class="card overflow-hidden">
                        <div class="overflow-x-auto">
                            <table class="w-full">
                                <thead><tr class="table-header">
                                    <th class="text-left px-6 py-3">Time</th>
                                    <th class="text-left px-6 py-3">Tool</th>
                                    <th class="text-left px-6 py-3">Method</th>
                                    <th class="text-left px-6 py-3">Status</th>
                                    <th class="text-left px-6 py-3">Duration</th>
                                </tr></thead>
                                <tbody id="logs-table-body">
                                    <tr><td colspan="5" class="px-6 py-12 text-center" style="color: var(--text-secondary)">No logs yet</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                <div id="view-api-keys" class="hidden">
                    <div class="flex items-center justify-between mb-8">
                        <div>
                            <h2 class="text-2xl font-bold mb-2">API Keys</h2>
                            <p style="color: var(--text-secondary)">Manage your API keys</p>
                        </div>
                        <button id="create-api-key-btn" class="btn-primary px-4 py-2 rounded-lg flex items-center gap-2">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
                            Create Key
                        </button>
                    </div>
                    <div class="card overflow-hidden">
                        <div class="overflow-x-auto">
                            <table class="w-full">
                                <thead><tr class="table-header">
                                    <th class="text-left px-6 py-3">Name</th>
                                    <th class="text-left px-6 py-3">Status</th>
                                    <th class="text-left px-6 py-3">Usage</th>
                                    <th class="text-left px-6 py-3">Last Used</th>
                                    <th class="text-left px-6 py-3">Actions</th>
                                </tr></thead>
                                <tbody id="api-keys-table-body">
                                    <tr><td colspan="5" class="px-6 py-12 text-center" style="color: var(--text-secondary)">No API keys yet. Create one to get started.</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                <div id="view-users" class="hidden">
                    <div class="flex items-center justify-between mb-8">
                        <div>
                            <h2 class="text-2xl font-bold mb-2">Users</h2>
                            <p style="color: var(--text-secondary)">Manage users and permissions</p>
                        </div>
                        <button id="create-user-btn" class="btn-primary px-4 py-2 rounded-lg flex items-center gap-2">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
                            Create User
                        </button>
                    </div>
                    <div class="card overflow-hidden">
                        <div class="overflow-x-auto">
                            <table class="w-full">
                                <thead><tr class="table-header">
                                    <th class="text-left px-6 py-3">Username</th>
                                    <th class="text-left px-6 py-3">Role</th>
                                    <th class="text-left px-6 py-3">Status</th>
                                    <th class="text-left px-6 py-3">Actions</th>
                                </tr></thead>
                                <tbody id="users-table-body">
                                    <tr><td colspan="4" class="px-6 py-12 text-center" style="color: var(--text-secondary)">No users</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
    <div id="modal-overlay" class="fixed inset-0 bg-black bg-opacity-50 hidden flex items-center justify-center z-50">
        <div class="card w-full max-w-md mx-4 p-6">
            <div class="flex items-center justify-between mb-6">
                <h3 id="modal-title" class="text-lg font-semibold">Modal Title</h3>
                <button id="modal-close" class="p-1 rounded-lg">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
            <div id="modal-content"></div>
        </div>
    </div>
    <div id="toast-container" class="fixed top-4 right-4 z-50 space-y-2"></div>
    <script>
        let config = {};
        
        async function fetchConfig() {
            try {
                const res = await fetch('api/config');
                config = await res.json();
                document.getElementById('panel-title').textContent = config.title || 'FastAPI MCP';
                document.getElementById('nav-logs').style.display = config.enable_logs ? 'flex' : 'none';
                document.getElementById('nav-api-keys').style.display = config.enable_api_keys ? 'flex' : 'none';
                document.getElementById('nav-users').style.display = config.enable_users ? 'flex' : 'none';
                if (config.theme === 'dark') document.documentElement.classList.add('dark');
            } catch (e) { console.error('Failed to fetch config:', e); }
        }
        
        function showToast(message, type = 'info') {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            const bgColor = type === 'success' ? 'bg-emerald-500' : type === 'error' ? 'bg-red-500' : 'bg-blue-500';
            toast.className = bgColor + ' text-white px-4 py-3 rounded-lg shadow-lg';
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }
        
        function formatUptime(seconds) {
            const days = Math.floor(seconds / 86400);
            const hours = Math.floor((seconds % 86400) / 3600);
            const mins = Math.floor((seconds % 3600) / 60);
            if (days > 0) return days + 'd ' + hours + 'h ' + mins + 'm';
            if (hours > 0) return hours + 'h ' + mins + 'm';
            return mins + 'm';
        }
        
        async function loadDashboard() {
            try {
                const res = await fetch('api/monitoring/stats');
                const data = await res.json();
                document.getElementById('stat-total-calls').textContent = data.summary.total_calls.toLocaleString();
                document.getElementById('stat-success').textContent = data.summary.success_calls.toLocaleString();
                document.getElementById('stat-errors').textContent = data.summary.error_calls.toLocaleString();
                document.getElementById('stat-success-rate').textContent = data.summary.success_rate_pct.toFixed(1) + '%';
                document.getElementById('stat-error-rate').textContent = data.summary.error_rate_pct.toFixed(1) + '%';
                document.getElementById('stat-avg-time').textContent = data.performance.avg_response_time_ms.toFixed(1);
                document.getElementById('stat-p99').textContent = data.performance.p99_response_time_ms.toFixed(1);
                document.getElementById('stat-rps').textContent = data.performance.requests_per_second.toFixed(3);
                document.getElementById('stat-uptime').textContent = formatUptime(data.performance.uptime_seconds);
                document.getElementById('stat-api-keys').textContent = data.system.active_api_keys.toLocaleString();
            } catch (e) { console.error('Failed to load dashboard:', e); }
            try {
                const res = await fetch('api/monitoring');
                const data = await res.json();
                document.getElementById('stat-rate-limited').textContent = data.rate_limited_calls.toLocaleString();
            } catch (e) { console.error('Failed to load monitoring:', e); }
        }
        
        async function loadLogs() {
            const statusFilter = document.getElementById('log-filter-status').value;
            let url = 'api/logs?limit=100';
            if (statusFilter) url += '&status=' + statusFilter;
            try {
                const res = await fetch(url);
                const data = await res.json();
                const tbody = document.getElementById('logs-table-body');
                if (data.logs && data.logs.length > 0) {
                    tbody.innerHTML = data.logs.map(log => {
                        const statusClass = log.status === 'success' ? 'status-success' : log.status === 'error' ? 'status-error' : 'status-warning';
                        return '<tr class="table-row"><td class="px-6 py-4 text-sm">' + new Date(log.timestamp).toLocaleString() + '</td><td class="px-6 py-4 font-mono text-sm">' + log.tool_name + '</td><td class="px-6 py-4"><span class="status-badge status-info">' + log.request_method.toUpperCase() + '</span></td><td class="px-6 py-4"><span class="status-badge ' + statusClass + '">' + log.status + '</span></td><td class="px-6 py-4 text-sm">' + log.duration_ms.toFixed(1) + 'ms</td></tr>';
                    }).join('');
                } else {
                    tbody.innerHTML = '<tr><td colspan="5" class="px-6 py-12 text-center" style="color: var(--text-secondary)">No logs yet</td></tr>';
                }
            } catch (e) { console.error('Failed to load logs:', e); }
        }
        
        async function loadApiKeys() {
            try {
                const res = await fetch('api/api-keys');
                const data = await res.json();
                const tbody = document.getElementById('api-keys-table-body');
                if (data.api_keys && data.api_keys.length > 0) {
                    tbody.innerHTML = data.api_keys.map(key => {
                        const statusClass = key.status === 'active' ? 'status-success' : key.status === 'revoked' ? 'status-error' : 'status-warning';
                        const lastUsed = key.last_used_at ? new Date(key.last_used_at).toLocaleDateString() : 'Never';
                        let actions = '';
                        if (key.status === 'active') {
                            actions += '<button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-orange-500" title="Revoke" onclick="revokeApiKey(\\'' + key.id + '\\')"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"></path></svg></button>';
                        }
                        actions += '<button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-red-500" title="Delete" onclick="deleteApiKey(\\'' + key.id + '\\')"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg></button>';
                        return '<tr class="table-row"><td class="px-6 py-4"><div class="font-medium">' + key.name + '</div><div class="text-sm" style="color: var(--text-secondary)">' + (key.description || '-') + '</div></td><td class="px-6 py-4"><span class="status-badge ' + statusClass + '">' + key.status + '</span></td><td class="px-6 py-4 text-sm">' + key.usage_count + '</td><td class="px-6 py-4 text-sm" style="color: var(--text-secondary)">' + lastUsed + '</td><td class="px-6 py-4"><div class="flex items-center gap-2">' + actions + '</div></td></tr>';
                    }).join('');
                } else {
                    tbody.innerHTML = '<tr><td colspan="5" class="px-6 py-12 text-center" style="color: var(--text-secondary)">No API keys yet. Create one to get started.</td></tr>';
                }
            } catch (e) { console.error('Failed to load API keys:', e); }
        }
        
        function showModal(title, content) {
            document.getElementById('modal-title').textContent = title;
            document.getElementById('modal-content').innerHTML = content;
            document.getElementById('modal-overlay').classList.remove('hidden');
        }
        
        function hideModal() {
            document.getElementById('modal-overlay').classList.add('hidden');
        }
        
        async function showCreateApiKeyModal() {
            showModal('Create API Key', '<form id="create-key-form"><div class="space-y-4"><div><label class="block text-sm font-medium mb-1">Name *</label><input type="text" id="key-name" class="input-field w-full px-3 py-2 rounded-lg" required placeholder="e.g., Production API Key"></div><div><label class="block text-sm font-medium mb-1">Description</label><textarea id="key-desc" class="input-field w-full px-3 py-2 rounded-lg" rows="2" placeholder="Optional description"></textarea></div><div class="grid grid-cols-2 gap-4"><div><label class="block text-sm font-medium mb-1">Rate Limit</label><input type="number" id="key-rate-limit" class="input-field w-full px-3 py-2 rounded-lg" placeholder="100"></div><div><label class="block text-sm font-medium mb-1">Expires (days)</label><input type="number" id="key-expires" class="input-field w-full px-3 py-2 rounded-lg" placeholder="Never"></div></div><div class="flex justify-end gap-3 pt-4"><button type="button" onclick="hideModal()" class="px-4 py-2 rounded-lg" style="background-color: var(--bg-secondary)">Cancel</button><button type="submit" class="btn-primary px-4 py-2 rounded-lg">Create</button></div></div></form>');
            document.getElementById('create-key-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                const data = {
                    name: document.getElementById('key-name').value,
                    description: document.getElementById('key-desc').value || undefined,
                    permissions: ['read:tools', 'call:tools'],
                };
                const rateLimit = document.getElementById('key-rate-limit').value;
                if (rateLimit) data.rate_limit = parseInt(rateLimit);
                const expiresIn = document.getElementById('key-expires').value;
                if (expiresIn) data.expires_in_days = parseInt(expiresIn);
                try {
                    const res = await fetch('api/api-keys', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
                    if (res.ok) {
                        const result = await res.json();
                        hideModal();
                        showModal('API Key Created', '<div class="space-y-4"><p class="text-sm" style="color: var(--text-secondary)">Make sure to copy this key now - you won\\'t be able to see it again!</p><div class="code-block p-3 font-mono text-sm break-all">' + result.key + '</div><button onclick="navigator.clipboard.writeText(\\'' + result.key + '\\'); showToast(\\'Copied to clipboard!\\', \\'success\\');" class="btn-primary px-4 py-2 rounded-lg w-full">Copy Key</button></div>');
                        loadApiKeys();
                    } else { showToast('Failed to create API key', 'error'); }
                } catch (e) { showToast('Failed to create API key', 'error'); }
            });
        }
        
        async function revokeApiKey(id) {
            if (!confirm('Are you sure you want to revoke this API key?')) return;
            try {
                const res = await fetch('api/api-keys/' + id + '/revoke', { method: 'POST' });
                if (res.ok) { showToast('API key revoked', 'success'); loadApiKeys(); }
            } catch (e) { showToast('Failed to revoke API key', 'error'); }
        }
        
        async function deleteApiKey(id) {
            if (!confirm('Are you sure you want to delete this API key? This action cannot be undone.')) return;
            try {
                const res = await fetch('api/api-keys/' + id, { method: 'DELETE' });
                if (res.ok) { showToast('API key deleted', 'success'); loadApiKeys(); }
            } catch (e) { showToast('Failed to delete API key', 'error'); }
        }
        
        async function loadUsers() {
            try {
                const res = await fetch('api/users');
                const data = await res.json();
                const tbody = document.getElementById('users-table-body');
                if (data.users && data.users.length > 0) {
                    tbody.innerHTML = data.users.map(user => {
                        const statusClass = user.is_active ? 'status-success' : 'status-error';
                        return '<tr class="table-row"><td class="px-6 py-4 font-medium">' + user.username + '</td><td class="px-6 py-4"><span class="status-badge ' + (user.role === 'admin' ? 'status-info' : '') + '">' + user.role + '</span></td><td class="px-6 py-4"><span class="status-badge ' + statusClass + '">' + (user.is_active ? 'Active' : 'Inactive') + '</span></td><td class="px-6 py-4"><button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-red-500" onclick="deleteUser(\\'' + user.id + '\\')"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg></button></td></tr>';
                    }).join('');
                } else {
                    tbody.innerHTML = '<tr><td colspan="4" class="px-6 py-12 text-center" style="color: var(--text-secondary)">No users</td></tr>';
                }
            } catch (e) { console.error('Failed to load users:', e); }
        }
        
        async function deleteUser(id) {
            if (!confirm('Are you sure you want to delete this user?')) return;
            try {
                const res = await fetch('api/users/' + id, { method: 'DELETE' });
                if (res.ok) { showToast('User deleted', 'success'); loadUsers(); }
            } catch (e) { showToast('Failed to delete user', 'error'); }
        }
        
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const view = item.dataset.view;
                document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
                item.classList.add('active');
                document.querySelectorAll('[id^="view-"]').forEach(v => v.classList.add('hidden'));
                const targetView = document.getElementById('view-' + view);
                if (targetView) targetView.classList.remove('hidden');
                if (view === 'dashboard') loadDashboard();
                if (view === 'logs') loadLogs();
                if (view === 'api-keys') loadApiKeys();
                if (view === 'users') loadUsers();
            });
        });
        
        document.getElementById('theme-toggle').addEventListener('click', () => {
            document.documentElement.classList.toggle('dark');
        });
        
        document.getElementById('modal-close').addEventListener('click', hideModal);
        document.getElementById('modal-overlay').addEventListener('click', (e) => {
            if (e.target.id === 'modal-overlay') hideModal();
        });
        
        document.getElementById('create-api-key-btn').addEventListener('click', showCreateApiKeyModal);
        document.getElementById('refresh-logs').addEventListener('click', loadLogs);
        document.getElementById('log-filter-status').addEventListener('change', loadLogs);
        
        fetchConfig();
        loadDashboard();
    </script>
</body>
</html>
"""
