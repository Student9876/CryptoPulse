"""Constructs explainable, formatted HTML alert notifications for Telegram."""

from app.models.alert_rule import ConditionType, MetricType
from app.rules.cached_rule import CachedRule
from app.schemas.analytics import SymbolMetrics


def format_alert_message(rule: CachedRule, metrics: SymbolMetrics, actual_value: float) -> str:
    """Builds a human-readable Telegram alert with market context."""
    op = ">=" if rule.condition == ConditionType.GREATER_THAN.value else "<="
    sign = "+" if actual_value > 0 else ""

    if rule.metric_type == MetricType.PRICE_LEVEL.value:
        detail = f"• Condition: Price {op} ${rule.threshold_value:,.2f}\n• Actual Price: ${actual_value:,.2f}"
    elif rule.metric_type == MetricType.PRICE_CHANGE.value:
        win = f"{rule.window_seconds // 60}m"
        detail = f"• Condition: {win} Move {op} {rule.threshold_value:+.2f}%\n• Actual Move: {sign}{actual_value:.2f}%"
    elif rule.metric_type == MetricType.VOLUME_SPIKE.value:
        detail = f"• Condition: 5m Volume Spike {op} {rule.threshold_value:.1f}x\n• Actual Spike: {actual_value:.2f}x"
    elif rule.metric_type == MetricType.TAKER_BUY_RATIO.value:
        flow = "Buyer Frenzy" if actual_value >= 50 else "Seller Dominance"
        detail = f"• Condition: Taker Buy Flow {op} {rule.threshold_value:.1f}%\n• Actual Flow: {actual_value:.1f}% ({flow})"
    elif rule.metric_type == MetricType.RANGE_BREAKOUT.value:
        side = "Upper (High)" if rule.condition == ConditionType.GREATER_THAN.value else "Lower (Low)"
        detail = f"• Condition: 15m {side} Breakout\n• Price: ${metrics.current_price:,.2f} | Range: [${metrics.low_15m:,.2f} - ${metrics.high_15m:,.2f}]"
    elif rule.metric_type == MetricType.VWAP_CROSSOVER.value:
        detail = f"• Condition: VWAP Deviation {op} {rule.threshold_value:+.2f}%\n• Actual Deviation: {sign}{actual_value:.2f}%"
    else:
        detail = f"• Condition: {rule.metric_type} {op} {rule.threshold_value:.2f}\n• Actual: {actual_value:.2f}"

    return (
        f"🚨 <b>{metrics.symbol} Market Alert Triggered!</b>\n"
        f"────────────────────────\n"
        f"{detail}\n"
        f"────────────────────────\n"
        f"• Current Price: ${metrics.current_price:,.2f}\n"
        f"• 5m VWAP: ${metrics.vwap_5m:,.2f}\n"
        f"• 5m Volume Spike: {metrics.volume_spike_ratio:.1f}x\n"
        f"• Order Flow: {metrics.taker_buy_ratio_pct:.1f}% Taker Buys\n"
        f"⏱ <i>Cooldown: {rule.cooldown_seconds // 60}m</i>"
    )

