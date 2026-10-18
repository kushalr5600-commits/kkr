"""Benchmark evaluation on user-mapped datasets (Challenge Lab).

Separates three label spaces — never mixed:

1. External labels (fraud / default / other) from user mapping.
2. Gate decisions (simulate vs skip) from the frozen Impact Gate.
3. Synthetic stress outcomes — only when explicitly requested on a capped sample.

Metrics for (1)x(2) describe selection, not safety. Fraud recall means the
fraction of fraud-labeled rows the gate selected for simulation, not the
fraction of simulator failures caught.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import numpy as np

from backend.data.repository import DependencyGraph, GraphEdge, GraphNode, build_graph
from backend.datasets.store import DatasetStore
from backend.gate.impact_gate import ImpactGate
from backend.gate.interaction_aware import is_enabled as _interaction_enabled
from backend.gate.models import GateModels, extract_features
from backend.shared import config
from backend.shared.errors import InputError
from backend.shared.schemas import Account, EventContext, Transaction

LabelKind = Literal["fraud", "default", "operational_failure", "other"]


@dataclass
class MappedRow:
    transaction: Transaction
    account: Account
    graph: DependencyGraph
    context: EventContext
    label: float | None
    row_index: int


def _parse_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(value):
        return None
    return value


def _parse_label(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        return 1.0 if float(raw) != 0 else 0.0
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "y", "fraud", "default", "positive", "fail"}:
        return 1.0
    if text in {"0", "false", "no", "n", "legit", "legitimate", "negative", "ok"}:
        return 0.0
    try:
        return 1.0 if float(text) != 0 else 0.0
    except ValueError:
        return None


def map_rows(
    store: DatasetStore,
    dataset_id: str,
    limit: int | None = None,
) -> list[MappedRow]:
    meta = store.get(dataset_id)
    if not meta.mapping:
        raise InputError(f"dataset {dataset_id!r} has no column mapping")
    mapping = meta.mapping
    rows = store.rows(dataset_id, limit=limit)
    amount_col = mapping["amount"]
    id_col = mapping["id"]
    acct_col = mapping["account_id"]
    ts_col = mapping["timestamp"]
    type_col = mapping["transaction_type"]
    label_col = mapping.get("label") or ""

    by_account: dict[str, list[float]] = {}
    for r in rows:
        amt = _parse_float(r.get(amount_col))
        acct = str(r.get(acct_col, "")).strip() or "unknown"
        if amt is not None and amt > 0:
            by_account.setdefault(acct, []).append(amt)

    default_type = "wire_transfer"
    mapped: list[MappedRow] = []
    for idx, r in enumerate(rows):
        amt = _parse_float(r.get(amount_col))
        tx_id = str(r.get(id_col, "")).strip() or f"row-{idx}"
        acct_id = str(r.get(acct_col, "")).strip() or "unknown"
        ts_raw = str(r.get(ts_col, "")).strip() or "2026-01-01T00:00:00Z"
        if "T" not in ts_raw and " " in ts_raw:
            ts_raw = ts_raw.replace(" ", "T", 1)
        if ts_raw and not ts_raw.endswith("Z") and "+" not in ts_raw[10:]:
            ts_raw = ts_raw + "Z"
        ttype = str(r.get(type_col, "")).strip() or default_type
        if ttype not in config.TRANSACTION_TYPES:
            ttype = default_type
        if amt is None or amt <= 0:
            continue
        history = by_account.get(acct_id, [amt])
        avg = float(np.mean(history))
        std = float(np.std(history)) if len(history) > 1 else max(avg * 0.2, 1.0)
        account = Account(
            id=acct_id,
            historical_avg_amount=avg,
            historical_std_amount=max(std, 1e-6),
            related_account_ids=[],
        )
        try:
            tx = Transaction(
                id=tx_id,
                account_id=acct_id,
                amount=amt,
                timestamp=ts_raw,
                transaction_type=ttype,
            )
            graph = build_graph(tx, account)
        except Exception:  # noqa: BLE001 - skip unmappable rows, count as excluded
            continue
        label = _parse_label(r.get(label_col)) if label_col else None
        mapped.append(
            MappedRow(
                transaction=tx,
                account=account,
                graph=graph,
                context=EventContext(),
                label=label,
                row_index=idx,
            )
        )
    return mapped


def _metrics_from_labels(y_true: np.ndarray, selected: np.ndarray) -> dict[str, Any]:
    tp = int(np.sum((y_true == 1) & selected))
    fp = int(np.sum((y_true == 0) & selected))
    fn = int(np.sum((y_true == 1) & ~selected))
    tn = int(np.sum((y_true == 0) & ~selected))
    n_pos = int(np.sum(y_true == 1))
    n_neg = int(np.sum(y_true == 0))
    recall = tp / n_pos if n_pos else None
    precision = tp / (tp + fp) if (tp + fp) else None
    fpr = fp / n_neg if n_neg else None
    return {
        "tp_selected_labeled_positive": tp,
        "fp_selected_labeled_negative": fp,
        "fn_skipped_labeled_positive": fn,
        "tn_skipped_labeled_negative": tn,
        "label_positive_count": n_pos,
        "label_negative_count": n_neg,
        "label_positive_prevalence": (n_pos / len(y_true)) if len(y_true) else None,
        "selection_recall_positive_label": recall,
        "selection_precision_positive_label": precision,
        "selection_false_positive_rate": fpr,
        "confusion_note": (
            "Confusion matrix is gate selection vs external label — NOT stress-test survival."
        ),
    }


def run_gate_benchmark(
    store: DatasetStore,
    dataset_id: str,
    models: GateModels | None = None,
    max_rows: int | None = None,
) -> dict[str, Any]:
    """Score mapped rows with the frozen gate and report selection metrics."""
    meta = store.get(dataset_id)
    if not meta.mapping:
        raise InputError("map columns before running an experiment")
    limit = max_rows or config.DATASET_EVAL_MAX_ROWS
    t0 = time.perf_counter()
    rows = map_rows(store, dataset_id, limit=limit)
    if not rows:
        raise InputError(
            "no mappable rows after filtering",
            recovery_action="check amount > 0 and required columns",
        )
    models = models or ImpactGate.models()
    # Score through the production gate (ImpactGate.score_batch) so the
    # benchmark measures the SAME policy production runs (frozen or
    # interaction-aware) rather than a hand-copied formula that can silently
    # diverge from the gate it claims to evaluate.
    items = [(r.transaction, r.account, r.graph, r.context) for r in rows]
    impact_scores = ImpactGate.score_batch(items, models=models)
    score_arr = np.asarray([s.score for s in impact_scores], dtype=float)
    sel_arr = np.asarray([s.gate_decision for s in impact_scores], dtype=bool)
    labels_present = [r.label for r in rows if r.label is not None]
    metrics: dict[str, Any] = {}
    if labels_present:
        y = np.asarray([r.label if r.label is not None else 0.0 for r in rows], dtype=float)
        known = np.asarray([r.label is not None for r in rows], dtype=bool)
        metrics = _metrics_from_labels(y[known], sel_arr[known])
        metrics["rows_with_known_label"] = int(known.sum())
        metrics["rows_with_unknown_label"] = int((~known).sum())
    else:
        metrics = {
            "label_semantics": meta.label_semantics,
            "note": "no usable labels after parsing — selection metrics omitted",
        }

    elapsed = time.perf_counter() - t0
    run_id = "EX-" + uuid.uuid4().hex[:10]
    interaction_on = _interaction_enabled()
    if interaction_on:
        w = config.INTERACTION_AWARE_WEIGHTS
        policy_formula = (
            f"I = {w['anomaly']:.2f}*A + {w['window_pressure']:.2f}*W + "
            f"{w['dependency']:.2f}*D + {w['load_pressure']:.2f}*L"
        )
        active_weights = dict(config.INTERACTION_AWARE_WEIGHTS)
        policy_mode = "interaction_aware"
    else:
        fw = config.IMPACT_WEIGHTS
        policy_formula = (
            f"I = {fw['magnitude']:.2f}*M + {fw['dependency']:.2f}*D + "
            f"{fw['anomaly']:.2f}*A + {fw['uncertainty']:.2f}*U"
        )
        active_weights = dict(config.IMPACT_WEIGHTS)
        policy_mode = "frozen_reference"
    rows_truncated_by_limit = max(0, meta.row_count - len(rows))
    report = {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "dataset_sha256": meta.sha256,
        "dataset_row_count": meta.row_count,
        "rows_scored": len(rows),
        "rows_excluded_unmappable_or_invalid": max(0, meta.row_count - len(rows)),
        "rows_truncated_by_limit_or_unmappable": rows_truncated_by_limit,
        "mapping": meta.mapping,
        "label_semantics": meta.label_semantics,
        "policy_version": config.POLICY_VERSION,
        "policy_mode": policy_mode,
        "policy_formula": policy_formula,
        "weights": active_weights,
        "threshold": config.IMPACT_THRESHOLD,
        "model_backend": models.backend,
        "model_versions": models.versions(),
        "split_method": "none_scoring_only",
        "split_seed": config.MODEL_SEED,
        "gate_selected_count": int(sel_arr.sum()),
        "gate_skipped_count": int((~sel_arr).sum()),
        "simulation_rate": float(sel_arr.mean()) if len(sel_arr) else None,
        "score_mean": float(score_arr.mean()) if len(score_arr) else None,
        "score_max": float(score_arr.max()) if len(score_arr) else None,
        "metrics": metrics,
        "false_negative_analysis": _false_negative_analysis(rows, score_arr, sel_arr, meta, metrics),
        "elapsed_ms": round(elapsed * 1000.0, 3),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "External labels are not synthetic stress-failure labels.",
            "Selection metrics describe gate routing, not safety under load.",
            "Models are the production gate models fitted on the synthetic calibration split, not refit on this upload.",
            "Scored through the production Impact Gate (same policy production runs); "
            "window/load pressure (W/L) are zero for uploads because a CSV carries no "
            "dependency-load context window.",
            "Frozen gate weights and threshold are unchanged.",
            "False-negative patterns are descriptive research only and never alter production gate decisions.",
        ],
    }
    return report


def _false_negative_analysis(
    rows: list[MappedRow],
    scores: np.ndarray,
    selected: np.ndarray,
    meta: Any,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Descriptive research patterns among labeled positives the gate skipped."""
    if "fn_skipped_labeled_positive" not in metrics or metrics["fn_skipped_labeled_positive"] == 0:
        return {
            "available": True,
            "finding_count": 0,
            "findings": [],
            "note": "No false negatives (labeled positives skipped by gate) in this run.",
            "missed_transaction_types": {},
            "missed_score_stats": {"count": 0, "mean": None, "max": None, "min": None},
            "research_only": True,
            "never_changes_production_gate": True,
            "label_semantics": meta.label_semantics,
            "dataset_id": meta.dataset_id,
            "dataset_sha256": meta.sha256,
        }
    fn_idx = [i for i, r in enumerate(rows) if r.label == 1.0 and not selected[i]]
    fn_scores = scores[fn_idx]
    tp_scores = scores[[i for i, r in enumerate(rows) if r.label == 1.0 and selected[i]]]
    types: dict[str, int] = {}
    amounts = []
    for i in fn_idx:
        t = rows[i].transaction.transaction_type
        types[t] = types.get(t, 0) + 1
        amounts.append(rows[i].transaction.amount)
    findings = [
        {
            "finding_id": "FN-001",
            "summary": (
                f"{len(fn_idx)} labeled-positive row(s) scored below threshold "
                f"(max FN score {float(fn_scores.max()):.4f} < {config.IMPACT_THRESHOLD:.2f})."
            ),
            "method": "descriptive_threshold_gap",
            "supporting_records": len(fn_idx),
            "sample_size_labeled_positive": int(metrics.get("label_positive_count", 0)),
            "finding_type": "descriptive",
            "validated": False,
        }
    ]
    if tp_scores.size:
        findings.append(
            {
                "finding_id": "FN-002",
                "summary": (
                    f"Mean gate score of missed positives {float(fn_scores.mean()):.4f} vs "
                    f"selected positives {float(tp_scores.mean()):.4f}."
                ),
                "method": "score_distribution_compare",
                "supporting_records": int(fn_scores.size + tp_scores.size),
                "finding_type": "descriptive",
                "validated": False,
            }
        )
    return {
        "available": True,
        "research_only": True,
        "finding_count": len(findings),
        "findings": findings,
        "missed_transaction_types": types,
        "missed_score_stats": {
            "count": int(fn_scores.size),
            "mean": float(fn_scores.mean()) if fn_scores.size else None,
            "max": float(fn_scores.max()) if fn_scores.size else None,
            "min": float(fn_scores.min()) if fn_scores.size else None,
        },
        "sample_size_limitation": (
            "Fewer than 5 missed positives — treat patterns as anecdotal."
            if fn_scores.size < 5
            else "Descriptive only; not experimentally validated."
        ),
        "label_semantics": meta.label_semantics,
        "dataset_id": meta.dataset_id,
        "dataset_sha256": meta.sha256,
        "never_changes_production_gate": True,
    }


