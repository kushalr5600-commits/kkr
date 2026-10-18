"""Phase 2/3 — gate diagnosis + interaction-aware selection experiment.

READ-ONLY with respect to frozen constants, published evidence and the locked
test split. Uses calibration only for model fitting (via existing
``fit_models``) and validation only for policy comparison.

Outputs a timestamped directory under ``evidence/results/analysis/`` with
JSON + Markdown. Never writes to ``evidence/results/validation/``.

Usage (repository root):
    python scripts/phase2_research_experiment.py
    python scripts/phase2_research_experiment.py --split validation --budgets 0.01,0.05,0.10
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gate.calibration import (  # noqa: E402
    SplitEvaluation,
    _budget_count,
    _top_k_mask,
    evaluate_split,
    fit_models,
    label_record,
    threshold_operating_point,
)
from backend.gate.impact_gate import ImpactGate  # noqa: E402
from backend.gate.models import FEATURE_NAMES, extract_features  # noqa: E402
from backend.data.repository import DataRepository  # noqa: E402
from backend.shared import config  # noqa: E402

ANALYSIS_ROOT = ROOT / "evidence" / "results" / "analysis"


def _idx(name: str) -> int:
    return FEATURE_NAMES.index(name)


def _clip01(x: np.ndarray | float) -> np.ndarray | float:
    return np.clip(x, 0.0, 1.0)


def _point_biserial(x: np.ndarray, y: np.ndarray) -> float:
    """Correlation of continuous x with bool failure y. 0 if degenerate."""
    yf = y.astype(float)
    if yf.std() < 1e-12 or x.std() < 1e-12:
        return 0.0
    return float(np.corrcoef(x, yf)[0, 1])


def _wilson_interval(found: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion (recall uncertainty)."""
    if total <= 0:
        return (0.0, 0.0)
    p = found / total
    denom = 1.0 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (max(0.0, (centre - margin) / denom), min(1.0, (centre + margin) / denom))


def build_interaction_features(ev: SplitEvaluation, repo: DataRepository) -> dict[str, np.ndarray]:
    """Per-transaction window/load interaction features (no labels used)."""
    records = {r.transaction.id: r for r in repo.records_for_split(ev.split)}
    rows = []
    for tx_id in ev.transaction_ids:
        rec = records[tx_id]
        account, graph, context = repo.load_context(rec.transaction)
        rows.append(extract_features(rec.transaction, account, graph, context))
    X = np.stack(rows)
    recent_count = X[:, _idx("recent_count")]
    recent_amount_ratio = X[:, _idx("recent_amount_ratio")]
    recent_same_type = X[:, _idx("recent_same_type")]
    max_bg = X[:, _idx("max_background_load")]
    path_max_bg = X[:, _idx("path_max_background_load")]
    # Window pressure: co-occurrence / clustering context (joint-interaction proxy).
    window_pressure = _clip01(
        0.45 * (recent_count / 10.0)
        + 0.35 * np.clip(recent_amount_ratio / 50.0, 0.0, 1.0)
        + 0.20 * (recent_same_type / 10.0)
    )
    load_pressure = _clip01(0.5 * np.clip(max_bg, 0, 1) + 0.5 * np.clip(path_max_bg, 0, 1))
    return {
        "X": X,
        "recent_count": recent_count,
        "recent_amount_ratio": recent_amount_ratio,
        "recent_same_type": recent_same_type,
        "max_bg": max_bg,
        "path_max_bg": path_max_bg,
        "window_pressure": window_pressure,
        "load_pressure": load_pressure,
    }


def interaction_aware_score(ev: SplitEvaluation, extras: dict[str, np.ndarray]) -> np.ndarray:
    """Ranking-only interaction-aware candidate (NOT the production gate).

    Uses frozen signal A and D plus deterministic window/load context features.
    No failure labels, no test split, no frozen weight change.
    """
    a = ev.signals["anomaly"]
    d = ev.signals["dependency"]
    wp = extras["window_pressure"]
    lp = extras["load_pressure"]
    return _clip01(0.45 * a + 0.30 * wp + 0.15 * d + 0.10 * lp)


