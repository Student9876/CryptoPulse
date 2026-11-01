"""Unit tests for the In-Memory Sliding Window Metrics Engine."""

from datetime import datetime
import pytest

from app.schemas.events import TradeEvent
from app.services.window_engine import SymbolWindow, WindowEngine


def make_trade(
    symbol: str = "BTCUSDT",
    price: float = 65000.0,
    quantity: float = 1.0,
    timestamp_ms: int = 1700000000000,
    is_buyer_maker: bool = False,
) -> TradeEvent:
    """Helper to construct synthetic TradeEvents."""
    return TradeEvent(
        symbol=symbol,
        price=price,
        quantity=quantity,
        timestamp_ms=timestamp_ms,
        is_buyer_maker=is_buyer_maker,
    )


def test_empty_window_returns_none():
    """Verifies that an empty window produces None metrics."""
    window = SymbolWindow("BTCUSDT")
    assert window.compute_metrics() is None
    assert window.generate_sparkline() == []


def test_single_trade_metrics():
    """Verifies baseline metric values when only one trade is present."""
    window = SymbolWindow("BTCUSDT")
    t0 = 1700000000000
    window.add_trade(make_trade(price=50000.0, quantity=2.0, timestamp_ms=t0))

    metrics = window.compute_metrics()
    assert metrics is not None
    assert metrics.symbol == "BTCUSDT"
    assert metrics.current_price == 50000.0
    assert metrics.price_change_1m_pct == 0.0
    assert metrics.price_change_5m_pct == 0.0
    assert metrics.vwap_5m == 50000.0
    assert metrics.high_15m == 50000.0
    assert metrics.low_15m == 50000.0
    assert metrics.range_spread_pct == 0.0
    assert metrics.volume_5m == 2.0
    assert metrics.volatility_5m == 0.0
    assert metrics.trade_count_5m == 1


def test_multi_horizon_price_change():
    """Verifies percentage price changes over 1m, 5m, and 15m windows."""
    window = SymbolWindow("BTCUSDT")
    base_time = 1700000000000  # t0

    # Trade 1: 10 minutes ago -> Price 10,000
    window.add_trade(make_trade(price=10000.0, timestamp_ms=base_time))
    # Trade 2: 4 minutes ago (inside 5m & 15m, outside 1m) -> Price 11,000
    window.add_trade(make_trade(price=11000.0, timestamp_ms=base_time + (6 * 60 * 1000)))
    # Trade 3: 30 seconds ago (inside 1m, 5m, 15m) -> Price 12,000
    window.add_trade(make_trade(price=12000.0, timestamp_ms=base_time + (9 * 60 * 1000) + 30000))
    # Trade 4: Current (now) -> Price 12,500
    now_ms = base_time + (10 * 60 * 1000)  # exactly 10 minutes after t0
    window.add_trade(make_trade(price=12500.0, timestamp_ms=now_ms))

    metrics = window.compute_metrics()
    assert metrics is not None
    assert metrics.current_price == 12500.0

    # 1-minute window: oldest trade within 60s is Trade 3 ($12,000)
    # Change = (12,500 - 12,000) / 12,000 * 100 = +4.1667%
    assert metrics.price_change_1m_pct == pytest.approx(4.1667, rel=1e-3)

    # 5-minute window: oldest trade within 300s is Trade 2 ($11,000)
    # Change = (12,500 - 11,000) / 11,000 * 100 = +13.6364%
    assert metrics.price_change_5m_pct == pytest.approx(13.6364, rel=1e-3)

    # 15-minute window: oldest trade within 900s is Trade 1 ($10,000)
    # Change = (12,500 - 10,000) / 10,000 * 100 = +25.0%
    assert metrics.price_change_15m_pct == pytest.approx(25.0, rel=1e-3)


