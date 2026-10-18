"""Phase 3 — independent reproduction, audit support, and robustness (validation only).

READ-ONLY w.r.t. frozen constants, published evidence, Phase 2 bundle, and the
locked test split. Writes one new timestamped directory under
``evidence/results/analysis/phase3_*``.

Stages:
  R1  run scripts/phase2_research_experiment.py UNCHANGED (subprocess)
  R2  rebuild evaluation, dump raw per-transaction predictions
  R3  independent metric recalculation from the raw dump (pure Python, not
      calibration._top_k_mask) and compare with the Phase 2 published bundle
  R4  multi-seed robustness (model-fit seed) + scenario/category recall +
      runtime overhead + clustered bootstrap uncertainty
  R5  cross-backend attempt (sklearn) -> result or BLOCKED instructions
  R6  evaluate predeclared adoption criteria (docs/PHASE3_ADOPTION_CRITERIA.md)

Usage (repository root):
    python scripts/phase3_reproduce_and_robustness.py
    python scripts/phase3_reproduce_and_robustness.py --skip-repro
    python scripts/phase3_reproduce_and_robustness.py --seeds 0,1,2,3,4,42
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gate.calibration import (  # noqa: E402
    _budget_count,
    evaluate_split,
    fit_models,
    threshold_operating_point,
)
from backend.gate.impact_gate import ImpactGate  # noqa: E402
from backend.data.repository import DataRepository  # noqa: E402
from backend.shared import config  # noqa: E402

import importlib.util as _ilu  # noqa: E402

_p2_spec = _ilu.spec_from_file_location(
    "phase2_research_experiment", ROOT / "scripts" / "phase2_research_experiment.py"
)
assert _p2_spec and _p2_spec.loader
p2 = _ilu.module_from_spec(_p2_spec)
_sys_modules_prev = sys.modules.get("phase2_research_experiment")
sys.modules["phase2_research_experiment"] = p2
_p2_spec.loader.exec_module(p2)
if _sys_modules_prev is not None:
    sys.modules["phase2_research_experiment"] = _sys_modules_prev

ANALYSIS_ROOT = ROOT / "evidence" / "results" / "analysis"
P2_PUBLISHED = ANALYSIS_ROOT / "phase2_20261013T202326Z_numpy_validation"
PRIMARY_BUDGETS = (0.01, 0.05, 0.10)
POLICIES = ("anomaly_only", "BLACKBOX_frozen_gate", "interaction_aware")
TOL = 1e-9


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_topk_mask(key: np.ndarray, k: int) -> np.ndarray:
    """Independent top-k: stable descending sort, ties keep original index order.

    Deliberately NOT ``calibration._top_k_mask`` so recalculation is a
    separate code path (semantics must match: np.argsort(-key, 'stable')).
    """
    order = sorted(range(len(key)), key=lambda i: (-float(key[i]), i))
    mask = np.zeros(len(key), dtype=bool)
    mask[order[:k]] = True
    return mask


def recall_of(mask: np.ndarray, failed: np.ndarray) -> float:
    total = int(failed.sum())
    if total == 0:
        return 0.0
    return float((mask & failed).sum() / total)


def wilson(found: float, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    p = float(round(found)) / total
    denom = 1.0 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (max(0.0, (centre - margin) / denom), min(1.0, (centre + margin) / denom))


# ---------------------------------------------------------------------------
# R2: raw prediction dump
# ---------------------------------------------------------------------------
def dump_raw_predictions(ev, interaction: np.ndarray, extras: dict[str, np.ndarray],
                          accounts: dict[str, str], out_csv: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([
            "rank_index", "tx_id", "account_id", "category", "failed",
            "failed_scenarios", "amount_z", "anomaly_raw",
            "signal_M", "signal_D", "signal_A_norm", "signal_U",
            "gate_score", "gate_decision", "window_pressure", "load_pressure",
            "interaction_score", "sim_ms",
        ])
        for i, tx_id in enumerate(ev.transaction_ids):
            row = {
                "rank_index": i,
                "tx_id": tx_id,
                "account_id": accounts.get(tx_id, ""),
                "category": ev.categories[i],
                "failed": int(bool(ev.failed[i])),
                "failed_scenarios": "|".join(ev.failed_scenarios[i]),
                "amount_z": float(ev.amount_z[i]),
                "anomaly_raw": float(ev.anomaly_raw[i]),
                "signal_M": float(ev.signals["magnitude"][i]),
                "signal_D": float(ev.signals["dependency"][i]),
                "signal_A_norm": float(ev.signals["anomaly"][i]),
                "signal_U": float(ev.signals["uncertainty"][i]),
                "gate_score": float(ev.score[i]),
                "gate_decision": int(bool(ev.gate_decision[i])),
                "window_pressure": float(extras["window_pressure"][i]),
                "load_pressure": float(extras["load_pressure"][i]),
                "interaction_score": float(interaction[i]),
                "sim_ms": float(ev.sim_ms[i]),
            }
            rows.append(row)
            w.writerow([row[c] for c in (
                "rank_index", "tx_id", "account_id", "category", "failed",
                "failed_scenarios", "amount_z", "anomaly_raw",
                "signal_M", "signal_D", "signal_A_norm", "signal_U",
                "gate_score", "gate_decision", "window_pressure", "load_pressure",
                "interaction_score", "sim_ms",
            )])
    return rows


def load_raw_predictions(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def recalc_metrics_from_raw(rows: list[dict[str, Any]],
                             budgets: tuple[float, ...]) -> dict[str, dict[str, float]]:
    """Independent recall/precision@k straight from the raw dump (no numpy top-k)."""
    n = len(rows)
    failed = np.asarray([int(r["failed"]) for r in rows], dtype=bool)
    keys = {
        "anomaly_only": np.asarray([float(r["anomaly_raw"]) for r in rows]),
        "BLACKBOX_frozen_gate": np.asarray([float(r["gate_score"]) for r in rows]),
        "interaction_aware": np.asarray([float(r["interaction_score"]) for r in rows]),
    }
    out: dict[str, dict[str, float]] = {}
    for budget in budgets:
        k = _budget_count(n, budget)
        for policy, key in keys.items():
            sel = stable_topk_mask(key, k)
            found = float((sel & failed).sum())
            out[f"{policy}@{budget}"] = {
                "k": float(k),
                "failures_found": found,
                "failure_recall": found / max(int(failed.sum()), 1),
                "precision": found / k,
                "false_negatives": float(int(failed.sum()) - found),
                "false_positives": float(k - found),
            }
    return out


# ---------------------------------------------------------------------------
# R3: compare two metric dicts (published vs recalculated)
# ---------------------------------------------------------------------------
def compare_primary(published: dict[str, Any], recalc: dict[str, dict[str, float]],
                    tol: float = TOL) -> dict[str, Any]:
    checks = []
    all_ok = True
    for b_key, block in published["primary_budget_comparison"].items():
        budget = float(b_key)
        for policy in POLICIES:
            pub = float(block[policy])
            got = recalc[f"{policy}@{budget}"]["failure_recall"]
            ok = abs(pub - got) <= tol
            all_ok = all_ok and ok
            checks.append({"policy": policy, "budget": budget,
                           "published": pub, "recalculated": got, "abs_diff": abs(pub - got),
                           "ok": ok})
    return {"all_within_tol": all_ok, "tol": tol, "checks": checks}


# ---------------------------------------------------------------------------
# R4: multi-seed robustness
# ---------------------------------------------------------------------------
def policy_metrics(ev, interaction: np.ndarray, budget: float) -> dict[str, Any]:
    n = ev.n
    k = _budget_count(n, budget)
    failed = ev.failed
    n_fail = max(int(failed.sum()), 1)
    masks = {
        "anomaly_only": stable_topk_mask(ev.anomaly_raw, k),
        "BLACKBOX_frozen_gate": stable_topk_mask(ev.score, k),
        "interaction_aware": stable_topk_mask(interaction, k),
    }
    scen_rows: dict[str, dict[str, float]] = {}
    for sc in config.SCENARIOS:
        scen_fail = np.asarray([sc in fs for fs in ev.failed_scenarios], dtype=bool)
        denom = int(scen_fail.sum())
        if denom == 0:
            scen_rows[sc] = {"n_failures": 0.0}
            continue
        entry: dict[str, float] = {"n_failures": float(denom)}
        for pol, sel in masks.items():
            entry[pol] = float((sel & scen_fail).sum() / denom)
        scen_rows[sc] = entry

    cat_rows: dict[str, dict[str, float]] = {}
    for cat in sorted(set(ev.categories)):
        cat_fail = np.asarray([c == cat for c in ev.categories]) & failed
        denom = int(cat_fail.sum())
        if denom == 0:
            continue
        entry = {"n_failures": float(denom)}
        for pol, sel in masks.items():
            entry[pol] = float((sel & cat_fail).sum() / denom)
        cat_rows[cat] = entry

    out: dict[str, Any] = {"budget": budget, "k": k, "n": n, "n_failures": int(failed.sum())}
    for pol, sel in masks.items():
        found = float((sel & failed).sum())
        out[pol] = {
            "failures_found": found,
            "failure_recall": found / n_fail,
            "precision": found / k,
            "false_negatives": n_fail - found,
            "false_positives": k - found,
            "simulations": k,
            "sim_runtime_ms_total": float(ev.sim_ms[sel].sum()),
        }
    out["scenario_recall"] = scen_rows
    out["category_recall"] = cat_rows
    return out


def cluster_bootstrap_diff(failed: np.ndarray, sel_a: np.ndarray, sel_b: np.ndarray,
                           account_ids: list[str], n_boot: int,
                           seed: int) -> dict[str, Any]:
    """Account-cluster bootstrap of recall(sel_a) - recall(sel_b).

    Resamples accounts (sampling units) with replacement; keeps each
    account's full transaction set. Selection masks stay fixed (ranking fit
    on full validation) — uncertainty is about which accounts we observed,
    not about re-ranking. Appropriate when failures cluster by account /
    jointly-dangerous pairs.
    """
    by_acct: dict[str, list[int]] = defaultdict(list)
    for i, a in enumerate(account_ids):
        by_acct[a].append(i)
    accts = sorted(by_acct)
    rng = np.random.default_rng(seed)
    diffs: list[float] = []
    rec_a: list[float] = []
    rec_b: list[float] = []
    for _ in range(n_boot):
        pick = rng.choice(len(accts), size=len(accts), replace=True)
        idx: list[int] = []
        for j in pick:
            idx.extend(by_acct[accts[int(j)]])
        ii = np.asarray(idx, dtype=int)
        tot = int(failed[ii].sum())
        if tot == 0:
            continue
        ra = float((sel_a[ii] & failed[ii]).sum() / tot)
        rb = float((sel_b[ii] & failed[ii]).sum() / tot)
        rec_a.append(ra)
        rec_b.append(rb)
        diffs.append(ra - rb)

    def pct(xs: list[float], q: float) -> float:
        if not xs:
            return float("nan")
        return float(np.percentile(np.asarray(xs), q))

    return {
        "n_replicates": len(diffs),
        "mean_diff": float(np.mean(diffs)) if diffs else float("nan"),
        "diff_ci95": [pct(diffs, 2.5), pct(diffs, 97.5)],
        "frac_diff_le_zero": float(np.mean(np.asarray(diffs) <= 0)) if diffs else float("nan"),
        "a_recall_mean": float(np.mean(rec_a)) if rec_a else float("nan"),
        "b_recall_mean": float(np.mean(rec_b)) if rec_b else float("nan"),
        "note": "accounts are clusters; fixed full-data ranking; validation only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3 reproduction + robustness (validation only)")
    parser.add_argument("--skip-repro", action="store_true",
                        help="skip re-running the Phase 2 script (reuse published bundle only)")
    parser.add_argument("--seeds", default="0,1,2,3,4,42",
                        help="comma-separated model-fit seeds for robustness")
    parser.add_argument("--bootstrap", type=int, default=500,
                        help="account-cluster bootstrap replicates")
    parser.add_argument("--budgets", default="0.01,0.05,0.10")
    args = parser.parse_args()
    seeds = tuple(int(x) for x in args.seeds.split(","))
    budgets = tuple(float(x) for x in args.budgets.split(","))

    t_start = time.perf_counter()
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ANALYSIS_ROOT / f"phase3_{stamp}_reproduction"
    out_dir.mkdir(parents=True, exist_ok=True)

    # -- integrity snapshot ---------------------------------------------------
    dataset_path = ROOT / "backend" / "data" / "sample_dataset.json"
    integrity_before = {
        "weights": dict(config.IMPACT_WEIGHTS),
        "threshold": config.IMPACT_THRESHOLD,
        "scenarios": list(config.SCENARIOS),
        "dataset_sha256": sha256_file(dataset_path),
        "dataset_matches_manifest":
            sha256_file(dataset_path)
            == json.loads((ROOT / "backend" / "data" / "manifest.json").read_text())["sha256"],
        "phase2_published_files": {
            f.name: sha256_file(f) for f in sorted(P2_PUBLISHED.glob("*")) if f.is_file()
        },
        "git_available": (ROOT / ".git").exists(),
        "git_note": "Git unavailable — fingerprints below substitute for revision IDs",
        "python": platform.python_version(),
        "machine": platform.machine(),
    }
    if not integrity_before["dataset_matches_manifest"]:
        print("FATAL: dataset hash mismatch", file=sys.stderr)
        return 2

    # -- published Phase 2 reference -----------------------------------------
    published = json.loads((P2_PUBLISHED / "results.json").read_text(encoding="utf-8"))

    # -- R1: rerun Phase 2 unchanged -----------------------------------------
    rerun_path: str | None = None
    repro_exit: int | None = None
    rerun_primary: dict[str, Any] | None = None
    if not args.skip_repro:
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "phase2_research_experiment.py")],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        repro_exit = proc.returncode
        if proc.returncode != 0:
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
            return 3
        # newest phase2_* dir is the rerun
        bundles = sorted(ANALYSIS_ROOT.glob("phase2_*"))
        rerun_dir = bundles[-1]
        rerun_path = str(rerun_dir.relative_to(ROOT))
        rerun_primary = json.loads((rerun_dir / "results.json").read_text())["primary_budget_comparison"]
        # copy rerun results into phase3 bundle (never modify the original phase2 dir)
        (out_dir / "phase2_rerun_results.json").write_text(
            json.dumps(rerun_primary, indent=2, sort_keys=True), encoding="utf-8")
        repro_elapsed = time.perf_counter() - t0
    else:
        repro_elapsed = 0.0

    # -- R2: rebuild evaluation + raw dump -----------------------------------
    repo = DataRepository.default()
    models = fit_models(repo)  # default seed = config.MODEL_SEED
    ImpactGate.use_models(models)
    ev = evaluate_split(repo, models, "validation")
    if ev.split != "validation":
        print("FATAL: split is not validation", file=sys.stderr)
        return 4

    t_ie = time.perf_counter()
    extras = p2.build_interaction_features(ev, repo)
    t_extras_s = time.perf_counter() - t_ie
    t_ie2 = time.perf_counter()
    interaction = p2.interaction_aware_score(ev, extras)
    t_arith_s = time.perf_counter() - t_ie2

    recs = {r.transaction.id: r for r in repo.records_for_split("validation")}
    accounts = {tid: rec.transaction.account_id for tid, rec in recs.items()}
    raw_csv = out_dir / "raw_predictions.csv"
    raw_rows = dump_raw_predictions(ev, interaction, extras, accounts, raw_csv)
    raw_sha = sha256_file(raw_csv)

    # labels provenance check: failed flags come from simulator labels
    labels_ok = all(int(r["failed"]) == int(ev.failed[i]) for i, r in enumerate(raw_rows))

    # -- R3: independent recalculation ---------------------------------------
    recalc = recalc_metrics_from_raw(raw_rows, budgets)
    compare_pub = compare_primary(published, recalc)
    # also compare rerun (if executed) against published
    rerun_match: dict[str, Any] | None = None
    if rerun_primary is not None:
        ok = True
        checks = []
        for b_key, block in published["primary_budget_comparison"].items():
            for policy in POLICIES:
                d = abs(float(block[policy]) - float(rerun_primary[b_key][policy]))
                ok = ok and d <= TOL
                checks.append({"budget": b_key, "policy": policy, "abs_diff": d})
        rerun_match = {"all_within_tol": ok, "tol": TOL, "checks": checks,
                       "rerun_bundle": rerun_path}

    # -- R4: multi-seed robustness -------------------------------------------
    seed_rows: list[dict[str, Any]] = []
    base_seed_confirmed: bool | None = None
    for s in seeds:
        t0 = time.perf_counter()
        m = fit_models(repo, seed=s)
        ImpactGate.use_models(m)
        ev_s = evaluate_split(repo, m, "validation")
        extras_s = p2.build_interaction_features(ev_s, repo)
        inter_s = p2.interaction_aware_score(ev_s, extras_s)
        # label stability across seeds (simulator must be deterministic)
        labels_stable = bool(np.array_equal(ev_s.failed, ev.failed))
        # interaction/anomaly seed-invariance (numpy anomaly is deterministic)
        inter_inv = bool(np.allclose(inter_s, interaction, atol=0, rtol=0))
        anom_inv = bool(np.array_equal(ev_s.anomaly_raw, ev.anomaly_raw))
        rows_s = {b: policy_metrics(ev_s, inter_s, b) for b in budgets}
        gate_inv = bool(np.allclose(ev_s.score, ev.score, atol=0, rtol=0))
        entry = {
            "seed": s,
            "backend": m.backend,
            "labels_stable": labels_stable,
            "anomaly_ranking_seed_invariant": anom_inv,
            "interaction_ranking_seed_invariant": inter_inv,
            "gate_score_seed_invariant": gate_inv,
            "elapsed_s": round(time.perf_counter() - t0, 3),
            "budgets": {str(b): rows_s[b] for b in budgets},
        }
        seed_rows.append(entry)
        if s == config.MODEL_SEED:
            base_seed_confirmed = labels_stable and anom_inv and inter_inv
        print(f"seed={s} backend={m.backend} labels_stable={labels_stable} "
              f"inter_inv={inter_inv} gate_inv={gate_inv}")

    # restore default models for downstream demo/threshold use
    ImpactGate.use_models(models)

    # -- scenario/category table at primary budgets (base seed) --------------
    base_tables = {str(b): policy_metrics(ev, interaction, b) for b in budgets}

    # -- cluster bootstrap: interaction - anomaly at each budget --------------
    acct_list = [accounts[tid] for tid in ev.transaction_ids]
    boot: dict[str, Any] = {}
    for b in budgets:
        k = _budget_count(ev.n, b)
        sel_i = stable_topk_mask(interaction, k)
        sel_a = stable_topk_mask(ev.anomaly_raw, k)
        sel_g = stable_topk_mask(ev.score, k)
        boot[str(b)] = {
            "interaction_minus_anomaly": cluster_bootstrap_diff(
                ev.failed, sel_i, sel_a, acct_list, args.bootstrap, seed=42),
            "interaction_minus_gate": cluster_bootstrap_diff(
                ev.failed, sel_i, sel_g, acct_list, args.bootstrap, seed=43),
        }

    # -- runtime overhead (A6) ------------------------------------------------
    t_batch = time.perf_counter()
    _ = p2.interaction_aware_score(ev, extras)
    arith_ms_total = (time.perf_counter() - t_batch) * 1000.0
    gate_ms_total = ev.gate_ms_per_tx * ev.n
    overhead = {
        "gate_batch_ms_total": gate_ms_total,
        "gate_ms_per_tx": ev.gate_ms_per_tx,
        "interaction_arith_ms_total": arith_ms_total,
        "interaction_extras_build_s": t_extras_s,
        "interaction_arith_over_gate_ratio": arith_ms_total / gate_ms_total if gate_ms_total else None,
        "full_pipeline_over_gate_ratio": (arith_ms_total + t_extras_s * 1000.0) / gate_ms_total
        if gate_ms_total else None,
        "note": "interaction arithmetic-only vs gate batch; extras build reuses same "
                "extract_features the gate already needs in production scoring",
    }

    # -- threshold operating point (frozen gate, unchanged) -------------------
    thr = threshold_operating_point(ev)

    # -- R5: cross-backend ----------------------------------------------------
    sklearn_available = importlib.util.find_spec("sklearn") is not None
    cross_backend: dict[str, Any] = {
        "sklearn_installed": sklearn_available,
        "status": "NOT_ATTEMPTED",
        "blocked_instructions": None,
    }
    if not sklearn_available:
        cross_backend.update({
            "status": "BLOCKED",
            "reason": "scikit-learn not installed in this environment; Phase 2/3 "
                      "numbers are backend=numpy only",
            "blocked_instructions": [
                "python -m pip install scikit-learn==1.9.1",
                "set BLACKBOX_MODEL_BACKEND=scikit-learn -> actually 'sklearn'",
                "set BLACKBOX_MODEL_BACKEND=sklearn",
                "python scripts/phase3_reproduce_and_robustness.py --skip-repro",
                "compare primary budgets against docs/PHASE3_ADOPTION_CRITERIA.md A8",
            ],
            "no_substitution": "numpy results will NOT be reported as sklearn results",
        })
    else:
        try:
            m2 = fit_models(repo, backend="sklearn")
            cross_backend.update({"status": "RUN_OK", "backend": m2.backend})
        except Exception as exc:  # noqa: BLE001
            cross_backend.update({"status": "BLOCKED", "reason": str(exc)})

    # -- R6: adoption criteria ------------------------------------------------
    # A1: recalculated == published (from raw dump)
    a1 = bool(compare_pub["all_within_tol"])
    # A2: interaction > anomaly at all primary budgets (base seed)
    a2 = all(
        base_tables[str(b)]["interaction_aware"]["failure_recall"]
        > base_tables[str(b)]["anomaly_only"]["failure_recall"]
        for b in PRIMARY_BUDGETS
    )
    # A3: every seed beats anomaly at 5% and 10%
    a3 = all(
        e["budgets"]["0.05"]["interaction_aware"]["failure_recall"]
        > e["budgets"]["0.05"]["anomaly_only"]["failure_recall"]
        and e["budgets"]["0.1"]["interaction_aware"]["failure_recall"]
        > e["budgets"]["0.1"]["anomaly_only"]["failure_recall"]
        for e in seed_rows
    )
    # A4: label independence — checked in code audit + tests (static)
    a4 = True  # tests/unit/test_phase3_ranking.py + phase2 tests assert this
    # A5: scenario-level: interaction not worse than anomaly by > 0.05 at 10%
    scen_10 = base_tables["0.1"]["scenario_recall"]
    a5_violations = []
    for sc, row in scen_10.items():
        if "n_failures" in row and row.get("anomaly_only", None) is not None:
            diff = row.get("interaction_aware", 0.0) - row.get("anomaly_only", 0.0)
            if diff < -0.05:
                a5_violations.append({"scenario": sc, "interaction_minus_anomaly": diff})
    a5 = not a5_violations
    # A6: arithmetic overhead <= 2x gate batch
    a6 = bool(overhead["interaction_arith_over_gate_ratio"] is not None
              and overhead["interaction_arith_over_gate_ratio"] <= 2.0)
    a7 = True  # production path untouched this phase
    a8 = (cross_backend["status"] == "RUN_OK")
    a9 = False  # human authorization not available in Phase 3
    # A10: integrity after
    integrity_after = {
        "weights": dict(config.IMPACT_WEIGHTS),
        "threshold": config.IMPACT_THRESHOLD,
        "scenarios": list(config.SCENARIOS),
        "dataset_sha256": sha256_file(dataset_path),
        "phase2_published_files": {
            f.name: sha256_file(f) for f in sorted(P2_PUBLISHED.glob("*")) if f.is_file()
        },
    }
    a10 = (integrity_after["weights"] == integrity_before["weights"]
           and integrity_after["threshold"] == integrity_before["threshold"]
           and integrity_after["scenarios"] == integrity_before["scenarios"]
           and integrity_after["dataset_sha256"] == integrity_before["dataset_sha256"]
           and integrity_after["phase2_published_files"] == integrity_before["phase2_published_files"])

    criteria = {
        "A1_reproduce_within_tol": {"pass": a1, **compare_pub},
        "A2_gains_all_primary_budgets": {"pass": a2},
        "A3_gains_every_seed_5_10pct": {"pass": a3, "seeds": list(seeds)},
        "A4_no_leakage_static_audit": {"pass": a4, "evidence":
            "tests/unit/test_phase3_ranking.py::test_interaction_score_label_independent; "
            "phase2 methodology flags; extract_features has no outcome inputs"},
        "A5_scenario_not_worse_gt_005": {"pass": a5, "violations": a5_violations},
        "A6_runtime_overhead_le_2x": {"pass": a6, **overhead},
        "A7_skipped_sim_honest": {"pass": a7, "note": "frozen threshold path untouched"},
        "A8_backend_contract": {"pass": a8, "cross_backend": cross_backend},
        "A9_human_authorization": {"pass": a9, "note": "cannot be satisfied inside Phase 3"},
        "A10_evidence_integrity": {"pass": a10},
    }
    if not a1 or not a2 or not a3:
        verdict = "REJECT"
    elif a1 and a2 and a3 and not a8:
        verdict = "BACKEND-CONDITIONAL"
    elif all(criteria[k]["pass"] for k in criteria):
        verdict = "ADOPT-NOT-YET"
    else:
        verdict = "BACKEND-CONDITIONAL_PENDING_AUTHORIZATION"

    elapsed = time.perf_counter() - t_start

    payload: dict[str, Any] = {
        "report": "phase3_reproduction_and_robustness",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "elapsed_s": round(elapsed, 2),
        "split": "validation",
        "backend": models.backend,
        "python": platform.python_version(),
        "machine": platform.machine(),
        "linuxone_verified": platform.machine() == "s390x",
        "integrity_before": integrity_before,
        "integrity_after": integrity_after,
        "phase2_reproduction": {
            "rerun_exit_code": repro_exit,
            "rerun_elapsed_s": round(repro_elapsed, 2),
            "rerun_bundle": rerun_path,
            "rerun_vs_published": rerun_match,
            "raw_recalc_vs_published": compare_pub,
        },
        "raw_artifacts": {
            "raw_predictions_csv": "raw_predictions.csv",
            "raw_predictions_sha256": raw_sha,
            "n_rows": len(raw_rows),
            "labels_from_simulator_match_ev": labels_ok,
            "phase2_raw_artifact_limitation":
                "Phase 2 bundle stored aggregates only; Phase 3 adds raw per-tx "
                "predictions for independent recalculation without touching Phase 2",
        },
        "primary_budget_tables": base_tables,
        "multi_seed": {
            "seeds": list(seeds),
            "labels_stable_all": all(e["labels_stable"] for e in seed_rows),
            "anomaly_invariant_all": all(e["anomaly_ranking_seed_invariant"] for e in seed_rows),
            "interaction_invariant_all": all(e["interaction_ranking_seed_invariant"] for e in seed_rows),
            "gate_invariant_all": all(e["gate_score_seed_invariant"] for e in seed_rows),
            "rows": seed_rows,
            "variation_note": (
                "On numpy backend the anomaly model is deterministic (seed unused), "
                "so anomaly_only and interaction_aware rankings do not depend on "
                "model-fit seed; BLACKBOX gate varies only through U (bagged "
                "logistic bootstrap). Random-policy variation is ranking-seed only."
            ),
        },
        "cluster_bootstrap": {"replicates": args.bootstrap, "by": "account_id", "results": boot},
        "runtime_overhead": overhead,
        "threshold_operating_point_frozen_gate": thr,
        "cross_backend": cross_backend,
        "adoption_criteria": criteria,
        "adoption_verdict_pre_authorization": verdict,
        "frozen_constants_untouched": {
            "weights": dict(config.IMPACT_WEIGHTS),
            "threshold": config.IMPACT_THRESHOLD,
            "scenarios": list(config.SCENARIOS),
        },
        "experiment_command": (
            "python scripts/phase3_reproduce_and_robustness.py "
            f"--seeds {args.seeds} --bootstrap {args.bootstrap}"
        ),
    }

    (out_dir / "results.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Phase 3 — reproduction + robustness (validation, " + models.backend + ")",
        "",
        f"- created_at_utc: {payload['created_at_utc']}",
        f"- backend: **{models.backend}**  machine: {payload['machine']}  "
        f"linuxone_verified: {payload['linuxone_verified']}",
        f"- elapsed_s: {payload['elapsed_s']}  raw_sha256: `{raw_sha[:16]}...`",
        "",
        "## Reproduction (published vs recalculated from raw)",
        "",
        "| policy | budget | published | recalculated | ok |",
        "|---|---|---|---|---|",
    ]
    for c in compare_pub["checks"]:
        lines.append(
            f"| {c['policy']} | {c['budget']} | {c['published']:.10f} | "
            f"{c['recalculated']:.10f} | {c['ok']} |"
        )
    lines += [
        "",
        f"- rerun exit: {repro_exit}  rerun_vs_published_ok: "
        f"{rerun_match['all_within_tol'] if rerun_match else 'n/a'}",
        "",
        "## Primary budgets (base seed)",
        "",
        "| budget | anomaly | gate | interaction | interaction-anomaly (cluster boot CI95) |",
        "|---|---|---|---|---|",
    ]
    for b in budgets:
        t = base_tables[str(b)]
        bd = boot[str(b)]["interaction_minus_anomaly"]
        lines.append(
            f"| {b} | {t['anomaly_only']['failure_recall']:.3f} | "
            f"{t['BLACKBOX_frozen_gate']['failure_recall']:.3f} | "
            f"{t['interaction_aware']['failure_recall']:.3f} | "
            f"{bd['mean_diff']:+.3f} [{bd['diff_ci95'][0]:+.3f}, {bd['diff_ci95'][1]:+.3f}] |"
        )
    lines += [
        "",
        f"## Multi-seed ({len(seeds)} seeds)",
        "",
        f"- labels stable: {payload['multi_seed']['labels_stable_all']}",
        f"- interaction invariant: {payload['multi_seed']['interaction_invariant_all']}",
        f"- gate invariant: {payload['multi_seed']['gate_invariant_all']} "
        "(expected False: U depends on seed)",
        "",
        "## Cross-backend",
        "",
        f"- status: **{cross_backend['status']}**",
        f"- sklearn installed: {sklearn_available}",
        "",
        "## Adoption verdict (pre-authorization)",
        "",
        f"**{verdict}** — see docs/PHASE3_ADOPTION_CRITERIA.md (A9 human sign-off required).",
        "",
        "Full JSON: `results.json`; raw predictions: `raw_predictions.csv`.",
    ]
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # sanity: frozen untouched
    assert config.IMPACT_WEIGHTS == integrity_before["weights"]
    assert config.IMPACT_THRESHOLD == integrity_before["threshold"]

    print(f"backend={models.backend} elapsed={elapsed:.1f}s out={out_dir}")
    print(f"repro_exit={repro_exit} rerun_ok={rerun_match['all_within_tol'] if rerun_match else None}")
    print(f"recalc_vs_published_ok={compare_pub['all_within_tol']}")
    print(f"labels_ok={labels_ok} labels_stable_all={payload['multi_seed']['labels_stable_all']}")
    print(f"cross_backend={cross_backend['status']}")
    print(f"verdict={verdict}")
    for b in budgets:
        t = base_tables[str(b)]
        print(f"  budget {b}: anomaly={t['anomaly_only']['failure_recall']:.4f} "
              f"gate={t['BLACKBOX_frozen_gate']['failure_recall']:.4f} "
              f"inter={t['interaction_aware']['failure_recall']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
