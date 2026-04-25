import logging
import time
from collections import defaultdict, deque
from typing import Dict, Optional, Any
from typing_extensions import Annotated, Doc

from fastapi_mcp.types import (
    RateLimitConfig,
    ApiKey,
)


logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter implementation.
    
    This uses a deque to track request timestamps within each window.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: int,
    ):
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: deque = deque()

    def check_and_acquire(self) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds

        while self._requests and self._requests[0] <= cutoff:
            self._requests.popleft()

        if len(self._requests) >= self.limit:
            return False

        self._requests.append(now)
        return True

    def get_remaining(self) -> int:
        now = time.time()
        cutoff = now - self.window_seconds

        while self._requests and self._requests[0] <= cutoff:
            self._requests.popleft()

        return max(0, self.limit - len(self._requests))

    def get_reset_time(self) -> float:
        if not self._requests:
            return 0.0
        now = time.time()
        oldest = self._requests[0]
        return max(0.0, oldest + self.window_seconds - now)


class RateLimiter:
    """
    Rate limiter for FastAPI-MCP.
    
    Supports:
    - Global rate limiting
    - Per-user rate limiting
    - Per-API-key rate limiting
    - Custom rate limits for specific API keys
    """

    def __init__(
        self,
        config: Annotated[
            Optional[RateLimitConfig],
            Doc("Rate limit configuration"),
        ] = None,
    ):
        self.config = config or RateLimitConfig()
        self._global_limiter: Optional[SlidingWindowRateLimiter] = None
        self._user_limiters: Dict[str, SlidingWindowRateLimiter] = {}
        self._api_key_limiters: Dict[str, SlidingWindowRateLimiter] = {}
        self._start_time = time.time()

        if self.config.global_limit:
            self._global_limiter = SlidingWindowRateLimiter(
                limit=self.config.global_limit,
                window_seconds=self.config.default_window,
            )

    def _get_or_create_limiter(
        self,
        key: str,
        limit: int,
        window: int,
        limiter_dict: Dict[str, SlidingWindowRateLimiter],
    ) -> SlidingWindowRateLimiter:
        if key not in limiter_dict:
            limiter_dict[key] = SlidingWindowRateLimiter(limit=limit, window_seconds=window)
        return limiter_dict[key]

    def check_rate_limit(
        self,
        user_id: Optional[str] = None,
        api_key: Optional[ApiKey] = None,
    ) -> tuple[bool, Dict[str, Any]]:
        if not self.config.enabled:
            return True, {"allowed": True, "reason": "rate_limit_disabled"}

        if self._global_limiter:
            if not self._global_limiter.check_and_acquire():
                return False, {
                    "allowed": False,
                    "reason": "global_rate_limit_exceeded",
                    "limit": self.config.global_limit,
                    "remaining": self._global_limiter.get_remaining(),
                    "reset_seconds": self._global_limiter.get_reset_time(),
                }

        if api_key:
            effective_limit = self.config.get_effective_limit(api_key)
            effective_window = api_key.rate_limit_window if api_key.rate_limit else self.config.default_window

            limiter = self._get_or_create_limiter(
                key=api_key.id,
                limit=effective_limit,
                window=effective_window,
                limiter_dict=self._api_key_limiters,
            )

            if not limiter.check_and_acquire():
                return False, {
                    "allowed": False,
                    "reason": "api_key_rate_limit_exceeded",
                    "limit": effective_limit,
                    "window_seconds": effective_window,
                    "remaining": limiter.get_remaining(),
                    "reset_seconds": limiter.get_reset_time(),
                    "api_key_id": api_key.id,
                }

        elif user_id:
            effective_limit = self.config.user_limit or self.config.default_limit
            effective_window = self.config.default_window

            limiter = self._get_or_create_limiter(
                key=user_id,
                limit=effective_limit,
                window=effective_window,
                limiter_dict=self._user_limiters,
            )

            if not limiter.check_and_acquire():
                return False, {
                    "allowed": False,
                    "reason": "user_rate_limit_exceeded",
                    "limit": effective_limit,
                    "window_seconds": effective_window,
                    "remaining": limiter.get_remaining(),
                    "reset_seconds": limiter.get_reset_time(),
                    "user_id": user_id,
                }

        return True, {"allowed": True}

    def get_rate_limit_status(
        self,
        user_id: Optional[str] = None,
        api_key: Optional[ApiKey] = None,
    ) -> Dict[str, Any]:
        status = {
            "enabled": self.config.enabled,
            "global": None,
            "user": None,
            "api_key": None,
        }

        if self._global_limiter:
            status["global"] = {
                "limit": self.config.global_limit,
                "remaining": self._global_limiter.get_remaining(),
                "reset_seconds": self._global_limiter.get_reset_time(),
            }

        if api_key and api_key.id in self._api_key_limiters:
            limiter = self._api_key_limiters[api_key.id]
            effective_limit = self.config.get_effective_limit(api_key)
            status["api_key"] = {
                "id": api_key.id,
                "limit": effective_limit,
                "remaining": limiter.get_remaining(),
                "reset_seconds": limiter.get_reset_time(),
            }
        elif api_key:
            effective_limit = self.config.get_effective_limit(api_key)
            status["api_key"] = {
                "id": api_key.id,
                "limit": effective_limit,
                "remaining": effective_limit,
                "reset_seconds": 0.0,
            }

        if user_id and user_id in self._user_limiters:
            limiter = self._user_limiters[user_id]
            effective_limit = self.config.user_limit or self.config.default_limit
            status["user"] = {
                "id": user_id,
                "limit": effective_limit,
                "remaining": limiter.get_remaining(),
                "reset_seconds": limiter.get_reset_time(),
            }
        elif user_id:
            effective_limit = self.config.user_limit or self.config.default_limit
            status["user"] = {
                "id": user_id,
                "limit": effective_limit,
                "remaining": effective_limit,
                "reset_seconds": 0.0,
            }

        return status

    def reset_limiter(
        self,
        user_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
    ) -> bool:
        if user_id and user_id in self._user_limiters:
            del self._user_limiters[user_id]
            logger.info(f"Rate limiter reset for user: {user_id}")
            return True

        if api_key_id and api_key_id in self._api_key_limiters:
            del self._api_key_limiters[api_key_id]
            logger.info(f"Rate limiter reset for API key: {api_key_id}")
            return True

        return False

    def get_stats(self) -> Dict[str, Any]:
        uptime = time.time() - self._start_time

        active_user_limiters = len(self._user_limiters)
        active_api_key_limiters = len(self._api_key_limiters)

        total_user_requests = sum(
            len(limiter._requests) for limiter in self._user_limiters.values()
        )
        total_api_key_requests = sum(
            len(limiter._requests) for limiter in self._api_key_limiters.values()
        )

        return {
            "enabled": self.config.enabled,
            "uptime_seconds": round(uptime, 2),
            "active_user_limiters": active_user_limiters,
            "active_api_key_limiters": active_api_key_limiters,
            "total_user_requests_tracked": total_user_requests,
            "total_api_key_requests_tracked": total_api_key_requests,
            "config": {
                "default_limit": self.config.default_limit,
                "default_window": self.config.default_window,
                "user_limit": self.config.user_limit,
                "api_key_limit": self.config.api_key_limit,
                "global_limit": self.config.global_limit,
            },
        }

    def cleanup_stale_limiters(self, max_age_seconds: int = 3600) -> int:
        now = time.time()
        cutoff = now - max_age_seconds

        cleaned = 0

        for key in list(self._user_limiters.keys()):
            limiter = self._user_limiters[key]
            if not limiter._requests or (limiter._requests and limiter._requests[-1] <= cutoff):
                del self._user_limiters[key]
                cleaned += 1

        for key in list(self._api_key_limiters.keys()):
            limiter = self._api_key_limiters[key]
            if not limiter._requests or (limiter._requests and limiter._requests[-1] <= cutoff):
                del self._api_key_limiters[key]
                cleaned += 1

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} stale rate limiters")

        return cleaned
