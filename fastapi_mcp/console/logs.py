"""
Log storage and types for MCP tool call logging.

Provides in-memory storage for tool call logs with configurable max size.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class LogStatus(str, Enum):
    """Status of a tool call log entry."""

    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class LogEntry:
    """A single log entry for an MCP tool call."""

    id: str
    tool_name: str
    arguments: Dict[str, Any]
    status: LogStatus = LogStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    method: Optional[str] = None
    path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to a dictionary for JSON serialization."""
        start_datetime = datetime.fromtimestamp(self.start_time).isoformat()
        end_datetime = datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None

        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time,
            "start_datetime": start_datetime,
            "end_time": self.end_time,
            "end_datetime": end_datetime,
            "duration_ms": self.duration_ms,
            "method": self.method,
            "path": self.path,
        }

    def complete(self, result: Any, error: Optional[str] = None) -> None:
        """Mark the log entry as completed."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000

        if error:
            self.status = LogStatus.ERROR
            self.error = error
        else:
            self.status = LogStatus.SUCCESS
            try:
                self.result = json.dumps(result, indent=2, ensure_ascii=False, default=str)
            except Exception:
                self.result = str(result)


ToolCallLog = LogEntry


class LogStore:
    """In-memory storage for tool call logs."""

    def __init__(self, max_size: int = 1000):
        """Initialize the log store.

        Args:
            max_size: Maximum number of log entries to keep. Oldest entries are removed when limit is reached.
        """
        self._logs: List[LogEntry] = []
        self._max_size = max_size
        self._counter: int = 0

    def _generate_id(self) -> str:
        """Generate a unique log entry ID."""
        self._counter += 1
        return f"log_{self._counter}_{int(time.time() * 1000)}"

    def create_entry(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        method: Optional[str] = None,
        path: Optional[str] = None,
    ) -> LogEntry:
        """Create a new log entry for a pending tool call.

        Args:
            tool_name: Name of the tool being called
            arguments: Arguments passed to the tool
            method: HTTP method (if applicable)
            path: API path (if applicable)

        Returns:
            The created LogEntry
        """
        entry = LogEntry(
            id=self._generate_id(),
            tool_name=tool_name,
            arguments=arguments,
            method=method,
            path=path,
        )

        self._logs.append(entry)

        if len(self._logs) > self._max_size:
            self._logs = self._logs[-self._max_size :]

        return entry

    def get_all(self, limit: Optional[int] = None) -> List[LogEntry]:
        """Get all log entries, newest first.

        Args:
            limit: Maximum number of entries to return. If None, returns all.

        Returns:
            List of log entries, newest first
        """
        entries = list(reversed(self._logs))
        if limit is not None:
            entries = entries[:limit]
        return entries

    def get_by_id(self, log_id: str) -> Optional[LogEntry]:
        """Get a log entry by its ID.

        Args:
            log_id: The log entry ID

        Returns:
            The LogEntry if found, None otherwise
        """
        for entry in self._logs:
            if entry.id == log_id:
                return entry
        return None

    def clear(self) -> int:
        """Clear all log entries.

        Returns:
            Number of entries cleared
        """
        count = len(self._logs)
        self._logs.clear()
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the logs.

        Returns:
            Dictionary with statistics
        """
        total = len(self._logs)
        success = sum(1 for e in self._logs if e.status == LogStatus.SUCCESS)
        error = sum(1 for e in self._logs if e.status == LogStatus.ERROR)
        pending = sum(1 for e in self._logs if e.status == LogStatus.PENDING)

        durations = [e.duration_ms for e in self._logs if e.duration_ms is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total": total,
            "success": success,
            "error": error,
            "pending": pending,
            "avg_duration_ms": round(avg_duration, 2),
        }


_global_log_store: Optional[LogStore] = None


def get_global_log_store() -> LogStore:
    """Get or create the global log store instance.

    Returns:
        The global LogStore instance
    """
    global _global_log_store
    if _global_log_store is None:
        _global_log_store = LogStore()
    return _global_log_store
