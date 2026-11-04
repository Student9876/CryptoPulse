"""Natural text parser converting Telegram user chat messages into alert rules."""

from typing import Optional, Tuple
from app.models.alert_rule import ConditionType, MetricType


def parse_alert_command(text: str) -> Optional[Tuple[str, str, str, float, int]]:
    """Parses natural text commands into structured alert parameters."""
    parts = text.strip().split()
    if len(parts) < 4:
        return None

    raw_sym = parts[1].upper()
    symbol = raw_sym if raw_sym.endswith("USDT") else f"{raw_sym}USDT"
    window_sec = 300

    # Pattern A: /alert <SYM> > <PRICE>
    if parts[2] in (">", ">=", "<", "<=") and len(parts) >= 4:
        try:
            val = float(parts[3].replace("$", "").replace(",", ""))
            cond = ConditionType.GREATER_THAN.value if ">" in parts[2] else ConditionType.LESS_THAN.value
            return (symbol, MetricType.PRICE_LEVEL.value, cond, val, window_sec)
        except ValueError:
            return None

    # Pattern B: /alert <SYM> <METRIC> <OP> <THRESHOLD> [WINDOW]
    metric_kw = parts[2].lower()
    op = parts[3]
    cond = ConditionType.GREATER_THAN.value if ">" in op else ConditionType.LESS_THAN.value

    if len(parts) >= 6:
        win_str = parts[5].lower()
        window_sec = 60 if "1m" in win_str else (900 if "15m" in win_str else 300)

    try:
        if metric_kw in ("price", "level", "target"):
            val = float(parts[4].replace("$", "").replace(",", ""))
            return (symbol, MetricType.PRICE_LEVEL.value, cond, val, window_sec)
        elif metric_kw in ("chg", "change", "momentum"):
            return (symbol, MetricType.PRICE_CHANGE.value, cond, float(parts[4].replace("%", "")), window_sec)
        elif metric_kw in ("vol", "volume", "spike"):
            return (symbol, MetricType.VOLUME_SPIKE.value, cond, float(parts[4].replace("x", "")), window_sec)
        elif metric_kw in ("flow", "buyer", "taker"):
            return (symbol, MetricType.TAKER_BUY_RATIO.value, cond, float(parts[4].replace("%", "")), window_sec)
        elif metric_kw in ("vwap", "dev"):
            return (symbol, MetricType.VWAP_CROSSOVER.value, cond, float(parts[4].replace("%", "")), window_sec)
        elif metric_kw in ("breakout", "range"):
            return (symbol, MetricType.RANGE_BREAKOUT.value, cond, 0.0, 900)
    except (ValueError, IndexError):
        return None

    return None

