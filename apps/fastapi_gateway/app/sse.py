# app/sse.py
"""
Subscriber management, broadcast routing, and the background
PostgreSQL LISTEN task with reconnect and backoff.
"""

import asyncio
import json
import logging

import asyncpg

from app.config import DATABASE_URL, NOTIFY_CHANNEL

logger = logging.getLogger("labfinder-realtime")

# channel_key (e.g. "lab:1", "order:42", "global") -> set of subscriber queues
subscribers: dict[str, set[asyncio.Queue]] = {}


async def broadcast(payload: dict):
    """
    Broadcasts payload to relevant subscriber channels.
    Target channels are resolved from branch_id, order_id, or global.
    """
    target_channels = set()

    branch_id = payload.get("branch_id")
    if branch_id:
        target_channels.add(f"lab:{branch_id}")

    # Inspect data payload for other entity keys if available
    data = payload.get("data")
    if isinstance(data, dict):
        order_id = data.get("order_id") or data.get("lims_order_id")
        if order_id:
            target_channels.add(f"order:{order_id}")

    # Always broadcast to global channel for admin monitoring / activity feeds
    target_channels.add("global")

    for ch in target_channels:
        channel_queues = subscribers.get(ch)
        if not channel_queues:
            continue

        dead = []
        for q in channel_queues:
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
            channel_queues.discard(q)


async def pg_listener():
    """Runs forever in the background, LISTENing on NOTIFY_CHANNEL.
    Reconnects with exponential backoff if the connection drops."""
    backoff = 1
    max_backoff = 60

    while True:
        conn = None
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            logger.info("Postgres connection established for LISTEN on '%s'", NOTIFY_CHANNEL)

            def on_notify(connection, pid, channel, payload_str):
                try:
                    data = json.loads(payload_str)
                except json.JSONDecodeError:
                    logger.error("Bad NOTIFY payload on '%s' (not valid JSON): %s", channel, payload_str)
                    return
                logger.info(
                    "NOTIFY on '%s' -> table='%s' action='%s' branch='%s' id='%s'",
                    channel,
                    data.get("table"),
                    data.get("action"),
                    data.get("branch_id"),
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
