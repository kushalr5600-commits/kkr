"""Deterministic enterprise load/latency model used by the simulator.

This is the "physics" of the synthetic enterprise: how much load a
transaction puts on each downstream service, and when a stressed system is
considered failed. It is pure and side-effect free.

Failure predicates (thresholds live in ``backend/shared/config.py``):

  3x_volume        every load on the path is multiplied by the intensity;
                   FAIL if any path service exceeds its capacity.
  fraud_spike      fraud_engine / risk_model load is multiplied by the
                   intensity and the downstream cascade services by
                   ``1 + FRAUD_CASCADE_COEFF * (intensity - 1)``;
                   FAIL if any path service exceeds its capacity.
  service_latency  gateway / ledger / settlement latency is multiplied by the
                   intensity; every service latency also grows with its own
                   utilization; FAIL if end-to-end path latency exceeds the
                   latency budget.

All three predicates are monotone non-decreasing in the intensity (>= 1),
which is what makes the bounded fragility search valid. Unit tests assert it.
"""
from __future__ import annotations

import math
from typing import Iterable, Mapping

from backend.shared import config
from backend.shared.errors import SimulationError


def amount_factor(amount: float) -> float:
    """Load multiplier for a transaction amount (bounded)."""
    ratio = min(amount / config.AMOUNT_LOAD_REF, config.AMOUNT_LOAD_CAP)
    return config.AMOUNT_LOAD_BASE + config.AMOUNT_LOAD_SLOPE * ratio


def transaction_load_units(transaction_type: str, amount: float) -> dict[str, float]:
    """Load units a single transaction places on each service it touches."""
    profile = config.TRANSACTION_PROFILES.get(transaction_type)
    if profile is None:
        raise SimulationError(f"unknown transaction_type {transaction_type!r}")
    factor = amount_factor(amount)
    return {svc: units * factor for svc, units in profile["footprint"].items()}


def nominal_utilization(
    path_services: Iterable[str],
    background: Mapping[str, float],
    transactions: Iterable[tuple[str, float]],
) -> dict[str, float]:
    """Nominal utilization of each path service.

    ``background`` is the utilization fraction caused by other traffic;
    ``transactions`` are (transaction_type, amount) pairs placing additional
    load (the transaction under test plus its recent-window neighbours).
    """
    path = tuple(path_services)
    util = {svc: float(background[svc]) for svc in path}
    for ttype, amount in transactions:
        units = transaction_load_units(ttype, amount)
        for svc in path:
            util[svc] += units.get(svc, 0.0) / config.CAPACITY[svc]
    return util


def _utilization_outcome(stressed: dict[str, float], intensity: float) -> tuple[bool, dict[str, float]]:
    max_util = max(stressed.values())
    survived = max_util <= config.UTILIZATION_FAILURE_LIMIT
    metrics = {
        "intensity": float(intensity),
        "max_utilization": float(max_util),
        "utilization_limit": float(config.UTILIZATION_FAILURE_LIMIT),
        "headroom": float(config.UTILIZATION_FAILURE_LIMIT - max_util),
    }
    for svc, value in stressed.items():
        metrics[f"util_{svc}"] = float(value)
    return survived, metrics


def evaluate(
    scenario: str,
    utilization: Mapping[str, float],
    intensity: float,
) -> tuple[bool, dict[str, float]]:
    """Apply one scenario at ``intensity`` to a nominal utilization map.

    Returns ``(survived, metrics)``. ``intensity == 1.0`` is the nominal
    ("normal") outcome of the same predicate.
    """
    if scenario not in config.SCENARIOS:
        raise SimulationError(
            f"unknown scenario {scenario!r}; exact identifiers are {config.SCENARIOS}"
        )
    if not math.isfinite(intensity) or intensity < config.MIN_INTENSITY:
        raise SimulationError(f"intensity must be finite and >= {config.MIN_INTENSITY}, got {intensity!r}")
    if not utilization:
        raise SimulationError("utilization map is empty; the transaction has no downstream path")

    if scenario == "3x_volume":
        stressed = {svc: u * intensity for svc, u in utilization.items()}
        return _utilization_outcome(stressed, intensity)

    if scenario == "fraud_spike":
        cascade = 1.0 + config.FRAUD_CASCADE_COEFF * (intensity - 1.0)
        stressed = {}
        for svc, u in utilization.items():
            if svc in config.FRAUD_AFFECTED_SERVICES:
                factor = intensity
            elif svc in config.FRAUD_CASCADE_SERVICES:
                factor = cascade
            else:
                factor = 1.0
            stressed[svc] = u * factor
        return _utilization_outcome(stressed, intensity)

    # service_latency
    total = 0.0
    for svc, u in utilization.items():
        latency = config.BASE_LATENCY_MS[svc] * (1.0 + config.LATENCY_UTILIZATION_COEFF * u)
        if svc in config.LATENCY_AFFECTED_SERVICES:
            latency *= intensity
        total += latency
    survived = total <= config.LATENCY_BUDGET_MS
    metrics = {
        "intensity": float(intensity),
        "end_to_end_latency_ms": float(total),
        "latency_budget_ms": float(config.LATENCY_BUDGET_MS),
        "headroom": float(config.LATENCY_BUDGET_MS - total),
        "max_utilization": float(max(utilization.values())),
    }
    for svc, u in utilization.items():
        metrics[f"util_{svc}"] = float(u)
    return survived, metrics
