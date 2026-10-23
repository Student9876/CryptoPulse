"""Tests for application health and core configuration."""

import pytest
from httpx import AsyncClient
from app.core.config import Settings


@pytest.mark.asyncio
async def test_health_check_endpoint(async_client: AsyncClient):
    """Verifies that the /healthz endpoint returns 200 OK and expected metadata."""
    response = await async_client.get("/healthz")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "CryptoPulse"
    assert "version" in data


def test_tracked_symbols_normalization():
    """Verifies that symbol strings are properly lowercased and stripped."""
    test_settings = Settings(TRACKED_SYMBOLS=" BTCUSDT , EthUsdt,solusdt ")
    assert test_settings.TRACKED_SYMBOLS == ["btcusdt", "ethusdt", "solusdt"]

