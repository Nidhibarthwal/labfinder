# app/auth.py
"""
DRF TokenAuthentication validator, using the shared asyncpg pool.
Includes a short-lived in-memory cache so repeated checks (heartbeats,
reconnects) don't hit Postgres every time.

If you use SimpleJWT instead, replace validate_django_token() with the
JWT variant at the bottom of this file (swap the import and the call
site in sse.py).
"""

import time

import asyncpg
from fastapi import HTTPException

from app.config import TOKEN_CACHE_TTL_SECONDS

# token -> (user_dict, expiry_epoch_seconds)
_token_cache: dict[str, tuple[dict, float]] = {}


def _cache_get(token: str) -> dict | None:
    entry = _token_cache.get(token)
    if not entry:
        return None
    user, expiry = entry
    if time.time() > expiry:
        _token_cache.pop(token, None)
        return None
    return user


def _cache_set(token: str, user: dict):
    _token_cache[token] = (user, time.time() + TOKEN_CACHE_TTL_SECONDS)


async def validate_django_token(token: str, tenant_id: str, pool: asyncpg.Pool) -> dict:
    """
    Validates the token INSIDE the caller-specified tenant schema only.

    Why tenant_id is required (not inferred): authtoken_token / auth_user
    live inside each tenant schema here, and the same token key can exist
    in more than one tenant's table (seen in practice -- a token
    belonging to 'cipet' also matched inside 'niftembackend'). Scanning
    all schemas and returning the first match is a data-leak risk: the
    wrong tenant's data could be streamed to the client. The frontend
    already knows which tenant the logged-in user belongs to (subdomain,
    session, etc.) -- it must send that alongside the token so we check
    the RIGHT schema, not just any schema that happens to match.
    """
    cache_key = f"{tenant_id}:{token}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    async with pool.acquire() as conn:
        table_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = $1 AND table_name = 'authtoken_token'
            )
            """,
            tenant_id,
        )
        if not table_exists:
            raise HTTPException(status_code=401, detail="Unknown tenant")

        row = await conn.fetchrow(
            f'''
            SELECT u.id AS user_id, u.username
            FROM "{tenant_id}".authtoken_token t
            JOIN "{tenant_id}".auth_user u ON u.id = t.user_id
            WHERE t.key = $1 AND u.is_active = true
            ''',
            token,
        )

    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired token for this tenant")

    user = dict(row)
    user["tenant_id"] = tenant_id
    _cache_set(cache_key, user)
    return user


# --- JWT variant (SimpleJWT), use instead of the DB-backed function above ---
# import jwt
# from django.conf import settings  # or hardcode SECRET_KEY via env var
#
# async def validate_django_token(token: str, pool: asyncpg.Pool = None) -> dict:
#     try:
#         decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
#     except jwt.PyJWTError:
#         raise HTTPException(status_code=401, detail="Invalid or expired token")
#     return {"user_id": decoded["user_id"], "tenant_id": decoded["tenant_id"]}