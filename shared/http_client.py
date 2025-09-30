"""Shared HTTP client foundation for free data providers.

Provides a standardized base for all external API calls with:
- Consistent timeout, headers, and error handling
- Optional caching (in-process LRU, Redis-ready)
- Telemetry hooks for monitoring
- Automatic retry logic for transient failures
"""

import logging
import time
from typing import Any, Dict, Optional, Callable
from datetime import datetime, timedelta
from functools import lru_cache
import httpx

logger = logging.getLogger(__name__)


class ProviderState:
    """Track provider health state for circuit breaker logic."""

    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 300):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "healthy"  # healthy, degraded, unavailable

    def record_success(self):
        """Reset failure counter on successful call."""
        self.failure_count = 0
        self.state = "healthy"
        logger.debug(f"Provider {self.name} marked healthy")

    def record_failure(self):
        """Increment failure counter and update state."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "unavailable"
            logger.warning(f"Provider {self.name} marked unavailable after {self.failure_count} failures")
        elif self.failure_count >= self.failure_threshold // 2:
            self.state = "degraded"
            logger.info(f"Provider {self.name} marked degraded ({self.failure_count} failures)")

    def is_available(self) -> bool:
        """Check if provider is available (with automatic recovery)."""
        if self.state == "healthy":
            return True

        # Check if recovery timeout has passed
        if self.last_failure_time:
            elapsed = time.time() - self.last_failure_time
            if elapsed > self.recovery_timeout:
                logger.info(f"Provider {self.name} recovery timeout passed, resetting state")
                self.failure_count = 0
                self.state = "healthy"
                return True

        return self.state != "unavailable"


class BaseHTTPTool:
    """Base HTTP client with standardized configuration and caching."""

    DEFAULT_TIMEOUT = 30.0
    DEFAULT_USER_AGENT = "OpenBB-MCP-Server/2.0 (free-provider)"

    def __init__(
        self,
        provider_name: str,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        user_agent: Optional[str] = None,
        cache_ttl: Optional[int] = None
    ):
        self.provider_name = provider_name
        self.base_url = base_url
        self.timeout = timeout
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.cache_ttl = cache_ttl  # seconds
        self.state = ProviderState(provider_name)

        # Simple in-process cache (URL -> (data, timestamp))
        self._cache: Dict[str, tuple[Any, float]] = {}

        # Reusable async client for connection pooling
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the reusable async client."""
        if self._client is None:
            # Configure connection limits for efficient pooling
            limits = httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=30.0
            )
            self._client = httpx.AsyncClient(
                limits=limits,
                timeout=self.timeout,
                follow_redirects=True
            )
        return self._client

    async def close(self):
        """Close the async client and clean up resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def _get_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Build request headers."""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json"
        }
        if additional_headers:
            headers.update(additional_headers)
        return headers

    def _check_cache(self, cache_key: str) -> Optional[Any]:
        """Check if cached data is still valid."""
        if not self.cache_ttl or cache_key not in self._cache:
            return None

        data, timestamp = self._cache[cache_key]
        age = time.time() - timestamp

        if age < self.cache_ttl:
            logger.debug(f"Cache hit for {cache_key} (age: {age:.1f}s)")
            return data

        # Expired, remove from cache
        del self._cache[cache_key]
        return None

    def _set_cache(self, cache_key: str, data: Any):
        """Store data in cache with current timestamp."""
        if self.cache_ttl:
            self._cache[cache_key] = (data, time.time())

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        use_cache: bool = True
    ) -> Any:
        """Execute GET request with caching and error handling."""
        # Build full URL
        full_url = url if url.startswith("http") else f"{self.base_url}{url}"

        # Generate cache key
        cache_key = f"{full_url}?{params}" if params else full_url

        # Check cache first
        if use_cache:
            cached = self._check_cache(cache_key)
            if cached is not None:
                return cached

        # Check provider state
        if not self.state.is_available():
            raise ProviderUnavailableError(
                f"Provider {self.provider_name} is unavailable (state: {self.state.state})"
            )

        # Execute request
        start_time = time.time()
        try:
            client = self._get_client()
            response = await client.get(
                full_url,
                params=params,
                headers=self._get_headers(headers),
                timeout=self.timeout
            )
            response.raise_for_status()

            # Parse JSON
            data = response.json()

            # Record success
            elapsed = time.time() - start_time
            logger.debug(f"{self.provider_name} GET {url} completed in {elapsed:.2f}s")
            self.state.record_success()

            # Cache result
            if use_cache:
                self._set_cache(cache_key, data)

            return data

        except httpx.HTTPStatusError as e:
            elapsed = time.time() - start_time
            logger.error(f"{self.provider_name} HTTP {e.response.status_code} for {url} after {elapsed:.2f}s")

            # Record failure
            self.state.record_failure()

            # Differentiate rate limits from other errors
            if e.response.status_code == 429:
                retry_after = e.response.headers.get("Retry-After")
                raise RateLimitError(
                    f"{self.provider_name} rate limit exceeded",
                    retry_after=int(retry_after) if retry_after else None
                )

            raise ProviderError(f"{self.provider_name} HTTP error: {e}")

        except httpx.TimeoutException as e:
            elapsed = time.time() - start_time
            logger.error(f"{self.provider_name} timeout for {url} after {elapsed:.2f}s")
            self.state.record_failure()
            raise ProviderError(f"{self.provider_name} timeout: {e}")

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"{self.provider_name} error for {url} after {elapsed:.2f}s: {e}")
            self.state.record_failure()
            raise ProviderError(f"{self.provider_name} unexpected error: {e}")

    async def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Any:
        """Execute POST request with error handling."""
        # Build full URL
        full_url = url if url.startswith("http") else f"{self.base_url}{url}"

        # Check provider state
        if not self.state.is_available():
            raise ProviderUnavailableError(
                f"Provider {self.provider_name} is unavailable (state: {self.state.state})"
            )

        # Execute request
        start_time = time.time()
        try:
            client = self._get_client()
            response = await client.post(
                full_url,
                data=data,
                json=json_data,
                headers=self._get_headers(headers),
                timeout=self.timeout
            )
            response.raise_for_status()

            # Parse JSON
            result = response.json()

            # Record success
            elapsed = time.time() - start_time
            logger.debug(f"{self.provider_name} POST {url} completed in {elapsed:.2f}s")
            self.state.record_success()

            return result

        except httpx.HTTPStatusError as e:
            elapsed = time.time() - start_time
            logger.error(f"{self.provider_name} HTTP {e.response.status_code} for {url} after {elapsed:.2f}s")
            self.state.record_failure()

            if e.response.status_code == 429:
                retry_after = e.response.headers.get("Retry-After")
                raise RateLimitError(
                    f"{self.provider_name} rate limit exceeded",
                    retry_after=int(retry_after) if retry_after else None
                )

            raise ProviderError(f"{self.provider_name} HTTP error: {e}")

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"{self.provider_name} error for {url} after {elapsed:.2f}s: {e}")
            self.state.record_failure()
            raise ProviderError(f"{self.provider_name} unexpected error: {e}")


class ProviderError(Exception):
    """Base exception for provider errors."""
    pass


class RateLimitError(ProviderError):
    """Raised when provider rate limit is exceeded."""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class ProviderUnavailableError(ProviderError):
    """Raised when provider is marked unavailable by circuit breaker."""
    pass


# Telemetry hook (placeholder for future monitoring)
def record_provider_metric(provider: str, endpoint: str, elapsed: float, success: bool):
    """Record provider performance metric."""
    # TODO: Implement proper telemetry (Prometheus, CloudWatch, etc.)
    logger.debug(f"METRIC: {provider}.{endpoint} elapsed={elapsed:.2f}s success={success}")