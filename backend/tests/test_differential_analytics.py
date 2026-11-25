"""Differential correctness tests: BaselineSymbolWindow vs OptimizedSymbolWindow."""

import pytest
from app.schemas.events import TradeEvent
from app.stream.symbol_window import BaselineSymbolWindow, OptimizedSymbolWindow
from benchmarks.data.generator import ReplayConfig, TradeEventGenerator


def test_differential_analytics_stream():
    """Feeds 2,500 deterministic trades to baseline and optimized engines, validating exact match."""
    gen = TradeEventGenerator(ReplayConfig(seed=42, event_count=2500, symbols=["BTCUSDT"]))
    events = gen.generate_events()

    base_win = BaselineSymbolWindow("BTCUSDT")
    opt_win = OptimizedSymbolWindow("BTCUSDT")

    # Empty window check
    assert base_win.compute_metrics() is None
    assert opt_win.compute_metrics() is None

    for i, trade in enumerate(events):
        base_win.add_trade(trade)
        opt_win.add_trade(trade)

        m_base = base_win.compute_metrics()
        m_opt = opt_win.compute_metrics()

        assert m_base is not None and m_opt is not None

        # Verify exact numerical equivalence across all rolling metrics
        assert m_opt.current_price == m_base.current_price, f"current_price mismatch at tick {i}"
        assert m_opt.high_15m == m_base.high_15m, f"high_15m mismatch at tick {i}: {m_opt.high_15m} vs {m_base.high_15m}"
        assert m_opt.low_15m == m_base.low_15m, f"low_15m mismatch at tick {i}: {m_opt.low_15m} vs {m_base.low_15m}"
        assert m_opt.range_spread_pct == m_base.range_spread_pct, f"range_spread mismatch at tick {i}"
        assert m_opt.price_change_1m_pct == m_base.price_change_1m_pct, f"1m chg mismatch at tick {i}: {m_opt.price_change_1m_pct} vs {m_base.price_change_1m_pct}"
        assert m_opt.price_change_5m_pct == m_base.price_change_5m_pct, f"5m chg mismatch at tick {i}: {m_opt.price_change_5m_pct} vs {m_base.price_change_5m_pct}"
        assert m_opt.price_change_15m_pct == m_base.price_change_15m_pct, f"15m chg mismatch at tick {i}: {m_opt.price_change_15m_pct} vs {m_base.price_change_15m_pct}"
        assert m_opt.trade_count_5m == m_base.trade_count_5m, f"trade_count mismatch at tick {i}: {m_opt.trade_count_5m} vs {m_base.trade_count_5m}"
        assert m_opt.trades_per_second == m_base.trades_per_second, f"tps mismatch at tick {i}"
        assert m_opt.volume_5m == m_base.volume_5m, f"volume_5m mismatch at tick {i}: {m_opt.volume_5m} vs {m_base.volume_5m}"
        assert m_opt.volume_spike_ratio == m_base.volume_spike_ratio, f"vol_spike mismatch at tick {i}"
        assert m_opt.vwap_5m == m_base.vwap_5m, f"vwap mismatch at tick {i}: {m_opt.vwap_5m} vs {m_base.vwap_5m}"
        assert m_opt.taker_buy_ratio_pct == m_base.taker_buy_ratio_pct, f"taker_buy mismatch at tick {i}: {m_opt.taker_buy_ratio_pct} vs {m_base.taker_buy_ratio_pct}"

        # Volatility is subject to float precision; verify difference < 0.0002
        vol_diff = abs(m_opt.volatility_5m - m_base.volatility_5m)
        assert vol_diff <= 0.0002, f"volatility mismatch at tick {i}: opt={m_opt.volatility_5m} base={m_base.volatility_5m} diff={vol_diff}"


def test_differential_out_of_order_recovery():
    """Tests out-of-order trade insertion and recovery."""
    base_win = BaselineSymbolWindow("ETHUSDT")
    opt_win = OptimizedSymbolWindow("ETHUSDT")

    t0 = 1700000000000
    trades = [
        TradeEvent(symbol="ETHUSDT", price=2500.0, quantity=1.0, timestamp_ms=t0, is_buyer_maker=False),
        TradeEvent(symbol="ETHUSDT", price=2520.0, quantity=1.5, timestamp_ms=t0 + 2000, is_buyer_maker=True),
        TradeEvent(symbol="ETHUSDT", price=2510.0, quantity=0.8, timestamp_ms=t0 + 1000, is_buyer_maker=False),  # Out-of-order!
        TradeEvent(symbol="ETHUSDT", price=2530.0, quantity=2.0, timestamp_ms=t0 + 3000, is_buyer_maker=False),
    ]

    for t in trades:
        base_win.add_trade(t)
        opt_win.add_trade(t)

    mb = base_win.compute_metrics()
    mo = opt_win.compute_metrics()

    assert mo.current_price == mb.current_price
    assert mo.high_15m == mb.high_15m
    assert mo.low_15m == mb.low_15m
    assert mo.vwap_5m == mb.vwap_5m
    assert mo.volume_5m == mb.volume_5m
