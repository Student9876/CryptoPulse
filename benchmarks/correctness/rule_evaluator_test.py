"""Labeled scenario validation and correctness benchmarking for CryptoPulse Rule Engine.

Validates:
1. Trigger thresholds (>=, <=, exact match)
2. Cooldown suppression
3. Cooldown expiration for recurring rules
4. Auto-deactivation of one-shot (non-recurring) rules
5. Duplicate suppression during sustained above-threshold periods
6. Flapping condition hysteresis (crossing edge resets)
7. Boundary conditions (just below vs exact threshold)
8. Multi-symbol and multi-user isolation
9. Non-trigger noise rejection (false positive immunity)
"""

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.alert_rule import ConditionType, MetricType
from app.rules.cached_rule import CachedRule
from app.rules.evaluator import RuleEngine
from app.schemas.events import AlertEvent, TradeEvent
from app.stream.window_manager import WindowManager
from benchmarks.data.generator import TradeEventGenerator


@dataclass
class ScenarioResult:
    """Detailed outcome of a single labeled scenario test."""

    name: str
    description: str
    total_ticks: int
    expected_triggers: int
    actual_triggers: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    f1_score: float
    passed: bool
    details: str = ""


@dataclass
class CorrectnessReport:
    """Aggregate correctness metrics across all labeled scenarios."""

    total_scenarios: int
    scenarios_passed: int
    total_ticks_evaluated: int
    total_expected_triggers: int
    total_actual_triggers: int
    aggregate_tp: int
    aggregate_fp: int
    aggregate_fn: int
    aggregate_tn: int
    overall_precision: float
    overall_recall: float
    overall_f1: float
    overall_specificity: float
    scenarios: List[ScenarioResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RuleCorrectnessBenchmark:
    """Runs a suite of deterministic, labeled scenarios against RuleEngine & WindowManager."""

    def __init__(self) -> None:
        self.generator = TradeEventGenerator()

    def _execute_scenario(
        self,
        name: str,
        description: str,
        rules: List[CachedRule],
        trades: List[TradeEvent],
        expected_trigger_indices: List[int],
    ) -> ScenarioResult:
        """Executes a scenario tick-by-tick, checking whether triggers match expected ticks."""
        window_manager = WindowManager()
        rule_engine = RuleEngine()

        for r in rules:
            rule_engine.register_rule(r)

        actual_trigger_indices: List[int] = []

        for idx, trade in enumerate(trades):
            window_manager.process_trade(trade)
            metrics = window_manager.get_metrics(trade.symbol)
            if metrics:
                now_ts = trade.timestamp_ms / 1000.0
                alerts = rule_engine.evaluate_metrics(metrics, now_ts=now_ts)
                if alerts:
                    actual_trigger_indices.append(idx)

        # Compute confusion matrix per tick
        expected_set = set(expected_trigger_indices)
        actual_set = set(actual_trigger_indices)

        tp = len(expected_set & actual_set)
        fp = len(actual_set - expected_set)
        fn = len(expected_set - actual_set)
        tn = len(trades) - len(expected_set | actual_set)

        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 1.0
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 1.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else (1.0 if tp == 0 and fp == 0 and fn == 0 else 0.0)

        passed = (fp == 0) and (fn == 0)

        return ScenarioResult(
            name=name,
            description=description,
            total_ticks=len(trades),
            expected_triggers=len(expected_trigger_indices),
            actual_triggers=len(actual_trigger_indices),
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            true_negatives=tn,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            passed=passed,
            details=f"Expected at ticks {expected_trigger_indices}, got {actual_trigger_indices}",
        )

    # 1. Price Level Greater Than
    def scenario_threshold_greater_than(self) -> ScenarioResult:
        rule = CachedRule(
            id=1,
            user_id=101,
            telegram_id=1001,
            symbol="BTCUSDT",
            metric_type=MetricType.PRICE_LEVEL.value,
            condition=ConditionType.GREATER_THAN.value,
            threshold_value=65000.0,
            cooldown_seconds=60,
            is_recurring=False,
        )
        # Ticks: 64900 (no), 64950 (no), 65050 (trigger at tick 2), 65100 (suppressed)
        trades = self.generator.generate_controlled_scenario(
            symbol="BTCUSDT",
            prices=[64900.0, 64950.0, 65050.0, 65100.0],
            time_step_ms=1000,
        )
        return self._execute_scenario(
            name="Threshold Greater Than",
            description="Triggers exactly once when price crosses above target threshold.",
            rules=[rule],
            trades=trades,
            expected_trigger_indices=[2],
        )

    # 2. Price Level Less Than
    def scenario_threshold_less_than(self) -> ScenarioResult:
        rule = CachedRule(
            id=2,
            user_id=102,
            telegram_id=1002,
            symbol="ETHUSDT",
            metric_type=MetricType.PRICE_LEVEL.value,
            condition=ConditionType.LESS_THAN.value,
            threshold_value=2500.0,
            cooldown_seconds=60,
            is_recurring=False,
        )
        trades = self.generator.generate_controlled_scenario(
            symbol="ETHUSDT",
            prices=[2550.0, 2520.0, 2490.0, 2480.0],
            time_step_ms=1000,
        )
        return self._execute_scenario(
            name="Threshold Less Than",
            description="Triggers when price falls below target threshold.",
            rules=[rule],
            trades=trades,
            expected_trigger_indices=[2],
        )

    # 3. Cooldown Suppression (Recurring Rule)
    def scenario_cooldown_suppression(self) -> ScenarioResult:
        rule = CachedRule(
            id=3,
            user_id=103,
            telegram_id=1003,
            symbol="BTCUSDT",
            metric_type=MetricType.PRICE_LEVEL.value,
            condition=ConditionType.GREATER_THAN.value,
            threshold_value=65000.0,
            cooldown_seconds=60,
            is_recurring=True,
        )
        # Ticks at t=0s (65100, trigger), t=10s (65200, cooldown), t=30s (65300, cooldown), t=50s (65400, cooldown)
        trades = self.generator.generate_controlled_scenario(
            symbol="BTCUSDT",
            prices=[65100.0, 65200.0, 65300.0, 65400.0],
            time_step_ms=10_000,
        )
        return self._execute_scenario(
            name="Cooldown Suppression",
            description="Suppresses subsequent triggers within the active cooldown window (60s).",
            rules=[rule],
            trades=trades,
            expected_trigger_indices=[0],
        )

    # 4. Cooldown Expiration for Recurring Rules
    def scenario_cooldown_expiration_recurring(self) -> ScenarioResult:
        rule = CachedRule(
            id=4,
            user_id=104,
            telegram_id=1004,
            symbol="BTCUSDT",
            metric_type=MetricType.PRICE_LEVEL.value,
            condition=ConditionType.GREATER_THAN.value,
            threshold_value=65000.0,
            cooldown_seconds=60,
            is_recurring=True,
        )
        # Ticks: t=0s (65100, trigger), t=30s (65200, cooldown), t=70s (65300, cooldown expired >= 60s, triggers!)
        trades = self.generator.generate_controlled_scenario(
            symbol="BTCUSDT",
            prices=[65100.0, 65200.0, 65300.0],
            time_step_ms=35_000,  # 0s, 35s, 70s
        )
        return self._execute_scenario(
            name="Cooldown Expiration (Recurring)",
            description="Re-triggers on breach after the cooldown interval expires for recurring alerts.",
            rules=[rule],
            trades=trades,
            expected_trigger_indices=[0, 2],
        )

    # 5. One-Shot Auto-Deactivation (Non-Recurring)
    def scenario_non_recurring_one_shot(self) -> ScenarioResult:
        rule = CachedRule(
            id=5,
            user_id=105,
            telegram_id=1005,
            symbol="BTCUSDT",
            metric_type=MetricType.PRICE_LEVEL.value,
            condition=ConditionType.GREATER_THAN.value,
            threshold_value=65000.0,
            cooldown_seconds=60,
            is_recurring=False,
        )
        # Ticks: t=0s (65100, trigger), t=30s (64800, dip below), t=80s (65500, above, but one-shot is disabled!)
        trades = self.generator.generate_controlled_scenario(
            symbol="BTCUSDT",
            prices=[65100.0, 64800.0, 65500.0],
            time_step_ms=40_000,
        )
        return self._execute_scenario(
            name="Non-Recurring One-Shot Deactivation",
            description="One-time alert fires once, unregisters from RAM, and never fires again.",
            rules=[rule],
            trades=trades,
            expected_trigger_indices=[0],
        )

    # 6. Flapping Condition Hysteresis (Resetting State)
    def scenario_flapping_hysteresis(self) -> ScenarioResult:
        rule = CachedRule(
            id=6,
            user_id=106,
            telegram_id=1006,
            symbol="SOLUSDT",
            metric_type=MetricType.PRICE_LEVEL.value,
            condition=ConditionType.GREATER_THAN.value,
            threshold_value=150.0,
            cooldown_seconds=30,
            is_recurring=True,
        )
        # t=0s (151.0, trigger #1)
        # t=10s (149.0, dips below -> disarms active condition)
        # t=35s (152.0, rises above after 30s cooldown -> trigger #2)
        trades = self.generator.generate_controlled_scenario(
            symbol="SOLUSDT",
            prices=[151.0, 149.0, 152.0],
            time_step_ms=17_500,  # 0s, 17.5s, 35s
        )
        return self._execute_scenario(
            name="Flapping Hysteresis",
            description="Re-arms edge trigger when condition dips below threshold and re-crosses after cooldown.",
            rules=[rule],
            trades=trades,
            expected_trigger_indices=[0, 2],
        )

    # 7. Boundary Conditions (Exact Match vs Epsilon Below)
    def scenario_boundary_conditions(self) -> ScenarioResult:
        rule = CachedRule(
            id=7,
            user_id=107,
            telegram_id=1007,
            symbol="BTCUSDT",
            metric_type=MetricType.PRICE_LEVEL.value,
            condition=ConditionType.GREATER_THAN.value,
            threshold_value=65000.0,
            cooldown_seconds=60,
            is_recurring=False,
        )
        # 64999.99 (just below, no trigger), 65000.00 (exact equality, triggers!)
        trades = self.generator.generate_controlled_scenario(
            symbol="BTCUSDT",
            prices=[64999.99, 65000.00],
            time_step_ms=1000,
        )
        return self._execute_scenario(
            name="Boundary Exact Equality",
            description="Verifies >= boundary: exact threshold value triggers, 0.01 below does not.",
            rules=[rule],
            trades=trades,
            expected_trigger_indices=[1],
        )

    # 8. Duplicate / Sustained Sequence Suppression
    def scenario_duplicate_suppression(self) -> ScenarioResult:
        rule = CachedRule(
            id=8,
            user_id=108,
            telegram_id=1008,
            symbol="ETHUSDT",
            metric_type=MetricType.PRICE_LEVEL.value,
            condition=ConditionType.GREATER_THAN.value,
            threshold_value=2500.0,
            cooldown_seconds=300,
            is_recurring=False,
        )
        # 50 consecutive ticks above threshold within 50 seconds
        prices = [2510.0 + (i * 0.1) for i in range(50)]
        trades = self.generator.generate_controlled_scenario(
            symbol="ETHUSDT",
            prices=prices,
            time_step_ms=1000,
        )
        return self._execute_scenario(
            name="Duplicate Flood Suppression",
            description="Blocks 49 consecutive ticks above threshold within cooldown (0 duplicate alerts).",
            rules=[rule],
            trades=trades,
            expected_trigger_indices=[0],
        )

    # 9. Non-Trigger Rejection (False Positive Rejection)
    def scenario_non_trigger_noise(self) -> ScenarioResult:
        rule = CachedRule(
            id=9,
            user_id=109,
            telegram_id=1009,
            symbol="BTCUSDT",
            metric_type=MetricType.PRICE_LEVEL.value,
            condition=ConditionType.GREATER_THAN.value,
            threshold_value=70000.0,
            cooldown_seconds=60,
            is_recurring=True,
        )
        # 100 ticks hovering between 64000 and 66000, never touching 70000
        rng = TradeEventGenerator(None).rng
        prices = [round(65000.0 + rng.uniform(-1000, 1000), 2) for _ in range(100)]
        trades = self.generator.generate_controlled_scenario(
            symbol="BTCUSDT",
            prices=prices,
            time_step_ms=1000,
        )
        return self._execute_scenario(
            name="Non-Trigger Noise Rejection",
            description="Verifies 100% false positive rejection (0 triggers for noise below target).",
            rules=[rule],
            trades=trades,
            expected_trigger_indices=[],
        )

    # 10. Multi-Symbol Cross-Talk Isolation
    def scenario_multi_symbol_isolation(self) -> ScenarioResult:
        btc_rule = CachedRule(
            id=10,
            user_id=110,
            telegram_id=1010,
            symbol="BTCUSDT",
            metric_type=MetricType.PRICE_LEVEL.value,
            condition=ConditionType.GREATER_THAN.value,
            threshold_value=65000.0,
            cooldown_seconds=60,
            is_recurring=False,
        )
        eth_rule = CachedRule(
            id=11,
            user_id=111,
            telegram_id=1011,
            symbol="ETHUSDT",
            metric_type=MetricType.PRICE_LEVEL.value,
            condition=ConditionType.GREATER_THAN.value,
            threshold_value=3000.0,
            cooldown_seconds=60,
            is_recurring=False,
        )
        # Trades alternate BTC (triggers at tick 0) and ETH (does NOT trigger at 2500)
        trades = [
            TradeEvent(symbol="BTCUSDT", price=65100.0, quantity=1.0, timestamp_ms=1700000000000, is_buyer_maker=False),
            TradeEvent(symbol="ETHUSDT", price=2500.0, quantity=5.0, timestamp_ms=1700000001000, is_buyer_maker=False),
            TradeEvent(symbol="BTCUSDT", price=65200.0, quantity=1.0, timestamp_ms=1700000002000, is_buyer_maker=False),
            TradeEvent(symbol="ETHUSDT", price=2600.0, quantity=5.0, timestamp_ms=1700000003000, is_buyer_maker=False),
        ]
        return self._execute_scenario(
            name="Multi-Symbol Isolation",
            description="Guarantees events on one symbol never falsely trigger rules on another.",
            rules=[btc_rule, eth_rule],
            trades=trades,
            expected_trigger_indices=[0],
        )

    def run_all_scenarios(self) -> CorrectnessReport:
        """Runs all 10 scenario tests and aggregates precision, recall, and confusion matrix."""
        scenarios = [
            self.scenario_threshold_greater_than(),
            self.scenario_threshold_less_than(),
            self.scenario_cooldown_suppression(),
            self.scenario_cooldown_expiration_recurring(),
            self.scenario_non_recurring_one_shot(),
            self.scenario_flapping_hysteresis(),
            self.scenario_boundary_conditions(),
            self.scenario_duplicate_suppression(),
            self.scenario_non_trigger_noise(),
            self.scenario_multi_symbol_isolation(),
        ]

        total_scenarios = len(scenarios)
        scenarios_passed = sum(1 for s in scenarios if s.passed)
        total_ticks = sum(s.total_ticks for s in scenarios)
        total_expected = sum(s.expected_triggers for s in scenarios)
        total_actual = sum(s.actual_triggers for s in scenarios)

        agg_tp = sum(s.true_positives for s in scenarios)
        agg_fp = sum(s.false_positives for s in scenarios)
        agg_fn = sum(s.false_negatives for s in scenarios)
        agg_tn = sum(s.true_negatives for s in scenarios)

        overall_precision = (agg_tp / (agg_tp + agg_fp)) if (agg_tp + agg_fp) > 0 else 1.0
        overall_recall = (agg_tp / (agg_tp + agg_fn)) if (agg_tp + agg_fn) > 0 else 1.0
        overall_f1 = (
            (2 * overall_precision * overall_recall / (overall_precision + overall_recall))
            if (overall_precision + overall_recall) > 0
            else 0.0
        )
        overall_specificity = (agg_tn / (agg_tn + agg_fp)) if (agg_tn + agg_fp) > 0 else 1.0

        return CorrectnessReport(
            total_scenarios=total_scenarios,
            scenarios_passed=scenarios_passed,
            total_ticks_evaluated=total_ticks,
            total_expected_triggers=total_expected,
            total_actual_triggers=total_actual,
            aggregate_tp=agg_tp,
            aggregate_fp=agg_fp,
            aggregate_fn=agg_fn,
            aggregate_tn=agg_tn,
            overall_precision=round(overall_precision, 4),
            overall_recall=round(overall_recall, 4),
            overall_f1=round(overall_f1, 4),
            overall_specificity=round(overall_specificity, 4),
            scenarios=scenarios,
        )
