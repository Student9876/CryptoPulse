"""In-Memory Sliding Window Metrics Engine.

Computes rolling market intelligence statistics from streaming TradeEvents:
- Multi-horizon percentage price changes (1m, 5m, 15m)
- Volume-Weighted Average Price (VWAP)
- Order flow / Taker Buy Volume Ratio
- Volume spikes against rolling historical baselines
- 15-minute price range spread and local highs/lows
- Realized return volatility
- Sparkline downsampling for Telegram Mini App charts

Data structures:
- Uses collections.deque for O(1) amortized appends and left-pops
- Trades older than the maximum rolling window (15 minutes) are pruned dynamically
- Historical 5-minute volume buckets (up to 1 hour) are maintained for baseline spike ratios
"""

import math
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional, Tuple

from app.core.logging import get_logger
from app.schemas.analytics import MarketOverview, SparklinePoint, SymbolAnalytics, SymbolMetrics
from app.schemas.events import TradeEvent

logger = get_logger("cryptopulse.window_engine")

# Window constants in seconds
WINDOW_1M_SEC = 60
WINDOW_5M_SEC = 300
WINDOW_15M_SEC = 900
MAX_WINDOW_SEC = 900  # 15 minutes of raw trade ticks retained in deque
BASELINE_BUCKET_SEC = 300  # 5-minute baseline buckets
MAX_BASELINE_BUCKETS = 12  # 12 * 5m = 60 minutes of baseline history


