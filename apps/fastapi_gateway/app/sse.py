# app/sse.py
"""
Per-tenant subscriber management, broadcast, and the background
LISTEN task with reconnect/backoff.
"""

import asyncio
import json
import logging

import asyncpg

from app.config import DATABASE_URL, NOTIFY_CHANNEL

logger = logging.getLogger("inventory-realtime")

# tenant_id -> set of subscriber queues. Per-tenant keys mean a NOTIFY for
# tenant A can never leak into tenant B's stream.
subscribers: dict[str, set[asyncio.Queue]] = {}


async def broadcast(payload: dict):
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        logger.warning("Dropping NOTIFY payload with no tenant_id: %s", payload)
        return

    tenant_queues = subscribers.get(str(tenant_id))
    if not tenant_queues:
        return

    dead = []
    for q in tenant_queues:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            # Drop the oldest buffered message rather than disconnecting
            # a slow consumer outright.
            try:
                q.get_nowait()
                q.put_nowait(payload)
            except asyncio.QueueEmpty:
                dead.append(q)

    for q in dead:
        tenant_queues.discard(q)


async def pg_listener():
    """Runs forever in the background, LISTENing on NOTIFY_CHANNEL.
    Reconnects with exponential backoff if the connection drops."""
    backoff = 1
    max_backoff = 60

    while True:
        conn = None
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            logger.info("Postgres connection established for LISTEN")

            def on_notify(connection, pid, channel, payload):
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    logger.error("Bad NOTIFY payload on '%s' (not valid JSON): %s", channel, payload)
                    return
                logger.info(
                    "NOTIFY received on '%s' -> table='%s' action='%s' tenant='%s' id='%s'",
                    channel,
                    data.get("table"),
                    data.get("action"),
                    data.get("tenant_id"),
                    data.get("id"),
                )
                asyncio.create_task(broadcast(data))

            await conn.add_listener(NOTIFY_CHANNEL, on_notify)
            logger.info("LISTEN registered on channel '%s' -- waiting for events", NOTIFY_CHANNEL)
            backoff = 1  # reset after a stable connect

            while True:
                await asyncio.sleep(30)
                if conn.is_closed():
                    raise ConnectionError("Postgres LISTEN connection dropped unexpectedly")

        except asyncio.CancelledError:
            if conn is not None and not conn.is_closed():
                logger.info("Shutting down: closing Postgres LISTEN connection")
            raise
        except Exception as e:
            logger.error(
                "Postgres LISTEN connection lost/failed (%r) -- reconnecting in %ss",
                e, backoff,
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
        finally:
            if conn is not None and not conn.is_closed():
                await conn.close()
                logger.info("Postgres LISTEN connection closed")