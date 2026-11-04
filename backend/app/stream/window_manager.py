"""Central registry managing SymbolWindows across all tracked crypto trading pairs."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.schemas.analytics import MarketOverview, SymbolAnalytics, SymbolMetrics
from app.schemas.events import TradeEvent
from app.stream.symbol_window import SymbolWindow


class WindowManager:
    """Coordinates sliding windows, metrics aggregation, and market overviews."""

    def __init__(self, symbols: Optional[List[str]] = None) -> None:
        self.windows: Dict[str, SymbolWindow] = {}
        if symbols:
            for s in symbols:
                self.get_or_create_window(s)

    def get_or_create_window(self, symbol: str) -> SymbolWindow:
        sym = symbol.upper()
        if sym not in self.windows:
            self.windows[sym] = SymbolWindow(sym)
        return self.windows[sym]

    def process_trade(self, trade: TradeEvent) -> None:
        self.get_or_create_window(trade.symbol).add_trade(trade)

    def get_metrics(self, symbol: str) -> Optional[SymbolMetrics]:
        window = self.windows.get(symbol.upper())
        return window.compute_metrics() if window else None

    def get_all_metrics(self) -> Dict[str, SymbolMetrics]:
        result: Dict[str, SymbolMetrics] = {}
        for sym, window in self.windows.items():
            metrics = window.compute_metrics()
            if metrics:
                result[sym] = metrics
        return result

    def get_analytics(self, symbol: str) -> Optional[SymbolAnalytics]:
        window = self.windows.get(symbol.upper())
        if not window:
            return None
        metrics = window.compute_metrics()
        if not metrics:
            return None
        return SymbolAnalytics(metrics=metrics, sparkline=window.generate_sparkline(bucket_count=30))

    def get_market_overview(
        self, feed_status: str = "connected", active_alerts_count: int = 0
    ) -> MarketOverview:
        all_metrics = self.get_all_metrics()
        top_mover_str, top_spike_str = None, None

        if all_metrics:
            top_mover = max(all_metrics.values(), key=lambda m: abs(m.price_change_5m_pct))
            sign = "+" if top_mover.price_change_5m_pct > 0 else ""
            top_mover_str = f"{top_mover.symbol} ({sign}{top_mover.price_change_5m_pct}% in 5m)"

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

