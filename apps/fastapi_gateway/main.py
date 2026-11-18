# main.py
"""
Entrypoint. Run with:

    uvicorn main:app --port 8001

On every startup this automatically (re)installs NOTIFY triggers for every
table listed in config/watched_tables.json, on every tenant schema that
has that table. To watch a new table: add its name to that JSON file and
restart the server -- no code changes needed.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.auth import validate_django_token
from app.config import (
    FRONTEND_ORIGINS,
    HEARTBEAT_SECONDS,
    MAX_SUBSCRIBERS_PER_TENANT,
    QUEUE_MAXSIZE,
)
from app.db import create_pool, install_notify_triggers
from app.sse import pg_listener, subscribers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("inventory-realtime")

logger.info("CORS origins loaded: %s", FRONTEND_ORIGINS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool()
    await install_notify_triggers(app.state.pool)

    listener_task = asyncio.create_task(pg_listener())
    app.state.listener_task = listener_task

    yield

    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass
    await app.state.pool.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/stream/inventory")
async def stream_inventory(request: Request, token: str = Query(...), tenant: str = Query(...)):
    user = await validate_django_token(token, tenant, request.app.state.pool)
    tenant_id = user["tenant_id"]

    tenant_queues = subscribers.setdefault(tenant_id, set())
    if len(tenant_queues) >= MAX_SUBSCRIBERS_PER_TENANT:
        raise HTTPException(status_code=503, detail="Too many active connections, try again later")

    queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    tenant_queues.add(queue)
    logger.info("Client subscribed (tenant=%s, total=%d)", tenant_id, len(tenant_queues))

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            tenant_queues.discard(queue)
            logger.info("Client unsubscribed (tenant=%s, remaining=%d)", tenant_id, len(tenant_queues))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )




@app.get("/stream/inbox")
async def stream_inbox(request: Request, token: str = Query(...), tenant: str = Query(...)):
    user = await validate_django_token(token, tenant, request.app.state.pool)
    tenant_id = user["tenant_id"]

    tenant_queues = subscribers.setdefault(tenant_id, set())
    if len(tenant_queues) >= MAX_SUBSCRIBERS_PER_TENANT:
        raise HTTPException(status_code=503, detail="Too many active connections, try again later")

    queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    tenant_queues.add(queue)
    logger.info("Client subscribed (tenant=%s, total=%d)", tenant_id, len(tenant_queues))

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            tenant_queues.discard(queue)
            logger.info("Client unsubscribed (tenant=%s, remaining=%d)", tenant_id, len(tenant_queues))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )



@app.get("/health")
async def health():
    total = sum(len(q) for q in subscribers.values())
    return {
        "status": "ok",
        "tenants_connected": len(subscribers),
        "total_listeners": total,
    }


# # main.py
# """
# Production-ready realtime inventory SSE service.

# Assumptions (change the marked sections if these don't match your setup):
#   - Auth: Django REST Framework TokenAuthentication (authtoken_token table)
#   - Multitenancy: schema-based (django-tenants / django-tenant-schemas),
#     single Postgres database, tenant identified by `tenant_id` column /
#     schema_name on your models.

# If you use SimpleJWT instead of DRF Token -> replace validate_django_token()
# with a JWT signature check (see comment near that function).

# If you use separate-database-per-tenant instead of shared-schema ->
# you need one asyncpg pool + one LISTEN connection per tenant DB, not one
# global pool. Say the word and I'll give you that variant.
# """

# import asyncio
# import json
# import logging
# import os
# from contextlib import asynccontextmanager
# from urllib.parse import quote

# import asyncpg
# from dotenv import load_dotenv
# from fastapi import FastAPI, HTTPException, Query, Request
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import StreamingResponse

# load_dotenv()

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
# )
# logger = logging.getLogger("inventory-realtime")

# # ---------------------------------------------------------------------------
# # Config
# # ---------------------------------------------------------------------------

