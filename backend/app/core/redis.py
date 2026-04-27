import os
import redis

_REDIS_HOST = os.getenv("REDIS_HOST", "redis")
_REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))


def get_sync_redis(db: int = 0) -> redis.Redis:
    """Synchronous Redis client used by rate limiters and background services."""
    return redis.Redis(host=_REDIS_HOST, port=_REDIS_PORT, db=db, decode_responses=True)
