"""
FastAPI-MCP Web Console Module.

Provides a lightweight web management console for visualizing and debugging MCP tools.
"""

from .logs import (
    ToolCallLog,
    LogStore,
    LogEntry,
    LogStatus,
    get_global_log_store,
)
from .router import ConsoleConfig, get_console_router

__all__ = [
    "ToolCallLog",
    "LogStore",
    "LogEntry",
    "LogStatus",
    "get_global_log_store",
    "ConsoleConfig",
    "get_console_router",
]
