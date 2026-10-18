"""Fragility Search: how much extra stress can a decision absorb?

The scenario intensity is searched on a fixed grid
``MIN_INTENSITY + k * FRAGILITY_RESOLUTION`` (k = 0..N) with bisection, so the
search always terminates in at most ``ceil(log2(N)) + 2`` evaluations and the
reported interval is exactly one grid step wide:

    survives through (breaking_threshold - resolution)
    fails by          breaking_threshold
    resolution        FRAGILITY_RESOLUTION

Edge cases are reported honestly instead of with false precision:

  * fails already at nominal intensity ->
        breaking_threshold == MIN_INTENSITY, unit == FRAGILITY_UNIT
  * never fails up to MAX_INTENSITY ->
        breaking_threshold == MAX_INTENSITY (a LOWER bound),
        unit == FRAGILITY_UNIT_LOWER_BOUND

Bisection is valid because every failure predicate is monotone in the
intensity; ``verify_monotone`` checks that assumption on the full grid.
"""
from __future__ import annotations

from backend.shared import config
from backend.shared.errors import FragilityError, SimulationError
from backend.shared.schemas import FragilityResult
from backend.simulation import physics
from backend.simulation.forks import BaselineFork


def _grid_steps() -> int:
    steps = round((config.MAX_INTENSITY - config.MIN_INTENSITY) / config.FRAGILITY_RESOLUTION)
    if steps < 1:
        raise FragilityError("fragility grid must contain at least one step")
    return steps


def _level(k: int) -> float:
    return round(config.MIN_INTENSITY + k * config.FRAGILITY_RESOLUTION, 6)


def _fails(baseline: BaselineFork, scenario: str, k: int) -> bool:
    survived, _ = physics.evaluate(scenario, baseline.utilization, _level(k))
    return not survived


def verify_monotone(baseline_fork: BaselineFork, scenario: str) -> bool:
    """True if the failure predicate never flips from fail back to survive."""
    seen_failure = False
    for k in range(_grid_steps() + 1):
        failed = _fails(baseline_fork, scenario, k)
        if seen_failure and not failed:
            return False
        seen_failure = seen_failure or failed
    return True


class FragilitySearch:
    @staticmethod
    def find_threshold(baseline_fork: object, scenario: str) -> FragilityResult:
        if not isinstance(baseline_fork, BaselineFork):
            raise SimulationError(
                f"baseline_fork must come from RealityForkGenerator.generate_baseline, got {type(baseline_fork).__name__}"
            )
        if scenario not in config.SCENARIOS:
            raise SimulationError(
                f"unknown scenario {scenario!r}; exact identifiers are {config.SCENARIOS}"
            )

        steps = _grid_steps()
        resolution = config.FRAGILITY_RESOLUTION

        if _fails(baseline_fork, scenario, 0):
            return FragilityResult(
                scenario=scenario,
                breaking_threshold=_level(0),
                unit=config.FRAGILITY_UNIT,
                resolution=resolution,
            )
        if not _fails(baseline_fork, scenario, steps):
            return FragilityResult(
                scenario=scenario,
                breaking_threshold=_level(steps),
                unit=config.FRAGILITY_UNIT_LOWER_BOUND,
                resolution=resolution,
            )

        lo, hi = 0, steps  # survives at lo, fails at hi
        guard = steps + 2
        while hi - lo > 1:
            guard -= 1
            if guard < 0:  # cannot happen for a bisection; defensive termination guarantee
                raise FragilityError("fragility search failed to terminate")
            mid = (lo + hi) // 2
            if _fails(baseline_fork, scenario, mid):
                hi = mid
            else:
                lo = mid

        return FragilityResult(
            scenario=scenario,
            breaking_threshold=_level(hi),
            unit=config.FRAGILITY_UNIT,
            resolution=resolution,
        )
