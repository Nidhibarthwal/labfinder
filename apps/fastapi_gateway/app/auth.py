# app/auth.py
"""
Authentication utilities for FastAPI Gateway in LabFinder.
Supports DRF Token authentication and Django session validation.
Includes an in-memory TTL cache to avoid hitting Postgres on every reconnect.
"""

import time
import asyncpg
from fastapi import HTTPException

from app.config import TOKEN_CACHE_TTL_SECONDS

_auth_cache: dict[str, tuple[dict, float]] = {}


def _cache_get(key: str) -> dict | None:
    entry = _auth_cache.get(key)
    if not entry:
        return None
    user, expiry = entry
    if time.time() > expiry:
        _auth_cache.pop(key, None)
        return None
    return user


def _cache_set(key: str, user: dict):
    _auth_cache[key] = (user, time.time() + TOKEN_CACHE_TTL_SECONDS)


async def validate_django_token(token: str, pool: asyncpg.Pool) -> dict:
    """
    Validates a DRF Token in the public schema.
    """
    cache_key = f"token:{token}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    async with pool.acquire() as conn:
        table_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'authtoken_token'
            )
            """
        )
        if not table_exists:
            # If authtoken table doesn't exist, allow pass-through or basic auth
            return {"user_id": 0, "username": "anonymous"}

        row = await conn.fetchrow(
            """
            SELECT u.id AS user_id, u.username, u.email
            FROM "public".authtoken_token t
            JOIN "public".auth_user u ON u.id = t.user_id
            WHERE t.key = $1 AND u.is_active = true
            """,
            token,
        )

    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = dict(row)
    _cache_set(cache_key, user)
    return user
