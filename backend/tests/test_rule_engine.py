"""Unit tests for the Alert Rule Evaluator and Cooldown Engine."""

from datetime import datetime, timezone
import pytest

from app.models.alert_rule import ConditionType, MetricType
from app.schemas.analytics import SymbolMetrics
from app.services.rule_engine import CachedRule, CooldownManager, RuleEngine


def make_test_metrics(
    symbol: str = "BTCUSDT",
    current_price: float = 78000.0,
    price_change_1m_pct: float = 0.5,
    price_change_5m_pct: float = 2.5,
    price_change_15m_pct: float = 4.0,
    vwap_5m: float = 77500.0,
    high_15m: float = 78500.0,
    low_15m: float = 76000.0,
    volume_5m: float = 120.0,
    volume_spike_ratio: float = 3.5,
    taker_buy_ratio_pct: float = 82.0,
    volatility_5m: float = 1.8,
) -> SymbolMetrics:
    """Helper creating a test SymbolMetrics snapshot."""
    return SymbolMetrics(
        symbol=symbol,
        current_price=current_price,
        price_change_1m_pct=price_change_1m_pct,
        price_change_5m_pct=price_change_5m_pct,
        price_change_15m_pct=price_change_15m_pct,
        vwap_5m=vwap_5m,
        high_15m=high_15m,
        low_15m=low_15m,
        range_spread_pct=round(((high_15m - low_15m) / low_15m) * 100, 2),
        volume_5m=volume_5m,
        volume_spike_ratio=volume_spike_ratio,
        taker_buy_ratio_pct=taker_buy_ratio_pct,
        volatility_5m=volatility_5m,
        trades_per_second=10.0,
        trade_count_5m=3000,
        last_trade_time=datetime.now(timezone.utc),
    )


def test_cooldown_manager():
    """Verifies suppression within cooldown window and expiration after."""
    cm = CooldownManager()
    rule_id = 1
    cooldown = 600  # 10 minutes

    # Initially cooled down
    assert cm.is_cooled_down(rule_id, cooldown, now_ts=1000.0) is True

    # Record trigger at t=1000
    cm.record_trigger(rule_id, now_ts=1000.0)

    # At t=1100 (100s later), still in cooldown (600s needed)
    assert cm.is_cooled_down(rule_id, cooldown, now_ts=1100.0) is False

    # At t=1600 (600s later), cooldown has elapsed!
    assert cm.is_cooled_down(rule_id, cooldown, now_ts=1600.0) is True

    # Reset clears cooldown
    cm.record_trigger(rule_id, now_ts=1600.0)
    cm.reset(rule_id)
    assert cm.is_cooled_down(rule_id, cooldown, now_ts=1605.0) is True


def test_price_level_alert():
    """Verifies target price alerts (GREATER_THAN and LESS_THAN)."""
    engine = RuleEngine()
    metrics = make_test_metrics(current_price=80500.0)

    rule = CachedRule(
        id=1,
        user_id=10,
        telegram_id=999,
        symbol="BTCUSDT",
        metric_type=MetricType.PRICE_LEVEL.value,
        condition=ConditionType.GREATER_THAN.value,
        threshold_value=80000.0,
    )
    engine.register_rule(rule)

    alerts = engine.evaluate_metrics(metrics, now_ts=1000.0)
    assert len(alerts) == 1
    assert alerts[0].rule_id == 1
    assert alerts[0].actual_value == 80500.0
    assert "Price >=" in alerts[0].message


def test_price_change_alert_multi_window():
    """Verifies price change evaluation across window durations."""
    engine = RuleEngine()
    metrics = make_test_metrics(
        price_change_1m_pct=0.8,
        price_change_5m_pct=2.5,
        price_change_15m_pct=5.0,
    )

    # 1-minute window rule (threshold 0.5% -> actual is 0.8% -> triggers)
    rule_1m = CachedRule(
        id=1,
        user_id=1,
        telegram_id=123,
        symbol="BTCUSDT",
        metric_type=MetricType.PRICE_CHANGE.value,
        condition=ConditionType.GREATER_THAN.value,
        threshold_value=0.5,
        window_seconds=60,
    )
    # 5-minute window rule (threshold 3.0% -> actual is 2.5% -> does NOT trigger)
    rule_5m = CachedRule(
        id=2,
        user_id=1,
        telegram_id=123,
        symbol="BTCUSDT",
        metric_type=MetricType.PRICE_CHANGE.value,
        condition=ConditionType.GREATER_THAN.value,
        threshold_value=3.0,
        window_seconds=300,
    )
    engine.register_rule(rule_1m)
    engine.register_rule(rule_5m)

    alerts = engine.evaluate_metrics(metrics, now_ts=1000.0)
    assert len(alerts) == 1
    assert alerts[0].rule_id == 1
    assert alerts[0].actual_value == 0.8


