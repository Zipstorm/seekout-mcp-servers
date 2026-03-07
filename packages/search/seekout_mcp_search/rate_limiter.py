"""Redis-backed rate limiter with daily and per-second limits."""

import time

import redis.asyncio as redis


class RateLimitExceeded(Exception):
    """Raised when a rate limit is exceeded."""

    def __init__(self, limit_type: str, retry_after: int):
        self.limit_type = limit_type
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded ({limit_type}). "
            f"Retry after {retry_after} seconds."
        )


class RateLimiter:
    """Per-user rate limiter using Redis counters.

    Two windows:
      - daily:      max_daily requests per calendar day (UTC)
      - per-second: max_per_second requests per 1-second window
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        max_daily: int = 1000,
        max_per_second: int = 10,
    ):
        self._redis = redis_client
        self._max_daily = max_daily
        self._max_per_second = max_per_second

    def _daily_key(self, user_id: str) -> str:
        day = time.strftime("%Y-%m-%d", time.gmtime())
        return f"mcp:rate:daily:{user_id}:{day}"

    def _second_key(self, user_id: str) -> str:
        second = int(time.time())
        return f"mcp:rate:sec:{user_id}:{second}"

    async def check(self, user_id: str) -> None:
        """Check both rate limits. Raises RateLimitExceeded if over."""
        pipe = self._redis.pipeline()

        daily_key = self._daily_key(user_id)
        second_key = self._second_key(user_id)

        # Atomically increment both counters
        pipe.incr(daily_key)
        pipe.expire(daily_key, 86400)
        pipe.incr(second_key)
        pipe.expire(second_key, 2)

        results = await pipe.execute()
        daily_count = results[0]
        second_count = results[2]

        if second_count > self._max_per_second:
            raise RateLimitExceeded("per_second", retry_after=1)

        if daily_count > self._max_daily:
            raise RateLimitExceeded("daily", retry_after=self._seconds_until_midnight())

    @staticmethod
    def _seconds_until_midnight() -> int:
        now = time.time()
        midnight = (int(now) // 86400 + 1) * 86400
        return midnight - int(now)
