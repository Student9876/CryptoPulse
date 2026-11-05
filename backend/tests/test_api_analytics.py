"""Unit tests for the Market Analytics REST API endpoints."""

import pytest
from httpx import AsyncClient

from app.main import app
from app.schemas.events import TradeEvent
from app.stream.window_manager import WindowManager


@pytest.mark.asyncio
async def test_get_market_overview(async_client: AsyncClient):
    """Verifies that /api/v1/analytics/overview returns overview summary."""
    # Seed app.state with initialized WindowManager and synthetic trades
    manager = WindowManager(["BTCUSDT", "ETHUSDT"])
    manager.process_trade(TradeEvent(symbol="BTCUSDT", price=65000.0, quantity=1.0, timestamp_ms=1700000000000, is_buyer_maker=False))
    manager.process_trade(TradeEvent(symbol="BTCUSDT", price=67000.0, quantity=1.0, timestamp_ms=1700000010000, is_buyer_maker=False))
    app.state.window_engine = manager

    response = await async_client.get("/api/v1/analytics/overview")
    assert response.status_code == 200

    data = response.json()
    assert "feed_status" in data
    assert "symbols" in data
    assert "BTCUSDT" in data["symbols"]
    assert data["symbols"]["BTCUSDT"]["current_price"] == 67000.0
    assert "BTCUSDT" in data["top_mover"]


@pytest.mark.asyncio
async def test_get_symbol_analytics(async_client: AsyncClient):
    """Verifies that /api/v1/analytics/{symbol} returns metrics and sparklines."""
    manager = WindowManager(["SOLUSDT"])
    manager.process_trade(TradeEvent(symbol="SOLUSDT", price=145.50, quantity=5.0, timestamp_ms=1700000000000, is_buyer_maker=True))
    app.state.window_engine = manager

    response = await async_client.get("/api/v1/analytics/SOLUSDT")
    assert response.status_code == 200

    data = response.json()
    assert "metrics" in data
    assert "sparkline" in data
    assert data["metrics"]["symbol"] == "SOLUSDT"
    assert data["metrics"]["current_price"] == 145.50
    assert len(data["sparkline"]) == 30


@pytest.mark.asyncio
async def test_get_symbol_analytics_not_found(async_client: AsyncClient):
    """Verifies that untracked symbols return 404 Not Found."""
    manager = WindowManager()
    app.state.window_engine = manager

    response = await async_client.get("/api/v1/analytics/DOGEUSDT")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

