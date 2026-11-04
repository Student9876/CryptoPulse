"""Single-symbol sliding window buffer and rolling metric calculations."""

import math
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional, Tuple

from app.schemas.analytics import SparklinePoint, SymbolMetrics
from app.schemas.events import TradeEvent

MAX_WINDOW_SEC = 900       # 15 minutes max raw ticks in RAM
BASELINE_BUCKET_SEC = 300  # 5-minute baseline buckets
MAX_BASELINE_BUCKETS = 12  # 12 * 5m = 1 hour history


class SymbolWindow:
    """Manages sliding trade history and computes rolling metrics for one asset."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol.upper()
        self.trades: Deque[TradeEvent] = deque()
        self.baseline_buckets: Deque[float] = deque(maxlen=MAX_BASELINE_BUCKETS)
        self.current_bucket_start_ms: Optional[int] = None
        self.current_bucket_volume: float = 0.0

    def add_trade(self, trade: TradeEvent) -> None:
        self.trades.append(trade)
        self._update_volume_buckets(trade)
        self._prune_expired_trades(trade.timestamp_ms)

    def _update_volume_buckets(self, trade: TradeEvent) -> None:
        trade_time_ms = trade.timestamp_ms
        if self.current_bucket_start_ms is None:
            self.current_bucket_start_ms = trade_time_ms
            self.current_bucket_volume = trade.quantity
            return

        if trade_time_ms - self.current_bucket_start_ms >= BASELINE_BUCKET_SEC * 1000:
            self.baseline_buckets.append(self.current_bucket_volume)
            self.current_bucket_start_ms = trade_time_ms
            self.current_bucket_volume = trade.quantity
        else:
            self.current_bucket_volume += trade.quantity

    def _prune_expired_trades(self, current_time_ms: int) -> None:
        cutoff_ms = current_time_ms - (MAX_WINDOW_SEC * 1000)
        while self.trades and self.trades[0].timestamp_ms < cutoff_ms:
            self.trades.popleft()

    def _get_price_change(self, current_time_ms: int, window_sec: int) -> float:
        if not self.trades:
            return 0.0
        latest_price = self.trades[-1].price
        cutoff_ms = current_time_ms - (window_sec * 1000)
        oldest_price = latest_price
        for trade in self.trades:
            if trade.timestamp_ms >= cutoff_ms:
                oldest_price = trade.price
                break
        return round(((latest_price - oldest_price) / oldest_price) * 100.0, 4) if oldest_price > 0 else 0.0

    def compute_metrics(self, as_of_time_ms: Optional[int] = None) -> Optional[SymbolMetrics]:
        if not self.trades:
            return None

        latest = self.trades[-1]
        now_ms = as_of_time_ms or latest.timestamp_ms
        cutoff_5m = now_ms - (300 * 1000)
        cutoff_15m = now_ms - (900 * 1000)

        sum_pv, vol_5m, taker_vol_5m, count_5m = 0.0, 0.0, 0.0, 0
        high_15m, low_15m = latest.price, latest.price
        prices_5m: List[float] = []

        for t in self.trades:
            if t.timestamp_ms >= cutoff_15m:
                if t.price > high_15m:
                    high_15m = t.price
                if t.price < low_15m:
                    low_15m = t.price

            if t.timestamp_ms >= cutoff_5m:
                count_5m += 1
                vol_5m += t.quantity
                sum_pv += t.price * t.quantity
                prices_5m.append(t.price)
                if not t.is_buyer_maker:
                    taker_vol_5m += t.quantity

        vol_spike = 1.0
        if self.baseline_buckets:
            avg_base = sum(self.baseline_buckets) / len(self.baseline_buckets)
            vol_spike = round(vol_5m / avg_base, 2) if avg_base > 0 else 1.0

        return SymbolMetrics(
            symbol=self.symbol,
            current_price=round(latest.price, 2),
            price_change_1m_pct=self._get_price_change(now_ms, 60),
            price_change_5m_pct=self._get_price_change(now_ms, 300),
            price_change_15m_pct=self._get_price_change(now_ms, 900),
            vwap_5m=round(sum_pv / vol_5m, 2) if vol_5m > 0 else latest.price,
            high_15m=round(high_15m, 2),
            low_15m=round(low_15m, 2),
            range_spread_pct=round(((high_15m - low_15m) / low_15m) * 100.0, 4) if low_15m > 0 else 0.0,
            volume_5m=round(vol_5m, 4),
            volume_spike_ratio=vol_spike,
            taker_buy_ratio_pct=round((taker_vol_5m / vol_5m) * 100.0, 2) if vol_5m > 0 else 50.0,
            volatility_5m=self._calculate_volatility(prices_5m),
            trades_per_second=round(count_5m / 300.0, 2),
            trade_count_5m=count_5m,
            last_trade_time=datetime.fromtimestamp(latest.timestamp_ms / 1000, tz=timezone.utc),
        )

    @staticmethod
    def _calculate_volatility(prices: List[float]) -> float:
        if len(prices) < 2:
            return 0.0
        returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices)) if prices[i - 1] > 0]
        if len(returns) < 2:
            return 0.0
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        return round(math.sqrt(var) * 100.0, 4)

    def generate_sparkline(self, bucket_count: int = 30) -> List[SparklinePoint]:
        if not self.trades:
            return []
        now_ms = self.trades[-1].timestamp_ms
        bucket_duration_ms = 60 * 1000
        start_ms = now_ms - (bucket_count * bucket_duration_ms)

        buckets: Dict[int, Tuple[float, float]] = {}
        for t in self.trades:
            if t.timestamp_ms >= start_ms:
                raw_idx = int((t.timestamp_ms - start_ms) // bucket_duration_ms)
                idx = min(max(raw_idx, 0), bucket_count - 1)
                buckets[idx] = (t.price, buckets[idx][1] + t.quantity if idx in buckets else t.quantity)

        sparkline: List[SparklinePoint] = []
        last_price = self.trades[0].price
        for i in range(bucket_count):
            pt_time = start_ms + (i * bucket_duration_ms)
            if i in buckets:
                last_price = buckets[i][0]
                sparkline.append(SparklinePoint(timestamp_ms=pt_time, price=round(last_price, 2), volume=round(buckets[i][1], 4)))
            else:
                sparkline.append(SparklinePoint(timestamp_ms=pt_time, price=round(last_price, 2), volume=0.0))
        return sparkline

