"""Lightweight in-memory model representing an active user alert rule."""

from dataclasses import dataclass


@dataclass
class CachedRule:
    """Stores rule threshold and routing data in RAM for rapid evaluation."""
    id: int
    user_id: int
    telegram_id: int
    symbol: str
    metric_type: str
    condition: str
    threshold_value: float
    window_seconds: int = 300
    cooldown_seconds: int = 600
    is_recurring: bool = False
    is_active: bool = True