# DB_USER = os.environ["DB_USER"]
# DB_PASSWORD = quote(os.environ["DB_PASSWORD"], safe="")
# DB_HOST = os.environ["DB_HOST"]
# DB_PORT = os.environ.get("DB_PORT", "5432")
# DB_NAME = os.environ["DB_NAME"]

# DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# raw_origins = os.environ.get("FRONTEND_ORIGINS", "http://localhost:3000")
# FRONTEND_ORIGINS = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

# MAX_SUBSCRIBERS_PER_TENANT = int(os.environ.get("MAX_SUBSCRIBERS_PER_TENANT", "2000"))
# QUEUE_MAXSIZE = int(os.environ.get("QUEUE_MAXSIZE", "100"))
# HEARTBEAT_SECONDS = int(os.environ.get("HEARTBEAT_SECONDS", "15"))
# TOKEN_CACHE_TTL_SECONDS = int(os.environ.get("TOKEN_CACHE_TTL_SECONDS", "60"))

# logger.info("CORS origins loaded: %s", FRONTEND_ORIGINS)

# # ---------------------------------------------------------------------------
# # In-memory state
# # ---------------------------------------------------------------------------

# # tenant_id -> set of subscriber queues. Keeping this per-tenant means a
# # NOTIFY for tenant A can never leak into tenant B's stream.
# subscribers: dict[str, set[asyncio.Queue]] = {}

# # tiny in-process token cache so we don't hit Postgres on every single
# # reconnect/heartbeat-driven auth check. (token -> (user_dict, expiry_ts))
# _token_cache: dict[str, tuple[dict, float]] = {}


# def _cache_get(token: str) -> dict | None:
#     entry = _token_cache.get(token)
#     if not entry:
#         return None
#     user, expiry = entry
#     if asyncio.get_event_loop().time() > expiry:
#         _token_cache.pop(token, None)
#         return None
#     return user


# def _cache_set(token: str, user: dict):
#     expiry = asyncio.get_event_loop().time() + TOKEN_CACHE_TTL_SECONDS
#     _token_cache[token] = (user, expiry)


# # ---------------------------------------------------------------------------
# # Broadcast
# # ---------------------------------------------------------------------------


# async def broadcast(payload: dict):
#     tenant_id = payload.get("tenant_id")
#     if tenant_id is None:
#         logger.warning("Dropping NOTIFY payload with no tenant_id: %s", payload)
#         return

#     tenant_queues = subscribers.get(str(tenant_id))
#     if not tenant_queues:
#         return

#     dead = []
#     for q in tenant_queues:
#         try:
#             q.put_nowait(payload)
#         except asyncio.QueueFull:
#             # Drop the oldest buffered message rather than killing the
#             # client outright -- a slow consumer shouldn't lose its
#             # connection over one burst of updates.
#             try:
#                 q.get_nowait()
#                 q.put_nowait(payload)
#             except asyncio.QueueEmpty:
#                 dead.append(q)

#     for q in dead:
#         tenant_queues.discard(q)


# # ---------------------------------------------------------------------------
# # Postgres LISTEN with reconnect + backoff
# # ---------------------------------------------------------------------------


# async def pg_listener():
#     """Runs forever in the background, LISTENing on inventory_channel.
#     Reconnects with exponential backoff if the connection drops, instead
#     of crashing the whole realtime feature."""
#     backoff = 1
#     max_backoff = 60

#     while True:
#         conn = None
#         try:
#             conn = await asyncpg.connect(DATABASE_URL)
#             logger.info("Connected to Postgres for LISTEN")

#             def on_notify(connection, pid, channel, payload):
#                 logger.info("NOTIFY received on '%s': %s", channel, payload)
#                 try:
#                     data = json.loads(payload)
#                 except json.JSONDecodeError:
#                     logger.error("Bad NOTIFY payload (not valid JSON): %s", payload)
#                     return
#                 asyncio.create_task(broadcast(data))

