import logging
import uuid
import time
from collections import deque, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Deque
from typing_extensions import Annotated, Doc

from fastapi_mcp.types import (
    CallLog,
    CallStatus,
    MonitorData,
)


logger = logging.getLogger(__name__)


class CallLogger:
    """
    Call logging and monitoring system for FastAPI-MCP.
    
    Provides:
    - Call logging with detailed request/response information
    - Real-time monitoring data aggregation
    - Statistics collection
    - Error tracking
    """

    def __init__(
        self,
        max_logs: Annotated[
            int,
            Doc("Maximum number of logs to keep in memory"),
        ] = 10000,
        max_errors: Annotated[
            int,
            Doc("Maximum number of errors to keep in memory"),
        ] = 1000,
        metrics_window_seconds: Annotated[
            int,
            Doc("Time window for metrics calculation in seconds"),
        ] = 3600,
    ):
        self._max_logs = max_logs
        self._max_errors = max_errors
        self._metrics_window_seconds = metrics_window_seconds

        self._logs: Deque[CallLog] = deque(maxlen=max_logs)
        self._errors: Deque[CallLog] = deque(maxlen=max_errors)

        self._tool_call_counts: Dict[str, int] = defaultdict(int)
        self._tool_durations: Dict[str, List[float]] = defaultdict(list)
        self._recent_durations: Deque[float] = deque(maxlen=10000)

        self._start_time = time.time()
        self._total_calls = 0
        self._success_calls = 0
        self._error_calls = 0
        self._rate_limited_calls = 0

        self._user_activity: Dict[str, datetime] = {}
        self._api_key_activity: Dict[str, datetime] = {}

    def log_call(
        self,
        tool_name: str,
        status: CallStatus,
        duration_ms: float,
        request_method: str,
        request_path: str,
        user_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        request_headers: Optional[Dict[str, str]] = None,
        request_body: Optional[str] = None,
        response_status: int = 200,
        response_body: Optional[str] = None,
        error_message: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CallLog:
        call_log = CallLog(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            tool_name=tool_name,
            user_id=user_id,
            api_key_id=api_key_id,
            status=status,
            duration_ms=duration_ms,
            request_method=request_method,
            request_path=request_path,
            request_headers=request_headers or {},
            request_body=request_body,
            response_status=response_status,
            response_body=response_body,
            error_message=error_message,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        self._logs.append(call_log)

        self._total_calls += 1
        self._tool_call_counts[tool_name] += 1
        self._tool_durations[tool_name].append(duration_ms)
        self._recent_durations.append(duration_ms)

        if status == CallStatus.SUCCESS:
            self._success_calls += 1
        elif status == CallStatus.ERROR:
            self._error_calls += 1
            self._errors.append(call_log)
        elif status == CallStatus.RATE_LIMITED:
            self._rate_limited_calls += 1

        if user_id:
            self._user_activity[user_id] = datetime.utcnow()
        if api_key_id:
            self._api_key_activity[api_key_id] = datetime.utcnow()

        logger.debug(
            f"Call logged: {tool_name} - {status.value} - {duration_ms}ms "
            f"(user: {user_id}, api_key: {api_key_id})"
        )

        return call_log

    def get_logs(
        self,
        tool_name: Optional[str] = None,
        user_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        status: Optional[CallStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CallLog]:
        filtered = list(self._logs)

        if tool_name:
            filtered = [log for log in filtered if log.tool_name == tool_name]
        if user_id:
            filtered = [log for log in filtered if log.user_id == user_id]
        if api_key_id:
            filtered = [log for log in filtered if log.api_key_id == api_key_id]
        if status:
            filtered = [log for log in filtered if log.status == status]

        filtered = list(reversed(filtered))

        return filtered[offset : offset + limit]

    def get_errors(
        self,
        tool_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[CallLog]:
        errors = list(self._errors)

        if tool_name:
            errors = [e for e in errors if e.tool_name == tool_name]

        return list(reversed(errors))[:limit]

    def get_monitor_data(self) -> MonitorData:
        uptime = time.time() - self._start_time

        avg_response_time = 0.0
        if self._recent_durations:
            avg_response_time = sum(self._recent_durations) / len(self._recent_durations)

        p99_response_time = 0.0
        if self._recent_durations:
            sorted_durations = sorted(self._recent_durations)
            p99_index = int(len(sorted_durations) * 0.99)
            if p99_index < len(sorted_durations):
                p99_response_time = sorted_durations[p99_index]

        window_start = time.time() - self._metrics_window_seconds
        calls_in_window = sum(
            1 for log in self._logs
            if log.timestamp.timestamp() >= window_start
        )
        requests_per_second = calls_in_window / self._metrics_window_seconds if self._metrics_window_seconds > 0 else 0

        top_tools = sorted(
            [{"tool": t, "count": c} for t, c in self._tool_call_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:10]

        recent_errors = [
            {
                "id": e.id,
                "tool_name": e.tool_name,
                "error_message": e.error_message,
                "timestamp": e.timestamp.isoformat(),
                "response_status": e.response_status,
            }
            for e in list(self._errors)[-20:]
        ]

        active_cutoff = datetime.utcnow() - timedelta(minutes=30)
        active_users = [
            {"user_id": uid, "last_active": last.isoformat()}
            for uid, last in self._user_activity.items()
            if last >= active_cutoff
        ]

        return MonitorData(
            total_calls=self._total_calls,
            success_calls=self._success_calls,
            error_calls=self._error_calls,
            rate_limited_calls=self._rate_limited_calls,
            total_users=len(self._user_activity),
            active_api_keys=len(self._api_key_activity),
            uptime_seconds=round(uptime, 2),
            avg_response_time_ms=round(avg_response_time, 2),
            p99_response_time_ms=round(p99_response_time, 2),
            requests_per_second=round(requests_per_second, 4),
            top_tools=top_tools,
            recent_errors=recent_errors,
            active_users=active_users,
        )

    def get_tool_statistics(
        self,
        tool_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        if tool_name:
            counts = {tool_name: self._tool_call_counts.get(tool_name, 0)}
            durations = {tool_name: self._tool_durations.get(tool_name, [])}
        else:
            counts = dict(self._tool_call_counts)
            durations = dict(self._tool_durations)

        stats = {}
        for t, count in counts.items():
            tool_durations = durations.get(t, [])
            if tool_durations:
                avg = sum(tool_durations) / len(tool_durations)
                min_d = min(tool_durations)
                max_d = max(tool_durations)
                sorted_d = sorted(tool_durations)
                p99_idx = int(len(sorted_d) * 0.99)
                p99 = sorted_d[p99_idx] if p99_idx < len(sorted_d) else max_d
            else:
                avg = 0.0
                min_d = 0.0
                max_d = 0.0
                p99 = 0.0

            stats[t] = {
                "count": count,
                "avg_duration_ms": round(avg, 2),
                "min_duration_ms": round(min_d, 2),
                "max_duration_ms": round(max_d, 2),
                "p99_duration_ms": round(p99, 2),
            }

        return stats

    def clear_logs(self) -> int:
        count = len(self._logs)
        self._logs.clear()
        self._errors.clear()
        logger.info(f"Cleared {count} logs")
        return count

    def get_stats_summary(self) -> Dict[str, Any]:
        monitor_data = self.get_monitor_data()

        success_rate = 0.0
        if monitor_data.total_calls > 0:
            success_rate = (monitor_data.success_calls / monitor_data.total_calls) * 100

        error_rate = 0.0
        if monitor_data.total_calls > 0:
            error_rate = (monitor_data.error_calls / monitor_data.total_calls) * 100

        return {
            "summary": {
                "total_calls": monitor_data.total_calls,
                "success_calls": monitor_data.success_calls,
                "error_calls": monitor_data.error_calls,
                "rate_limited_calls": monitor_data.rate_limited_calls,
                "success_rate_pct": round(success_rate, 2),
                "error_rate_pct": round(error_rate, 2),
            },
            "performance": {
                "avg_response_time_ms": monitor_data.avg_response_time_ms,
                "p99_response_time_ms": monitor_data.p99_response_time_ms,
                "requests_per_second": monitor_data.requests_per_second,
                "uptime_seconds": monitor_data.uptime_seconds,
            },
            "system": {
                "total_users": monitor_data.total_users,
                "active_api_keys": monitor_data.active_api_keys,
                "active_tools": len(self._tool_call_counts),
            },
        }
