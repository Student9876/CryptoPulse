"""Performance profiler identifying CPU and algorithmic bottlenecks in the pipeline."""

import cProfile
import io
import pstats
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.models.alert_rule import ConditionType, MetricType
from app.rules.cached_rule import CachedRule
from app.rules.evaluator import RuleEngine
from app.stream.window_manager import WindowManager
from benchmarks.data.generator import ReplayConfig, TradeEventGenerator


class PipelineProfiler:
    """Profiles the ingestion, analytics, and rule evaluation hot path with cProfile."""

    def __init__(self, event_count: int = 10_000, seed: int = 42) -> None:
        self.event_count = event_count
        self.generator = TradeEventGenerator(ReplayConfig(seed=seed, event_count=event_count))

    def run_profile(self) -> Dict[str, Any]:
        """Profiles the full pipeline and extracts top bottleneck functions."""
        events = self.generator.generate_events()

        wm = WindowManager()
        re = RuleEngine()

        # Register sample rules
        rules = [
            CachedRule(1, 100, 1000, "BTCUSDT", MetricType.PRICE_LEVEL.value, ConditionType.GREATER_THAN.value, 65000.0, 300, 60, True),
            CachedRule(2, 100, 1000, "BTCUSDT", MetricType.PRICE_CHANGE.value, ConditionType.GREATER_THAN.value, 1.5, 300, 60, True),
            CachedRule(3, 101, 1001, "ETHUSDT", MetricType.VOLUME_SPIKE.value, ConditionType.GREATER_THAN.value, 2.0, 300, 60, True),
            CachedRule(4, 102, 1002, "SOLUSDT", MetricType.TAKER_BUY_RATIO.value, ConditionType.GREATER_THAN.value, 55.0, 300, 60, True),
        ]
        for r in rules:
            re.register_rule(r)

        profiler = cProfile.Profile()
        profiler.enable()

        for trade in events:
            wm.process_trade(trade)
            metrics = wm.get_metrics(trade.symbol)
            if metrics:
                re.evaluate_metrics(metrics, now_ts=trade.timestamp_ms / 1000.0)

        profiler.disable()

        # Format stats to stream
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats(pstats.SortKey.CUMULATIVE)
        ps.print_stats(30)
        cumulative_output = s.getvalue()

        s_tot = io.StringIO()
        ps_tot = pstats.Stats(profiler, stream=s_tot).sort_stats(pstats.SortKey.TIME)
        ps_tot.print_stats(30)
        tottime_output = s_tot.getvalue()

        # Parse top functions
        top_cum_functions: List[Dict[str, Any]] = []
        for func, (cc, nc, tt, ct, callers) in sorted(ps.stats.items(), key=lambda item: item[1][3], reverse=True)[:15]:
            file_name, line_no, func_name = func
            top_cum_functions.append({
                "function": func_name,
                "file": Path(file_name).name if file_name else "<built-in>",
                "line": line_no,
                "ncalls": nc,
                "tottime_sec": round(tt, 4),
                "cumtime_sec": round(ct, 4),
            })

        top_tot_functions: List[Dict[str, Any]] = []
        for func, (cc, nc, tt, ct, callers) in sorted(ps.stats.items(), key=lambda item: item[1][2], reverse=True)[:15]:
            file_name, line_no, func_name = func
            top_tot_functions.append({
                "function": func_name,
                "file": Path(file_name).name if file_name else "<built-in>",
                "line": line_no,
                "ncalls": nc,
                "tottime_sec": round(tt, 4),
                "cumtime_sec": round(ct, 4),
            })

        return {
            "event_count": self.event_count,
            "total_calls": ps.total_calls,
            "total_time_seconds": round(ps.total_tt, 4),
            "top_cumulative_functions": top_cum_functions,
            "top_tottime_functions": top_tot_functions,
            "cumulative_profile_text": cumulative_output,
            "tottime_profile_text": tottime_output,
        }
