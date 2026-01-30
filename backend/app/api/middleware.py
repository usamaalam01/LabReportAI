"""Redis-based per-IP rate limiting.

Implemented as a callable for use in the upload endpoint.
Uses INCR + EXPIRE on `rate_limit:{ip}` keys with 1-hour TTL.
"""
import logging

import redis.asyncio as redis
from fastapi import Request

from app.config import get_settings

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when per-IP rate limit is exceeded."""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        self.message = f"Rate limit exceeded. Try again in {retry_after} seconds."
        super().__init__(self.message)


_redis_client: redis.Redis | None = None


async def get_redis_client() -> redis.Redis:
    """Get or create the async Redis client."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(
            settings.redis_url, decode_responses=True
        )
    return _redis_client


async def check_rate_limit(request: Request) -> None:
    """Check per-IP rate limit for the upload endpoint.

    Uses Redis INCR + EXPIRE on key `rate_limit:{ip}`.
    Raises RateLimitExceeded if limit exceeded.
    """
    settings = get_settings()
    ip = request.client.host if request.client else "unknown"
    key = f"rate_limit:{ip}"

    client = await get_redis_client()
    count = await client.incr(key)

    if count == 1:
        await client.expire(key, 3600)

    if count > settings.rate_limit_per_ip:
        ttl = await client.ttl(key)
        raise RateLimitExceeded(retry_after=max(ttl, 1))
