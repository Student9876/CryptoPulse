"""Unit tests for Server-Sent Events (SSE) live streaming endpoints."""

import json
import time
from unittest.mock import MagicMock
import pytest
from httpx import AsyncClient

from app.main import app
from app.schemas.events import TradeEvent
from app.stream.window_manager import WindowManager


@pytest.mark.asyncio
async def test_stream_market_overview(async_client: AsyncClient):
    """Verifies that the SSE endpoint streams live market snapshots in real time."""
    manager = WindowManager(["BTCUSDT"])
    now_ms = int(time.time() * 1000)
    manager.process_trade(
        TradeEvent(
            symbol="BTCUSDT",
            price=85000.0,
            quantity=1.5,
            timestamp_ms=now_ms,
            is_buyer_maker=False,
        )
    )
    app.state.window_engine = manager
    app.state.ws_client = MagicMock(is_connected=True)

    async with async_client.stream("GET", "/api/v1/stream/overview?limit=1") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        first_payload = None
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                raw_json = line[len("data:"):].strip()
                first_payload = json.loads(raw_json)
                break

        assert first_payload is not None
        assert first_payload["feed_status"] == "connected"
        assert "BTCUSDT" in first_payload["symbols"]
        assert first_payload["symbols"]["BTCUSDT"]["current_price"] == 85000.0


@pytest.mark.asyncio
async def test_stream_feed_status_reconnecting(async_client: AsyncClient):
    """Verifies that disconnected WebSocket client propagates 'reconnecting' status in stream."""
    manager = WindowManager(["ETHUSDT"])
    app.state.window_engine = manager
    app.state.ws_client = MagicMock(is_connected=False)

    async with async_client.stream("GET", "/api/v1/stream/overview?limit=1") as response:
        assert response.status_code == 200

        first_payload = None
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                raw_json = line[len("data:"):].strip()
                first_payload = json.loads(raw_json)
                break

        assert first_payload is not None
        assert first_payload["feed_status"] == "reconnecting"
