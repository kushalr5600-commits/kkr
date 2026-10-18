"""Phase 2 diagnostic invariants and interaction-score purity tests.

These tests protect experiment-methodology guarantees discovered during the
gate underperformance investigation. They do not change frozen gate weights.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gate.calibration import (  # noqa: E402
    SplitEvaluation,
    _budget_count,
    _top_k_mask,
)
from backend.data.repository import DataRepository  # noqa: E402
from backend.gate.calibration import evaluate_split, fit_models  # noqa: E402
from backend.gate.impact_gate import ImpactGate  # noqa: E402
from backend.shared import config  # noqa: E402
from scripts.phase2_research_experiment import (  # noqa: E402
    build_interaction_features,
    interaction_aware_score,
    methodology_checks,
    rank_policies,
)


def _tiny_eval() -> SplitEvaluation:
    """Deterministic micro evaluation for pure ranking math."""
    n = 20
    failed = np.zeros(n, dtype=bool)
    failed[0:3] = True
    score = np.linspace(0.9, 0.1, n)
    anomaly = np.linspace(0.95, 0.05, n)
    return SplitEvaluation(
        split="validation",
        transaction_ids=[f"T{i}" for i in range(n)],
        categories=["normal"] * n,
        failed=failed,
        failed_scenarios=[("3x_volume",) if failed[i] else () for i in range(n)],
        score=score,
        gate_decision=score >= 0.6,
        amount_z=np.linspace(0, 1, n),
        anomaly_raw=anomaly,
        sim_ms=np.ones(n),
        gate_ms_per_tx=0.0,
        signals={
            "magnitude": np.zeros(n),
            "dependency": np.zeros(n),
            "anomaly": anomaly,
            "uncertainty": np.zeros(n),
        },
    )


def test_budget_count_is_ceil_and_capped():
    assert _budget_count(1000, 0.01) == 10
    assert _budget_count(1000, 0.005) == 5
    assert _budget_count(10, 1.0) == 10
    assert _budget_count(10, 0.5) == 5


def test_top_k_mask_selects_highest_scores():
    key = np.array([0.1, 0.9, 0.5, 0.7])
    mask = _top_k_mask(key, 2)
    assert mask.tolist() == [False, True, False, True]


def test_rank_policies_same_k_for_all_deterministic_policies():
    ev = _tiny_eval()
    # Interaction ranking aligned with failures (indices 0..2 high).
    inter = np.array([0.9, 0.85, 0.8] + [0.1] * (ev.n - 3))
    rows = rank_policies(ev, inter, budgets=(0.10,))
    ks = {r["k"] for r in rows}
    assert ks == {_budget_count(ev.n, 0.10)}
    recalls = {r["policy"]: r["failure_recall"] for r in rows}
    # n=20, budget 0.10 => k=2; failures at indices 0..2, top-2 by A/score/inter catch 2/3
    assert recalls["anomaly_only"] == 2.0 / 3.0
    assert recalls["BLACKBOX_frozen_gate"] == 2.0 / 3.0
    assert recalls["interaction_aware"] == 2.0 / 3.0
    assert recalls["amount_only"] == 0.0  # amount_z ascending puts failures last


def test_interaction_score_in_unit_interval_and_deterministic():
    ev = _tiny_eval()
    extras = {
        "window_pressure": np.linspace(0, 1, ev.n),
        "load_pressure": np.linspace(0, 1, ev.n),
    }
    s1 = interaction_aware_score(ev, extras)
    s2 = interaction_aware_score(ev, extras)
    assert np.allclose(s1, s2)
    assert float(s1.min()) >= 0.0 and float(s1.max()) <= 1.0


def test_interaction_score_does_not_read_failure_labels():
    """Same features+signals must yield same score if labels are flipped."""
    ev = _tiny_eval()
    extras = {"window_pressure": np.linspace(0, 1, ev.n), "load_pressure": np.linspace(0, 1, ev.n)}
    s_before = interaction_aware_score(ev, extras)
    flipped = SplitEvaluation(
        split=ev.split,
        transaction_ids=ev.transaction_ids,
        categories=ev.categories,
        failed=~ev.failed,
        failed_scenarios=ev.failed_scenarios,
        score=ev.score,
        gate_decision=ev.gate_decision,
        amount_z=ev.amount_z,
        anomaly_raw=ev.anomaly_raw,
        sim_ms=ev.sim_ms,
        gate_ms_per_tx=ev.gate_ms_per_tx,
        signals=ev.signals,
    )
    s_after = interaction_aware_score(flipped, extras)
    assert np.allclose(s_before, s_after)


def test_methodology_flags_test_split_unused():
    ev = _tiny_eval()
    m = methodology_checks(ev, DataRepository.default())
    assert m["test_split_used"] is False
    assert m["n"] == ev.n


def test_validation_anomaly_raw_and_cdf_A_share_topk():
    """Ranking fairness: raw A vs ECDF-A top-k should match (monotone)."""
    repo = DataRepository.default()
    models = fit_models(repo)
    ImpactGate.use_models(models)
    ev = evaluate_split(repo, models, "validation")
    for budget in (0.01, 0.05, 0.10):
        k = _budget_count(ev.n, budget)
        sa = set(np.argsort(-ev.anomaly_raw, kind="stable")[:k].tolist())
        sb = set(np.argsort(-ev.signals["anomaly"], kind="stable")[:k].tolist())
        assert sa == sb, f"top-{k} mismatch between raw A and ECDF A at budget {budget}"


def test_window_pressure_feature_build_without_labels():
    repo = DataRepository.default()
    models = fit_models(repo)
    ImpactGate.use_models(models)
    ev = evaluate_split(repo, models, "validation")
    extras = build_interaction_features(ev, repo)
    assert extras["window_pressure"].shape == (ev.n,)
    assert float(extras["window_pressure"].min()) >= 0.0
    assert float(extras["window_pressure"].max()) <= 1.0
    # frozen constants still intact after importing phase2 module
    assert config.IMPACT_THRESHOLD == 0.60
    assert config.IMPACT_WEIGHTS["magnitude"] == 0.30
