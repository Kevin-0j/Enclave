from redis.asyncio import Redis

from app.config import get_settings

_redis: Redis | None = None


def redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url.get_secret_value(), decode_responses=True)
    return _redis


async def close() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None
