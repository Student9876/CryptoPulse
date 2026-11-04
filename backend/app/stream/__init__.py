"""Real-time market data streaming and in-memory analytics package."""

from app.stream.ingestion import BinanceWebSocketClient
from app.stream.symbol_window import SymbolWindow
from app.stream.window_manager import WindowManager

__all__ = [
    "BinanceWebSocketClient",
    "SymbolWindow",
    "WindowManager",
]

