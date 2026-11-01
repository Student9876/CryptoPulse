"""Binance WebSocket Ingestion Client.

Maintains a persistent, resilient connection to Binance public multi-stream WebSockets,
ingests raw trade messages for configured trading pairs, normalizes them into
standardized TradeEvent objects, and delivers them to a registered callback.

Resilience features:
- Automatic reconnect with exponential backoff and jitter
- Stale feed watchdog detecting half-open sockets / silent disconnects
- Clean handling of Binance 24-hour forced connection rotation
- Graceful asynchronous task cancellation on shutdown
"""

import asyncio
import json
import random
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

import websockets
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.events import TradeEvent

logger = get_logger("cryptopulse.ingestion")

TradeCallback = Callable[[TradeEvent], Awaitable[None]]


class BinanceWebSocketClient:
    """Manages real-time market data streaming from Binance."""

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        base_ws_url: Optional[str] = None,
        on_trade: Optional[TradeCallback] = None,
        watchdog_timeout: float = 20.0,
        initial_backoff: float = 1.0,
        max_backoff: float = 30.0,
    ) -> None:
        """Initializes the WebSocket client.

        Args:
            symbols: List of trading pair symbols (e.g. ['btcusdt', 'ethusdt']).
            base_ws_url: Base WebSocket stream URL.
            on_trade: Async callback function invoked on each normalized trade.
            watchdog_timeout: Max seconds between messages before declaring socket stale.
            initial_backoff: Starting reconnection delay in seconds.
            max_backoff: Maximum cap for reconnection backoff.
        """
        self.symbols = [s.lower() for s in (symbols or settings.TRACKED_SYMBOLS)]
        self.base_ws_url = base_ws_url or settings.BINANCE_WS_URL
        self.on_trade = on_trade
        self.watchdog_timeout = watchdog_timeout
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff

        # State and telemetry tracking
        self._running: bool = False
        self._is_connected: bool = False
        self._task: Optional[asyncio.Task] = None
        self._ws: Optional[ClientConnection] = None

        self.messages_received: int = 0
        self.reconnect_count: int = 0
        self.last_message_time: Optional[datetime] = None

    @property
    def is_connected(self) -> bool:
        """Returns True if the client is actively connected and consuming."""
        return self._is_connected

    def build_stream_url(self) -> str:
        """Constructs the combined multi-stream URL for tracked symbols.

        Example: wss://stream.binance.com:9443/stream?streams=btcusdt@trade/ethusdt@trade
        """
        streams = "/".join(f"{symbol}@trade" for symbol in self.symbols)
        return f"{self.base_ws_url}?streams={streams}"

    @staticmethod
    def parse_trade_message(raw_data: str) -> Optional[TradeEvent]:
        """Parses and validates a raw WebSocket message into a normalized TradeEvent.

        Returns None if the message is malformed, a heartbeat, or a non-trade event.
        """
        try:
            payload = json.loads(raw_data)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Received invalid non-JSON payload from stream")
            return None

        # Multi-stream payloads are wrapped in: {"stream": "<name>", "data": {...}}
        data: Dict[str, Any] = payload.get("data", payload)

        # Confirm message is a trade event
        if data.get("e") != "trade":
            return None

        try:
            return TradeEvent(
                symbol=str(data["s"]).upper(),
                price=float(data["p"]),
                quantity=float(data["q"]),
                timestamp_ms=int(data["T"]),
                is_buyer_maker=bool(data["m"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Failed to normalize trade event: %s | payload: %s", exc, data)
            return None

    def calculate_backoff(self, retry_count: int) -> float:
        """Calculates exponential backoff with random jitter to prevent thundering herds."""
        delay = min(self.initial_backoff * (2 ** retry_count), self.max_backoff)
        jitter = random.uniform(0.1, 0.5)
        return delay + jitter

    async def _listen_loop(self, ws: ClientConnection) -> None:
        """Internal receive loop. Reads messages until disconnected or socket times out."""
        self._is_connected = True
        logger.info("Connected to Binance stream for %s", self.symbols)

        while self._running:
            try:
                # Watchdog: If no message arrives within timeout, raise TimeoutError
                # This catches silent 'half-open' socket drops where TCP never sends FIN
                raw_message = await asyncio.wait_for(ws.recv(), timeout=self.watchdog_timeout)
                self.messages_received += 1
                self.last_message_time = datetime.now(timezone.utc)

                trade = self.parse_trade_message(raw_message)
                if trade and self.on_trade:
                    try:
                        await self.on_trade(trade)
                    except Exception as err:
                        logger.error("Error in on_trade consumer callback: %s", err, exc_info=True)

            except asyncio.TimeoutError:
                logger.warning(
                    "Stale feed detected: No message received for %s seconds. Reconnecting...",
                    self.watchdog_timeout,
                )
                break
            except ConnectionClosed as err:
                logger.info("WebSocket connection closed: code=%s, reason=%s", err.code, err.reason)
                break

    async def run_forever(self) -> None:
        """Continuous execution loop with automatic reconnection and backoff."""
        self._running = True
        retry_count = 0
        url = self.build_stream_url()

        while self._running:
            try:
                logger.info("Opening WebSocket connection to %s (attempt #%d)...", url, retry_count + 1)
                async with connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    self._ws = ws
                    # Reset backoff after a successful connection handshake
                    retry_count = 0
                    await self._listen_loop(ws)

            except (asyncio.CancelledError, KeyboardInterrupt):
                logger.info("Binance ingestion task received cancellation signal")
                break
            except Exception as exc:
                self.reconnect_count += 1
                delay = self.calculate_backoff(retry_count)
                logger.error(
                    "Connection error: %s. Reconnecting in %.2f seconds (retry #%d)...",
                    exc,
                    delay,
                    retry_count + 1,
                )
                retry_count += 1
                await asyncio.sleep(delay)
            finally:
                self._is_connected = False
                self._ws = None

        logger.info("Binance ingestion runner stopped cleanly")

    def start(self) -> asyncio.Task:
        """Starts the ingestion loop as a background asyncio Task."""
        if self._task and not self._task.done():
            logger.warning("Ingestion client task is already running")
            return self._task

        self._task = asyncio.create_task(self.run_forever(), name="binance-ws-ingestion")
        return self._task

    async def stop(self) -> None:
        """Signals the client to stop, closes socket, and awaits task termination."""
        logger.info("Stopping Binance ingestion client...")
        self._running = False
        self._is_connected = False

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Binance ingestion client stopped")

    def get_health_status(self) -> Dict[str, Any]:
        """Returns health telemetry for monitoring endpoints."""
        return {
            "is_connected": self._is_connected,
            "tracked_symbols": self.symbols,
            "messages_received": self.messages_received,
            "reconnect_count": self.reconnect_count,
            "last_message_time": self.last_message_time.isoformat() if self.last_message_time else None,
        }
