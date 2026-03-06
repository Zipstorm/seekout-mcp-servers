import time

import httpx


class SeekOutAPI:
    """httpx-based client for SeekOut Runtime API."""

    def __init__(self, base_url: str, api_key: str):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Api-Key": api_key, "Accept": "application/json"},
            timeout=30.0,
        )

    async def ping(self) -> tuple[int, float]:
        """GET /api/Search/CheckBooleanExpression?query=test. Returns (status_code, elapsed_ms)."""
        start = time.monotonic()
        resp = await self._client.get(
            "/api/Search/CheckBooleanExpression",
            params={"query": "test"},
        )
        elapsed_ms = (time.monotonic() - start) * 1000
        return resp.status_code, elapsed_ms

    async def search_people(self, query: dict) -> tuple[dict, int]:
        """POST /api/PeopleSearch/SearchPeople. Returns (response_body, total_count)."""
        resp = await self._client.post(
            "/api/PeopleSearch/SearchPeople",
            json=query,
        )
        resp.raise_for_status()
        data = resp.json()
        return data, data.get("count", 0)

    async def get_count(self, query: dict) -> int:
        """Same endpoint with Top=0, returns count only."""
        query = {**query, "top": 0}
        resp = await self._client.post(
            "/api/PeopleSearch/SearchPeople",
            json=query,
        )
        resp.raise_for_status()
        return resp.json().get("count", 0)

    async def get_profile(self, key: str, index: str = "NorthAmerica") -> dict | None:
        """GET /api/PeopleSearch/GetProfile."""
        resp = await self._client.get(
            "/api/PeopleSearch/GetProfile",
            params={"key": key, "index": index},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def search_entities(
        self, entity_type: str, query: str, max_results: int = 5
    ) -> list[dict]:
        """GET /api/Search/Get. Returns list of {Text, Id, Count}."""
        resp = await self._client.get(
            "/api/Search/Get",
            params={
                "entityType": entity_type,
                "query": query,
                "maxResults": max_results,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def validate_boolean(self, query: str) -> tuple[bool, str | None]:
        """GET /api/Search/CheckBooleanExpression. Returns (is_valid, error)."""
        resp = await self._client.get(
            "/api/Search/CheckBooleanExpression",
            params={"query": query},
        )
        resp.raise_for_status()
        data = resp.json()
        has_errors = data.get("has_errors", False)
        error_msg = data.get("error_message")
        return not has_errors, error_msg

    async def close(self):
        await self._client.aclose()
