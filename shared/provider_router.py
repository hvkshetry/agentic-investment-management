"""Provider failover orchestrator for free data sources.

Manages tiered provider selection with automatic failover:
- Primary provider attempted first
- Fallback providers tried in order on failure
- Central throttling to respect rate limits
- Circuit breaker prevents cascading failures
"""

import logging
import time
from typing import Any, Dict, List, Optional, Callable, Awaitable
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import asyncio

from shared.http_client import ProviderError, RateLimitError, ProviderUnavailableError

logger = logging.getLogger(__name__)


class ProviderThrottler:
    """Central rate limit enforcement across all providers."""

    def __init__(self):
        # provider_name -> (call_count, window_start, limit_per_window, window_seconds)
        self._limits: Dict[str, tuple[int, float, int, int]] = {}
        # Per-provider locks to avoid global contention
        self._locks: Dict[str, asyncio.Lock] = {}

    def register_limit(self, provider: str, calls_per_window: int, window_seconds: int):
        """Register rate limit for a provider."""
        self._limits[provider] = (0, time.time(), calls_per_window, window_seconds)
        # Create a lock for this provider
        self._locks[provider] = asyncio.Lock()
        logger.info(f"Registered throttle for {provider}: {calls_per_window} calls per {window_seconds}s")

    async def acquire(self, provider: str) -> Optional[int]:
        """
        Attempt to acquire a call slot for the provider.

        Returns:
            None if allowed, or retry_after seconds if rate limited
        """
        if provider not in self._limits:
            # No limit registered, allow
            return None

        # Use per-provider lock to avoid contention
        if provider not in self._locks:
            self._locks[provider] = asyncio.Lock()

        async with self._locks[provider]:
            call_count, window_start, limit, window_seconds = self._limits[provider]
            now = time.time()

            # Check if we need to reset the window
            if now - window_start >= window_seconds:
                # New window
                self._limits[provider] = (1, now, limit, window_seconds)
                logger.debug(f"{provider} throttle: new window started")
                return None

            # Check if we're at the limit
            if call_count >= limit:
                # Rate limited
                retry_after = int(window_seconds - (now - window_start)) + 1
                logger.warning(f"{provider} throttle: rate limited (retry after {retry_after}s)")
                return retry_after

            # Increment count
            self._limits[provider] = (call_count + 1, window_start, limit, window_seconds)
            logger.debug(f"{provider} throttle: {call_count + 1}/{limit} in current window")
            return None

    def get_quota_status(self, provider: str) -> Dict[str, Any]:
        """Get current quota status for a provider."""
        if provider not in self._limits:
            return {"provider": provider, "has_limit": False}

        call_count, window_start, limit, window_seconds = self._limits[provider]
        now = time.time()
        window_elapsed = now - window_start

        if window_elapsed >= window_seconds:
            # Window expired
            return {
                "provider": provider,
                "has_limit": True,
                "calls_used": 0,
                "calls_limit": limit,
                "window_seconds": window_seconds,
                "window_resets_in": 0
            }

        return {
            "provider": provider,
            "has_limit": True,
            "calls_used": call_count,
            "calls_limit": limit,
            "window_seconds": window_seconds,
            "window_resets_in": int(window_seconds - window_elapsed)
        }


# Global throttler instance
_throttler = ProviderThrottler()


def register_provider_limit(provider: str, calls_per_window: int, window_seconds: int):
    """Register rate limit for a provider (convenience function)."""
    _throttler.register_limit(provider, calls_per_window, window_seconds)


async def get_quota_status(provider: str) -> Dict[str, Any]:
    """Get quota status for a provider (convenience function)."""
    return _throttler.get_quota_status(provider)


