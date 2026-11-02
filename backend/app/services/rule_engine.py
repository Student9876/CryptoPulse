"""Alert Rule Evaluation and Cooldown Engine.

Evaluates incoming real-time SymbolMetrics against active user alert rules.
Enforces sliding cooldown periods to eliminate notification spam, formats
explainable alert messages, and dispatches AlertEvents to an asynchronous queue
for Telegram delivery and database persistence.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.logging import get_logger
from app.models.alert_rule import ConditionType, MetricType
from app.schemas.analytics import SymbolMetrics
from app.schemas.events import AlertEvent

logger = get_logger("cryptopulse.rule_engine")


@dataclass
class CachedRule:
    """Lightweight in-memory representation of an active user alert rule."""
    id: int
    user_id: int
    telegram_id: int
    symbol: str
    metric_type: str
    condition: str
    threshold_value: float
    window_seconds: int = 300
    cooldown_seconds: int = 600
    is_active: bool = True


class CooldownManager:
    """Manages sliding in-memory cooldown timestamps per rule to prevent alert spam."""

    def __init__(self) -> None:
        # Maps rule_id -> timestamp (seconds since epoch) when alert last fired
        self._last_triggered: Dict[int, float] = {}

    def is_cooled_down(self, rule_id: int, cooldown_seconds: int, now_ts: Optional[float] = None) -> bool:
        """Returns True if the cooldown period has elapsed and the rule may fire again."""
        if rule_id not in self._last_triggered:
            return True

        current_time = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
        last_time = self._last_triggered[rule_id]
        return (current_time - last_time) >= cooldown_seconds

    def record_trigger(self, rule_id: int, now_ts: Optional[float] = None) -> None:
        """Records the trigger timestamp for a rule."""
        self._last_triggered[rule_id] = (
            now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
        )

    def reset(self, rule_id: Optional[int] = None) -> None:
        """Clears cooldown for a specific rule, or resets all if rule_id is None."""
        if rule_id is not None:
            self._last_triggered.pop(rule_id, None)
        else:
            self._last_triggered.clear()


class RuleEngine:
    """Evaluates live market metrics against active alert rules with cooldown throttling."""

    def __init__(self) -> None:
        # In-memory cached active rules: rule_id -> CachedRule
        self.rules: Dict[int, CachedRule] = {}
        self.cooldown_manager = CooldownManager()
        # Internal asynchronous queue for alert events to be consumed by dispatchers
        self.alert_queue: asyncio.Queue[AlertEvent] = asyncio.Queue()

    def register_rule(self, rule: CachedRule) -> None:
        """Adds or updates an active rule in the in-memory cache."""
        self.rules[rule.id] = rule
        logger.info(
            "Registered alert rule #%d: %s %s %s %.2f (cooldown: %ds)",
            rule.id,
            rule.symbol,
            rule.metric_type,
            rule.condition,
            rule.threshold_value,
            rule.cooldown_seconds,
        )

    def unregister_rule(self, rule_id: int) -> None:
        """Removes a rule from the in-memory cache and clears its cooldown."""
        self.rules.pop(rule_id, None)
        self.cooldown_manager.reset(rule_id)
        logger.info("Unregistered alert rule #%d", rule_id)

    @staticmethod
    def _extract_metric_value(rule: CachedRule, metrics: SymbolMetrics) -> Optional[float]:
        """Maps rule criteria to the corresponding numeric value on SymbolMetrics."""
        metric_type = rule.metric_type

        if metric_type == MetricType.PRICE_LEVEL.value:
            return metrics.current_price

        elif metric_type == MetricType.PRICE_CHANGE.value:
            if rule.window_seconds <= 60:
                return metrics.price_change_1m_pct
            elif rule.window_seconds >= 900:
                return metrics.price_change_15m_pct
            return metrics.price_change_5m_pct

        elif metric_type == MetricType.VOLUME_SPIKE.value:
            return metrics.volume_spike_ratio

        elif metric_type == MetricType.TAKER_BUY_RATIO.value:
            return metrics.taker_buy_ratio_pct

        elif metric_type == MetricType.VOLATILITY.value:
            return metrics.volatility_5m

        elif metric_type == MetricType.RANGE_BREAKOUT.value:
            # For breakout: GREATER_THAN compares price vs 15m high, LESS_THAN vs 15m low
            if rule.condition == ConditionType.GREATER_THAN.value:
                return metrics.current_price - metrics.high_15m
            return metrics.low_15m - metrics.current_price

        elif metric_type == MetricType.VWAP_CROSSOVER.value:
            # Percentage deviation from 5m VWAP
            if metrics.vwap_5m > 0:
                return round(((metrics.current_price - metrics.vwap_5m) / metrics.vwap_5m) * 100.0, 2)
            return 0.0

        return None

    @staticmethod
    def _is_condition_met(actual_value: float, condition: str, threshold: float) -> bool:
        """Evaluates whether the comparison condition is satisfied."""
        if condition == ConditionType.GREATER_THAN.value:
            return actual_value >= threshold
        elif condition == ConditionType.LESS_THAN.value:
            return actual_value <= threshold
        return False

    @staticmethod
    def format_alert_message(rule: CachedRule, metrics: SymbolMetrics, actual_value: float) -> str:
        """Constructs an explainable, contextual alert message for Telegram."""
        symbol = metrics.symbol
        op_symbol = ">=" if rule.condition == ConditionType.GREATER_THAN.value else "<="
        sign = "+" if actual_value > 0 else ""

        if rule.metric_type == MetricType.PRICE_LEVEL.value:
            detail = f"• Condition: Price {op_symbol} ${rule.threshold_value:,.2f}\n• Actual Price: ${actual_value:,.2f}"
        elif rule.metric_type == MetricType.PRICE_CHANGE.value:
            window_str = f"{rule.window_seconds // 60}m"
            detail = (
                f"• Condition: {window_str} Move {op_symbol} {rule.threshold_value:+.2f}%\n"
                f"• Actual Move: {sign}{actual_value:.2f}%"
            )
        elif rule.metric_type == MetricType.VOLUME_SPIKE.value:
            detail = (
                f"• Condition: 5m Volume Spike {op_symbol} {rule.threshold_value:.1f}x baseline\n"
                f"• Actual Spike: {actual_value:.2f}x"
            )
        elif rule.metric_type == MetricType.TAKER_BUY_RATIO.value:
            flow_desc = "Buyer Frenzy" if actual_value >= 50 else "Seller Dominance"
            detail = (
                f"• Condition: Taker Buy Flow {op_symbol} {rule.threshold_value:.1f}%\n"
                f"• Actual Flow: {actual_value:.1f}% ({flow_desc})"
            )
        elif rule.metric_type == MetricType.RANGE_BREAKOUT.value:
            breakout_type = "Upper (High)" if rule.condition == ConditionType.GREATER_THAN.value else "Lower (Low)"
            detail = (
                f"• Condition: 15m {breakout_type} Breakout\n"
                f"• Current Price: ${metrics.current_price:,.2f} | 15m Range: [${metrics.low_15m:,.2f} - ${metrics.high_15m:,.2f}]"
            )
        elif rule.metric_type == MetricType.VWAP_CROSSOVER.value:
            detail = (
                f"• Condition: VWAP Deviation {op_symbol} {rule.threshold_value:+.2f}%\n"
                f"• Actual Deviation: {sign}{actual_value:.2f}% (VWAP: ${metrics.vwap_5m:,.2f})"
            )
        else:
            detail = f"• Condition: {rule.metric_type} {op_symbol} {rule.threshold_value:.2f}\n• Actual Value: {actual_value:.2f}"

        msg = (
            f"🚨 <b>{symbol} Market Alert Triggered!</b>\n"
            f"────────────────────────\n"
            f"{detail}\n"
            f"────────────────────────\n"
            f"• Current Price: ${metrics.current_price:,.2f}\n"
            f"• 5m VWAP: ${metrics.vwap_5m:,.2f}\n"
            f"• 5m Volume Spike: {metrics.volume_spike_ratio:.1f}x\n"
            f"• Order Flow: {metrics.taker_buy_ratio_pct:.1f}% Taker Buys\n"
            f"⏱ <i>Cooldown: {rule.cooldown_seconds // 60}m</i>"
        )
        return msg

    def evaluate_metrics(
        self, metrics: SymbolMetrics, now_ts: Optional[float] = None
    ) -> List[AlertEvent]:
        """Evaluates active rules for a symbol and returns triggered AlertEvents."""
        current_time = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
        triggered_events: List[AlertEvent] = []

        for rule in self.rules.values():
            if not rule.is_active or rule.symbol.upper() != metrics.symbol.upper():
                continue

            # Check if condition is satisfied
            actual_value = self._extract_metric_value(rule, metrics)
            if actual_value is None:
                continue

            if self._is_condition_met(actual_value, rule.condition, rule.threshold_value):
                # Verify cooldown
                if self.cooldown_manager.is_cooled_down(rule.id, rule.cooldown_seconds, current_time):
                    # Trigger alert!
                    self.cooldown_manager.record_trigger(rule.id, current_time)
                    alert_message = self.format_alert_message(rule, metrics, actual_value)

                    event = AlertEvent(
                        rule_id=rule.id,
                        user_id=rule.user_id,
                        telegram_id=rule.telegram_id,
                        symbol=metrics.symbol,
                        metric_type=rule.metric_type,
                        condition=rule.condition,
                        threshold_value=rule.threshold_value,
                        actual_value=round(actual_value, 4),
                        message=alert_message,
                        triggered_at=datetime.fromtimestamp(current_time, tz=timezone.utc),
                    )
                    triggered_events.append(event)
                    # Non-blocking enqueue for downstream notification workers
                    self.alert_queue.put_nowait(event)

                    logger.warning(
                        "ALERT TRIGGERED | Rule #%d | %s | %s %s %.2f | Actual: %.2f",
                        rule.id,
                        rule.symbol,
                        rule.metric_type,
                        rule.condition,
                        rule.threshold_value,
                        actual_value,
                    )

        return triggered_events

