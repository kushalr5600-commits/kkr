"""Crash Test Engine: attack one baseline under one named scenario.

``attack`` returns exactly two logical outcomes for the scenario:

    normal  - the nominal state (intensity 1.0)
    stress  - the SAME state after the scenario is applied once

The state is never stressed twice. Scenario identifiers are exact
(``3x_volume``, ``fraud_spike``, ``service_latency``); unknown names raise
``SimulationError`` instead of being aliased.
"""
from __future__ import annotations

from backend.shared import config
from backend.shared.errors import SimulationError
from backend.shared.schemas import ForkResult
from backend.simulation import physics
from backend.simulation.forks import BaselineFork


def _check_baseline(baseline_fork: object) -> BaselineFork:
    if not isinstance(baseline_fork, BaselineFork):
        raise SimulationError(
            f"baseline_fork must come from RealityForkGenerator.generate_baseline, got {type(baseline_fork).__name__}"
        )
    return baseline_fork


class CrashTestEngine:
    @staticmethod
    def attack(baseline_fork: object, scenario: str) -> list[ForkResult]:
        baseline = _check_baseline(baseline_fork)
        if scenario not in config.SCENARIOS:
            raise SimulationError(
                f"unknown scenario {scenario!r}; exact identifiers are {config.SCENARIOS}"
            )

        extras = {
            "recent_transactions_in_window": float(baseline.recent_count),
            "defaulted_load_services": float(len(baseline.defaulted_services)),
        }

        normal_ok, normal_metrics = physics.evaluate(scenario, baseline.utilization, config.MIN_INTENSITY)
        intensity = config.SCENARIO_DEFAULT_INTENSITY[scenario]
        stress_ok, stress_metrics = physics.evaluate(scenario, baseline.utilization, intensity)

        return [
            ForkResult(
                fork_name="normal",
                scenario=scenario,
                survived=normal_ok,
                metrics={**normal_metrics, **extras},
            ),
            ForkResult(
                fork_name="stress",
                scenario=scenario,
                survived=stress_ok,
                metrics={**stress_metrics, **extras},
            ),
        ]