def rank_policies(
    ev: SplitEvaluation,
    interaction_score: np.ndarray,
    budgets: tuple[float, ...],
) -> list[dict[str, Any]]:
    """Recall-vs-budget for all policies including interaction_aware."""
    rows: list[dict[str, Any]] = []
    rng = np.random.default_rng(config.MODEL_SEED)
    n = ev.n
    for budget in budgets:
        k = _budget_count(n, budget)
        # random: average over fixed draws
        found_rand = 0.0
        for _ in range(config.EXPERIMENT_RANDOM_DRAWS):
            sel = np.zeros(n, dtype=bool)
            sel[rng.permutation(n)[:k]] = True
            found_rand += float((sel & ev.failed).sum())
        found_rand /= config.EXPERIMENT_RANDOM_DRAWS
        policies = {
            "random": found_rand / max(ev.n_failures, 1),
            "amount_only": float(( _top_k_mask(ev.amount_z, k) & ev.failed).sum()) / max(ev.n_failures, 1),
            "anomaly_only": float((_top_k_mask(ev.anomaly_raw, k) & ev.failed).sum()) / max(ev.n_failures, 1),
            "BLACKBOX_frozen_gate": float((_top_k_mask(ev.score, k) & ev.failed).sum()) / max(ev.n_failures, 1),
            "interaction_aware": float((_top_k_mask(interaction_score, k) & ev.failed).sum()) / max(ev.n_failures, 1),
        }
        selected_counts = {
            "random": k,
            "amount_only": k,
            "anomaly_only": k,
            "BLACKBOX_frozen_gate": k,
            "interaction_aware": k,
        }
        for policy, recall in policies.items():
            if policy == "random":
                found = found_rand
                lo, hi = _wilson_interval(int(round(found)), ev.n_failures)
            else:
                sel = {
                    "amount_only": _top_k_mask(ev.amount_z, k),
                    "anomaly_only": _top_k_mask(ev.anomaly_raw, k),
                    "BLACKBOX_frozen_gate": _top_k_mask(ev.score, k),
                    "interaction_aware": _top_k_mask(interaction_score, k),
                }[policy]
                found = float((sel & ev.failed).sum())
                lo, hi = _wilson_interval(int(found), ev.n_failures)
            fn = ev.n_failures - found
            fp = selected_counts[policy] - found
            precision = found / selected_counts[policy] if selected_counts[policy] else 0.0
            rows.append(
                {
                    "policy": policy,
                    "budget": budget,
                    "k": k,
                    "failure_recall": float(recall),
                    "recall_ci95": [lo, hi],
                    "failures_found": float(found),
                    "false_negatives": float(fn),
                    "false_positives": float(fp),
                    "precision": float(precision),
                    "simulations": int(selected_counts[policy]),
                    "sim_runtime_ms_total": float(ev.sim_ms.sum() * (k / n)),
                }
            )
    return rows


def false_negative_profile(
    ev: SplitEvaluation,
    ranking_score: np.ndarray,
    budget: float,
    policy_name: str,
) -> dict[str, Any]:
    """Which failures are missed by top-k of ranking_score at budget."""
    k = _budget_count(ev.n, budget)
    selected = _top_k_mask(ranking_score, k)
    missed = (~selected) & ev.failed
    found = selected & ev.failed
    by_category: dict[str, int] = {}
    by_scenario: dict[str, int] = {}
    by_type: dict[str, int] = {}
    missed_ids = []
    records = {r.transaction.id: r for r in DataRepository.default().records_for_split(ev.split)}
    for i, tx_id in enumerate(ev.transaction_ids):
        if not missed[i]:
            continue
        missed_ids.append(tx_id)
        cat = ev.categories[i]
        by_category[cat] = by_category.get(cat, 0) + 1
        for sc in ev.failed_scenarios[i]:
            by_scenario[sc] = by_scenario.get(sc, 0) + 1
        rec = records.get(tx_id)
        if rec is not None:
            t = rec.transaction.transaction_type
            by_type[t] = by_type.get(t, 0) + 1
    return {
        "policy": policy_name,
        "budget": budget,
        "k": k,
        "n_selected": int(k),
        "n_found": int(found.sum()),
        "n_missed_failures": int(missed.sum()),
        "miss_rate_of_failures": float(missed.sum() / max(ev.n_failures, 1)),
        "missed_by_category": by_category,
        "missed_by_failed_scenario": by_scenario,
        "missed_by_transaction_type": by_type,
        "missed_ids_sample": missed_ids[:30],
    }


def signal_correlations(ev: SplitEvaluation) -> dict[str, float]:
    out = {
        "M_magnitude": _point_biserial(ev.signals["magnitude"], ev.failed),
        "D_dependency": _point_biserial(ev.signals["dependency"], ev.failed),
        "A_anomaly_norm": _point_biserial(ev.signals["anomaly"], ev.failed),
        "U_uncertainty": _point_biserial(ev.signals["uncertainty"], ev.failed),
        "gate_score": _point_biserial(ev.score, ev.failed),
        "anomaly_raw": _point_biserial(ev.anomaly_raw, ev.failed),
        "amount_z": _point_biserial(ev.amount_z, ev.failed),
    }
    return out


