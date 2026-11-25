"""Integration test ensuring benchmark correctness suite passes within pytest."""

import pytest
from benchmarks.correctness.rule_evaluator_test import RuleCorrectnessBenchmark


def test_rule_evaluator_correctness_suite():
    """Validates that all labeled scenarios in the benchmark suite pass with 100% precision and recall."""
    benchmark = RuleCorrectnessBenchmark()
    report = benchmark.run_all_scenarios()

    assert report.scenarios_passed == report.total_scenarios, (
        f"Failed {report.total_scenarios - report.scenarios_passed} scenarios: "
        f"{[s.name for s in report.scenarios if not s.passed]}"
    )
    assert report.overall_precision == 1.0
    assert report.overall_recall == 1.0
    assert report.aggregate_fp == 0
    assert report.aggregate_fn == 0