def test_vwap_and_order_flow_calculations():
    """Verifies Volume-Weighted Average Price and Taker Buy Ratio math."""
    window = SymbolWindow("ETHUSDT")
    t0 = 1700000000000

    # Trade 1: 1.0 ETH at $2,000 - Taker BUY (is_buyer_maker=False)
    window.add_trade(make_trade(symbol="ETHUSDT", price=2000.0, quantity=1.0, timestamp_ms=t0, is_buyer_maker=False))
    # Trade 2: 3.0 ETH at $2,100 - Taker SELL (is_buyer_maker=True)
    window.add_trade(make_trade(symbol="ETHUSDT", price=2100.0, quantity=3.0, timestamp_ms=t0 + 1000, is_buyer_maker=True))

    metrics = window.compute_metrics()
    assert metrics is not None
    assert metrics.volume_5m == 4.0

    # VWAP = (2000*1 + 2100*3) / 4 = 8300 / 4 = 2075.0
    assert metrics.vwap_5m == 2075.0

    # Taker Buy Volume = 1.0, Total Volume = 4.0 -> 25.0%
    assert metrics.taker_buy_ratio_pct == 25.0


def test_pruning_expired_trades():
    """Verifies that trades older than 15 minutes (900s) are evicted."""
    window = SymbolWindow("SOLUSDT")
    t0 = 1700000000000

    # Old trade at t0
    window.add_trade(make_trade(symbol="SOLUSDT", price=100.0, quantity=1.0, timestamp_ms=t0))
    assert len(window.trades) == 1

    # New trade 905 seconds later (past 900s max window)
    t_new = t0 + (905 * 1000)
    window.add_trade(make_trade(symbol="SOLUSDT", price=120.0, quantity=2.0, timestamp_ms=t_new))

    # Old trade must be pruned
    assert len(window.trades) == 1
    assert window.trades[0].timestamp_ms == t_new


def test_volume_spike_baseline_ratio():
    """Verifies historical 5-minute bucket baseline tracking."""
    window = SymbolWindow("BTCUSDT")
    t0 = 1700000000000

    # Bucket 1 (0 to 5m): Volume = 100
    window.add_trade(make_trade(price=60000.0, quantity=100.0, timestamp_ms=t0))

    # Trigger Bucket 2 transition at 5m + 1s: Bucket 1 is pushed to history (volume 100)
    t_bucket_2 = t0 + (301 * 1000)
    # Current 5m volume is 300
    window.add_trade(make_trade(price=60500.0, quantity=300.0, timestamp_ms=t_bucket_2))

    metrics = window.compute_metrics()
    assert metrics is not None
    # Prior completed bucket had 100 volume. Current bucket has 300 volume.
    # Volume spike ratio should be 300 / 100 = 3.0x
    assert metrics.volume_spike_ratio == pytest.approx(3.0, rel=1e-2)


def test_sparkline_generation():
    """Verifies generation of 30 downsampled 1-minute chart buckets."""
    window = SymbolWindow("BTCUSDT")
    t0 = 1700000000000

    # Add trades spaced over 10 minutes
    for i in range(10):
        window.add_trade(
            make_trade(
                price=50000.0 + (i * 100.0),
                quantity=0.5,
                timestamp_ms=t0 + (i * 60 * 1000),
            )
        )

    sparkline = window.generate_sparkline(bucket_count=30)
    assert len(sparkline) == 30
    # Last point should match latest price
    assert sparkline[-1].price == 50900.0


def test_window_engine_multi_symbol_and_overview():
    """Verifies WindowEngine coordination, top mover, and top volume spike discovery."""
    engine = WindowEngine(["BTCUSDT", "ETHUSDT"])
    t0 = 1700000000000

    # BTC moves +5%
    engine.process_trade(make_trade(symbol="BTCUSDT", price=60000.0, quantity=1.0, timestamp_ms=t0))
    engine.process_trade(make_trade(symbol="BTCUSDT", price=63000.0, quantity=1.0, timestamp_ms=t0 + 10000))

    # ETH moves -1%
    engine.process_trade(make_trade(symbol="ETHUSDT", price=3000.0, quantity=2.0, timestamp_ms=t0))
    engine.process_trade(make_trade(symbol="ETHUSDT", price=2970.0, quantity=2.0, timestamp_ms=t0 + 10000))

    all_metrics = engine.get_all_metrics()
    assert "BTCUSDT" in all_metrics
    assert "ETHUSDT" in all_metrics

    overview = engine.get_market_overview(feed_status="connected", active_alerts_count=5)
    assert overview.feed_status == "connected"
    assert overview.active_alerts_count == 5
    assert "BTCUSDT" in overview.top_mover  # BTC had the biggest move (+5%)
    assert overview.symbols["BTCUSDT"].current_price == 63000.0