def score_distributions(ev: SplitEvaluation) -> dict[str, Any]:
    def stats(x: np.ndarray, mask: np.ndarray) -> dict[str, float]:
        v = x[mask]
        if v.size == 0:
            return {"n": 0}
        return {
            "n": int(v.size),
            "mean": float(v.mean()),
            "std": float(v.std()),
            "p50": float(np.percentile(v, 50)),
            "p90": float(np.percentile(v, 90)),
            "max": float(v.max()),
        }

    fail = ev.failed
    ok = ~ev.failed
    return {
        "gate_score": {"failures": stats(ev.score, fail), "non_failures": stats(ev.score, ok)},
        "anomaly_raw": {"failures": stats(ev.anomaly_raw, fail), "non_failures": stats(ev.anomaly_raw, ok)},
        "M": {"failures": stats(ev.signals["magnitude"], fail), "non_failures": stats(ev.signals["magnitude"], ok)},
        "D": {"failures": stats(ev.signals["dependency"], fail), "non_failures": stats(ev.signals["dependency"], ok)},
        "A": {"failures": stats(ev.signals["anomaly"], fail), "non_failures": stats(ev.signals["anomaly"], ok)},
        "U": {"failures": stats(ev.signals["uncertainty"], fail), "non_failures": stats(ev.signals["uncertainty"], ok)},
    }


def methodology_checks(ev: SplitEvaluation, repo: DataRepository) -> dict[str, Any]:
    """Verify budget_curve fairness assumptions on this evaluation."""
    n = ev.n
    budget_checks = {}
    for b in config.EXPERIMENT_BUDGETS:
        k = _budget_count(n, b)
        budget_checks[str(b)] = {"k": k, "fraction": k / n}
    # anomaly_raw vs CDF-A rank agreement (Spearman via top-k Jaccard at several k)
    agreement = []
    for b in (0.01, 0.05, 0.10):
        k = _budget_count(n, b)
        sa = set(np.argsort(-ev.anomaly_raw, kind="stable")[:k].tolist())
        sb = set(np.argsort(-ev.signals["anomaly"], kind="stable")[:k].tolist())
        agreement.append({"budget": b, "jaccard": len(sa & sb) / max(len(sa | sb), 1)})
    # same labels for all policies (implicit: single ev)
    return {
        "n": n,
        "n_failures": ev.n_failures,
        "split": ev.split,
        "budget_k": budget_checks,
        "anomaly_raw_vs_cdf_A_topk_jaccard": agreement,
        "labels_source": "CrashTestEngine via label_record (simulator, not gate)",
        "models_fitted_on": "calibration only (GateModels.fit DataLeakError guard)",
        "test_split_used": False,
        "ranking_semantics": "stable argsort descending; top-k simulated; identical k per budget for all policies",
    }


def demo_tx_breakdown(repo: DataRepository, models) -> dict[str, Any]:
    tx = repo.demo_transaction()
    account, graph, context = repo.load_context(tx)
    impact = ImpactGate.score(tx, account, graph, context)
    X = extract_features(tx, account, graph, context)
    extras_needed = {
        "recent_count": float(X[_idx("recent_count")]),
        "recent_amount_ratio": float(X[_idx("recent_amount_ratio")]),
        "recent_same_type": float(X[_idx("recent_same_type")]),
        "amount_z": float(X[_idx("amount_zscore")]),
        "max_bg": float(X[_idx("max_background_load")]),
        "path_max_bg": float(X[_idx("path_max_background_load")]),
    }
    rec = repo.record(tx.id)
    return {
        "transaction_id": tx.id,
        "model_backend": models.backend,
        "amount": tx.amount,
        "account_avg": account.historical_avg_amount,
        "account_std": account.historical_std_amount,
        "signals": {
            "M": impact.signals.magnitude,
            "D": impact.signals.dependency,
            "A": impact.signals.anomaly,
            "U": impact.signals.uncertainty,
        },
        "contributions": {
            "M": 0.30 * impact.signals.magnitude,
            "D": 0.30 * impact.signals.dependency,
            "A": 0.25 * impact.signals.anomaly,
            "U": 0.15 * impact.signals.uncertainty,
        },
        "score": impact.score,
        "threshold": config.IMPACT_THRESHOLD,
        "gate_decision": impact.gate_decision,
        "features": extras_needed,
        "category_label_not_used_by_gate": rec.category if rec else None,
        "path": f"score {impact.score:.6f} {'>=' if impact.gate_decision else '<'} 0.60 -> "
        + ("SIMULATE" if impact.gate_decision else "SKIP NO_SIMULATION"),
    }


