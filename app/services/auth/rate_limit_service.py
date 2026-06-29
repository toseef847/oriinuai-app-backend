import hashlib
import logging
import time
from dataclasses import dataclass

from fastapi import HTTPException, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Redis | None = None


@dataclass(frozen=True)
class RateLimitLease:
    key: str


def _get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=settings.REDIS_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_TIMEOUT_SECONDS,
        )
    return _redis_client


def _fingerprint(value: str, *, normalize: bool) -> str:
    prepared = value.strip().lower() if normalize else value.strip()
    return hashlib.sha256(prepared.encode("utf-8")).hexdigest()


async def enforce_auth_rate_limit(
    action: str,
    identity: str,
    *,
    normalize_identity: bool = True,
) -> RateLimitLease | None:
    """Count an auth attempt, failing open if Redis is unavailable."""
    window = settings.AUTH_RATE_LIMIT_WINDOW_SECONDS
    attempts = settings.AUTH_RATE_LIMIT_ATTEMPTS
    now = int(time.time())
    bucket = now // window
    key = (
        f"oriinu:auth-rate:{action}:"
        f"{_fingerprint(identity, normalize=normalize_identity)}:{bucket}"
    )

    try:
        pipeline = _get_redis_client().pipeline(transaction=True)
        pipeline.incr(key)
        pipeline.expire(key, window * 2)
        count, _ = await pipeline.execute()
    except RedisError:
        logger.exception("Auth rate limiter unavailable; allowing request")
        return None

    if int(count) > attempts:
        retry_after = max(1, window - (now % window))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    return RateLimitLease(key=key)


async def clear_auth_rate_limit(lease: RateLimitLease | None) -> None:
    """Clear failed-attempt state after a successful credential operation."""
    if lease is None:
        return

    try:
        await _get_redis_client().delete(lease.key)
    except RedisError:
        logger.exception("Unable to clear auth rate-limit state")
