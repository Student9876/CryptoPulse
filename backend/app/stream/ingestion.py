"""Resilient Binance WebSocket ingestion client with exponential backoff and watchdog."""

import asyncio
import json
import random
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.events import TradeEvent

logger = get_logger("cryptopulse.ingestion")

TradeCallback = Callable[[TradeEvent], Awaitable[None]]


class BinanceWebSocketClient:
    """Consumes real-time trades from Binance combined stream."""

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        base_ws_url: Optional[str] = None,
        on_trade: Optional[TradeCallback] = None,
        watchdog_timeout: float = 20.0,
        initial_backoff: float = 1.0,
        max_backoff: float = 30.0,
    ) -> None:
        self.symbols = [s.lower() for s in (symbols or settings.TRACKED_SYMBOLS)]
        self.base_ws_url = base_ws_url or settings.BINANCE_WS_URL
        self.on_trade = on_trade
        self.watchdog_timeout = watchdog_timeout
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff

        self._running: bool = False
        self._is_connected: bool = False
        self._task: Optional[asyncio.Task] = None
        self._ws: Optional[ClientConnection] = None

        self.messages_received: int = 0
        self.reconnect_count: int = 0
        self.last_message_time: Optional[datetime] = None

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def build_stream_url(self) -> str:
        streams = "/".join(f"{s}@trade" for s in self.symbols)
        return f"{self.base_ws_url}?streams={streams}"

    @staticmethod
    def parse_trade_message(raw_data: str) -> Optional[TradeEvent]:
        try:
            payload = json.loads(raw_data)
            data: Dict[str, Any] = payload.get("data", payload)
            if data.get("e") != "trade":
                return None

            return TradeEvent(
                symbol=str(data["s"]).upper(),
                price=float(data["p"]),
                quantity=float(data["q"]),
                timestamp_ms=int(data["T"]),
                is_buyer_maker=bool(data["m"]),
            )
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return None

    def calculate_backoff(self, retry_count: int) -> float:
        delay = min(self.initial_backoff * (2 ** retry_count), self.max_backoff)
        return delay + random.uniform(0.1, 0.5)

    async def _listen_loop(self, ws: ClientConnection) -> None:
        self._is_connected = True
        logger.info("Connected to Binance stream for %s", self.symbols)

        while self._running:
            try:
                raw_msg = await asyncio.wait_for(ws.recv(), timeout=self.watchdog_timeout)
                self.messages_received += 1
                self.last_message_time = datetime.now(timezone.utc)

                trade = self.parse_trade_message(raw_msg)
                if trade and self.on_trade:
                    await self.on_trade(trade)
            except asyncio.TimeoutError:
                logger.warning("Feed watchdog timeout. Reconnecting...")
                break
            except ConnectionClosed:
                break

    async def run_forever(self) -> None:
        self._running = True
        retry = 0
        url = self.build_stream_url()

        while self._running:
            try:
                async with connect(url, ping_interval=20, ping_timeout=10, close_timeout=5) as ws:
                    self._ws = ws
                    retry = 0
                    await self._listen_loop(ws)
            except (asyncio.CancelledError, KeyboardInterrupt):
                break
            except Exception as err:
                self.reconnect_count += 1
                delay = self.calculate_backoff(retry)
                logger.error("Connection error: %s. Retry in %.1fs (#%d)", err, delay, retry + 1)
                retry += 1
                await asyncio.sleep(delay)
            finally:
                self._is_connected = False
                self._ws = None

    def start(self) -> asyncio.Task:
        if self._task and not self._task.done():
            return self._task
        self._task = asyncio.create_task(self.run_forever(), name="binance-ws-stream")
        return self._task

    async def stop(self) -> None:
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

    def get_health_status(self) -> Dict[str, Any]:
        return {
            "is_connected": self._is_connected,
            "tracked_symbols": self.symbols,
            "messages_received": self.messages_received,
            "reconnect_count": self.reconnect_count,
            "last_message_time": self.last_message_time.isoformat() if self.last_message_time else None,
        }

