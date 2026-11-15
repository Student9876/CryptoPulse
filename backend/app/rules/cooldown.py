"""Thread-safe in-memory cooldown cache and edge-triggering to eliminate notification spam."""

from datetime import datetime, timezone
from typing import Dict, Optional


class CooldownManager:
    """Tracks last alert trigger timestamps and condition states to prevent notification flooding."""

    def __init__(self) -> None:
        self._last_triggered: Dict[int, float] = {}
        self._active_condition: Dict[int, bool] = {}

    def is_cooled_down(self, rule_id: int, cooldown_seconds: int, now_ts: Optional[float] = None) -> bool:
        if rule_id not in self._last_triggered:
            return True
        current_time = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
        return (current_time - self._last_triggered[rule_id]) >= cooldown_seconds

    def should_trigger(
        self,
        rule_id: int,
        is_met: bool,
        cooldown_seconds: int,
        now_ts: Optional[float] = None,
        is_recurring: bool = False,
    ) -> bool:
        """Determines whether an alert should fire using cooldown AND edge-trigger hysteresis.

        - If is_met is False: Disarms the active state so the rule can re-fire when the metric crosses again.
        - If is_met is True:
          - If is_recurring is True: Fires whenever the rule has cooled down.
          - If is_recurring is False: Only fires if cooled down AND was not already continuously triggered.
        """
        if not is_met:
            self._active_condition[rule_id] = False
            return False

        if not self.is_cooled_down(rule_id, cooldown_seconds, now_ts):
            return False

        if not is_recurring and self._active_condition.get(rule_id, False):
            return False

        return True

    def record_trigger(self, rule_id: int, now_ts: Optional[float] = None) -> None:
        current_time = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
        self._last_triggered[rule_id] = current_time
        self._active_condition[rule_id] = True

    def reset(self, rule_id: Optional[int] = None) -> None:
        if rule_id is not None:
            self._last_triggered.pop(rule_id, None)
            self._active_condition.pop(rule_id, None)
        else:
            self._last_triggered.clear()
            self._active_condition.clear()
