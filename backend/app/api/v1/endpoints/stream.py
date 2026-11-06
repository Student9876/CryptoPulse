"""Server-Sent Events (SSE) live streaming endpoints for the Telegram Mini App."""

import asyncio
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/stream", tags=["Streaming"])


async def overview_event_generator(
    request: Request,
    interval_seconds: float = 1.0,
    limit: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """Generates continuous SSE data frames containing live market snapshot updates."""
    count = 0
    try:
        while True:
            if await request.is_disconnected():
                break

            manager = getattr(request.app.state, "window_engine", None)
            if manager:
                feed_status = "connected"
                ws_client = getattr(request.app.state, "ws_client", None)
                if ws_client and not ws_client.is_connected:
                    feed_status = "reconnecting"

                rule_engine = getattr(request.app.state, "rule_engine", None)
                active_count = len(rule_engine.rules) if rule_engine else 0

                overview = manager.get_market_overview(
                    feed_status=feed_status,
                    active_alerts_count=active_count,
                )
                yield f"data: {overview.model_dump_json()}\n\n"
                count += 1
                if limit is not None and count >= limit:
                    break

            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        pass


@router.get("/overview")
async def stream_market_overview(
    request: Request,
    limit: Optional[int] = Query(None, description="Optional maximum event count for testing or one-shot fetches"),
) -> StreamingResponse:
    """Streams real-time 1-second market intelligence snapshots to connected TMA clients."""
    return StreamingResponse(
        overview_event_generator(request, limit=limit),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
