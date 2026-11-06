"""Fixed-window rate limits in Redis (rule 6). Shared by all API replicas, so limits hold when scaled out."""

import time

from app.problems import Problem
from app.redis_client import redis


async def hit(bucket: str, limit: int, window_s: int = 60) -> None:
    window = int(time.time() // window_s)
    key = f"rl:{bucket}:{window}"
    pipe = redis().pipeline()
    pipe.incr(key)
    pipe.expire(key, window_s + 5)
    count, _ = await pipe.execute()
    if int(count) > limit:
        retry = window_s - int(time.time() % window_s)
        raise Problem(429, "Too many attempts. Wait a moment and try again.", retry_after=retry)
