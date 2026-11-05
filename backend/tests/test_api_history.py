"""Unit tests for the Alert History REST API endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.main import app
from app.models.alert_history import AlertHistory
from app.models.user import User


@pytest.fixture
def override_db(db_session: AsyncSession):
    """Overrides the get_db dependency to point to the in-memory test database."""
    async def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_get_history_empty(async_client: AsyncClient, override_db):
    """Verifies that an authenticated user with no alert history gets an empty list."""
    headers = {"X-Dev-Telegram-Id": "999001"}
    res = await async_client.get("/api/v1/history/", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_get_history_records_and_isolation(
    async_client: AsyncClient, override_db, db_session: AsyncSession
):
    """Verifies retrieval, sorting, filtering by symbol, and user isolation."""
    # Create two users
    user_a = User(telegram_id=999002, username="user_a", first_name="Alice")
    user_b = User(telegram_id=999003, username="user_b", first_name="Bob")
    db_session.add_all([user_a, user_b])
    await db_session.commit()
    await db_session.refresh(user_a)
    await db_session.refresh(user_b)

    # Add alert history records
    h1 = AlertHistory(
        user_id=user_a.id,
        symbol="BTCUSDT",
        metric_value=85500.0,
        threshold_value=85000.0,
        message="BTC broke above $85,000",
    )
    h2 = AlertHistory(
        user_id=user_a.id,
        symbol="ETHUSDT",
        metric_value=3250.0,
        threshold_value=3200.0,
        message="ETH broke above $3,200",
    )
    h3 = AlertHistory(
        user_id=user_b.id,
        symbol="SOLUSDT",
        metric_value=195.0,
        threshold_value=190.0,
        message="SOL broke above $190",
    )
    db_session.add_all([h1, h2, h3])
    await db_session.commit()

    # 1. User A lists all history
    headers_a = {"X-Dev-Telegram-Id": "999002"}
    res_a = await async_client.get("/api/v1/history/", headers=headers_a)
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert len(data_a) == 2
    symbols_a = [entry["symbol"] for entry in data_a]
    assert "BTCUSDT" in symbols_a
    assert "ETHUSDT" in symbols_a
    assert "SOLUSDT" not in symbols_a

    # 2. User A filters by symbol BTCUSDT
    res_btc = await async_client.get("/api/v1/history/?symbol=BTCUSDT", headers=headers_a)
    assert res_btc.status_code == 200
    data_btc = res_btc.json()
    assert len(data_btc) == 1
    assert data_btc[0]["symbol"] == "BTCUSDT"
    assert data_btc[0]["metric_value"] == 85500.0

    # 3. User A limit test
    res_limit = await async_client.get("/api/v1/history/?limit=1", headers=headers_a)
    assert res_limit.status_code == 200
    assert len(res_limit.json()) == 1

    # 4. User B lists history (cross-user isolation)
    headers_b = {"X-Dev-Telegram-Id": "999003"}
    res_b = await async_client.get("/api/v1/history/", headers=headers_b)
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert len(data_b) == 1
    assert data_b[0]["symbol"] == "SOLUSDT"
