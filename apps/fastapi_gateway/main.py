# main.py
"""
LabFinder Real-Time SSE Gateway

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8001

On server startup, this automatically:
1. Connects to the LabFinder PostgreSQL database.
2. Installs / updates the notify_row_change() trigger on watched tables in the public schema.
3. Listens on PostgreSQL's LISTEN/NOTIFY channel.
4. Streams real-time changes to connected browser clients via Server-Sent Events (SSE).
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import (
    FRONTEND_ORIGINS,
    HEARTBEAT_SECONDS,
    MAX_SUBSCRIBERS_PER_ROOM,
    QUEUE_MAXSIZE,
)
from app.db import create_pool, install_notify_triggers
from app.sse import pg_listener, subscribers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("labfinder-realtime")

logger.info("CORS origins loaded: %s", FRONTEND_ORIGINS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting LabFinder Real-Time Gateway...")
    app.state.pool = await create_pool()
    await install_notify_triggers(app.state.pool)

    listener_task = asyncio.create_task(pg_listener())
    app.state.listener_task = listener_task

    yield

    # Shutdown
    logger.info("Shutting down LabFinder Real-Time Gateway...")
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass
    await app.state.pool.close()
    logger.info("Gateway shutdown complete.")


app = FastAPI(
    title="LabFinder Real-Time Gateway",
    description="Real-time event streaming for LabFinder via PostgreSQL LISTEN/NOTIFY and SSE",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS if FRONTEND_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint reporting active connection metrics."""
    total_listeners = sum(len(q) for q in subscribers.values())
    return {
        "status": "ok",
        "active_channels": len(subscribers),
        "total_listeners": total_listeners,
    }


@app.get("/stream/lab/{branch_id}")
async def stream_lab(
    request: Request,
    branch_id: str = Path(..., description="ID of the lab branch to watch (UUID or int string)"),
):
    """
    Real-time stream for users watching a specific lab page.
    Receives instant notifications when:
    - Lab updates profile (name, min_order_value, address, about_us)
    - Lab replies to a customer review or a new review is posted
    - Lab updates test scopes or accreditations
    """
    channel_key = f"lab:{branch_id}"
    channel_queues = subscribers.setdefault(channel_key, set())

    if len(channel_queues) >= MAX_SUBSCRIBERS_PER_ROOM:
        raise HTTPException(
            status_code=503,
            detail="Too many active watchers for this lab, please try again later",
        )

    queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    channel_queues.add(queue)
    logger.info("Client subscribed to '%s' (active viewers: %d)", channel_key, len(channel_queues))

    async def event_generator():
        try:
            # Send initial connected greeting
            yield f"data: {json.dumps({'type': 'connected', 'channel': channel_key})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            channel_queues.discard(queue)
            if not channel_queues:
                subscribers.pop(channel_key, None)
            logger.info("Client disconnected from '%s' (remaining viewers: %d)", channel_key, len(channel_queues))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/stream/order/{order_id}")
async def stream_order(
    request: Request,
    order_id: str = Path(..., description="ID of the order to watch (UUID or int string)"),
):
    """
    Real-time stream for users watching a specific order detail page.
    Receives instant messages and order status changes.
    """
    channel_key = f"order:{order_id}"
    channel_queues = subscribers.setdefault(channel_key, set())

    if len(channel_queues) >= MAX_SUBSCRIBERS_PER_ROOM:
        raise HTTPException(
            status_code=503,
            detail="Too many active watchers for this order",
        )

    queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    channel_queues.add(queue)
    logger.info("Client subscribed to '%s' (active viewers: %d)", channel_key, len(channel_queues))

    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'connected', 'channel': channel_key})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            channel_queues.discard(queue)
            if not channel_queues:
                subscribers.pop(channel_key, None)
            logger.info("Client disconnected from '%s' (remaining viewers: %d)", channel_key, len(channel_queues))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/stream/global")
async def stream_global(request: Request):
    """
    Global activity feed for admin dashboards watching platform-wide updates.
    """
    channel_key = "global"
    channel_queues = subscribers.setdefault(channel_key, set())

    queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    channel_queues.add(queue)
    logger.info("Client subscribed to global stream (total: %d)", len(channel_queues))

    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'connected', 'channel': 'global'})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            channel_queues.discard(queue)
            logger.info("Client disconnected from global stream (remaining: %d)", len(channel_queues))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
