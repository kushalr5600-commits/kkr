"""Phase 3 — ranking, top-k, tie-break, label-independence, metric recalculation.

Plain ``test_*`` functions (no fixtures) so both ``pytest`` and
``scripts/run_tests.py`` collect them. No frozen constants are changed.
"""
from __future__ import annotations

import csv
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gate.calibration import SplitEvaluation, _budget_count, _top_k_mask  # noqa: E402
from scripts.phase2_research_experiment import interaction_aware_score  # noqa: E402
from scripts.phase3_reproduce_and_robustness import (  # noqa: E402
    cluster_bootstrap_diff,
    load_raw_predictions,
    recalc_metrics_from_raw,
    stable_topk_mask,
)


def test_budget_count_ceil_and_bounds():
    assert _budget_count(1000, 0.01) == 10
    assert _budget_count(1000, 0.05) == 50
    assert _budget_count(1000, 0.10) == 100
    assert _budget_count(10, 0.001) == 1
    assert _budget_count(10, 1.0) == 10


def test_topk_selects_exactly_k():
    rng = np.random.default_rng(0)
    key = rng.normal(size=200)
    for b in (0.01, 0.05, 0.10, 0.5):
        k = _budget_count(200, b)
        for fn in (stable_topk_mask, _top_k_mask):
            assert int(fn(key, k).sum()) == k


def test_stable_topk_matches_numpy_stable_argsort():
    rng = np.random.default_rng(1)
    key = rng.integers(0, 3, size=50).astype(float)
    for k in (1, 5, 10, 25):
        assert np.array_equal(stable_topk_mask(key, k), _top_k_mask(key, k)), k


def test_tie_break_prefers_lower_original_index():
    key = np.zeros(8)
    assert np.where(stable_topk_mask(key, 3))[0].tolist() == [0, 1, 2]
    key2 = np.array([1.0, 0.5, 0.5, 0.2, 0.1, 1.0, 0.0, 0.0])
    m2 = stable_topk_mask(key2, 3)
    assert np.where(m2)[0].tolist() == [0, 1, 5]
    assert m2[0] and m2[1] and m2[5] and not m2[2]


def test_ranking_deterministic_across_calls():
    rng = np.random.default_rng(42)
    key = rng.normal(size=100)
    assert np.array_equal(stable_topk_mask(key, 10), stable_topk_mask(key, 10))


def test_monotonic_shift_preserves_ranking():
    key = np.array([0.9, 0.1, 0.5, 0.3])
    assert np.array_equal(stable_topk_mask(key, 2), stable_topk_mask(key + 100.0, 2))


def _synth_eval(failed: np.ndarray, seed: int = 7) -> SplitEvaluation:
    n = len(failed)
    rng = np.random.default_rng(seed)
    anomaly = rng.random(n)
    return SplitEvaluation(
        split="validation",
        transaction_ids=[f"TX-{i}" for i in range(n)],
        categories=["normal"] * n,
        failed=failed,
        failed_scenarios=[tuple() for _ in range(n)],
        score=rng.random(n),
        gate_decision=rng.random(n) >= 0.5,
        amount_z=rng.random(n),
        anomaly_raw=anomaly,
        sim_ms=np.ones(n),
        gate_ms_per_tx=1.0,
        signals={
            "magnitude": rng.random(n),
            "dependency": rng.random(n),
            "anomaly": anomaly,
            "uncertainty": rng.random(n),
        },
    )


def test_interaction_score_label_independent():
    n = 12
    rng = np.random.default_rng(7)
    extras = {
        "window_pressure": rng.random(n),
        "load_pressure": rng.random(n),
        "recent_count": rng.random(n),
        "recent_amount_ratio": rng.random(n),
        "recent_same_type": rng.random(n),
        "max_bg": rng.random(n),
        "path_max_bg": rng.random(n),
        "X": np.zeros((n, 1)),
    }
    failed_a = np.zeros(n, dtype=bool)
    failed_a[:3] = True
    failed_b = np.ones(n, dtype=bool)
    # rebuild identical rng draws by re-seeding inside helper with same seed
    s1 = interaction_aware_score(_synth_eval(failed_a), extras)
    s2 = interaction_aware_score(_synth_eval(failed_b), extras)
    # _synth_eval uses same seed => same scores/dependency; only failed differs
    assert np.array_equal(s1, s2)


