"""Concurrent SSE streaming benchmark for CryptoPulse market overview endpoint.

Supports both in-process ASGI streaming and real TCP loopback network socket streaming.
"""

import asyncio
import os
import socket
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
import httpx
import psutil
import uvicorn

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.api.v1.endpoints.stream import router as stream_router
from app.stream.window_manager import WindowManager
from benchmarks.data.generator import ReplayConfig, TradeEventGenerator


def create_stream_benchmark_app(wm: WindowManager) -> FastAPI:
    """Creates an isolated, lightweight FastAPI app for streaming benchmarks without side-effects."""
    test_app = FastAPI()
    test_app.include_router(stream_router, prefix="/api/v1")
    test_app.state.window_engine = wm
    test_app.state.rule_engine = None
    test_app.state.ws_client = None

    @test_app.get("/healthz")
    def health_check():
        return {"status": "ok"}

    return test_app


@dataclass
class StreamClientStats:
    """Metrics recorded for a single connected SSE client."""

    client_id: int
    connected: bool
    connection_time_ms: float
    messages_received: int
    arrival_intervals_ms: List[float]
    disconnected_early: bool
    error: Optional[str] = None


@dataclass
class ConcurrentStreamResult:
    """Summary of concurrent SSE load test at a specific concurrency tier."""

    transport: str  # 'in_process_asgi' or 'network_tcp'
    concurrent_clients: int
    target_messages_per_client: int
    connection_success_rate_pct: float
    total_messages_received: int
    expected_total_messages: int
    message_loss_rate_pct: float
    disconnection_count: int
    avg_connection_time_ms: float
    delivery_interval_p50_ms: float
    delivery_interval_p95_ms: float
    delivery_interval_p99_ms: float
    delivery_interval_mean_ms: float
    duration_seconds: float
    peak_memory_mb: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConcurrentStreamBenchmark:
    """Simulates multi-tenant concurrent SSE clients connecting to /api/v1/stream/overview."""

    def __init__(self) -> None:
        self.process = psutil.Process(os.getpid())

    @staticmethod
    def _find_free_port() -> int:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port

    async def benchmark_concurrency_tier(
        self,
        concurrent_clients: int = 25,
        target_messages_per_client: int = 4,
        use_network_tcp: bool = False,
    ) -> ConcurrentStreamResult:
        """Connects N concurrent async SSE clients (ASGI or real TCP network socket)."""
        wm = WindowManager(symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"])

        # Seed sample trades so market overview has data
        gen = TradeEventGenerator(ReplayConfig(seed=42, event_count=50))
        for trade in gen.generate_events():
            wm.process_trade(trade)

        app = create_stream_benchmark_app(wm)

        server_thread: Optional[threading.Thread] = None
        server: Optional[uvicorn.Server] = None
        base_url = "http://testserver"
        transport = None

        if use_network_tcp:
            port = self._find_free_port()
            base_url = f"http://127.0.0.1:{port}"
            config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", loop="asyncio")
            server = uvicorn.Server(config)
            server_thread = threading.Thread(target=server.run, daemon=True)
            server_thread.start()

            # Wait for TCP server port readiness
            for _ in range(50):
                await asyncio.sleep(0.05)
                try:
                    async with httpx.AsyncClient() as c:
                        res = await c.get(f"{base_url}/healthz", timeout=1.0)
                        if res.status_code == 200:
                            break
                except Exception:
                    pass
        else:
            transport = httpx.ASGITransport(app=app)

        client_stats: List[StreamClientStats] = []
        rss_start = self.process.memory_info().rss / (1024 * 1024)
        peak_rss = rss_start

        t_bench_start = time.perf_counter()

        async def run_single_client(cid: int) -> StreamClientStats:
            t0 = time.perf_counter()
            intervals: List[float] = []
            msg_count = 0
            last_msg_time: Optional[float] = None
            conn_time_ms = 0.0

            client_kwargs = {"base_url": base_url, "timeout": 25.0}
            if transport:
                client_kwargs["transport"] = transport

            try:
                async with httpx.AsyncClient(**client_kwargs) as client:
                    async with client.stream(
                        "GET",
                        f"/api/v1/stream/overview?limit={target_messages_per_client}",
                    ) as response:
                        conn_time_ms = (time.perf_counter() - t0) * 1000.0
                        if response.status_code != 200:
                            return StreamClientStats(
                                client_id=cid,
                                connected=False,
                                connection_time_ms=conn_time_ms,
                                messages_received=0,
                                arrival_intervals_ms=[],
                                disconnected_early=True,
                                error=f"HTTP {response.status_code}",
                            )

                        async for line in response.aiter_lines():
                            if line.startswith("data:"):
                                now = time.perf_counter()
                                if last_msg_time is not None:
                                    intervals.append((now - last_msg_time) * 1000.0)
                                last_msg_time = now
                                msg_count += 1
                                if msg_count >= target_messages_per_client:
                                    break

                return StreamClientStats(
                    client_id=cid,
                    connected=True,
                    connection_time_ms=round(conn_time_ms, 2),
                    messages_received=msg_count,
                    arrival_intervals_ms=intervals,
                    disconnected_early=False,
                )
            except Exception as err:
                return StreamClientStats(
                    client_id=cid,
                    connected=conn_time_ms > 0,
                    connection_time_ms=round(conn_time_ms, 2),
                    messages_received=msg_count,
                    arrival_intervals_ms=intervals,
                    disconnected_early=True,
                    error=str(err),
                )

        tasks = [asyncio.create_task(run_single_client(i)) for i in range(concurrent_clients)]
        results = await asyncio.gather(*tasks)
        client_stats.extend(results)

        duration = time.perf_counter() - t_bench_start
        final_rss = self.process.memory_info().rss / (1024 * 1024)
        peak_rss = max(peak_rss, final_rss)

        # Cleanup TCP server if running
        if server and server_thread:
            server.should_exit = True
            server_thread.join(timeout=2.0)

        successful_connections = sum(1 for c in client_stats if c.connected)
        total_msgs = sum(c.messages_received for c in client_stats)
        expected_total = concurrent_clients * target_messages_per_client
        disconnections = sum(1 for c in client_stats if c.disconnected_early)

        conn_times = [c.connection_time_ms for c in client_stats if c.connected]
        avg_conn_time = round(sum(conn_times) / len(conn_times), 2) if conn_times else 0.0

        all_intervals: List[float] = []
        for c in client_stats:
            all_intervals.extend(c.arrival_intervals_ms)

        if all_intervals:
            sorted_intervals = sorted(all_intervals)
            n = len(sorted_intervals)
            p50 = round(sorted_intervals[min(int(n * 0.50), n - 1)], 2)
            p95 = round(sorted_intervals[min(int(n * 0.95), n - 1)], 2)
            p99 = round(sorted_intervals[min(int(n * 0.99), n - 1)], 2)
            mean_int = round(sum(sorted_intervals) / n, 2)
        else:
            p50 = p95 = p99 = mean_int = 0.0

        loss_rate = round(((expected_total - total_msgs) / expected_total) * 100.0, 2) if expected_total > 0 else 0.0

        return ConcurrentStreamResult(
            transport="network_tcp" if use_network_tcp else "in_process_asgi",
            concurrent_clients=concurrent_clients,
            target_messages_per_client=target_messages_per_client,
            connection_success_rate_pct=round((successful_connections / concurrent_clients) * 100.0, 2),
            total_messages_received=total_msgs,
            expected_total_messages=expected_total,
            message_loss_rate_pct=max(0.0, loss_rate),
            disconnection_count=disconnections,
            avg_connection_time_ms=avg_conn_time,
            delivery_interval_p50_ms=p50,
            delivery_interval_p95_ms=p95,
            delivery_interval_p99_ms=p99,
            delivery_interval_mean_ms=mean_int,
            duration_seconds=round(duration, 2),
            peak_memory_mb=round(peak_rss, 2),
        )

    async def run_suite(self) -> Dict[str, ConcurrentStreamResult]:
        """Runs in-process ASGI and real network TCP streaming benchmarks."""
        results: Dict[str, ConcurrentStreamResult] = {}

        # 1. In-Process ASGI Tiers (10, 25, 50, 100)
        for tier in [10, 25, 50, 100]:
            target_msgs = 3 if tier >= 50 else 4
            res = await self.benchmark_concurrency_tier(
                concurrent_clients=tier, target_messages_per_client=target_msgs, use_network_tcp=False
            )
            results[f"asgi_tier_{tier}"] = res

        # 2. Real Network TCP Tiers (10, 25, 50, 100)
        for tier in [10, 25, 50, 100]:
            target_msgs = 3 if tier >= 50 else 4
            res = await self.benchmark_concurrency_tier(
                concurrent_clients=tier, target_messages_per_client=target_msgs, use_network_tcp=True
            )
            results[f"tcp_tier_{tier}"] = res

        return results
