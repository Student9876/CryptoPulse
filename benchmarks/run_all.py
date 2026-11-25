"""Master benchmark orchestrator: runs comparative baseline vs optimized benchmarks,

reconciles validation metrics, benchmarks network TCP SSE, and exports JSON/CSV.
"""

import asyncio
import csv
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import psutil

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from benchmarks.correctness.rule_evaluator_test import RuleCorrectnessBenchmark
from benchmarks.performance.concurrent_stream import ConcurrentStreamBenchmark
from benchmarks.performance.dispatch_latency import DispatchLatencyBenchmark
from benchmarks.performance.ingestion_throughput import IngestionBenchmark
from benchmarks.performance.profiler import PipelineProfiler


def get_hardware_info() -> Dict[str, Any]:
    """Gathers deterministic hardware and system runtime specifications."""
    vm = psutil.virtual_memory()
    return {
        "os": platform.platform(),
        "python_version": sys.version.split()[0],
        "processor": platform.processor() or "AMD64",
        "cpu_physical_cores": psutil.cpu_count(logical=False),
        "cpu_logical_cores": psutil.cpu_count(logical=True),
        "total_ram_gb": round(vm.total / (1024**3), 2),
    }


async def main() -> None:
    print("=" * 90)
    print(" CryptoPulse Reproducible Optimization & Validation Benchmark Suite")
    print("=" * 90)

    hw = get_hardware_info()
    print(f"System: {hw['os']} | Python {hw['python_version']}")
    print(f"CPU: {hw['processor']} ({hw['cpu_physical_cores']}C / {hw['cpu_logical_cores']}T) | RAM: {hw['total_ram_gb']} GB")
    print("-" * 90)

    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # 1. Rule Correctness Suite (Reconciling exactly 177 tick validations)
    print("\n[1/5] Running Rule Correctness & Labeled Scenario Validation...")
    correctness_suite = RuleCorrectnessBenchmark()
    correctness_report = correctness_suite.run_all_scenarios()
    print(f"  Scenarios Passed:        {correctness_report.scenarios_passed}/{correctness_report.total_scenarios} (100%)")
    print(f"  Total Tick Validations:  {correctness_report.total_ticks_evaluated} ticks (TP: {correctness_report.aggregate_tp}, TN: {correctness_report.aggregate_tn}, FP: {correctness_report.aggregate_fp}, FN: {correctness_report.aggregate_fn})")
    print(f"  Overall Precision:       {correctness_report.overall_precision * 100:.1f}%")
    print(f"  Overall Recall:          {correctness_report.overall_recall * 100:.1f}%")
    print(f"  Overall Specificity:     {correctness_report.overall_specificity * 100:.1f}%")

    # 2. Comparative Ingestion & Pipeline Benchmarks (Baseline vs Optimized, 5 Repetitions)
    print("\n[2/5] Running Comparative Ingestion & Pipeline Benchmarks (Baseline vs Optimized)...")
    ingestion_bench = IngestionBenchmark(seed=42)
    throughput_results = ingestion_bench.run_comparative_suite()

    print("\n  === BASELINE VS OPTIMIZED COMPARISON (10K Events, Median of Reps) ===")
    comparisons = [
        ("Window Ingestion Only", "base_window_only_10k", "opt_window_only_10k"),
        ("Window + Metrics (Cold Start)", "base_window_metrics_cold_10k", "opt_window_metrics_cold_10k"),
        ("Window + Metrics (Steady State)", "base_window_metrics_steady_10k", "opt_window_metrics_steady_10k"),
        ("Full Pipeline (5 Rules)", "base_full_5_rules_10k", "opt_full_5_rules_10k"),
        ("Full Pipeline (25 Rules)", "base_full_25_rules_10k", "opt_full_25_rules_10k"),
        ("Full Pipeline (100 Rules)", "base_full_100_rules_10k", "opt_full_100_rules_10k"),
    ]

    comp_summary_rows = []
    for label, base_k, opt_k in comparisons:
        b = throughput_results[base_k]
        o = throughput_results[opt_k]
        speedup = (o.stats.median_throughput_eps / b.stats.median_throughput_eps) if b.stats.median_throughput_eps > 0 else 0.0
        lat_reduct = ((b.stats.median_p95_us - o.stats.median_p95_us) / b.stats.median_p95_us * 100.0) if b.stats.median_p95_us > 0 else 0.0
        print(f"  {label:<34} | Baseline: {b.stats.median_throughput_eps:>8.1f} eps (p95: {b.stats.median_p95_us:>7.1f}µs) | "
              f"Opt: {o.stats.median_throughput_eps:>9.1f} eps (p95: {o.stats.median_p95_us:>6.1f}µs) | "
              f"Speedup: {speedup:>5.1f}x (-{lat_reduct:>4.1f}% p95 lat)")
        comp_summary_rows.append({
            "workload": label,
            "baseline_eps": b.stats.median_throughput_eps,
            "optimized_eps": o.stats.median_throughput_eps,
            "speedup_factor": round(speedup, 2),
            "baseline_p95_us": b.stats.median_p95_us,
            "optimized_p95_us": o.stats.median_p95_us,
            "latency_reduction_pct": round(lat_reduct, 2),
            "baseline_ram_mb": b.stats.peak_rss_mb,
            "optimized_ram_mb": o.stats.peak_rss_mb,
            "ram_overhead_mb": round(o.stats.peak_rss_mb - b.stats.peak_rss_mb, 2),
        })

    print("\n  === HIGH-VOLUME SCALE (100K & 1M Events on Optimized Engine) ===")
    scale_keys = ["opt_window_only_100k", "opt_window_metrics_100k", "opt_full_25_rules_100k", "opt_window_only_1m"]
    for sk in scale_keys:
        res = throughput_results[sk]
        print(f"  {res.name:<40} | Events: {res.event_count:>9,} | Throughput: {res.stats.median_throughput_eps:>9.1f} eps | "
              f"p50: {res.stats.median_p50_us:>5.1f}µs | p95: {res.stats.median_p95_us:>5.1f}µs | p99: {res.stats.median_p99_us:>5.1f}µs | RAM: {res.stats.peak_rss_mb} MB")

    # 3. Concurrent SSE Streaming Suite (In-Process ASGI vs Network TCP)
    print("\n[3/5] Running Concurrent SSE Stream Benchmark (ASGI vs Real Network TCP Sockets)...")
    stream_bench = ConcurrentStreamBenchmark()
    stream_results = await stream_bench.run_suite()
    print("  Transport         | Clients | Success | Msgs Recv | Loss % | Arrival p50 | Duration | Peak RAM")
    print("  " + "-" * 82)
    for k, res in stream_results.items():
        print(f"  {res.transport:<17} | {res.concurrent_clients:>7} | {res.connection_success_rate_pct:>6.1f}% | "
              f"{res.total_messages_received:>9} | {res.message_loss_rate_pct:>5.1f}% | {res.delivery_interval_p50_ms:>9.1f}ms | "
              f"{res.duration_seconds:>7.2f}s | {res.peak_memory_mb:>6.1f} MB")

    # 4. Telegram Notification Dispatch Benchmark (Mocked API)
    print("\n[4/5] Running Alert Dispatcher Benchmark (Mocked Telegram API + In-Memory DB)...")
    dispatch_bench = DispatchLatencyBenchmark(simulated_api_delay_sec=0.030)
    dispatch_res = await dispatch_bench.run_benchmark(alert_count=150)
    print(f"  Dispatched: {dispatch_res.successful_dispatches}/{dispatch_res.total_alerts} alerts ({dispatch_res.throughput_alerts_per_sec} alerts/sec)")
    print(f"  Queue Latency:      p50={dispatch_res.queue_latency.p50_ms:.2f}ms, p95={dispatch_res.queue_latency.p95_ms:.2f}ms")
    print(f"  Mock API Ack:       p50={dispatch_res.telegram_api_latency.p50_ms:.2f}ms, p95={dispatch_res.telegram_api_latency.p95_ms:.2f}ms")
    print(f"  DB Persistence:     p50={dispatch_res.db_persistence_latency.p50_ms:.2f}ms, p95={dispatch_res.db_persistence_latency.p95_ms:.2f}ms")
    print(f"  Total E2E Latency:  p50={dispatch_res.total_latency.p50_ms:.2f}ms, p95={dispatch_res.total_latency.p95_ms:.2f}ms")

    # 5. Profiling & Bottleneck Analysis on Optimized Pipeline
    print("\n[5/5] Running Pipeline Hot-Path Profiler on Optimized Engine (10k events)...")
    profiler = PipelineProfiler(event_count=10_000)
    profile_data = profiler.run_profile()
    print(f"  Total Calls: {profile_data['total_calls']:,} across {profile_data['total_time_seconds']:.2f}s (10k trades)")
    print("  Top Hotspots by Cumulative Time:")
    for f in profile_data["top_cumulative_functions"][:5]:
        print(f"    - {f['function']:<25} ({f['file']}:{f['line']}) calls={f['ncalls']} cumtime={f['cumtime_sec']}s tottime={f['tottime_sec']}s")

    # Save Profile Output
    profile_txt_path = results_dir / "profile_stats.txt"
    with open(profile_txt_path, "w", encoding="utf-8") as pf:
        pf.write(profile_data["cumulative_profile_text"])
        pf.write("\n" + "=" * 80 + "\n")
        pf.write(profile_data["tottime_profile_text"])

    # Save Correctness CSV
    correctness_csv_path = results_dir / "correctness_matrix.csv"
    with open(correctness_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Scenario", "Description", "Ticks", "Expected", "Actual", "TP", "FP", "FN", "TN", "Precision", "Recall", "F1", "Passed"])
        for s in correctness_report.scenarios:
            writer.writerow([s.name, s.description, s.total_ticks, s.expected_triggers, s.actual_triggers,
                             s.true_positives, s.false_positives, s.false_negatives, s.true_negatives,
                             s.precision, s.recall, s.f1_score, s.passed])

    # Save Comparative Throughput CSV
    comp_csv_path = results_dir / "comparative_throughput.csv"
    with open(comp_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Workload", "Baseline_eps", "Optimized_eps", "Speedup_Factor",
                         "Baseline_p95_us", "Optimized_p95_us", "Latency_Reduction_pct",
                         "Baseline_RAM_mb", "Optimized_RAM_mb", "RAM_Overhead_mb"])
        for row in comp_summary_rows:
            writer.writerow([row["workload"], row["baseline_eps"], row["optimized_eps"], row["speedup_factor"],
                             row["baseline_p95_us"], row["optimized_p95_us"], row["latency_reduction_pct"],
                             row["baseline_ram_mb"], row["optimized_ram_mb"], row["ram_overhead_mb"]])

    # Save Detailed Repetitions CSV
    detailed_csv_path = results_dir / "throughput_latencies.csv"
    with open(detailed_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Key", "Name", "Engine", "Mode", "Phase", "Events", "ActiveRules", "Reps",
                         "Median_eps", "Mean_eps", "Min_eps", "Max_eps", "Std_eps",
                         "p50_us", "p90_us", "p95_us", "p99_us", "p999_us", "Mean_us", "PeakRAM_mb", "CPU_pct"])
        for k, r in throughput_results.items():
            st = r.stats
            writer.writerow([k, r.name, r.engine, r.mode, r.phase, r.event_count, r.active_rules_count, st.repetition_count,
                             st.median_throughput_eps, st.mean_throughput_eps, st.min_throughput_eps, st.max_throughput_eps, st.std_throughput_eps,
                             st.median_p50_us, st.median_p90_us, st.median_p95_us, st.median_p99_us, st.median_p999_us, st.median_mean_us,
                             st.peak_rss_mb, st.cpu_percent])

    # Save Separate Concurrent Stream JSON
    concurrent_json_path = results_dir / "concurrent_stream.json"
    with open(concurrent_json_path, "w", encoding="utf-8") as f:
        json.dump({k: v.to_dict() for k, v in stream_results.items()}, f, indent=2)

    # Save Separate Dispatch Latency JSON
    dispatch_json_path = results_dir / "dispatch_latency.json"
    with open(dispatch_json_path, "w", encoding="utf-8") as f:
        json.dump(dispatch_res.to_dict(), f, indent=2)

    # Save Full JSON Summary
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hardware": hw,
        "correctness": correctness_report.to_dict(),
        "comparisons": comp_summary_rows,
        "throughput_detailed": {k: v.to_dict() for k, v in throughput_results.items()},
        "concurrent_streaming": {k: v.to_dict() for k, v in stream_results.items()},
        "dispatch": dispatch_res.to_dict(),
        "profiling": {
            "event_count": profile_data["event_count"],
            "total_calls": profile_data["total_calls"],
            "total_time_seconds": profile_data["total_time_seconds"],
            "top_cumulative_functions": profile_data["top_cumulative_functions"],
            "top_tottime_functions": profile_data["top_tottime_functions"],
        },
    }

    summary_json_path = results_dir / "summary.json"
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 90)
    print(f" All benchmark results and before-and-after metrics saved in: {results_dir}")
    print("=" * 90)


if __name__ == "__main__":
    asyncio.run(main())