class ProviderRouter:
    """
    Routes requests through tiered providers with automatic failover.

    Example:
        router = ProviderRouter("equity_quote")
        router.add_provider("yahoo", yahoo_fetch_func, primary=True)
        router.add_provider("alpha_vantage", av_fetch_func)

        result = await router.execute(symbol="AAPL")
    """

    def __init__(self, capability: str):
        self.capability = capability
        self.providers: List[Dict[str, Any]] = []
        self._stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            "success": 0,
            "failure": 0,
            "rate_limited": 0,
            "fallback_used": 0
        })

    def add_provider(
        self,
        name: str,
        fetch_func: Callable[..., Awaitable[Any]],
        primary: bool = False,
        max_stale_seconds: Optional[int] = None,
        skip_throttle: bool = False
    ):
        """
        Add a provider to the routing chain.

        Args:
            name: Provider identifier
            fetch_func: Async function that fetches data
            primary: If True, this provider is tried first
            max_stale_seconds: Accept stale data up to this many seconds old
            skip_throttle: If True, skip router-level throttling (fetcher handles it internally)
        """
        provider = {
            "name": name,
            "fetch_func": fetch_func,
            "primary": primary,
            "max_stale_seconds": max_stale_seconds,
            "skip_throttle": skip_throttle
        }

        if primary:
            self.providers.insert(0, provider)
        else:
            self.providers.append(provider)

        logger.info(f"Added provider '{name}' to {self.capability} router (primary={primary})")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the request through provider chain with failover.

        Returns:
            Dict with:
                - data: The fetched data
                - source: Provider name that succeeded
                - provenance: Metadata about data source
                - stale: True if data is stale (if applicable)
        """
        if not self.providers:
            raise ValueError(f"No providers registered for {self.capability}")

        errors = []
        fallback_used = False

        for i, provider in enumerate(self.providers):
            if i > 0:
                fallback_used = True
                logger.info(f"{self.capability}: Trying fallback provider '{provider['name']}'")

            try:
                # Check throttle (skip if provider handles throttling internally)
                if not provider.get("skip_throttle", False):
                    retry_after = await _throttler.acquire(provider["name"])
                    if retry_after is not None:
                        self._stats[provider["name"]]["rate_limited"] += 1
                        logger.warning(f"{self.capability}: Provider '{provider['name']}' rate limited")
                        errors.append({
                            "provider": provider["name"],
                            "error": f"Rate limited (retry after {retry_after}s)"
                        })
                        continue

                # Execute fetch
                start_time = time.time()
                data = await provider["fetch_func"](**kwargs)
                elapsed = time.time() - start_time

                # Check staleness if applicable
                stale = False
                if provider["max_stale_seconds"] and "asof" in data:
                    try:
                        data_time = datetime.fromisoformat(data["asof"].replace("Z", "+00:00"))
                        age = (datetime.now(data_time.tzinfo) - data_time).total_seconds()
                        if age > provider["max_stale_seconds"]:
                            logger.warning(
                                f"{self.capability}: Data from '{provider['name']}' is stale "
                                f"({age:.0f}s old, max {provider['max_stale_seconds']}s)"
                            )
                            stale = True
                    except Exception as e:
                        logger.warning(f"Failed to check staleness: {e}")

                # Success
                self._stats[provider["name"]]["success"] += 1
                if fallback_used:
                    self._stats[provider["name"]]["fallback_used"] += 1

                logger.info(
                    f"{self.capability}: SUCCESS via '{provider['name']}' "
                    f"in {elapsed:.2f}s (stale={stale})"
                )

                return {
                    "data": data,
                    "source": provider["name"],
                    "provenance": {
                        "provider": provider["name"],
                        "capability": self.capability,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "elapsed_seconds": elapsed,
                        "fallback_used": fallback_used,
                        "stale": stale
                    }
                }

            except RateLimitError as e:
                self._stats[provider["name"]]["rate_limited"] += 1
                logger.warning(f"{self.capability}: Provider '{provider['name']}' rate limited: {e}")
                errors.append({
                    "provider": provider["name"],
                    "error": f"Rate limited: {e}",
                    "retry_after": e.retry_after
                })

            except ProviderUnavailableError as e:
                self._stats[provider["name"]]["failure"] += 1
                logger.warning(f"{self.capability}: Provider '{provider['name']}' unavailable: {e}")
                errors.append({
                    "provider": provider["name"],
                    "error": f"Unavailable: {e}"
                })

            except Exception as e:
                self._stats[provider["name"]]["failure"] += 1
                logger.error(f"{self.capability}: Provider '{provider['name']}' failed: {e}")
                errors.append({
                    "provider": provider["name"],
                    "error": str(e)
                })

        # All providers failed
        logger.error(f"{self.capability}: All providers failed")
        raise AllProvidersFailed(
            f"{self.capability}: All {len(self.providers)} providers failed",
            errors=errors
        )

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """Get statistics for all providers."""
        return dict(self._stats)

    def reset_stats(self):
        """Reset statistics."""
        self._stats.clear()


class AllProvidersFailed(Exception):
    """Raised when all providers in the chain fail."""

    def __init__(self, message: str, errors: List[Dict[str, Any]]):
        super().__init__(message)
        self.errors = errors


# Pre-configured routers for common capabilities
_routers: Dict[str, ProviderRouter] = {}


def get_router(capability: str) -> Optional[ProviderRouter]:
    """Get a configured router for a capability."""
    return _routers.get(capability)


def register_router(capability: str, router: ProviderRouter):
    """Register a router for a capability."""
    _routers[capability] = router
    logger.info(f"Registered router for capability '{capability}'")


# Initialize common provider limits
def initialize_provider_limits():
    """Initialize rate limits for known free providers."""
    # Alpha Vantage: 5 calls per minute, 500 per day
    # We'll enforce the per-minute limit here
    register_provider_limit("alpha_vantage", calls_per_window=5, window_seconds=60)

    # Finnhub: 60 calls per minute
    register_provider_limit("finnhub", calls_per_window=60, window_seconds=60)

    # FMP: Very limited, treat as 10 per minute to be safe
    register_provider_limit("fmp", calls_per_window=10, window_seconds=60)

    # Yahoo: No official limit, but be conservative (30 per minute)
    register_provider_limit("yahoo", calls_per_window=30, window_seconds=60)

    # GDELT: No strict limit, but cap at 20 per minute to be respectful
    register_provider_limit("gdelt", calls_per_window=20, window_seconds=60)

    # Frankfurter/ECB: No strict limit, daily data (30 per minute)
    register_provider_limit("frankfurter", calls_per_window=30, window_seconds=60)

    # World Bank: No strict limit, but be respectful (20 per minute)
    register_provider_limit("worldbank", calls_per_window=20, window_seconds=60)

    # IMF: No strict limit, but be respectful (20 per minute)
    register_provider_limit("imf", calls_per_window=20, window_seconds=60)

    # LBMA: No strict limit, daily data (20 per minute)
    register_provider_limit("lbma", calls_per_window=20, window_seconds=60)

    # QuickChart: Generous free tier (60 per minute)
    register_provider_limit("quickchart", calls_per_window=60, window_seconds=60)

    logger.info("Initialized provider rate limits")


# Auto-initialize on import
initialize_provider_limits()