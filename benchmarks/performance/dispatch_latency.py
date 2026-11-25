"""Telegram notification dispatch latency and throughput benchmark with mocked API responses."""

import asyncio
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.base import Base
import app.models  # noqa: F401
from app.models.alert_history import AlertHistory
from app.models.alert_rule import AlertRule
from app.rules.evaluator import RuleEngine
from app.schemas.events import AlertEvent


@dataclass
class PhaseLatencyStats:
    """Statistical summary of latency for a dispatch pipeline stage in milliseconds."""

    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    min_ms: float
    max_ms: float

    @classmethod
    def from_seconds(cls, values_sec: List[float]) -> "PhaseLatencyStats":
        if not values_sec:
            return cls(0, 0, 0, 0, 0, 0)
        sorted_ms = sorted(v * 1000.0 for v in values_sec)
        n = len(sorted_ms)

        def pct(p: float) -> float:
            idx = min(int(n * (p / 100.0)), n - 1)
            return round(sorted_ms[idx], 3)

        return cls(
            p50_ms=pct(50.0),
            p95_ms=pct(95.0),
            p99_ms=pct(99.0),
            mean_ms=round(sum(sorted_ms) / n, 3),
            min_ms=round(sorted_ms[0], 3),
            max_ms=round(sorted_ms[-1], 3),
        )


@dataclass
class DispatchBenchmarkResult:
    """Comprehensive results for notification dispatch benchmark."""

    total_alerts: int
    successful_dispatches: int
    failed_dispatches: int
    duration_seconds: float
    throughput_alerts_per_sec: float
    simulated_api_delay_ms: float
    queue_latency: PhaseLatencyStats
    telegram_api_latency: PhaseLatencyStats
    db_persistence_latency: PhaseLatencyStats
    total_latency: PhaseLatencyStats

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MockTelegramBot:
    """Mock Telegram Bot simulating API acknowledgement latency without hitting Telegram servers."""

    def __init__(self, simulated_delay_sec: float = 0.030) -> None:
        self.simulated_delay_sec = simulated_delay_sec
        self.sent_messages: List[Dict[str, Any]] = []

    async def send_message(self, chat_id: int, text: str, parse_mode: Optional[str] = None) -> Dict[str, Any]:
        if self.simulated_delay_sec > 0:
            await asyncio.sleep(self.simulated_delay_sec)
        msg_record = {"chat_id": chat_id, "text": text, "timestamp": time.time()}
        self.sent_messages.append(msg_record)
        return msg_record


class DispatchLatencyBenchmark:
    """Benchmarks alert dispatch isolating queue latency, mock Telegram latency, and DB commit latency."""

    def __init__(self, simulated_api_delay_sec: float = 0.030) -> None:
        self.simulated_api_delay_sec = simulated_api_delay_sec

    async def run_benchmark(self, alert_count: int = 150) -> DispatchBenchmarkResult:
        """Executes notification dispatch load test measuring latency at each phase."""
        # 1. Setup isolated in-memory test database
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        # Pre-seed one user and alert rules
        async with session_factory() as session:
            for rid in range(1, alert_count + 1):
                session.add(
                    AlertRule(
                        id=rid,
                        user_id=1,
                        symbol="BTCUSDT",
                        metric_type="price_level",
                        condition="greater_than",
                        threshold_value=65000.0,
                        is_active=True,
                        is_recurring=True,
                    )
                )
            await session.commit()

        # 2. Setup mock bot and rule engine
        rule_engine = RuleEngine()
        bot = MockTelegramBot(simulated_delay_sec=self.simulated_api_delay_sec)

        # Latency tracking containers
        queue_latencies: List[float] = []
        api_latencies: List[float] = []
        db_latencies: List[float] = []
        total_latencies: List[float] = []

        enqueue_timestamps: Dict[int, float] = {}
        processed_count = 0
        all_done = asyncio.Event()

        # Custom instrumented dispatcher loop
        async def instrumented_dispatch_loop():
            nonlocal processed_count
            while processed_count < alert_count:
                try:
                    event: AlertEvent = await rule_engine.alert_queue.get()
                    t_dequeued = time.perf_counter()

                    t_enqueued = enqueue_timestamps.get(event.rule_id, t_dequeued)
                    t_queue = t_dequeued - t_enqueued

                    # Telegram API Phase
                    t_api_start = time.perf_counter()
                    await bot.send_message(chat_id=event.telegram_id, text=event.message)
                    t_api_end = time.perf_counter()
                    t_api = t_api_end - t_api_start

                    # Database Persistence Phase
                    t_db_start = time.perf_counter()
                    async with session_factory() as session:
                        session.add(
                            AlertHistory(
                                user_id=event.user_id,
                                rule_id=event.rule_id,
                                symbol=event.symbol,
                                metric_value=event.actual_value,
                                threshold_value=event.threshold_value,
                                message=event.message,
                                triggered_at=event.triggered_at,
                            )
                        )
                        await session.commit()
                    t_db_end = time.perf_counter()
                    t_db = t_db_end - t_db_start

                    t_total = t_dequeued - t_enqueued + t_api + t_db

                    queue_latencies.append(t_queue)
                    api_latencies.append(t_api)
                    db_latencies.append(t_db)
                    total_latencies.append(t_total)

                    rule_engine.alert_queue.task_done()
                    processed_count += 1
                except Exception as err:
                    print(f"Dispatcher error: {err}")
                    break

            all_done.set()

        # Start dispatcher task
        dispatcher_task = asyncio.create_task(instrumented_dispatch_loop())

        # Generate and enqueue AlertEvents
        t_start_total = time.perf_counter()
        for i in range(1, alert_count + 1):
            now_perf = time.perf_counter()
            enqueue_timestamps[i] = now_perf
            event = AlertEvent(
                rule_id=i,
                user_id=1,
                telegram_id=999888777,
                symbol="BTCUSDT",
                metric_type="price_level",
                condition="greater_than",
                threshold_value=65000.0,
                actual_value=65100.0,
                message=f"<b>BTCUSDT Price Alert</b>: $65,100.00 >= $65,000.00",
                triggered_at=datetime.now(timezone.utc),
                is_recurring=True,
            )
            rule_engine.alert_queue.put_nowait(event)

        # Wait for all alerts to be dispatched and recorded
        try:
            await asyncio.wait_for(all_done.wait(), timeout=30.0)
        finally:
            dispatcher_task.cancel()
            try:
                await dispatcher_task
            except asyncio.CancelledError:
                pass
            await engine.dispose()

        t_end_total = time.perf_counter()
        duration = t_end_total - t_start_total
        throughput = round(processed_count / duration, 2) if duration > 0 else 0.0

        return DispatchBenchmarkResult(
            total_alerts=alert_count,
            successful_dispatches=processed_count,
            failed_dispatches=alert_count - processed_count,
            duration_seconds=round(duration, 4),
            throughput_alerts_per_sec=throughput,
            simulated_api_delay_ms=round(self.simulated_api_delay_sec * 1000, 2),
            queue_latency=PhaseLatencyStats.from_seconds(queue_latencies),
            telegram_api_latency=PhaseLatencyStats.from_seconds(api_latencies),
            db_persistence_latency=PhaseLatencyStats.from_seconds(db_latencies),
            total_latency=PhaseLatencyStats.from_seconds(total_latencies),
        )
