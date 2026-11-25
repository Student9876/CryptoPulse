"""Deterministic trade event generator and replay harness for CryptoPulse benchmarks."""

import asyncio
import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Iterator, List, Optional

from app.schemas.events import TradeEvent


DEFAULT_BASE_PRICES = {
    "BTCUSDT": 65000.0,
    "ETHUSDT": 2500.0,
    "SOLUSDT": 150.0,
}


@dataclass
class ReplayConfig:
    """Configuration parameters for deterministic trade replay generation."""

    seed: int = 42
    symbols: List[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    event_count: int = 10_000
    start_time_ms: int = 1_700_000_000_000  # Fixed epoch ms for determinism
    interval_ms: int = 50  # Average ms between trades (20 trades/sec per symbol)
    base_prices: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_BASE_PRICES))
    volatility: float = 0.0005  # Per-tick price volatility (stdev)
    drift: float = 0.0
    taker_buy_probability: float = 0.52
    base_quantity_mean: float = 0.5
    base_quantity_std: float = 0.3


class TradeEventGenerator:
    """Generates synthetic, deterministic trade event sequences for benchmarking and correctness."""

    def __init__(self, config: Optional[ReplayConfig] = None) -> None:
        self.config = config or ReplayConfig()
        self.rng = random.Random(self.config.seed)

    def generate_events(self, config: Optional[ReplayConfig] = None) -> List[TradeEvent]:
        """Generates a complete deterministic list of trade events according to config."""
        cfg = config or self.config
        rng = random.Random(cfg.seed)

        current_prices = {s: cfg.base_prices.get(s, 100.0) for s in cfg.symbols}
        events: List[TradeEvent] = []
        current_time_ms = cfg.start_time_ms

        for i in range(cfg.event_count):
            # Select symbol round-robin or randomly from configured list
            sym = cfg.symbols[i % len(cfg.symbols)]
            price = current_prices[sym]

            # Geometric random walk with drift: P_new = P * exp((drift - 0.5 * vol^2) + vol * Z)
            z = rng.gauss(0.0, 1.0)
            ret = (cfg.drift - 0.5 * (cfg.volatility ** 2)) + cfg.volatility * z
            new_price = max(0.01, round(price * math.exp(ret), 2))
            current_prices[sym] = new_price

            # Log-normal or truncated normal quantity distribution
            qty = max(0.001, round(rng.lognormvariate(math.log(cfg.base_quantity_mean), cfg.base_quantity_std), 4))

            # Taker buy / sell determination
            is_buyer_maker = rng.random() > cfg.taker_buy_probability

            # Realistic tick spacing with slight jitter
            jitter = rng.randint(-max(1, cfg.interval_ms // 4), max(1, cfg.interval_ms // 4))
            current_time_ms += max(5, cfg.interval_ms + jitter)

            events.append(
                TradeEvent(
                    symbol=sym,
                    price=new_price,
                    quantity=qty,
                    timestamp_ms=current_time_ms,
                    is_buyer_maker=is_buyer_maker,
                )
            )

        return events

    async def stream_events(
        self,
        config: Optional[ReplayConfig] = None,
        target_rate: Optional[float] = None,
    ) -> AsyncGenerator[TradeEvent, None]:
        """Asynchronously streams generated events with optional target rate throttling."""
        events = self.generate_events(config)
        sleep_interval = (1.0 / target_rate) if target_rate and target_rate > 0 else 0.0

        for event in events:
            if sleep_interval > 0:
                await asyncio.sleep(sleep_interval)
            yield event

    @staticmethod
    def generate_controlled_scenario(
        symbol: str,
        prices: List[float],
        quantities: Optional[List[float]] = None,
        start_time_ms: int = 1_700_000_000_000,
        time_step_ms: int = 1000,
        buyer_makers: Optional[List[bool]] = None,
    ) -> List[TradeEvent]:
        """Creates an exact, deterministic list of trades from explicit price points.

        Useful for unit correctness testing where every tick's price and timestamp is pre-determined.
        """
        events: List[TradeEvent] = []
        for i, price in enumerate(prices):
            qty = quantities[i] if quantities and i < len(quantities) else 1.0
            is_bm = buyer_makers[i] if buyer_makers and i < len(buyer_makers) else False
            events.append(
                TradeEvent(
                    symbol=symbol,
                    price=round(price, 2),
                    quantity=round(qty, 4),
                    timestamp_ms=start_time_ms + (i * time_step_ms),
                    is_buyer_maker=is_bm,
                )
            )
        return events
