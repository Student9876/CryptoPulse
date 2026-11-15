"""Evaluates live market metrics against active alert rules."""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.logging import get_logger
from app.models.alert_rule import ConditionType, MetricType
from app.rules.cached_rule import CachedRule
from app.rules.cooldown import CooldownManager
from app.rules.formatter import format_alert_message
from app.schemas.analytics import SymbolMetrics
from app.schemas.events import AlertEvent

logger = get_logger("cryptopulse.rule_engine")


class RuleEngine:
    """In-memory rule evaluator matching streaming metrics against user alert rules."""

    def __init__(self) -> None:
        self.rules: Dict[int, CachedRule] = {}
        self.cooldown_manager = CooldownManager()
        self.alert_queue: asyncio.Queue[AlertEvent] = asyncio.Queue()

    def register_rule(self, rule: CachedRule) -> None:
        self.rules[rule.id] = rule
        logger.info("Registered rule #%d: %s %s %s %.2f", rule.id, rule.symbol, rule.metric_type, rule.condition, rule.threshold_value)

    def unregister_rule(self, rule_id: int) -> None:
        self.rules.pop(rule_id, None)
        self.cooldown_manager.reset(rule_id)
        logger.info("Unregistered rule #%d", rule_id)

    @staticmethod
    def _extract_metric_value(rule: CachedRule, metrics: SymbolMetrics) -> Optional[float]:
        mt = rule.metric_type
        if mt == MetricType.PRICE_LEVEL.value:
            return metrics.current_price
        if mt == MetricType.PRICE_CHANGE.value:
            return metrics.price_change_1m_pct if rule.window_seconds <= 60 else (metrics.price_change_15m_pct if rule.window_seconds >= 900 else metrics.price_change_5m_pct)
        if mt == MetricType.VOLUME_SPIKE.value:
            return metrics.volume_spike_ratio
        if mt == MetricType.TAKER_BUY_RATIO.value:
            return metrics.taker_buy_ratio_pct
        if mt == MetricType.VOLATILITY.value:
            return metrics.volatility_5m
        if mt == MetricType.RANGE_BREAKOUT.value:
            return metrics.current_price - metrics.high_15m if rule.condition == ConditionType.GREATER_THAN.value else metrics.low_15m - metrics.current_price
        if mt == MetricType.VWAP_CROSSOVER.value:
            return round(((metrics.current_price - metrics.vwap_5m) / metrics.vwap_5m) * 100.0, 2) if metrics.vwap_5m > 0 else 0.0
        return None

    def evaluate_metrics(self, metrics: SymbolMetrics, now_ts: Optional[float] = None) -> List[AlertEvent]:
        current_time = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
        triggered: List[AlertEvent] = []

        for rule in self.rules.values():
            if not rule.is_active or rule.symbol.upper() != metrics.symbol.upper():
                continue

            actual = self._extract_metric_value(rule, metrics)
            if actual is None:
                continue

            is_met = actual >= rule.threshold_value if rule.condition == ConditionType.GREATER_THAN.value else actual <= rule.threshold_value
            if self.cooldown_manager.should_trigger(rule.id, is_met, rule.cooldown_seconds, current_time):
                self.cooldown_manager.record_trigger(rule.id, current_time)
                event = AlertEvent(
                    rule_id=rule.id,
                    user_id=rule.user_id,
                    telegram_id=rule.telegram_id,
                    symbol=metrics.symbol,
                    metric_type=rule.metric_type,
                    condition=rule.condition,
                    threshold_value=rule.threshold_value,
                    actual_value=round(actual, 4),
                    message=format_alert_message(rule, metrics, actual),
                    triggered_at=datetime.fromtimestamp(current_time, tz=timezone.utc),
                )
                triggered.append(event)
                self.alert_queue.put_nowait(event)
                logger.warning("ALERT FIRED | Rule #%d | %s | Actual: %.2f", rule.id, rule.symbol, actual)

        return triggered