def test_volume_spike_alert():
    """Verifies volume spike ratio alerts against baseline."""
    engine = RuleEngine()
    metrics = make_test_metrics(volume_spike_ratio=4.2)

    rule = CachedRule(
        id=3,
        user_id=2,
        telegram_id=456,
        symbol="BTCUSDT",
        metric_type=MetricType.VOLUME_SPIKE.value,
        condition=ConditionType.GREATER_THAN.value,
        threshold_value=3.0,
    )
    engine.register_rule(rule)

    alerts = engine.evaluate_metrics(metrics, now_ts=1000.0)
    assert len(alerts) == 1
    assert alerts[0].actual_value == 4.2
    assert "Volume Spike" in alerts[0].message


def test_order_flow_taker_buy_alert():
    """Verifies buyer frenzy alert based on taker buy ratio."""
    engine = RuleEngine()
    metrics = make_test_metrics(taker_buy_ratio_pct=85.0)

    rule = CachedRule(
        id=4,
        user_id=3,
        telegram_id=789,
        symbol="BTCUSDT",
        metric_type=MetricType.TAKER_BUY_RATIO.value,
        condition=ConditionType.GREATER_THAN.value,
        threshold_value=80.0,
    )
    engine.register_rule(rule)

    alerts = engine.evaluate_metrics(metrics, now_ts=1000.0)
    assert len(alerts) == 1
    assert alerts[0].actual_value == 85.0
    assert "Buyer Frenzy" in alerts[0].message


def test_vwap_crossover_alert():
    """Verifies deviation percentage above/below VWAP."""
    engine = RuleEngine()
    # Price $80,000 vs VWAP $76,000 -> +5.26% deviation
    metrics = make_test_metrics(current_price=80000.0, vwap_5m=76000.0)

    rule = CachedRule(
        id=5,
        user_id=4,
        telegram_id=111,
        symbol="BTCUSDT",
        metric_type=MetricType.VWAP_CROSSOVER.value,
        condition=ConditionType.GREATER_THAN.value,
        threshold_value=4.0,  # 4% deviation threshold
    )
    engine.register_rule(rule)

    alerts = engine.evaluate_metrics(metrics, now_ts=1000.0)
    assert len(alerts) == 1
    assert alerts[0].actual_value == pytest.approx(5.26, rel=1e-2)


def test_cooldown_suppression_and_queue():
    """Verifies that duplicate alerts are silenced during cooldown and queued properly."""
    engine = RuleEngine()
    metrics = make_test_metrics(current_price=81000.0)

    rule = CachedRule(
        id=6,
        user_id=5,
        telegram_id=222,
        symbol="BTCUSDT",
        metric_type=MetricType.PRICE_LEVEL.value,
        condition=ConditionType.GREATER_THAN.value,
        threshold_value=80000.0,
        cooldown_seconds=300,
    )
    engine.register_rule(rule)

    # First evaluation at t=1000 -> triggers
    alerts_1 = engine.evaluate_metrics(metrics, now_ts=1000.0)
    assert len(alerts_1) == 1
    assert engine.alert_queue.qsize() == 1

    # Second evaluation 10 seconds later (t=1010) -> suppressed by cooldown
    alerts_2 = engine.evaluate_metrics(metrics, now_ts=1010.0)
    assert len(alerts_2) == 0
    assert engine.alert_queue.qsize() == 1  # No duplicate put in queue

    # Third evaluation at t=1305 (after 300s cooldown) -> triggers again!
    alerts_3 = engine.evaluate_metrics(metrics, now_ts=1305.0)
    assert len(alerts_3) == 1
    assert engine.alert_queue.qsize() == 2


def test_inactive_and_symbol_filtering():
    """Verifies that inactive rules or rules for other symbols never fire."""
    engine = RuleEngine()
    metrics_btc = make_test_metrics(symbol="BTCUSDT", current_price=90000.0)

    # Inactive rule
    rule_inactive = CachedRule(
        id=7,
        user_id=1,
        telegram_id=123,
        symbol="BTCUSDT",
        metric_type=MetricType.PRICE_LEVEL.value,
        condition=ConditionType.GREATER_THAN.value,
        threshold_value=80000.0,
        is_active=False,
    )
    # ETH rule evaluated against BTC metrics
    rule_eth = CachedRule(
        id=8,
        user_id=1,
        telegram_id=123,
        symbol="ETHUSDT",
        metric_type=MetricType.PRICE_LEVEL.value,
        condition=ConditionType.GREATER_THAN.value,
        threshold_value=2000.0,
    )
    engine.register_rule(rule_inactive)
    engine.register_rule(rule_eth)

    alerts = engine.evaluate_metrics(metrics_btc, now_ts=1000.0)
    assert len(alerts) == 0