class SymbolWindow:
    """Manages sliding trade history and computes real-time rolling metrics for a single symbol."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol.upper()
        # Deque of raw normalized trades: time-ordered, auto-pruned to MAX_WINDOW_SEC
        self.trades: Deque[TradeEvent] = deque()

        # Rolling 5-minute historical volume buckets for baseline calculation (up to 1 hour)
        self.baseline_buckets: Deque[float] = deque(maxlen=MAX_BASELINE_BUCKETS)
        self.current_bucket_start_ms: Optional[int] = None
        self.current_bucket_volume: float = 0.0

    def add_trade(self, trade: TradeEvent) -> None:
        """Appends a new normalized trade and prunes expired historical ticks."""
        self.trades.append(trade)

        # Update historical 5-minute volume buckets for baseline tracking
        self._update_volume_buckets(trade)

        # Prune trades older than MAX_WINDOW_SEC (15 minutes)
        self._prune_expired_trades(trade.timestamp_ms)

    def _update_volume_buckets(self, trade: TradeEvent) -> None:
        """Tracks completed 5-minute volume intervals to establish a baseline."""
        trade_time_ms = trade.timestamp_ms

        if self.current_bucket_start_ms is None:
            self.current_bucket_start_ms = trade_time_ms
            self.current_bucket_volume = trade.quantity
            return

        bucket_duration_ms = BASELINE_BUCKET_SEC * 1000
        # If trade time has crossed into a new 5-minute bucket:
        if trade_time_ms - self.current_bucket_start_ms >= bucket_duration_ms:
            self.baseline_buckets.append(self.current_bucket_volume)
            self.current_bucket_start_ms = trade_time_ms
            self.current_bucket_volume = trade.quantity
        else:
            self.current_bucket_volume += trade.quantity

    def _prune_expired_trades(self, current_time_ms: int) -> None:
        """Removes trades older than MAX_WINDOW_SEC from the front of the deque."""
        cutoff_ms = current_time_ms - (MAX_WINDOW_SEC * 1000)
        while self.trades and self.trades[0].timestamp_ms < cutoff_ms:
            self.trades.popleft()

    def _get_price_change(self, current_time_ms: int, window_sec: int) -> float:
        """Calculates percentage price change over a given time window.

        Formula: ((P_latest - P_oldest) / P_oldest) * 100
        """
        if not self.trades:
            return 0.0

        latest_price = self.trades[-1].price
        cutoff_ms = current_time_ms - (window_sec * 1000)

        # Find the oldest trade within the specified window
        # Since deque is ordered chronologically, search from oldest to newest
        oldest_price = latest_price
        for trade in self.trades:
            if trade.timestamp_ms >= cutoff_ms:
                oldest_price = trade.price
                break

        if oldest_price <= 0:
            return 0.0

        return round(((latest_price - oldest_price) / oldest_price) * 100.0, 4)

    def compute_metrics(self, as_of_time_ms: Optional[int] = None) -> Optional[SymbolMetrics]:
        """Calculates and returns a comprehensive SymbolMetrics snapshot."""
        if not self.trades:
            return None

        latest_trade = self.trades[-1]
        now_ms = as_of_time_ms or latest_trade.timestamp_ms

        current_price = latest_trade.price
        cutoff_5m_ms = now_ms - (WINDOW_5M_SEC * 1000)
        cutoff_15m_ms = now_ms - (WINDOW_15M_SEC * 1000)

        # Iteration variables for 5-minute window
        sum_pv_5m = 0.0
        volume_5m = 0.0
        taker_buy_volume_5m = 0.0
        trade_count_5m = 0

        # Iteration variables for 15-minute window
        high_15m = current_price
        low_15m = current_price

        # List of prices in 5m window for volatility standard deviation
        prices_5m: List[float] = []

        for trade in self.trades:
            # 15-minute range calculations
            if trade.timestamp_ms >= cutoff_15m_ms:
                if trade.price > high_15m:
                    high_15m = trade.price
                if trade.price < low_15m:
                    low_15m = trade.price

            # 5-minute metrics
            if trade.timestamp_ms >= cutoff_5m_ms:
                trade_count_5m += 1
                volume_5m += trade.quantity
                sum_pv_5m += trade.price * trade.quantity
                prices_5m.append(trade.price)

                # is_buyer_maker is False when buyer was the aggressive taker
                if not trade.is_buyer_maker:
                    taker_buy_volume_5m += trade.quantity

        # 1. Price Momentum across horizons
        price_change_1m = self._get_price_change(now_ms, WINDOW_1M_SEC)
        price_change_5m = self._get_price_change(now_ms, WINDOW_5M_SEC)
        price_change_15m = self._get_price_change(now_ms, WINDOW_15M_SEC)

        # 2. Institutional VWAP (5m)
        vwap_5m = round(sum_pv_5m / volume_5m, 2) if volume_5m > 0 else current_price

        # 3. High/Low Spread % (15m)
        range_spread_pct = round(((high_15m - low_15m) / low_15m) * 100.0, 4) if low_15m > 0 else 0.0

        # 4. Order Flow / Taker Buy Ratio % (5m)
        taker_buy_ratio_pct = (
            round((taker_buy_volume_5m / volume_5m) * 100.0, 2) if volume_5m > 0 else 50.0
        )

        # 5. Volume Spike Ratio (5m volume vs. historical 1-hour average baseline)
        if self.baseline_buckets:
            avg_baseline = sum(self.baseline_buckets) / len(self.baseline_buckets)
            volume_spike_ratio = round(volume_5m / avg_baseline, 2) if avg_baseline > 0 else 1.0
        else:
            volume_spike_ratio = 1.0

        # 6. Realized Volatility (Standard deviation of returns across 5m window)
        volatility_5m = self._calculate_volatility(prices_5m)

        # 7. Trade Velocity (Trades Per Second)
        trades_per_second = round(trade_count_5m / WINDOW_5M_SEC, 2)

        return SymbolMetrics(
            symbol=self.symbol,
            current_price=round(current_price, 2),
            price_change_1m_pct=price_change_1m,
            price_change_5m_pct=price_change_5m,
            price_change_15m_pct=price_change_15m,
            vwap_5m=vwap_5m,
            high_15m=round(high_15m, 2),
            low_15m=round(low_15m, 2),
            range_spread_pct=range_spread_pct,
            volume_5m=round(volume_5m, 4),
            volume_spike_ratio=volume_spike_ratio,
            taker_buy_ratio_pct=taker_buy_ratio_pct,
            volatility_5m=volatility_5m,
            trades_per_second=trades_per_second,
            trade_count_5m=trade_count_5m,
            last_trade_time=datetime.fromtimestamp(latest_trade.timestamp_ms / 1000, tz=timezone.utc),
        )

    @staticmethod
    def _calculate_volatility(prices: List[float]) -> float:
        """Calculates standard deviation of fractional returns."""
        if len(prices) < 2:
            return 0.0

        returns = [
            (prices[i] - prices[i - 1]) / prices[i - 1]
            for i in range(1, len(prices))
            if prices[i - 1] > 0
        ]
        if len(returns) < 2:
            return 0.0

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        return round(math.sqrt(variance) * 100.0, 4)

    def generate_sparkline(self, bucket_count: int = 30) -> List[SparklinePoint]:
        """Generates downsampled 1-minute close-price and volume buckets for charts."""
        if not self.trades:
            return []

        now_ms = self.trades[-1].timestamp_ms
        bucket_duration_ms = 60 * 1000  # 1-minute buckets
        start_ms = now_ms - (bucket_count * bucket_duration_ms)

        # Initialize buckets
        buckets: Dict[int, Tuple[float, float]] = {}  # bucket_idx -> (last_price, sum_vol)
        for trade in self.trades:
            if trade.timestamp_ms >= start_ms:
                # Clamp bucket_idx to [0, bucket_count - 1] so latest trade lands in the final bucket
                raw_idx = int((trade.timestamp_ms - start_ms) // bucket_duration_ms)
                bucket_idx = min(max(raw_idx, 0), bucket_count - 1)
                if bucket_idx in buckets:
                    _, vol = buckets[bucket_idx]
                    buckets[bucket_idx] = (trade.price, vol + trade.quantity)
                else:
                    buckets[bucket_idx] = (trade.price, trade.quantity)

        sparkline: List[SparklinePoint] = []
        last_known_price = self.trades[0].price

        for i in range(bucket_count):
            point_time_ms = start_ms + (i * bucket_duration_ms)
            if i in buckets:
                price, vol = buckets[i]
                last_known_price = price
                sparkline.append(
                    SparklinePoint(
                        timestamp_ms=point_time_ms,
                        price=round(price, 2),
                        volume=round(vol, 4),
                    )
                )
            else:
                # Carry forward last known price with 0 volume
                sparkline.append(
                    SparklinePoint(
                        timestamp_ms=point_time_ms,
                        price=round(last_known_price, 2),
                        volume=0.0,
                    )
                )

        return sparkline


class WindowEngine:
    """Central engine managing rolling SymbolWindows across all tracked assets."""

    def __init__(self, symbols: Optional[List[str]] = None) -> None:
        self.windows: Dict[str, SymbolWindow] = {}
        if symbols:
            for s in symbols:
                self.get_or_create_window(s)

    def get_or_create_window(self, symbol: str) -> SymbolWindow:
        """Retrieves or creates a SymbolWindow for the given asset symbol."""
        sym = symbol.upper()
        if sym not in self.windows:
            self.windows[sym] = SymbolWindow(sym)
        return self.windows[sym]

    def process_trade(self, trade: TradeEvent) -> None:
        """Feeds an incoming TradeEvent into the appropriate SymbolWindow."""
        window = self.get_or_create_window(trade.symbol)
        window.add_trade(trade)

    def get_metrics(self, symbol: str) -> Optional[SymbolMetrics]:
        """Returns the current computed metrics snapshot for a specific symbol."""
        window = self.windows.get(symbol.upper())
        if not window:
            return None
        return window.compute_metrics()

    def get_all_metrics(self) -> Dict[str, SymbolMetrics]:
        """Returns computed metrics snapshots for all active symbols."""
        result: Dict[str, SymbolMetrics] = {}
        for sym, window in self.windows.items():
            metrics = window.compute_metrics()
            if metrics:
                result[sym] = metrics
        return result

    def get_analytics(self, symbol: str) -> Optional[SymbolAnalytics]:
        """Returns combined metrics and sparkline history for a single symbol."""
        window = self.windows.get(symbol.upper())
        if not window:
            return None
        metrics = window.compute_metrics()
        if not metrics:
            return None
        sparkline = window.generate_sparkline(bucket_count=30)
        return SymbolAnalytics(metrics=metrics, sparkline=sparkline)

    def get_market_overview(
        self, feed_status: str = "connected", active_alerts_count: int = 0
    ) -> MarketOverview:
        """Produces a comprehensive market overview summary across all tracked assets."""
        all_metrics = self.get_all_metrics()

        top_mover_str = None
        top_spike_str = None

        if all_metrics:
            # Top mover by absolute 5-minute price percentage change
            top_mover = max(all_metrics.values(), key=lambda m: abs(m.price_change_5m_pct))
            sign = "+" if top_mover.price_change_5m_pct > 0 else ""
            top_mover_str = f"{top_mover.symbol} ({sign}{top_mover.price_change_5m_pct}% in 5m)"

            # Top volume spike by baseline ratio
            top_spike = max(all_metrics.values(), key=lambda m: m.volume_spike_ratio)
            if top_spike.volume_spike_ratio > 1.0:
                top_spike_str = f"{top_spike.symbol} ({top_spike.volume_spike_ratio}x baseline)"

        return MarketOverview(
            server_time=datetime.now(timezone.utc),
            feed_status=feed_status,
            top_mover=top_mover_str,
            top_volume_spike=top_spike_str,
            symbols=all_metrics,
            active_alerts_count=active_alerts_count,
        )
