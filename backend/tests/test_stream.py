"""Unit tests for market streaming: ingestion, symbol window, and window manager."""

import json
import pytest

from app.schemas.events import TradeEvent
from app.stream.ingestion import BinanceWebSocketClient
from app.stream.symbol_window import SymbolWindow
from app.stream.window_manager import WindowManager


def make_trade(
    symbol: str = "BTCUSDT",
    price: float = 65000.0,
    quantity: float = 1.0,
    timestamp_ms: int = 1700000000000,
    is_buyer_maker: bool = False,
) -> TradeEvent:
    return TradeEvent(
        symbol=symbol,
        price=price,
        quantity=quantity,
        timestamp_ms=timestamp_ms,
        is_buyer_maker=is_buyer_maker,
    )


# --- Ingestion Client Tests ---

def test_build_stream_url():
    client = BinanceWebSocketClient(symbols=["BTCUSDT", "ETHUSDT"], base_ws_url="wss://stream.binance.com/stream")
    assert client.build_stream_url() == "wss://stream.binance.com/stream?streams=btcusdt@trade/ethusdt@trade"


def test_parse_valid_multi_stream_trade():
    raw_payload = json.dumps({
        "stream": "btcusdt@trade",
        "data": {
            "e": "trade",
            "s": "BTCUSDT",
            "p": "68500.50",
            "q": "0.1500",
            "T": 1729740000123,
            "m": True,
        }
    })
    trade = BinanceWebSocketClient.parse_trade_message(raw_payload)
    assert trade is not None
    assert trade.symbol == "BTCUSDT"
    assert trade.price == 68500.50
    assert trade.quantity == 0.15
    assert trade.is_buyer_maker is True


def test_parse_ignores_non_trade_or_malformed():
    assert BinanceWebSocketClient.parse_trade_message("INVALID_JSON") is None
    kline_payload = json.dumps({"stream": "btcusdt@kline", "data": {"e": "kline"}})
    assert BinanceWebSocketClient.parse_trade_message(kline_payload) is None


def test_backoff_calculation_and_jitter():
    client = BinanceWebSocketClient(initial_backoff=1.0, max_backoff=10.0)
    delay_0 = client.calculate_backoff(0)
    assert 1.1 <= delay_0 <= 1.5


def test_health_telemetry_reporting():
    client = BinanceWebSocketClient(symbols=["btcusdt"])
    status = client.get_health_status()
    assert status["is_connected"] is False
    assert status["messages_received"] == 0


# --- Symbol Window Tests ---

def test_empty_window_returns_none():
    window = SymbolWindow("BTCUSDT")
    assert window.compute_metrics() is None
    assert window.generate_sparkline() == []


def test_single_trade_metrics():
    window = SymbolWindow("BTCUSDT")
    window.add_trade(make_trade(price=50000.0, quantity=2.0))
    metrics = window.compute_metrics()
    assert metrics is not None
    assert metrics.current_price == 50000.0
    assert metrics.price_change_5m_pct == 0.0
    assert metrics.vwap_5m == 50000.0


def test_multi_horizon_price_change():
    window = SymbolWindow("BTCUSDT")
    t0 = 1700000000000
    window.add_trade(make_trade(price=10000.0, timestamp_ms=t0))
    window.add_trade(make_trade(price=11000.0, timestamp_ms=t0 + (6 * 60 * 1000)))
    window.add_trade(make_trade(price=12000.0, timestamp_ms=t0 + (9 * 60 * 1000) + 30000))
    window.add_trade(make_trade(price=12500.0, timestamp_ms=t0 + (10 * 60 * 1000)))

    metrics = window.compute_metrics()
    assert metrics is not None
    assert metrics.price_change_1m_pct == pytest.approx(4.1667, rel=1e-3)
    assert metrics.price_change_5m_pct == pytest.approx(13.6364, rel=1e-3)
    assert metrics.price_change_15m_pct == pytest.approx(25.0, rel=1e-3)


def test_vwap_and_order_flow_calculations():
    window = SymbolWindow("ETHUSDT")
    t0 = 1700000000000
    window.add_trade(make_trade(symbol="ETHUSDT", price=2000.0, quantity=1.0, timestamp_ms=t0, is_buyer_maker=False))
    window.add_trade(make_trade(symbol="ETHUSDT", price=2100.0, quantity=3.0, timestamp_ms=t0 + 1000, is_buyer_maker=True))

    metrics = window.compute_metrics()
    assert metrics is not None
    assert metrics.volume_5m == 4.0
    assert metrics.vwap_5m == 2075.0
    assert metrics.taker_buy_ratio_pct == 25.0


def test_pruning_expired_trades():
    window = SymbolWindow("SOLUSDT")
    t0 = 1700000000000
    window.add_trade(make_trade(symbol="SOLUSDT", price=100.0, timestamp_ms=t0))
    t_new = t0 + (905 * 1000)
    window.add_trade(make_trade(symbol="SOLUSDT", price=120.0, timestamp_ms=t_new))
    assert len(window.trades) == 1
    assert window.trades[0].timestamp_ms == t_new


def test_volume_spike_baseline_ratio():
    window = SymbolWindow("BTCUSDT")
    t0 = 1700000000000
    window.add_trade(make_trade(price=60000.0, quantity=100.0, timestamp_ms=t0))
    window.add_trade(make_trade(price=60500.0, quantity=300.0, timestamp_ms=t0 + (301 * 1000)))
    metrics = window.compute_metrics()
    assert metrics is not None
    assert metrics.volume_spike_ratio == pytest.approx(3.0, rel=1e-2)


def test_sparkline_generation():
    window = SymbolWindow("BTCUSDT")
    t0 = 1700000000000
    for i in range(10):
        window.add_trade(make_trade(price=50000.0 + (i * 100.0), quantity=0.5, timestamp_ms=t0 + (i * 60 * 1000)))
    sparkline = window.generate_sparkline(bucket_count=30)
    assert len(sparkline) == 30
    assert sparkline[-1].price == 50900.0


# --- Window Manager Tests ---

def test_window_manager_multi_symbol_and_overview():
    manager = WindowManager(["BTCUSDT", "ETHUSDT"])
    t0 = 1700000000000
    manager.process_trade(make_trade(symbol="BTCUSDT", price=60000.0, timestamp_ms=t0))
    manager.process_trade(make_trade(symbol="BTCUSDT", price=63000.0, timestamp_ms=t0 + 1000))
    manager.process_trade(make_trade(symbol="ETHUSDT", price=3000.0, timestamp_ms=t0))

    overview = manager.get_market_overview(feed_status="connected", active_alerts_count=3)
    assert overview.feed_status == "connected"
    assert overview.active_alerts_count == 3
    assert "BTCUSDT" in overview.top_mover

