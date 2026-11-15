"""Unit tests for the Alert Rules package: evaluator, cooldowns, and formatters."""

from datetime import datetime, timezone
import pytest

from app.models.alert_rule import ConditionType, MetricType
from app.rules import CachedRule, CooldownManager, RuleEngine
from app.schemas.analytics import SymbolMetrics


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
    cm = CooldownManager()
    assert cm.is_cooled_down(1, 600, now_ts=1000.0) is True
    cm.record_trigger(1, now_ts=1000.0)
    assert cm.is_cooled_down(1, 600, now_ts=1100.0) is False
    assert cm.is_cooled_down(1, 600, now_ts=1600.0) is True


def test_price_level_alert():
    engine = RuleEngine()
    metrics = make_test_metrics(current_price=80500.0)
    engine.register_rule(CachedRule(
        id=1, user_id=10, telegram_id=999, symbol="BTCUSDT",
        metric_type=MetricType.PRICE_LEVEL.value, condition=ConditionType.GREATER_THAN.value,
        threshold_value=80000.0,
    ))
    alerts = engine.evaluate_metrics(metrics, now_ts=1000.0)
    assert len(alerts) == 1
    assert alerts[0].rule_id == 1
    assert alerts[0].actual_value == 80500.0


def test_price_change_alert_multi_window():
    engine = RuleEngine()
    metrics = make_test_metrics(price_change_1m_pct=0.8, price_change_5m_pct=2.5)
    engine.register_rule(CachedRule(
        id=1, user_id=1, telegram_id=123, symbol="BTCUSDT",
        metric_type=MetricType.PRICE_CHANGE.value, condition=ConditionType.GREATER_THAN.value,
        threshold_value=0.5, window_seconds=60,
    ))
    engine.register_rule(CachedRule(
        id=2, user_id=1, telegram_id=123, symbol="BTCUSDT",
        metric_type=MetricType.PRICE_CHANGE.value, condition=ConditionType.GREATER_THAN.value,
        threshold_value=3.0, window_seconds=300,
    ))
    alerts = engine.evaluate_metrics(metrics, now_ts=1000.0)
    assert len(alerts) == 1
    assert alerts[0].rule_id == 1


def test_volume_spike_and_flow_alerts():
    engine = RuleEngine()
    metrics = make_test_metrics(volume_spike_ratio=4.2, taker_buy_ratio_pct=85.0)
    engine.register_rule(CachedRule(
        id=3, user_id=2, telegram_id=456, symbol="BTCUSDT",
        metric_type=MetricType.VOLUME_SPIKE.value, condition=ConditionType.GREATER_THAN.value,
        threshold_value=3.0,
    ))
    engine.register_rule(CachedRule(
        id=4, user_id=3, telegram_id=789, symbol="BTCUSDT",
        metric_type=MetricType.TAKER_BUY_RATIO.value, condition=ConditionType.GREATER_THAN.value,
        threshold_value=80.0,
    ))
    alerts = engine.evaluate_metrics(metrics, now_ts=1000.0)
    assert len(alerts) == 2


def test_vwap_crossover_alert():
    engine = RuleEngine()
    metrics = make_test_metrics(current_price=80000.0, vwap_5m=76000.0)
    engine.register_rule(CachedRule(
        id=5, user_id=4, telegram_id=111, symbol="BTCUSDT",
        metric_type=MetricType.VWAP_CROSSOVER.value, condition=ConditionType.GREATER_THAN.value,
        threshold_value=4.0,
    ))
    alerts = engine.evaluate_metrics(metrics, now_ts=1000.0)
    assert len(alerts) == 1
    assert alerts[0].actual_value == pytest.approx(5.26, rel=1e-2)


def test_cooldown_suppression():
    engine = RuleEngine()
    metrics_above = make_test_metrics(current_price=81000.0)
    metrics_below = make_test_metrics(current_price=79000.0)
    engine.register_rule(CachedRule(
        id=6, user_id=5, telegram_id=222, symbol="BTCUSDT",
        metric_type=MetricType.PRICE_LEVEL.value, condition=ConditionType.GREATER_THAN.value,
        threshold_value=80000.0, cooldown_seconds=300,
    ))
    # 1. First trigger
    assert len(engine.evaluate_metrics(metrics_above, now_ts=1000.0)) == 1

    # 2. Within cooldown period -> suppressed
    assert len(engine.evaluate_metrics(metrics_above, now_ts=1010.0)) == 0

    # 3. After cooldown, but condition never reset (stayed > 80k) -> edge-triggering prevents flood
    assert len(engine.evaluate_metrics(metrics_above, now_ts=1305.0)) == 0

    # 4. Market drops below threshold -> re-arms the trigger
    assert len(engine.evaluate_metrics(metrics_below, now_ts=1350.0)) == 0

    # 5. Market crosses back up after re-arming and cooled down -> triggers cleanly
    assert len(engine.evaluate_metrics(metrics_above, now_ts=1400.0)) == 1

