"""Unit tests for the Telegram Bot package: parser, handlers, dispatcher, and rule loading."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.dispatcher import AlertDispatcher
from app.bot.handlers.base import get_or_create_user
from app.bot.parser import parse_alert_command
from app.bot.service import load_active_rules_into_engine
from app.models.alert_history import AlertHistory
from app.models.alert_rule import AlertRule, ConditionType, MetricType
from app.models.user import User
from app.rules import RuleEngine
from app.schemas.events import AlertEvent


def test_parse_alert_command_shorthand():
    res = parse_alert_command("/alert BTC > 85000")
    assert res == ("BTCUSDT", MetricType.PRICE_LEVEL.value, ConditionType.GREATER_THAN.value, 85000.0, 300)

    res_lt = parse_alert_command("/alert ETH < $2,150.50")
    assert res_lt is not None
    assert res_lt[0] == "ETHUSDT"
    assert res_lt[3] == 2150.50


def test_parse_alert_command_momentum_and_windows():
    res_5m = parse_alert_command("/alert BTC chg > 2.5 5m")
    assert res_5m is not None
    assert res_5m[1] == MetricType.PRICE_CHANGE.value
    assert res_5m[3] == 2.5
    assert res_5m[4] == 300

    res_15m = parse_alert_command("/alert SOL chg < -3.0 15m")
    assert res_15m is not None
    assert res_15m[0] == "SOLUSDT"
    assert res_15m[4] == 900


def test_parse_alert_command_volume_and_invalid():
    res_vol = parse_alert_command("/alert ETH vol > 3.5x")
    assert res_vol is not None
    assert res_vol[1] == MetricType.VOLUME_SPIKE.value

    assert parse_alert_command("/alert") is None
    assert parse_alert_command("/alert BTC") is None
    assert parse_alert_command("/alert BTC > abc") is None


@pytest.mark.asyncio
async def test_get_or_create_user(db_session: AsyncSession, monkeypatch):
    from app.bot.handlers import base

    class MockSessionContext:
        async def __aenter__(self):
            return db_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(base, "AsyncSessionLocal", lambda: MockSessionContext())

    user = await get_or_create_user(telegram_id=123456, username="trader", first_name="Bob")
    assert user.id is not None
    assert user.telegram_id == 123456

    user2 = await get_or_create_user(telegram_id=123456, username="trader", first_name="Robert")
    assert user2.id == user.id
    assert user2.first_name == "Robert"


@pytest.mark.asyncio
async def test_alert_dispatcher_worker(db_session: AsyncSession, monkeypatch):
    from app.bot import dispatcher

    class MockSessionContext:
        async def __aenter__(self):
            return db_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(dispatcher, "AsyncSessionLocal", lambda: MockSessionContext())

    user = User(telegram_id=999888, username="testuser", first_name="Test")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    rule = AlertRule(
        user_id=user.id,
        symbol="BTCUSDT",
        metric_type="PRICE_LEVEL",
        condition="GREATER_THAN",
        threshold_value=80000.0,
        is_recurring=False,
        is_active=True,
    )
    db_session.add(rule)
    await db_session.commit()
    await db_session.refresh(rule)

    rule_engine = RuleEngine()
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    worker = AlertDispatcher(rule_engine=rule_engine, bot=mock_bot)
    worker.start()

    event = AlertEvent(
        rule_id=rule.id, user_id=user.id, telegram_id=user.telegram_id, symbol="BTCUSDT",
        metric_type="PRICE_LEVEL", condition="GREATER_THAN", threshold_value=80000.0,
        actual_value=80500.0, message="BTC price alert!", triggered_at=datetime.now(timezone.utc),
        is_recurring=False,
    )
    await rule_engine.alert_queue.put(event)
    await rule_engine.alert_queue.join()
    await worker.stop()

    mock_bot.send_message.assert_awaited_once_with(chat_id=999888, text="BTC price alert!", parse_mode="HTML")
    stmt = select(AlertHistory).where(AlertHistory.user_id == user.id)
    history = (await db_session.execute(stmt)).scalars().all()
    assert len(history) == 1
    assert history[0].symbol == "BTCUSDT"

    # Verify rule was automatically deactivated upon one-time trigger but preserved in DB
    rule_check = (await db_session.execute(select(AlertRule).where(AlertRule.id == rule.id))).scalar_one_or_none()
    assert rule_check is not None
    assert rule_check.is_active is False


@pytest.mark.asyncio
async def test_load_active_rules_into_engine(db_session: AsyncSession, monkeypatch):
    from app.bot import service

    class MockSessionContext:
        async def __aenter__(self):
            return db_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(service, "AsyncSessionLocal", lambda: MockSessionContext())

    user = User(telegram_id=555444, username="loader_user", first_name="Loader")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    rule = AlertRule(
        user_id=user.id, symbol="ETHUSDT", metric_type=MetricType.VOLUME_SPIKE.value,
        condition=ConditionType.GREATER_THAN.value, threshold_value=3.0, is_active=True,
    )
    db_session.add(rule)
    await db_session.commit()

    engine = RuleEngine()
    count = await load_active_rules_into_engine(engine)
    assert count == 1
    assert rule.id in engine.rules

