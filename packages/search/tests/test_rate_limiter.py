import pytest
from unittest.mock import AsyncMock, MagicMock

from seekout_mcp_search.rate_limiter import RateLimiter, RateLimitExceeded


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    # Pipeline methods are synchronous in redis.asyncio (they queue commands),
    # only execute() is async. Use MagicMock for the pipeline itself.
    pipe = MagicMock()
    pipe.execute = AsyncMock(return_value=[1, True, 1, True])
    r.pipeline = MagicMock(return_value=pipe)
    return r, pipe


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_under_limit(self, mock_redis):
        redis_client, pipe = mock_redis
        pipe.execute = AsyncMock(return_value=[1, True, 1, True])

        limiter = RateLimiter(redis_client, max_daily=1000, max_per_second=10)
        await limiter.check("user1")  # Should not raise

    @pytest.mark.asyncio
    async def test_blocks_daily_limit(self, mock_redis):
        redis_client, pipe = mock_redis
        pipe.execute = AsyncMock(return_value=[1001, True, 1, True])

        limiter = RateLimiter(redis_client, max_daily=1000, max_per_second=10)
        with pytest.raises(RateLimitExceeded) as exc_info:
            await limiter.check("user1")
        assert exc_info.value.limit_type == "daily"
        assert exc_info.value.retry_after > 0

    @pytest.mark.asyncio
    async def test_blocks_per_second_limit(self, mock_redis):
        redis_client, pipe = mock_redis
        pipe.execute = AsyncMock(return_value=[5, True, 11, True])

        limiter = RateLimiter(redis_client, max_daily=1000, max_per_second=10)
        with pytest.raises(RateLimitExceeded) as exc_info:
            await limiter.check("user1")
        assert exc_info.value.limit_type == "per_second"
        assert exc_info.value.retry_after == 1

    @pytest.mark.asyncio
    async def test_per_second_checked_before_daily(self, mock_redis):
        """Per-second limit should fire even if daily is also exceeded."""
        redis_client, pipe = mock_redis
        pipe.execute = AsyncMock(return_value=[1001, True, 11, True])

        limiter = RateLimiter(redis_client, max_daily=1000, max_per_second=10)
        with pytest.raises(RateLimitExceeded) as exc_info:
            await limiter.check("user1")
        assert exc_info.value.limit_type == "per_second"

    @pytest.mark.asyncio
    async def test_different_users_independent(self, mock_redis):
        redis_client, pipe = mock_redis
        calls = []
        original_incr = pipe.incr

        def track_incr(key):
            calls.append(key)
            return original_incr(key)

        pipe.incr = track_incr
        pipe.execute = AsyncMock(return_value=[1, True, 1, True])

        limiter = RateLimiter(redis_client, max_daily=1000, max_per_second=10)
        await limiter.check("user1")
        await limiter.check("user2")

        user1_keys = [c for c in calls if "user1" in c]
        user2_keys = [c for c in calls if "user2" in c]
        assert len(user1_keys) == 2  # daily + second
        assert len(user2_keys) == 2