def category_recall_table(ev: SplitEvaluation, interaction_score: np.ndarray, budget: float = 0.10) -> dict[str, Any]:
    k = _budget_count(ev.n, budget)
    masks = {
        "anomaly_only": _top_k_mask(ev.anomaly_raw, k),
        "BLACKBOX_frozen_gate": _top_k_mask(ev.score, k),
        "interaction_aware": _top_k_mask(interaction_score, k),
    }
    out: dict[str, Any] = {}
    for cat in sorted(set(ev.categories)):
        fail_mask = np.asarray([c == cat for c in ev.categories]) & ev.failed
        n_cat = int(fail_mask.sum())
        if n_cat == 0:
            out[cat] = {"n_failures": 0}
            continue
        entry = {"n_failures": n_cat}
        for pol, sel in masks.items():
            entry[pol] = float((sel & fail_mask).sum() / n_cat)
        out[cat] = entry
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2/3 gate diagnosis and research experiment")
    parser.add_argument("--split", default="validation", choices=["validation", "calibration"])
    parser.add_argument("--budgets", default="0.005,0.01,0.02,0.05,0.10,1.0")
    args = parser.parse_args()
    budgets = tuple(float(x) for x in args.budgets.split(","))

    t0 = time.perf_counter()
    repo = DataRepository.default()
    models = fit_models(repo)
    ImpactGate.use_models(models)

    ev = evaluate_split(repo, models, args.split)
    extras = build_interaction_features(ev, repo)
    inter = interaction_aware_score(ev, extras)

    # Category recall at 10% for joint-danger focus
    cat_10 = category_recall_table(ev, inter, budget=0.10)

    # FN profiles at 10%
    fn_anomaly = false_negative_profile(ev, ev.anomaly_raw, 0.10, "anomaly_only")
    fn_gate = false_negative_profile(ev, ev.score, 0.10, "BLACKBOX_frozen_gate")
    fn_inter = false_negative_profile(ev, inter, 0.10, "interaction_aware")

    # Threshold operating points
    top_threshold = threshold_operating_point(ev)
    # Interaction-aware threshold analogue: same selection rate as gate threshold
    sel_rate = float(ev.gate_decision.mean())
    k_thr = max(1, int(round(sel_rate * ev.n)))
    inter_sel = _top_k_mask(inter, k_thr)
    inter_thr_recall = float((inter_sel & ev.failed).sum() / max(ev.n_failures, 1))
    inter_thr_precision = float((inter_sel & ev.failed).sum() / max(inter_sel.sum(), 1))

    corr = signal_correlations(ev)
    dists = score_distributions(ev)
    method = methodology_checks(ev, repo)
    demo = demo_tx_breakdown(repo, models)

    # Window pressure predictive check (validation, read-only)
    wp_fail = float(extras["window_pressure"][ev.failed].mean()) if ev.failed.any() else 0.0
    wp_ok = float(extras["window_pressure"][~ev.failed].mean()) if (~ev.failed).any() else 0.0
    wp_corr = _point_biserial(extras["window_pressure"], ev.failed)

    curve = rank_policies(ev, inter, budgets)

    elapsed = time.perf_counter() - t0
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ANALYSIS_ROOT / f"phase2_{stamp}_{models.backend}_{args.split}"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "report": "phase2_gate_diagnosis_and_research",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "split": args.split,
        "model_backend": models.backend,
        "python": platform.python_version(),
        "architecture": platform.machine(),
        "linuxone_verified": (platform.machine() == "s390x"),
        "elapsed_s": round(elapsed, 2),
        "methodology": method,
        "signal_point_biserial_with_failure": corr,
        "score_distributions": dists,
        "window_pressure": {"mean_failures": wp_fail, "mean_non_failures": wp_ok, "corr_with_failure": wp_corr},
        "budget_curve": curve,
        "category_recall_at_10pct": cat_10,
        "false_negative_profile_at_10pct": {
            "anomaly_only": fn_anomaly,
            "BLACKBOX_frozen_gate": fn_gate,
            "interaction_aware": fn_inter,
        },
        "threshold_operating_point_frozen_gate": top_threshold,
        "interaction_matched_select_rate": {
            "select_rate": sel_rate,
            "k": k_thr,
            "failure_recall": inter_thr_recall,
            "precision": inter_thr_precision,
        },
        "demo_tx": demo,
        "hypothesis_evaluation_rule": (
            "Hypothesis supported only if interaction_aware failure_recall > anomaly_only "
            "at 1%, 5% and 10% on validation with identical k, labels and seeds."
        ),
        "frozen_constants_untouched": {
            "weights": dict(config.IMPACT_WEIGHTS),
            "threshold": config.IMPACT_THRESHOLD,
            "scenarios": list(config.SCENARIOS),
        },
    }

    # Determine hypothesis outcome from primary budgets
    primary = {}
    for b in (0.01, 0.05, 0.10):
        row_i = next(r for r in curve if r["policy"] == "interaction_aware" and r["budget"] == b)
        row_a = next(r for r in curve if r["policy"] == "anomaly_only" and r["budget"] == b)
        row_g = next(r for r in curve if r["policy"] == "BLACKBOX_frozen_gate" and r["budget"] == b)
        primary[str(b)] = {
            "interaction_aware": row_i["failure_recall"],
            "anomaly_only": row_a["failure_recall"],
            "BLACKBOX_frozen_gate": row_g["failure_recall"],
            "beats_anomaly": row_i["failure_recall"] > row_a["failure_recall"],
            "beats_gate": row_i["failure_recall"] > row_g["failure_recall"],
        }
    wins = sum(1 for v in primary.values() if v["beats_anomaly"])
    if wins == 3:
        verdict = "SUPPORTED_on_validation"
    elif wins == 0:
        verdict = "REJECTED_on_validation"
    else:
        verdict = "INCONCLUSIVE_partial_wins"
    payload["primary_budget_comparison"] = primary
    payload["hypothesis_verdict"] = verdict

    (out_dir / "results.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    # Markdown summary
    lines = [
        "# Phase 2/3 — Gate diagnosis and interaction-aware experiment",
        "",
        f"- created_at_utc: {payload['created_at_utc']}",
        f"- split: **{args.split}** (test split NOT used)",
        f"- model_backend: **{models.backend}**",
        f"- architecture: {payload['architecture']} (linuxone_verified={payload['linuxone_verified']})",
        f"- elapsed_s: {payload['elapsed_s']}",
        "",
        "## Signal correlation with failure (point-biserial, validation)",
        "",
        "| signal | r |",
        "|---|---|",
    ]
    for k, v in corr.items():
        lines.append(f"| {k} | {v:.4f} |")
    lines += [
        "",
        "## Failure recall at fixed budget (validation)",
        "",
        "| budget | random | amount_only | anomaly_only | BLACKBOX frozen | interaction_aware |",
        "|---|---|---|---|---|---|",
    ]
    for b in budgets:
        def get(pol: str) -> str:
            r = next(x for x in curve if x["policy"] == pol and x["budget"] == b)
            return f"{r['failure_recall']:.3f}"
        lines.append(
            f"| {b:.3f} | {get('random')} | {get('amount_only')} | {get('anomaly_only')} | "
            f"{get('BLACKBOX_frozen_gate')} | {get('interaction_aware')} |"
        )
    lines += [
        "",
        f"**Hypothesis verdict (validation only): {verdict}**",
        "",
        "## Demo TX-DEMO-0001",
        "",
        f"- score {demo['score']:.6f} vs threshold {demo['threshold']}",
        f"- M={demo['signals']['M']:.4f} D={demo['signals']['D']:.4f} "
        f"A={demo['signals']['A']:.4f} U={demo['signals']['U']:.4f}",
        f"- path: {demo['path']}",
        "",
        "## False negatives at 10% budget",
        "",
        f"- anomaly_only missed {fn_anomaly['n_missed_failures']} / {ev.n_failures} failures",
        f"- BLACKBOX gate missed {fn_gate['n_missed_failures']} / {ev.n_failures} failures",
        f"- interaction_aware missed {fn_inter['n_missed_failures']} / {ev.n_failures} failures",
        "",
        "Full JSON: `results.json` in this directory.",
        "AMD64/numpy results do NOT establish LinuxONE or sklearn-backend equivalence.",
    ]
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"backend={models.backend} split={args.split} elapsed={elapsed:.1f}s")
    print(f"out={out_dir}")
    print(f"hypothesis_verdict={verdict}")
    for b in (0.01, 0.05, 0.10):
        p = primary[str(b)]
        print(
            f"  budget {b:.0%}: anomaly={p['anomaly_only']:.3f} "
            f"gate={p['BLACKBOX_frozen_gate']:.3f} interaction={p['interaction_aware']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
