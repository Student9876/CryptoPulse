"""Unit tests for Binance WebSocket ingestion, message normalization, and resilience."""

import json
import pytest
from app.schemas.events import TradeEvent
from app.services.binance_ws import BinanceWebSocketClient


def test_build_stream_url():
    """Verifies correct multi-stream URL structure for tracked symbols."""
    client = BinanceWebSocketClient(
        symbols=["BTCUSDT", "ETHUSDT"],
        base_ws_url="wss://stream.binance.com:9443/stream",
    )
    url = client.build_stream_url()
    assert url == "wss://stream.binance.com:9443/stream?streams=btcusdt@trade/ethusdt@trade"


def test_parse_valid_multi_stream_trade():
    """Verifies parsing of Binance combined multi-stream trade payload."""
    raw_payload = json.dumps({
        "stream": "btcusdt@trade",
        "data": {
            "e": "trade",
            "E": 1729740000000,
            "s": "BTCUSDT",
            "t": 1234567,
            "p": "68500.50",
            "q": "0.1500",
            "b": 88,
            "a": 50,
            "T": 1729740000123,
            "m": True,
            "M": True,
        }
    })

    trade = BinanceWebSocketClient.parse_trade_message(raw_payload)

    assert isinstance(trade, TradeEvent)
    assert trade.symbol == "BTCUSDT"
    assert trade.price == 68500.50
    assert trade.quantity == 0.15
    assert trade.timestamp_ms == 1729740000123
    assert trade.is_buyer_maker is True


def test_parse_valid_single_stream_trade():
    """Verifies parsing of unwrapped trade payload."""
    raw_payload = json.dumps({
        "e": "trade",
        "s": "ethusdt",
        "p": "2650.25",
        "q": "1.5",
        "T": 1729740001000,
        "m": False,
    })

    trade = BinanceWebSocketClient.parse_trade_message(raw_payload)

    assert isinstance(trade, TradeEvent)
    assert trade.symbol == "ETHUSDT"
    assert trade.price == 2650.25
    assert trade.quantity == 1.5
    assert trade.is_buyer_maker is False


def test_parse_ignores_non_trade_events():
    """Verifies that kline, depth, or ping payloads are safely ignored."""
    kline_payload = json.dumps({
        "stream": "btcusdt@kline_1m",
        "data": {"e": "kline", "s": "BTCUSDT"}
    })
    assert BinanceWebSocketClient.parse_trade_message(kline_payload) is None

    ping_payload = json.dumps({"ping": 123456})
    assert BinanceWebSocketClient.parse_trade_message(ping_payload) is None


def test_parse_handles_malformed_json_gracefully():
    """Verifies that invalid or non-JSON payloads return None without crashing."""
    assert BinanceWebSocketClient.parse_trade_message("NOT_JSON") is None
    assert BinanceWebSocketClient.parse_trade_message("{invalid_json:") is None

    # Missing mandatory price field
    incomplete_payload = json.dumps({"e": "trade", "s": "BTCUSDT"})
    assert BinanceWebSocketClient.parse_trade_message(incomplete_payload) is None


def test_backoff_calculation_and_jitter():
    """Verifies exponential increase and max backoff capping."""
    client = BinanceWebSocketClient(initial_backoff=1.0, max_backoff=10.0)

    delay_0 = client.calculate_backoff(0)
    delay_1 = client.calculate_backoff(1)
    delay_2 = client.calculate_backoff(2)
    delay_high = client.calculate_backoff(10)

    # Base backoff: 1.0, 2.0, 4.0 (+ jitter 0.1 - 0.5)
    assert 1.1 <= delay_0 <= 1.5
    assert 2.1 <= delay_1 <= 2.5
    assert 4.1 <= delay_2 <= 4.5

    # High retry count must be capped at max_backoff (10.0) + jitter
    assert 10.1 <= delay_high <= 10.5


def test_health_telemetry_reporting():
    """Verifies health telemetry dictionary."""
    client = BinanceWebSocketClient(symbols=["btcusdt"])
    status = client.get_health_status()

    assert status["is_connected"] is False
    assert status["tracked_symbols"] == ["btcusdt"]
    assert status["messages_received"] == 0
    assert status["reconnect_count"] == 0
    assert status["last_message_time"] is None

