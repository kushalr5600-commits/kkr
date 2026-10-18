"""The Impact Gate: decide which transactions deserve deep simulation.

    I(T) = 0.30*M + 0.30*D + 0.25*A + 0.15*U        simulate iff I(T) >= 0.60

  M  magnitude   amount vs the account baseline            (explainable stats)
  D  dependency  downstream exposure in the local graph    (deterministic graph feature)
  A  anomaly     anomaly model, empirical-CDF normalized   (learned)
  U  uncertainty ensemble disagreement of a risk model     (learned)

When ``config.INTERACTION_AWARE_ENABLED`` is set (human-authorized research
activation), the gate instead ranks with

    I(T) = 0.45*A + 0.30*W + 0.15*D + 0.10*L              simulate iff I(T) >= 0.60

  W  window pressure   recent co-occurrence context        (deterministic dataset feature)
  L  load pressure     background/path load context        (deterministic dataset feature)

Both formulas keep I(T) in [0, 1] by construction. The weights and threshold
are MVP parameters from ``backend/shared/config.py``; nothing here claims
they are optimal. ``combine()`` always computes the frozen formula and stays
available as the reference implementation.

``ImpactGate.score`` / ``should_simulate`` are class-level so the contract
shape ``ImpactGate.score(transaction, account, graph, context)`` works. The
fitted models live on the class (``ImpactGate.use_models`` swaps them, the
default is fitted lazily on the calibration split of the sample dataset).
"""
from __future__ import annotations

import threading
from typing import Iterable

import numpy as np

from backend.gate.models import FEATURE_NAMES, GateModels, criticality_share, extract_features
from backend.shared import config
from backend.shared.context_utils import reachable_accounts, reachable_services
from backend.shared.errors import GateError
from backend.gate.interaction_aware import is_enabled, score_feature_row
from backend.shared.schemas import (
    Account,
    DependencyGraph,
    EventContext,
    ImpactScore,
    ImpactSignals,
    Transaction,
)

GateItem = tuple[Transaction, Account, DependencyGraph, EventContext]


def _clip01(value: float) -> float:
    if not np.isfinite(value):
        raise GateError(f"non-finite signal value {value!r}")
    return float(min(1.0, max(0.0, value)))


def magnitude_signal(transaction: Transaction, account: Account) -> float:
    """M: how far above the account's own baseline this amount is, in [0, 1]."""
    std = max(float(account.historical_std_amount), 1e-6)
    z = (transaction.amount - float(account.historical_avg_amount)) / std
    return _clip01(max(z, 0.0) / config.MAGNITUDE_Z_SATURATION)


def dependency_signal(transaction: Transaction, graph: DependencyGraph) -> float:
    """D: criticality-weighted downstream exposure in the local graph, in [0, 1]."""
    if not any(n.id == transaction.id and n.node_type == "transaction" for n in graph.nodes):
        raise GateError(f"transaction node {transaction.id!r} is missing from the dependency graph")
    services = reachable_services(graph, transaction.id)
    accounts = reachable_accounts(graph, transaction.id)
    account_part = min(len(accounts) / config.DEPENDENCY_ACCOUNT_SATURATION, 1.0)
    value = (
        config.DEPENDENCY_SERVICE_WEIGHT * criticality_share(services)
        + config.DEPENDENCY_ACCOUNT_WEIGHT * account_part
    )
    return _clip01(value)


def combine(signals: ImpactSignals) -> float:
    """The frozen weighted sum, clipped to [0, 1]."""
    w = config.IMPACT_WEIGHTS
    total = (
        w["magnitude"] * signals.magnitude
        + w["dependency"] * signals.dependency
        + w["anomaly"] * signals.anomaly
        + w["uncertainty"] * signals.uncertainty
    )
    return _clip01(total)


class ImpactGate:
    _models: GateModels | None = None
    _lock = threading.Lock()

    # -- model management ------------------------------------------------------
    @classmethod
    def use_models(cls, models: GateModels | None) -> None:
        """Install fitted models (or ``None`` to force a lazy refit)."""
        cls._models = models

    @classmethod
    def models(cls) -> GateModels:
        if cls._models is None:
            with cls._lock:
                if cls._models is None:
                    from backend.gate.calibration import fit_default_models

                    cls._models = fit_default_models()
        return cls._models

    # -- scoring ---------------------------------------------------------------
    @classmethod
    def score_batch(cls, items: Iterable[GateItem], models: GateModels | None = None) -> list[ImpactScore]:
        items = list(items)
        if not items:
            return []
        models = models or cls.models()
        X = np.stack([extract_features(t, a, g, c) for t, a, g, c in items])
        anomaly = np.clip(np.asarray(models.anomaly_scores(X), dtype=float), 0.0, 1.0)
        uncertainty = np.clip(np.asarray(models.uncertainty_scores(X), dtype=float), 0.0, 1.0)
        magnitudes = np.array([magnitude_signal(t, a) for t, a, _, _ in items])
        dependencies = np.array([dependency_signal(t, g) for t, _, g, _ in items])

        if is_enabled():
            # Batch-size invariant: pressure from dataset-context features.
            values = score_feature_row(X, anomaly, dependencies, FEATURE_NAMES)
        else:
            values = np.array(
                [
                    combine(
                        ImpactSignals(
                            magnitude=float(m),
                            dependency=float(d),
                            anomaly=float(a),
                            uncertainty=float(u),
                        )
                    )
                    for m, d, a, u in zip(magnitudes, dependencies, anomaly, uncertainty)
                ]
            )

        # Hard guard: a non-finite score must never reach the threshold comparison
        # (nan >= 0.60 is False and would silently skip simulation -> false ALLOW).
        values = np.asarray(values, dtype=float)
        if not np.all(np.isfinite(values)):
            raise GateError(
                "Impact Gate produced a non-finite score; refusing to issue a gate decision"
            )

        scores: list[ImpactScore] = []
        for (transaction, _account, _graph, _context), m, d, a, u, value in zip(
            items, magnitudes, dependencies, anomaly, uncertainty, values
        ):
            signals = ImpactSignals(
                magnitude=float(m),
                dependency=float(d),
                anomaly=float(a),
                uncertainty=float(u),
            )
            scores.append(
                ImpactScore(
                    transaction_id=transaction.id,
                    signals=signals,
                    score=float(value),
                    gate_decision=float(value) >= config.IMPACT_THRESHOLD,
                )
            )
        return scores

    @classmethod
    def score(
        cls,
        transaction: Transaction,
        account: Account,
        graph: DependencyGraph,
        context: EventContext,
    ) -> ImpactScore:
        return cls.score_batch([(transaction, account, graph, context)])[0]

    @classmethod
    def should_simulate(cls, score: ImpactScore) -> bool:
        return score.score >= config.IMPACT_THRESHOLD
