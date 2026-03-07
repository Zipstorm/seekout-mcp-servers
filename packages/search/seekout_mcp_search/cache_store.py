"""Redis-backed result cache for search queries.

Stores PeopleSearchQuery + PeopleSearchResult by API-native search_id
for token reduction (avoids re-sending full results) and audit trail.

Key schema: mcp:cache:{search_id}
"""

import json

import redis.asyncio as redis


class CacheStore:
    """Caches search results in Redis by search_id."""

    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 3600):
        self._redis = redis_client
        self._ttl = ttl_seconds

    def _key(self, search_id: str) -> str:
        return f"mcp:cache:{search_id}"

    async def cache_search(
        self, search_id: str, query: dict, results: dict
    ) -> None:
        """Store query + results by search_id with TTL."""
        payload = {"query": query, "results": results}
        await self._redis.set(
            self._key(search_id), json.dumps(payload), ex=self._ttl
        )

    async def get_cached(self, search_id: str) -> dict | None:
        """Retrieve cached query + results by search_id."""
        data = await self._redis.get(self._key(search_id))
        if data is None:
            return None
        return json.loads(data)
