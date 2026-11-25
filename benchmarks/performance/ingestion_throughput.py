"""High-precision event processing throughput and latency benchmark with 5 repetitions,

cold-start vs steady-state separation, baseline vs optimized comparison,
and 10K, 100K, and 1M event workloads.
"""

import math
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.models.alert_rule import ConditionType, MetricType
from app.rules.cached_rule import CachedRule
from app.rules.evaluator import RuleEngine
from app.schemas.events import TradeEvent
from app.stream.symbol_window import BaselineSymbolWindow, OptimizedSymbolWindow
from app.stream.window_manager import WindowManager
from benchmarks.data.generator import ReplayConfig, TradeEventGenerator


@dataclass
class RepetitionStats:
    """Aggregated statistics across multiple measured repetitions."""

    repetition_count: int
    median_throughput_eps: float
    mean_throughput_eps: float
    min_throughput_eps: float
    max_throughput_eps: float
    std_throughput_eps: float
    median_p50_us: float
    median_p90_us: float
    median_p95_us: float
    median_p99_us: float
    median_p999_us: float
    median_mean_us: float
    peak_rss_mb: float
    cpu_percent: float


@dataclass
class BenchmarkExecutionResult:
    """Full result for a benchmark configuration combining repetitions and metadata."""

    name: str
    engine: str  # 'baseline' or 'optimized'
    mode: str    # 'window_only', 'window_metrics', 'full_pipeline'
    phase: str   # 'cold_start' or 'steady_state'
    event_count: int
    active_rules_count: int
    stats: RepetitionStats

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IngestionBenchmark:
    """Rigorously measures sustained throughput, latency percentiles, CPU, and RAM."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.generator = TradeEventGenerator(ReplayConfig(seed=seed))
        self.process = psutil.Process(os.getpid())

    def _sample_memory_mb(self) -> float:
        return round(self.process.memory_info().rss / (1024 * 1024), 2)

    def _create_sample_rules(self, count: int) -> List[CachedRule]:
        rules: List[CachedRule] = []
        metrics = [
            (MetricType.PRICE_LEVEL.value, ConditionType.GREATER_THAN.value, 65000.0),
            (MetricType.PRICE_LEVEL.value, ConditionType.LESS_THAN.value, 64000.0),
            (MetricType.PRICE_CHANGE.value, ConditionType.GREATER_THAN.value, 2.0),
            (MetricType.VOLUME_SPIKE.value, ConditionType.GREATER_THAN.value, 1.5),
            (MetricType.TAKER_BUY_RATIO.value, ConditionType.GREATER_THAN.value, 60.0),
        ]
        for i in range(count):
            mt, cond, thresh = metrics[i % len(metrics)]
            rules.append(
                CachedRule(
                    id=i + 1,
                    user_id=100 + (i % 10),
                    telegram_id=1000 + (i % 10),
                    symbol="BTCUSDT" if i % 2 == 0 else "ETHUSDT",
                    metric_type=mt,
                    condition=cond,
                    threshold_value=thresh,
                    cooldown_seconds=60,
                    is_recurring=True,
                )
            )
        return rules

    def _run_single_pass(
        self,
        engine_type: str,
        mode: str,
        phase: str,
        events: List[TradeEvent],
        prewarm_events: Optional[List[TradeEvent]],
        rules: List[CachedRule],
    ) -> Tuple[float, List[int], float, float]:
        """Runs one measurement pass, returning (duration_sec, latencies_ns, cpu_pct, peak_rss_mb)."""
        window_cls = OptimizedSymbolWindow if engine_type == "optimized" else BaselineSymbolWindow
        wm = WindowManager(symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"], window_cls=window_cls)
        re = RuleEngine()
        for r in rules:
            re.register_rule(r)

        # Pre-warm window for steady-state
        if phase == "steady_state" and prewarm_events:
            for trade in prewarm_events:
                wm.process_trade(trade)
                if mode in ("window_metrics", "full_pipeline"):
                    wm.get_metrics(trade.symbol)

        rss_start = self._sample_memory_mb()
        self.process.cpu_percent(interval=None)

        event_count = len(events)
        latencies_ns: List[int] = [0] * event_count
        peak_rss = rss_start

        t_start = time.perf_counter()

        for idx, trade in enumerate(events):
            t0 = time.perf_counter_ns()

            wm.process_trade(trade)
            if mode == "window_metrics":
                wm.get_metrics(trade.symbol)
            elif mode == "full_pipeline":
                m = wm.get_metrics(trade.symbol)
                if m:
                    re.evaluate_metrics(m, now_ts=trade.timestamp_ms / 1000.0)

            t1 = time.perf_counter_ns()
            latencies_ns[idx] = t1 - t0

            if idx % 10_000 == 0:
                cur_rss = self._sample_memory_mb()
                if cur_rss > peak_rss:
                    peak_rss = cur_rss

        t_end = time.perf_counter()
        cpu_pct = self.process.cpu_percent(interval=None)
        peak_rss = max(peak_rss, self._sample_memory_mb())

        duration = t_end - t_start
        return duration, latencies_ns, cpu_pct, peak_rss

    def benchmark_workload(
        self,
        name: str,
        engine_type: str,
        mode: str,
        phase: str = "cold_start",
        event_count: int = 10_000,
        rule_count: int = 0,
        repetitions: int = 5,
    ) -> BenchmarkExecutionResult:
        """Executes measured repetitions of a specific workload and aggregates statistics."""
        # Pre-generate prewarm and benchmark events in RAM
        prewarm_events: Optional[List[TradeEvent]] = None
        start_time_ms = 1_700_000_000_000

        if phase == "steady_state":
            # 10k trades at 100ms interval = 1,000s (> 15 minutes / 900s window saturation)
            prewarm_events = self.generator.generate_events(
                ReplayConfig(seed=self.seed + 100, event_count=10_000, interval_ms=100, symbols=["BTCUSDT", "ETHUSDT"])
            )
            # Ensure benchmark events continue chronologically from where prewarm finished
            start_time_ms = prewarm_events[-1].timestamp_ms + 100

        events = self.generator.generate_events(
            ReplayConfig(seed=self.seed, event_count=event_count, interval_ms=100, start_time_ms=start_time_ms, symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        )
        rules = self._create_sample_rules(rule_count)

        throughputs: List[float] = []
        p50s: List[float] = []
        p90s: List[float] = []
        p95s: List[float] = []
        p99s: List[float] = []
        p999s: List[float] = []
        means: List[float] = []
        cpus: List[float] = []
        peaks: List[float] = []

        for rep in range(repetitions):
            duration, latencies_ns, cpu_pct, peak_rss = self._run_single_pass(
                engine_type=engine_type,
                mode=mode,
                phase=phase,
                events=events,
                prewarm_events=prewarm_events,
                rules=rules,
            )

            throughput = event_count / duration if duration > 0 else 0.0
            throughputs.append(throughput)
            cpus.append(cpu_pct)
            peaks.append(peak_rss)

            # Latency percentiles in microseconds
            sorted_lat = sorted(latencies_ns)
            n = len(sorted_lat)
            p50s.append(sorted_lat[int(n * 0.50)] / 1000.0)
            p90s.append(sorted_lat[int(n * 0.90)] / 1000.0)
            p95s.append(sorted_lat[int(n * 0.95)] / 1000.0)
            p99s.append(sorted_lat[int(n * 0.99)] / 1000.0)
            p999s.append(sorted_lat[min(int(n * 0.999), n - 1)] / 1000.0)
            means.append((sum(sorted_lat) / n) / 1000.0)

        stats = RepetitionStats(
            repetition_count=repetitions,
            median_throughput_eps=round(statistics.median(throughputs), 2),
            mean_throughput_eps=round(statistics.mean(throughputs), 2),
            min_throughput_eps=round(min(throughputs), 2),
            max_throughput_eps=round(max(throughputs), 2),
            std_throughput_eps=round(statistics.stdev(throughputs), 2) if len(throughputs) > 1 else 0.0,
            median_p50_us=round(statistics.median(p50s), 2),
            median_p90_us=round(statistics.median(p90s), 2),
            median_p95_us=round(statistics.median(p95s), 2),
            median_p99_us=round(statistics.median(p99s), 2),
            median_p999_us=round(statistics.median(p999s), 2),
            median_mean_us=round(statistics.median(means), 2),
            peak_rss_mb=round(max(peaks), 2),
            cpu_percent=round(statistics.median(cpus), 2),
        )

        return BenchmarkExecutionResult(
            name=name,
            engine=engine_type,
            mode=mode,
            phase=phase,
            event_count=event_count,
            active_rules_count=rule_count,
            stats=stats,
        )

    def run_comparative_suite(self) -> Dict[str, BenchmarkExecutionResult]:
        """Runs the complete before-and-after baseline vs optimized matrix."""
        results: Dict[str, BenchmarkExecutionResult] = {}

        # -------------------------------------------------------------
        # Part A: Isolated Window Ingestion (Baseline vs Optimized)
        # -------------------------------------------------------------
        results["base_window_only_10k"] = self.benchmark_workload(
            name="Baseline Window Ingestion Only (10k)",
            engine_type="baseline",
            mode="window_only",
            phase="cold_start",
            event_count=10_000,
            repetitions=5,
        )
        results["opt_window_only_10k"] = self.benchmark_workload(
            name="Optimized Window Ingestion Only (10k)",
            engine_type="optimized",
            mode="window_only",
            phase="cold_start",
            event_count=10_000,
            repetitions=5,
        )

        # -------------------------------------------------------------
        # Part B: Window + Metrics (Baseline vs Optimized) - Cold vs Steady
        # -------------------------------------------------------------
        results["base_window_metrics_cold_10k"] = self.benchmark_workload(
            name="Baseline Window + Metrics Cold (10k)",
            engine_type="baseline",
            mode="window_metrics",
            phase="cold_start",
            event_count=10_000,
            repetitions=2,  # Baseline takes ~32s per rep
        )
        results["opt_window_metrics_cold_10k"] = self.benchmark_workload(
            name="Optimized Window + Metrics Cold (10k)",
            engine_type="optimized",
            mode="window_metrics",
            phase="cold_start",
            event_count=10_000,
            repetitions=5,
        )

        results["base_window_metrics_steady_10k"] = self.benchmark_workload(
            name="Baseline Window + Metrics Steady (10k)",
            engine_type="baseline",
            mode="window_metrics",
            phase="steady_state",
            event_count=10_000,
            repetitions=2,  # Baseline steady-state takes ~45s per rep
        )
        results["opt_window_metrics_steady_10k"] = self.benchmark_workload(
            name="Optimized Window + Metrics Steady (10k)",
            engine_type="optimized",
            mode="window_metrics",
            phase="steady_state",
            event_count=10_000,
            repetitions=5,
        )

        # -------------------------------------------------------------
        # Part C: Full Pipeline Scaling with 5, 25, 100 Rules (10k)
        # -------------------------------------------------------------
        for rule_count in [5, 25, 100]:
            results[f"base_full_{rule_count}_rules_10k"] = self.benchmark_workload(
                name=f"Baseline Full Pipeline ({rule_count} Rules, 10k)",
                engine_type="baseline",
                mode="full_pipeline",
                phase="steady_state",
                event_count=10_000,
                rule_count=rule_count,
                repetitions=2,
            )
            results[f"opt_full_{rule_count}_rules_10k"] = self.benchmark_workload(
                name=f"Optimized Full Pipeline ({rule_count} Rules, 10k)",
                engine_type="optimized",
                mode="full_pipeline",
                phase="steady_state",
                event_count=10_000,
                rule_count=rule_count,
                repetitions=5,
            )

        # -------------------------------------------------------------
        # Part D: High-Volume Scale (100K and 1M Events on Optimized Engine)
        # -------------------------------------------------------------
        results["opt_window_only_100k"] = self.benchmark_workload(
            name="Optimized Window Ingestion Only (100k)",
            engine_type="optimized",
            mode="window_only",
            phase="steady_state",
            event_count=100_000,
            repetitions=5,
        )
        results["opt_window_metrics_100k"] = self.benchmark_workload(
            name="Optimized Window + Metrics (100k)",
            engine_type="optimized",
            mode="window_metrics",
            phase="steady_state",
            event_count=100_000,
            repetitions=5,
        )
        results["opt_full_25_rules_100k"] = self.benchmark_workload(
            name="Optimized Full Pipeline (25 Rules, 100k)",
            engine_type="optimized",
            mode="full_pipeline",
            phase="steady_state",
            event_count=100_000,
            rule_count=25,
            repetitions=5,
        )

        # 1 Million Events Workload
        results["opt_window_only_1m"] = self.benchmark_workload(
            name="Optimized Window Ingestion Only (1M)",
            engine_type="optimized",
            mode="window_only",
            phase="steady_state",
            event_count=1_000_000,
            repetitions=5,
        )

        return results