#             await conn.add_listener("inventory_channel", on_notify)
#             logger.info("Listening on 'inventory_channel'")
#             backoff = 1  # reset after a successful, stable connect

#             # Detect a dead connection proactively instead of waiting an
#             # hour to find out LISTEN silently died.
#             while True:
#                 await asyncio.sleep(30)
#                 if conn.is_closed():
#                     raise ConnectionError("asyncpg connection closed unexpectedly")

#         except asyncio.CancelledError:
#             raise
#         except Exception as e:
#             logger.error("pg_listener error, retrying in %ss: %r", backoff, e)
#             await asyncio.sleep(backoff)
#             backoff = min(backoff * 2, max_backoff)
#         finally:
#             if conn is not None and not conn.is_closed():
#                 await conn.close()


# # ---------------------------------------------------------------------------
# # Auth  (DRF TokenAuthentication assumption -- see module docstring)
# # ---------------------------------------------------------------------------


# async def validate_django_token(token: str, pool: asyncpg.Pool) -> dict:
#     cached = _cache_get(token)
#     if cached is not None:
#         return cached

#     async with pool.acquire() as conn:
#         # Adjust table/column names if your User model / tenant field differs.
#         row = await conn.fetchrow(
#             """
#             SELECT u.id AS user_id, u.username, u.tenant_id
#             FROM authtoken_token t
#             JOIN auth_user u ON u.id = t.user_id
#             WHERE t.key = $1 AND u.is_active = true
#             """,
#             token,
#         )

#     if not row:
#         raise HTTPException(status_code=401, detail="Invalid or expired token")

#     user = dict(row)
#     _cache_set(token, user)
#     return user

#     # --- JWT variant (SimpleJWT) instead of the DB query above: ---
#     # import jwt
#     # try:
#     #     decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
#     # except jwt.PyJWTError:
#     #     raise HTTPException(status_code=401, detail="Invalid or expired token")
#     # return {"user_id": decoded["user_id"], "tenant_id": decoded["tenant_id"]}


# # ---------------------------------------------------------------------------
# # Auto-install the NOTIFY trigger on every server start.
# # No manual psql step needed anymore -- just run uvicorn and this runs
# # once at startup. Safe to run every time: CREATE OR REPLACE + DROP-IF-
# # EXISTS make it fully idempotent, won't error or duplicate on restart.
# # ---------------------------------------------------------------------------

# TABLES_TO_WATCH = ["samples_testrequest", "inventory_inventory"]

# TRIGGER_FUNCTION_SQL = """
# CREATE OR REPLACE FUNCTION notify_row_change() RETURNS trigger AS $$
# DECLARE
#     payload json;
# BEGIN
#     IF TG_OP = 'DELETE' THEN
#         payload := json_build_object(
#             'action', 'DELETE',
#             'table', TG_TABLE_NAME,
#             'id', OLD.id,
#             'tenant_id', TG_TABLE_SCHEMA,
#             'data', NULL
#         );
#     ELSIF TG_OP = 'INSERT' THEN
#         payload := json_build_object(
#             'action', 'CREATE',
#             'table', TG_TABLE_NAME,
#             'id', NEW.id,
#             'tenant_id', TG_TABLE_SCHEMA,
#             'data', row_to_json(NEW)
#         );
#     ELSE
#         payload := json_build_object(
#             'action', 'UPDATE',
#             'table', TG_TABLE_NAME,
#             'id', NEW.id,
#             'tenant_id', TG_TABLE_SCHEMA,
#             'data', row_to_json(NEW)
#         );
#     END IF;

#     PERFORM pg_notify('inventory_channel', payload::text);

#     IF TG_OP = 'DELETE' THEN
#         RETURN OLD;
#     END IF;
#     RETURN NEW;
# END;
# $$ LANGUAGE plpgsql;
# """


