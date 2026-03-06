"""Redis-backed search session store.

Each session stores accumulated filters as a JSON dict in Redis.
Sessions expire after a configurable TTL (default 1 hour).

Key schema: mcp:search:{session_id}
"""

import json
import uuid

import redis.asyncio as redis


class SessionStore:
    """Manages search sessions in Redis."""

    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 3600):
        self._redis = redis_client
        self._ttl = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"mcp:search:{session_id}"

    async def create(self, query: str = "") -> dict:
        session_id = str(uuid.uuid4())
        session = {
            "session_id": session_id,
            "query": query,
            "filters": {},
        }
        await self._redis.set(
            self._key(session_id), json.dumps(session), ex=self._ttl
        )
        return session

    async def get(self, session_id: str) -> dict | None:
        data = await self._redis.get(self._key(session_id))
        if data is None:
            return None
        return json.loads(data)

    async def update(self, session: dict) -> None:
        await self._redis.set(
            self._key(session["session_id"]),
            json.dumps(session),
            ex=self._ttl,
        )

    async def delete(self, session_id: str) -> bool:
        return await self._redis.delete(self._key(session_id)) > 0

    async def add_filter(
        self, session_id: str, filter_type: str, values: list[str]
    ) -> dict | None:
        session = await self.get(session_id)
        if session is None:
            return None

        filters = session["filters"]

        if filter_type == "query":
            session["query"] = values[0] if values else ""
        elif filter_type == "years_experience_min":
            yoe = filters.get("years_of_experience", {})
            yoe["min"] = int(values[0]) if values else 0
            filters["years_of_experience"] = yoe
        elif filter_type == "years_experience_max":
            yoe = filters.get("years_of_experience", {})
            yoe["max"] = int(values[0]) if values else 99
            filters["years_of_experience"] = yoe
        elif filter_type == "titles":
            filters["current_title"] = {"alt_names": values}
        elif filter_type == "companies":
            filters["current_company"] = {"alt_names": values}
        elif filter_type == "locations":
            filters["location"] = {"alt_names": values}
        elif filter_type == "skills":
            filters["_skill_names"] = values
        else:
            return None

        session["filters"] = filters
        await self.update(session)
        return session

    async def remove_filter(self, session_id: str, filter_type: str) -> dict | None:
        session = await self.get(session_id)
        if session is None:
            return None

        filters = session["filters"]
        type_to_key = {
            "titles": "current_title",
            "companies": "current_company",
            "locations": "location",
            "skills": "_skill_names",
            "years_experience_min": "years_of_experience",
            "years_experience_max": "years_of_experience",
            "query": None,
        }

        if filter_type == "query":
            session["query"] = ""
        elif filter_type in ("years_experience_min", "years_experience_max"):
            yoe = filters.get("years_of_experience", {})
            sub_key = "min" if filter_type == "years_experience_min" else "max"
            yoe.pop(sub_key, None)
            if yoe:
                filters["years_of_experience"] = yoe
            else:
                filters.pop("years_of_experience", None)
        elif filter_type in type_to_key:
            key = type_to_key[filter_type]
            if key:
                filters.pop(key, None)
        else:
            return None

        session["filters"] = filters
        await self.update(session)
        return session
