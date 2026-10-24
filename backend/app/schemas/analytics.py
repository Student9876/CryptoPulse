"""Pydantic schemas for live market metrics and dashboard analytics."""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class SparklinePoint(BaseModel):
    """Single point for rolling sparkline trend charts."""
    timestamp_ms: int = Field(..., description="Unix timestamp in milliseconds")
    price: float = Field(..., description="Bucket closing price")
    volume: float = Field(..., description="Bucket volume")


class SymbolMetrics(BaseModel):
    """Computed rolling metrics for a single tracked asset."""
    symbol: str
    current_price: float

    # Momentum
    price_change_1m_pct: float
    price_change_5m_pct: float
    price_change_15m_pct: float

    # Institutional Benchmarks & Range
    vwap_5m: float
    high_15m: float
    low_15m: float
    range_spread_pct: float

    # Volume & Order Flow
    volume_5m: float
    volume_spike_ratio: float
    taker_buy_ratio_pct: float

    # Volatility & Activity
    volatility_5m: float
    trades_per_second: float

    # State Metadata
    trade_count_5m: int
    last_trade_time: datetime


class SymbolAnalytics(BaseModel):
    """Combined current metrics and rolling sparkline history."""
    metrics: SymbolMetrics
    sparkline: List[SparklinePoint]


class MarketOverview(BaseModel):
    """Full snapshot delivered to the Telegram Mini App on initial connection."""
    server_time: datetime
    feed_status: str  # "connected" | "reconnecting" | "stale"
    top_mover: Optional[str] = None
    top_volume_spike: Optional[str] = None
    symbols: Dict[str, SymbolMetrics]
    active_alerts_count: int