# async def install_notify_triggers(pool: asyncpg.Pool):
#     """Creates the notify function once, then attaches a trigger to each
#     table in TABLES_TO_WATCH on every tenant schema that has that table.
#     Runs automatically on every app startup -- fully idempotent."""
#     async with pool.acquire() as conn:
#         await conn.execute(TRIGGER_FUNCTION_SQL)
#         logger.info("notify_row_change() function created/updated")

#         schemas = await conn.fetch(
#             """
#             SELECT nspname FROM pg_namespace
#             WHERE nspname NOT IN ('public', 'pg_catalog', 'information_schema')
#               AND nspname NOT LIKE 'pg_%'
#             """
#         )

#         installed = 0
#         for record in schemas:
#             schema_name = record["nspname"]
#             for table_name in TABLES_TO_WATCH:
#                 table_exists = await conn.fetchval(
#                     """
#                     SELECT EXISTS (
#                         SELECT 1 FROM information_schema.tables
#                         WHERE table_schema = $1 AND table_name = $2
#                     )
#                     """,
#                     schema_name,
#                     table_name,
#                 )
#                 if not table_exists:
#                     continue

#                 trigger_name = f"{table_name}_notify_trigger"
#                 await conn.execute(
#                     f'DROP TRIGGER IF EXISTS "{trigger_name}" ON "{schema_name}"."{table_name}"'
#                 )
#                 await conn.execute(
#                     f'''CREATE TRIGGER "{trigger_name}"
#                         AFTER INSERT OR UPDATE OR DELETE ON "{schema_name}"."{table_name}"
#                         FOR EACH ROW EXECUTE FUNCTION notify_row_change()'''
#                 )
#                 installed += 1
#                 logger.info("Trigger installed on %s.%s", schema_name, table_name)

#         logger.info("Trigger install complete: %d trigger(s) active", installed)


# # ---------------------------------------------------------------------------
# # App lifecycle
# # ---------------------------------------------------------------------------


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     app.state.pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
#     await install_notify_triggers(app.state.pool)
#     listener_task = asyncio.create_task(pg_listener())
#     app.state.listener_task = listener_task

#     yield

#     listener_task.cancel()
#     try:
#         await listener_task
#     except asyncio.CancelledError:
#         pass
#     await app.state.pool.close()


# app = FastAPI(lifespan=lifespan)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=FRONTEND_ORIGINS,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# # ---------------------------------------------------------------------------
# # Routes
# # ---------------------------------------------------------------------------


# @app.get("/stream/inventory")
# async def stream_inventory(request: Request, token: str = Query(...)):
#     user = await validate_django_token(token, request.app.state.pool)
#     tenant_id = str(user["tenant_id"])

#     tenant_queues = subscribers.setdefault(tenant_id, set())
#     if len(tenant_queues) >= MAX_SUBSCRIBERS_PER_TENANT:
#         raise HTTPException(status_code=503, detail="Too many active connections, try again later")

#     queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
#     tenant_queues.add(queue)
#     logger.info("Client subscribed (tenant=%s, total=%d)", tenant_id, len(tenant_queues))

#     async def event_generator():
#         try:
#             while True:
#                 if await request.is_disconnected():
#                     break
#                 try:
#                     data = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
#                     yield f"data: {json.dumps(data)}\n\n"
#                 except asyncio.TimeoutError:
#                     yield ": keep-alive\n\n"
#         finally:
#             tenant_queues.discard(queue)
#             logger.info("Client unsubscribed (tenant=%s, remaining=%d)", tenant_id, len(tenant_queues))

#     return StreamingResponse(
#         event_generator(),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache",
#             "X-Accel-Buffering": "no",  # disable nginx buffering for SSE
#         },
#     )


# @app.get("/health")
# async def health():
#     total = sum(len(q) for q in subscribers.values())
#     return {
#         "status": "ok",
#         "tenants_connected": len(subscribers),
#         "total_listeners": total,
#     }