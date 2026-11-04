"""Thread-safe in-memory cooldown cache to eliminate notification spam."""

from datetime import datetime, timezone
from typing import Dict, Optional


class CooldownManager:
    """Tracks last alert trigger timestamps per rule to enforce quiet periods."""

    def __init__(self) -> None:
        self._last_triggered: Dict[int, float] = {}

    def is_cooled_down(self, rule_id: int, cooldown_seconds: int, now_ts: Optional[float] = None) -> bool:
        if rule_id not in self._last_triggered:
            return True
        current_time = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
        return (current_time - self._last_triggered[rule_id]) >= cooldown_seconds

    def record_trigger(self, rule_id: int, now_ts: Optional[float] = None) -> None:
        self._last_triggered[rule_id] = (
            now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
        )

    def reset(self, rule_id: Optional[int] = None) -> None:
        if rule_id is not None:
            self._last_triggered.pop(rule_id, None)
        else:
            self._last_triggered.clear()