def test_interaction_formula_convex_combination_in_unit_interval():
    n = 5
    extras = {"window_pressure": np.full(n, 0.4), "load_pressure": np.full(n, 0.6)}
    ev = SplitEvaluation(
        split="validation",
        transaction_ids=[f"T{i}" for i in range(n)],
        categories=["normal"] * n,
        failed=np.zeros(n, dtype=bool),
        failed_scenarios=[tuple()] * n,
        score=np.zeros(n),
        gate_decision=np.zeros(n, dtype=bool),
        amount_z=np.zeros(n),
        anomaly_raw=np.zeros(n),
        sim_ms=np.ones(n),
        gate_ms_per_tx=0.0,
        signals={
            "magnitude": np.zeros(n),
            "dependency": np.full(n, 0.5),
            "anomaly": np.full(n, 0.5),
            "uncertainty": np.zeros(n),
        },
    )
    s = interaction_aware_score(ev, extras)
    assert np.all(s >= 0.0) and np.all(s <= 1.0)
    # 0.45*0.5 + 0.30*0.4 + 0.15*0.5 + 0.10*0.6 = 0.48
    assert np.allclose(s, 0.48)


def test_recalc_metrics_hand_computed():
    n = 10
    inter = [0.1, 0.2, 0.3, 0.0, 0.0, 0.9, 0.8, 0.7, 0.6, 0.5]
    anom = [0.95, 0.9, 0.85, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]
    failed = [1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
    rows = [
        {
            "rank_index": str(i),
            "failed": str(failed[i]),
            "anomaly_raw": str(anom[i]),
            "gate_score": "0.5",
            "interaction_score": str(inter[i]),
        }
        for i in range(n)
    ]
    out = recalc_metrics_from_raw(rows, budgets=(0.3,))
    assert out["interaction_aware@0.3"]["k"] == 3.0
    assert out["interaction_aware@0.3"]["failures_found"] == 0.0
    assert out["interaction_aware@0.3"]["failure_recall"] == 0.0
    assert out["anomaly_only@0.3"]["failures_found"] == 3.0
    assert out["anomaly_only@0.3"]["failure_recall"] == 1.0
    assert out["anomaly_only@0.3"]["precision"] == 1.0
    assert out["anomaly_only@0.3"]["false_negatives"] == 0.0
    assert out["anomaly_only@0.3"]["false_positives"] == 0.0


def test_csv_roundtrip_and_recalc():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "raw.csv"
        n = 6
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["failed", "anomaly_raw", "gate_score", "interaction_score"])
            for i in range(n):
                w.writerow([1 if i < 2 else 0, 10 - i, 0.5, i / 10])
        rows = load_raw_predictions(path)
        assert len(rows) == n
        out = recalc_metrics_from_raw(rows, budgets=(0.5,))
        assert out["interaction_aware@0.5"]["failure_recall"] == 0.0
        assert out["anomaly_only@0.5"]["failure_recall"] == 1.0


def test_bootstrap_diff_zero_when_masks_equal():
    rng = np.random.default_rng(0)
    failed = rng.random(40) < 0.3
    sel = rng.random(40) < 0.5
    accts = [f"A{i % 8}" for i in range(40)]
    out = cluster_bootstrap_diff(failed, sel, sel, accts, n_boot=50, seed=1)
    assert abs(out["mean_diff"]) < 1e-12
    assert out["n_replicates"] == 50


def test_bootstrap_respects_cluster_structure():
    failed = np.array([True, True, False, False])
    sel_a = np.array([True, False, False, False])
    sel_b = np.array([False, True, False, False])
    accts = ["X", "X", "Y", "Y"]
    out = cluster_bootstrap_diff(failed, sel_a, sel_b, accts, n_boot=100, seed=2)
    assert 0 < out["n_replicates"] <= 100
    assert math.isfinite(out["mean_diff"])
    assert abs(out["mean_diff"]) < 1e-6
