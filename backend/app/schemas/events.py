"""Pydantic event contracts for stream ingestion, alerting, and client broadcasting."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class TradeEvent(BaseModel):
    """Normalized real-time market trade tick consumed from Binance WebSocket."""
    symbol: str
    price: float
    quantity: float
    timestamp_ms: int
    is_buyer_maker: bool  # True = seller aggressive (maker was buyer); False = buyer aggressive


class AlertEvent(BaseModel):
    """Internal event generated when an AlertRule condition is satisfied."""
    rule_id: int
    user_id: int
    telegram_id: int
    symbol: str
    metric_type: str
    condition: str
    threshold_value: float
    actual_value: float
    message: str
    triggered_at: datetime
    is_recurring: bool = False


class BroadcastEventType(str, Enum):
    """Event types pushed to connected Telegram Mini App clients."""
    METRICS_SNAPSHOT = "METRICS_SNAPSHOT"
    ALERT_TRIGGERED = "ALERT_TRIGGERED"
    HEARTBEAT = "HEARTBEAT"


class LiveBroadcastEvent(BaseModel):
    """Standardized SSE / WebSocket push envelope for frontend clients."""
    event_type: BroadcastEventType
    timestamp_ms: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp() * 1000))
    data: Dict[str, Any]

