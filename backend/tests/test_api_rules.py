"""Unit tests for the Alert Rules REST API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.main import app
from app.models.alert_rule import ConditionType, MetricType
from app.models.user import User
from app.rules.evaluator import RuleEngine


@pytest.fixture
def override_db(db_session: AsyncSession):
    """Overrides the get_db dependency to point to the in-memory test database."""
    async def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_create_and_list_rules(async_client: AsyncClient, override_db, db_session: AsyncSession):
    """Verifies rule creation and retrieval for authenticated user."""
    rule_engine = RuleEngine()
    app.state.rule_engine = rule_engine

    headers = {"X-Dev-Telegram-Id": "1234567"}
    payload = {
        "symbol": "BTCUSDT",
        "metric_type": MetricType.PRICE_LEVEL.value,
        "condition": ConditionType.GREATER_THAN.value,
        "threshold_value": 85000.0,
        "window_seconds": 300,
        "cooldown_seconds": 600,
    }

    # 1. Create Rule
    res_post = await async_client.post("/api/v1/rules/", json=payload, headers=headers)
    assert res_post.status_code == 201
    created_rule = res_post.json()
    rule_id = created_rule["id"]
    assert created_rule["symbol"] == "BTCUSDT"
    assert created_rule["threshold_value"] == 85000.0

    # Verify registered in in-memory RuleEngine cache
    assert rule_id in rule_engine.rules
    assert rule_engine.rules[rule_id].symbol == "BTCUSDT"

    # 2. List Rules
    res_get = await async_client.get("/api/v1/rules/", headers=headers)
    assert res_get.status_code == 200
    rules_list = res_get.json()
    assert len(rules_list) == 1
    assert rules_list[0]["id"] == rule_id


@pytest.mark.asyncio
async def test_delete_rule_and_isolation(async_client: AsyncClient, override_db, db_session: AsyncSession):
    """Verifies rule deletion and cross-user isolation."""
    rule_engine = RuleEngine()
    app.state.rule_engine = rule_engine

    user_a_headers = {"X-Dev-Telegram-Id": "11111"}
    user_b_headers = {"X-Dev-Telegram-Id": "22222"}

    payload = {
        "symbol": "ETHUSDT",
        "metric_type": MetricType.VOLUME_SPIKE.value,
        "condition": ConditionType.GREATER_THAN.value,
        "threshold_value": 3.0,
    }

    # User A creates a rule
    res_post = await async_client.post("/api/v1/rules/", json=payload, headers=user_a_headers)
    rule_id = res_post.json()["id"]

    # User B tries to delete User A's rule -> 404 Not Found
    res_del_b = await async_client.delete(f"/api/v1/rules/{rule_id}", headers=user_b_headers)
    assert res_del_b.status_code == 404

    # User A deletes their own rule -> 200 OK
    res_del_a = await async_client.delete(f"/api/v1/rules/{rule_id}", headers=user_a_headers)
    assert res_del_a.status_code == 200
    assert res_del_a.json()["status"] == "deleted"

    # Rule must be removed from in-memory engine
    assert rule_id not in rule_engine.rules
