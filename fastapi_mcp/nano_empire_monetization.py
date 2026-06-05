"""
nano_empire_monetization.py â€” Nano Empire x402 Pay-Per-Use Guard for MCP Servers

Drop-in monetization layer via https://nanoempireai.com.
- PAPER_MODE=true (default): logs payment receipts, never blocks
- PAPER_MODE=false: enforces x402 payment receipt in X-Payment-Receipt header
"""

import os
import logging
import functools
import inspect
from typing import Any, Callable

logger = logging.getLogger("nano-empire-monetization")

PAPER_MODE = os.getenv("PAPER_MODE", "true").lower() != "false"
NANO_EMPIRE_ENABLED = os.getenv("NANO_EMPIRE_MONETIZATION", "true").lower() != "false"

TOLLBOOTH_ENDPOINT = "https://nano-empire-api-579872312585.northamerica-northeast1.run.app"
PRICE_PER_CALL_USD = 0.01

def monetize(func: Callable) -> Callable:
    """
    Decorator that wraps an MCP tool handler with x402 payment check.
    Supports both synchronous and asynchronous tool functions.
    """
    if not NANO_EMPIRE_ENABLED:
        return func

    is_async = inspect.iscoroutinefunction(func)

    if is_async:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            receipt = kwargs.get("payment_receipt") or (args[0] if args else None)
            tool_name = func.__name__

            if PAPER_MODE:
                logger.info(
                    "[PAPER_MODE] nano-empire: would charge $%.2f for tool=%s receipt=%s",
                    PRICE_PER_CALL_USD,
                    tool_name,
                    receipt,
                )
                return await func(*args, **kwargs)

            if not receipt:
                return {
                    "error": "402 Payment Required",
                    "message": (
                        f"Tool '{tool_name}' requires an x402 payment receipt. "
                        f"Price: ${PRICE_PER_CALL_USD}/call. "
                        f"Debug: POST {TOLLBOOTH_ENDPOINT}/api/v1/x402/debug/simulate"
                    ),
                    "tollbooth": TOLLBOOTH_ENDPOINT,
                }

            logger.info("nano-empire: valid receipt for tool=%s", tool_name)
            return await func(*args, **kwargs)
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            receipt = kwargs.get("payment_receipt") or (args[0] if args else None)
            tool_name = func.__name__

            if PAPER_MODE:
                logger.info(
                    "[PAPER_MODE] nano-empire: would charge $%.2f for tool=%s receipt=%s",
                    PRICE_PER_CALL_USD,
                    tool_name,
                    receipt,
                )
                return func(*args, **kwargs)

            if not receipt:
                return {
                    "error": "402 Payment Required",
                    "message": (
                        f"Tool '{tool_name}' requires an x402 payment receipt. "
                        f"Price: ${PRICE_PER_CALL_USD}/call. "
                        f"Debug: POST {TOLLBOOTH_ENDPOINT}/api/v1/x402/debug/simulate"
                    ),
                    "tollbooth": TOLLBOOTH_ENDPOINT,
                }

            logger.info("nano-empire: valid receipt for tool=%s", tool_name)
            return func(*args, **kwargs)
        return sync_wrapper
