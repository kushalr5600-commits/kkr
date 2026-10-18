"""P2 tests: fork isolation, normal/stress pairing, three scenario behaviours, bounded fragility."""
from __future__ import annotations

from tests.fixtures import expect_raises, repo

from backend.shared import config
from backend.shared.errors import SimulationError
from backend.simulation import physics
from backend.simulation.crash_test import CrashTestEngine
from backend.simulation.forks import BaselineFork, RealityForkGenerator
from backend.simulation.fragility import FragilitySearch, verify_monotone


def _fork(path, util) -> BaselineFork:
    return BaselineFork(
        transaction_id="T", transaction_type="wire_transfer", amount=100.0,
        path_services=tuple(path), utilization=dict(util), background=dict(util), recent_count=0,
    )


def _real_baseline(split="validation", index=0):
    r = repo()
    rec = r.records_for_split(split)[index]
    _a, graph, context = r.load_context(rec.transaction)
    return RealityForkGenerator.generate_baseline(rec.transaction, graph, context)


def test_attack_returns_one_normal_and_one_stress_result():
    baseline = _real_baseline()
    for scenario in config.SCENARIOS:
        normal, stress = CrashTestEngine.attack(baseline, scenario)
        assert (normal.fork_name, stress.fork_name) == ("normal", "stress")
        assert normal.scenario == stress.scenario == scenario
        assert normal.metrics["intensity"] == config.MIN_INTENSITY
        assert stress.metrics["intensity"] == config.SCENARIO_DEFAULT_INTENSITY[scenario]


def test_fork_isolation_state_is_never_stressed_twice():
    baseline = _real_baseline()
    before = dict(baseline.utilization)
    first = [CrashTestEngine.attack(baseline, s) for s in config.SCENARIOS]
    second = [CrashTestEngine.attack(baseline, s) for s in config.SCENARIOS]
    assert baseline.utilization == before            # attacking never mutates the baseline
    assert first == second                           # and is deterministic


def test_normal_and_stress_outcomes_are_distinct_under_load():
    util = {"payment_gateway": 0.4, "ledger": 0.4}
    normal, stress = CrashTestEngine.attack(_fork(util, util), "3x_volume")
    assert normal.survived and not stress.survived
    assert stress.metrics["max_utilization"] > normal.metrics["max_utilization"]


def test_three_scenarios_behave_differently():
    path = ("payment_gateway", "fraud_engine", "risk_model", "ledger", "settlement")
    quiet = _fork(path, {s: 0.05 for s in path})
    for scenario in config.SCENARIOS:
        assert CrashTestEngine.attack(quiet, scenario)[1].survived, f"{scenario} should survive a quiet system"

    # 0.4 utilization on the fraud services only: fraud_spike and 3x_volume fail, latency does not
    fraud_hot = _fork(path, {**{s: 0.05 for s in path}, "fraud_engine": 0.4})
    assert not CrashTestEngine.attack(fraud_hot, "fraud_spike")[1].survived
    assert not CrashTestEngine.attack(fraud_hot, "3x_volume")[1].survived
    assert CrashTestEngine.attack(fraud_hot, "service_latency")[1].survived

    # high utilization on the latency-affected services: latency budget is breached
    slow = _fork(("payment_gateway", "ledger", "settlement"), {"payment_gateway": 0.9, "ledger": 0.9, "settlement": 0.9})
    result = CrashTestEngine.attack(slow, "service_latency")[1]
    assert not result.survived and result.metrics["end_to_end_latency_ms"] > config.LATENCY_BUDGET_MS


def test_unknown_scenario_and_foreign_baseline_are_rejected():
    baseline = _real_baseline()
    expect_raises(SimulationError, CrashTestEngine.attack, baseline, "4x_volume")
    expect_raises(SimulationError, CrashTestEngine.attack, object(), "3x_volume")
    expect_raises(SimulationError, FragilitySearch.find_threshold, baseline, "nope")


def test_fragility_interval_is_one_resolution_wide_and_honest():
    r = repo()
    checked = 0
    for rec in r.records_for_split("validation")[:200]:
        _a, graph, context = r.load_context(rec.transaction)
        baseline = RealityForkGenerator.generate_baseline(rec.transaction, graph, context)
        for scenario in config.SCENARIOS:
            result = FragilitySearch.find_threshold(baseline, scenario)
            res = result.resolution
            assert res == config.FRAGILITY_RESOLUTION
            if result.unit == config.FRAGILITY_UNIT:
                assert physics.evaluate(scenario, baseline.utilization, result.breaking_threshold)[0] is False
                below = round(result.breaking_threshold - res, 6)
                if below >= config.MIN_INTENSITY:
                    assert physics.evaluate(scenario, baseline.utilization, below)[0] is True
                checked += 1
            else:
                assert result.unit == config.FRAGILITY_UNIT_LOWER_BOUND
                assert result.breaking_threshold == config.MAX_INTENSITY
                assert physics.evaluate(scenario, baseline.utilization, config.MAX_INTENSITY)[0] is True
    assert checked > 50


def test_fragility_edge_cases():
    already_failing = _fork(("ledger",), {"ledger": 1.4})
    r1 = FragilitySearch.find_threshold(already_failing, "3x_volume")
    assert r1.breaking_threshold == config.MIN_INTENSITY and r1.unit == config.FRAGILITY_UNIT
    never = _fork(("ledger",), {"ledger": 0.001})
    r2 = FragilitySearch.find_threshold(never, "3x_volume")
    assert r2.unit == config.FRAGILITY_UNIT_LOWER_BOUND and r2.breaking_threshold == config.MAX_INTENSITY


def test_failure_predicates_are_monotone_in_intensity():
    r = repo()
    for rec in r.records_for_split("validation")[:150]:
        _a, graph, context = r.load_context(rec.transaction)
        baseline = RealityForkGenerator.generate_baseline(rec.transaction, graph, context)
        for scenario in config.SCENARIOS:
            assert verify_monotone(baseline, scenario), f"{rec.transaction.id}/{scenario} is not monotone"


def test_failure_reasons_are_metrics_not_labels():
    path = ("ledger",)
    stress = CrashTestEngine.attack(_fork(path, {"ledger": 0.5}), "3x_volume")[1]
    assert not stress.survived
    assert stress.metrics["max_utilization"] > stress.metrics["utilization_limit"]
