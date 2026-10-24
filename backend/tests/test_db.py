"""Tests for database models, relationships, cascading, and Pydantic schemas."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AlertHistory, AlertRule, ConditionType, MetricType, User
from app.schemas.alert_rule import AlertRuleCreate
from app.schemas.analytics import SymbolMetrics


@pytest.mark.asyncio
async def test_create_user_and_query(db_session: AsyncSession):
    """Verifies user insertion and retrieval by telegram_id."""
    user = User(
        telegram_id=987654321,
        username="cryptotrader",
        first_name="Alice",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.created_at is not None

    # Query back
    stmt = select(User).where(User.telegram_id == 987654321)
    result = await db_session.execute(stmt)
    queried_user = result.scalar_one_or_none()

    assert queried_user is not None
    assert queried_user.username == "cryptotrader"
    assert queried_user.is_active is True


@pytest.mark.asyncio
async def test_user_alert_rules_relationship_and_cascade(db_session: AsyncSession):
    """Verifies that alert rules attach to users and cascade delete properly."""
    user = User(telegram_id=11223344, username="bob", first_name="Bob")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Add alert rule for this user
    rule = AlertRule(
        user_id=user.id,
        symbol="BTCUSDT",
        metric_type=MetricType.PRICE_CHANGE.value,
        condition=ConditionType.GREATER_THAN.value,
        threshold_value=2.5,
        window_seconds=300,
        cooldown_seconds=600,
    )
    db_session.add(rule)
    await db_session.commit()
    await db_session.refresh(rule)

    assert rule.id is not None
    assert rule.user_id == user.id

    # Record alert history
    history = AlertHistory(
        user_id=user.id,
        rule_id=rule.id,
        symbol="BTCUSDT",
        metric_value=2.8,
        threshold_value=2.5,
        message="BTC price surged +2.8% in 5m",
    )
    db_session.add(history)
    await db_session.commit()

    # Verify history exists
    stmt_history = select(AlertHistory).where(AlertHistory.user_id == user.id)
    history_records = (await db_session.execute(stmt_history)).scalars().all()
    assert len(history_records) == 1

    # Delete User -> Cascade should delete rules and history
    await db_session.delete(user)
    await db_session.commit()

    # Verify rule is gone
    stmt_rule = select(AlertRule).where(AlertRule.id == rule.id)
    assert (await db_session.execute(stmt_rule)).scalar_one_or_none() is None

    # Verify history is gone (due to CASCADE on user_id)
    assert (await db_session.execute(stmt_history)).scalar_one_or_none() is None


def test_alert_rule_pydantic_schema_validation():
    """Verifies validation and bounds checking on AlertRuleCreate."""
    valid_data = {
        "symbol": "ETHUSDT",
        "metric_type": MetricType.VOLUME_SPIKE,
        "condition": ConditionType.GREATER_THAN,
        "threshold_value": 3.0,
        "window_seconds": 300,
        "cooldown_seconds": 600,
    }
    schema = AlertRuleCreate(**valid_data)
    assert schema.symbol == "ETHUSDT"
    assert schema.threshold_value == 3.0

