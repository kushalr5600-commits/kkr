"""Calibration, ground-truth labelling and the fixed-budget experiment (P3).

Data discipline (Agent manual v4, Part 8):

  * Models are fitted on the CALIBRATION split only (``GateModels.fit`` refuses
    any other split name).
  * Ground truth comes from the simulator, never from the gate.
  * ``evaluate_split`` is a pure read-only evaluation. Which split it is run on
    is the caller's decision; the locked ``test`` split must be evaluated only
    after the configuration is frozen (see ``scripts/run_experiment.py``).

Failure label: a transaction is a true failure when ANY of the three stress
scenarios fails at its default intensity (``SCENARIO_DEFAULT_INTENSITY``). The
per-scenario outcomes are kept so misses can be attributed to a failure mode.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from backend.data.repository import DataRepository, DatasetRecord
from backend.gate.impact_gate import ImpactGate
from backend.gate.models import FEATURE_NAMES, GateModels, extract_features
from backend.shared import config
from backend.simulation.crash_test import CrashTestEngine
from backend.simulation.forks import RealityForkGenerator

Z_FEATURE = FEATURE_NAMES.index("amount_zscore")


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Label:
    transaction_id: str
    failed: bool
    failed_scenarios: tuple[str, ...]
    sim_ms: float  # wall-clock time of the three attacks for this transaction


def label_record(repo: DataRepository, record: DatasetRecord) -> Label:
    """Run the full stress simulation for one record and report the outcome."""
    account, graph, context = repo.load_context(record.transaction)
    start = time.perf_counter()
    baseline = RealityForkGenerator.generate_baseline(record.transaction, graph, context)
    failed = []
    for scenario in config.SCENARIOS:
        _normal, stress = CrashTestEngine.attack(baseline, scenario)
        if not stress.survived:
            failed.append(scenario)
    elapsed = (time.perf_counter() - start) * 1000.0
    return Label(record.transaction.id, bool(failed), tuple(failed), elapsed)


def label_split(repo: DataRepository, split: str) -> list[Label]:
    return [label_record(repo, rec) for rec in repo.records_for_split(split)]


# ---------------------------------------------------------------------------
# Fitting
# ---------------------------------------------------------------------------
def feature_matrix(repo: DataRepository, records: list[DatasetRecord]) -> np.ndarray:
    rows = []
    for rec in records:
        account, graph, context = repo.load_context(rec.transaction)
        rows.append(extract_features(rec.transaction, account, graph, context))
    return np.stack(rows) if rows else np.zeros((0, len(FEATURE_NAMES)))


def fit_models(
    repo: DataRepository,
    backend: str | None = None,
    seed: int = config.MODEL_SEED,
    hybrid: bool | None = None,
) -> GateModels:
    """Fit A and U on the calibration split of ``repo``."""
    records = repo.records_for_split("calibration")
    X = feature_matrix(repo, records)
    labels = [label_record(repo, r) for r in records]
    y = np.asarray([1.0 if lab.failed else 0.0 for lab in labels])
    return GateModels.fit(X, y, split="calibration", backend=backend, seed=seed, hybrid=hybrid)


def fit_default_models() -> GateModels:
    """Used by ``ImpactGate.models()``: fit on the default sample dataset."""
    return fit_models(DataRepository.default())


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
@dataclass
class SplitEvaluation:
    split: str
    transaction_ids: list[str]
    categories: list[str]
    failed: np.ndarray            # bool, ground truth
    failed_scenarios: list[tuple[str, ...]]
    score: np.ndarray             # Impact score
    gate_decision: np.ndarray     # bool, score >= threshold
    amount_z: np.ndarray          # raw amount z-score (amount-only baseline)
    anomaly_raw: np.ndarray       # raw anomaly score (anomaly-only baseline)
    sim_ms: np.ndarray            # per-transaction simulation runtime
    gate_ms_per_tx: float
    signals: dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.transaction_ids)

    @property
    def n_failures(self) -> int:
        return int(self.failed.sum())


def evaluate_split(repo: DataRepository, models: GateModels, split: str) -> SplitEvaluation:
    records = repo.records_for_split(split)
    if not records:
        raise ValueError(f"split {split!r} has no records")
    labels = [label_record(repo, r) for r in records]

    items = []
    for rec in records:
        account, graph, context = repo.load_context(rec.transaction)
        items.append((rec.transaction, account, graph, context))
    start = time.perf_counter()
    scores = ImpactGate.score_batch(items, models)
    gate_ms = (time.perf_counter() - start) * 1000.0 / len(items)

    X = np.stack([extract_features(*item) for item in items])
    return SplitEvaluation(
        split=split,
        transaction_ids=[r.transaction.id for r in records],
        categories=[r.category for r in records],
        failed=np.asarray([lab.failed for lab in labels]),
        failed_scenarios=[lab.failed_scenarios for lab in labels],
        score=np.asarray([s.score for s in scores]),
        gate_decision=np.asarray([s.gate_decision for s in scores]),
        amount_z=X[:, Z_FEATURE],
        anomaly_raw=models.anomaly.raw(X),
        sim_ms=np.asarray([lab.sim_ms for lab in labels]),
        gate_ms_per_tx=gate_ms,
        signals={
            "magnitude": np.asarray([s.signals.magnitude for s in scores]),
            "dependency": np.asarray([s.signals.dependency for s in scores]),
            "anomaly": np.asarray([s.signals.anomaly for s in scores]),
            "uncertainty": np.asarray([s.signals.uncertainty for s in scores]),
        },
    )


def _budget_count(n: int, budget: float) -> int:
    return min(n, max(1, math.ceil(budget * n - 1e-9)))


def _row(ev: SplitEvaluation, policy: str, budget: float, selected: np.ndarray) -> dict:
    """Metrics for one policy at one budget. ``selected`` is a bool mask or,
    for the random policy, an (draws, n) bool matrix that is averaged."""
    sel = np.atleast_2d(selected)
    found = (sel & ev.failed[None, :]).sum(axis=1).astype(float)
    total = float(ev.n_failures)
    recall = found / total if total else np.zeros_like(found)

    categories = sorted(set(ev.categories))
    cat_recall: dict[str, float | None] = {}
    for cat in categories:
        mask = np.asarray([c == cat for c in ev.categories]) & ev.failed
        n_cat = int(mask.sum())
        cat_recall[cat] = float((sel & mask[None, :]).sum(axis=1).mean() / n_cat) if n_cat else None

    n_sim = float(sel.sum(axis=1).mean())
    sim_runtime = float((sel * ev.sim_ms[None, :]).sum(axis=1).mean())
    return {
        "policy": policy,
        "simulation_budget": budget,
        "simulation_count": n_sim,
        "simulation_fraction": n_sim / ev.n,
        "failures_found": float(found.mean()),
        "total_failures": int(total),
        "failure_recall": float(recall.mean()),
        "false_negative_rate": float(1.0 - recall.mean()),
        "simulation_avoidance": 1.0 - n_sim / ev.n,
        "total_simulation_runtime_ms": sim_runtime,
        "mean_simulation_runtime_ms": sim_runtime / n_sim if n_sim else 0.0,
        "category_recall": cat_recall,
    }


def _top_k_mask(key: np.ndarray, k: int) -> np.ndarray:
    order = np.argsort(-key, kind="stable")
    mask = np.zeros(len(key), dtype=bool)
    mask[order[:k]] = True
    return mask


def budget_curve(ev: SplitEvaluation, budgets=config.EXPERIMENT_BUDGETS) -> list[dict]:
    """Failure recall at fixed simulation budget for every policy.

    This is a RANKING experiment: each policy ranks the split, the top
    ``budget`` fraction is simulated. It is not the 0.60-threshold operating
    point (see ``threshold_operating_point``).
    """
    rng = np.random.default_rng(config.MODEL_SEED)
    rows: list[dict] = []
    for budget in budgets:
        k = _budget_count(ev.n, budget)
        draws = np.zeros((config.EXPERIMENT_RANDOM_DRAWS, ev.n), dtype=bool)
        for i in range(config.EXPERIMENT_RANDOM_DRAWS):
            draws[i, rng.permutation(ev.n)[:k]] = True
        rows.append(_row(ev, "random", budget, draws))
        rows.append(_row(ev, "amount_only", budget, _top_k_mask(ev.amount_z, k)))
        rows.append(_row(ev, "anomaly_only", budget, _top_k_mask(ev.anomaly_raw, k)))
        rows.append(_row(ev, "BLACKBOX", budget, _top_k_mask(ev.score, k)))
    return rows


def threshold_operating_point(ev: SplitEvaluation) -> dict:
    """What the production rule (simulate iff score >= 0.60) does on this split."""
    row = _row(ev, "BLACKBOX@threshold", float(ev.gate_decision.mean()), ev.gate_decision)
    selected_failures = float((ev.gate_decision & ev.failed).sum())
    row["threshold"] = config.IMPACT_THRESHOLD
    row["precision"] = selected_failures / float(ev.gate_decision.sum()) if ev.gate_decision.any() else None
    return row
