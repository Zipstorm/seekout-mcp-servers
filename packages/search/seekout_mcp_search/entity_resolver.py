import asyncio

from cachetools import TTLCache

from seekout_mcp_search.seekout_api import SeekOutAPI


class EntityResolver:
    """Resolves entity names to IDs via SeekOut Runtime API.

    Results are cached in-process with a 1-hour TTL.
    """

    def __init__(self, seekout_api: SeekOutAPI):
        self._api = seekout_api
        self._cache: TTLCache = TTLCache(maxsize=1024, ttl=3600)

    async def resolve(
        self, entity_type: str, names: list[str]
    ) -> list[dict]:
        """Resolve a list of names in parallel.

        Returns list of {"name": str, "id": int | None, "resolved": bool}.
        """
        tasks = [self._resolve_one(entity_type, name) for name in names]
        return list(await asyncio.gather(*tasks))

    async def _resolve_one(self, entity_type: str, name: str) -> dict:
        cache_key = f"entity:{entity_type}:{name.lower()}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            results = await self._api.search_entities(entity_type, name, max_results=5)
            result = self._select_best_match(results, name)
            self._cache[cache_key] = result
            return result
        except Exception:
            return {"name": name, "id": None, "resolved": False}

    @staticmethod
    def _select_best_match(results: list[dict], input_name: str) -> dict:
        if not results:
            return {"name": input_name, "id": None, "resolved": False}

        # Rule 1: exact match (case-insensitive)
        for r in results:
            if r["text"].lower() == input_name.lower():
                return {"name": input_name, "id": r["id"], "resolved": True}

        # Rule 2: clear winner (top count > 2x second)
        if len(results) >= 2:
            if results[0]["count"] > 2 * results[1]["count"]:
                return {"name": input_name, "id": results[0]["id"], "resolved": True}

        # Rule 3: single result
        if len(results) == 1:
            return {"name": input_name, "id": results[0]["id"], "resolved": True}

        # Rule 4: ambiguous
        return {"name": input_name, "id": None, "resolved": False}