def maybe_run_stress_sample(
    rows: list[MappedRow],
    max_rows: int = 25,
) -> dict[str, Any]:
    """Optional stress sample using the production crash-test engine.

    Explicitly capped; never run automatically during upload or mapping.
    """
    from backend.simulation.crash_test import CrashTestEngine
    from backend.simulation.forks import RealityForkGenerator

    sample = rows[: max(0, max_rows)]
    outcomes = []
    for row in sample:
        try:
            baseline = RealityForkGenerator.generate_baseline(row.transaction, row.graph, row.context)
            failed_scenarios = []
            for scenario in config.SCENARIOS:
                _n, s = CrashTestEngine.attack(baseline, scenario)
                if not s.survived:
                    failed_scenarios.append(scenario)
            outcomes.append(
                {
                    "transaction_id": row.transaction.id,
                    "failed_scenarios": failed_scenarios,
                    "stress_failed": bool(failed_scenarios),
                }
            )
        except Exception as exc:  # noqa: BLE001
            outcomes.append(
                {
                    "transaction_id": row.transaction.id,
                    "error": f"{type(exc).__name__}: {exc}",
                    "stress_failed": None,
                }
            )
    known = [o for o in outcomes if o.get("stress_failed") is not None]
    return {
        "sample_size": len(outcomes),
        "outcomes": outcomes,
        "stress_failure_count": sum(1 for o in known if o["stress_failed"]),
        "note": "Synthetic stress outcomes are independent of external labels and gate decisions.",
    }
