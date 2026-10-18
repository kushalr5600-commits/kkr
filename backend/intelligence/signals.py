"""AI intelligence layer: expose real model outputs used by the Impact Gate.

Read-only with respect to production scoring: this module surfaces the same
models' richer outputs for the AI & Risk Signals panel. The reported gate
score always matches ImpactGate exactly — the frozen formula (0.30*M + 0.30*D
+ 0.25*A + 0.15*U) when interaction-aware mode is off, and the interaction
formula (0.45*A + 0.30*W + 0.15*D + 0.10*L) when
config.INTERACTION_AWARE_ENABLED is set.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from backend.gate.impact_gate import ImpactGate, combine, dependency_signal, magnitude_signal
from backend.gate.interaction_aware import build_load_pressure, build_window_pressure, is_enabled, score_feature_row
from backend.gate.models import FEATURE_NAMES, GateModels, extract_features
from backend.shared import config
from backend.shared.errors import InputError, ModelError
from backend.shared.schemas import (
    Account,
    DependencyGraph,
    EventContext,
    ImpactSignals,
    Transaction,
)

SIGNAL_SOURCE = {
    "M": "statistical",
    "D": "graph_derived",
    "A": "ml_model",
    "U": "ml_model",
    "W": "dataset_context",
    "L": "dataset_context",
}


def _percentile_span(reference_sorted: np.ndarray) -> tuple[float, float, float]:
    if reference_sorted.size == 0:
        return (0.0, 0.5, 1.0)
    return (
        float(np.percentile(reference_sorted, 5)),
        float(np.percentile(reference_sorted, 50)),
        float(np.percentile(reference_sorted, 95)),
    )


def _within_range(raw: float, ref_sorted: np.ndarray) -> dict[str, Any]:
    if ref_sorted.size == 0:
        return {"within_supported_range": None, "reason": "no calibration reference"}
    lo, _mid, hi = _percentile_span(ref_sorted)
    inside = bool(lo <= raw <= hi)
    return {
        "within_supported_range": inside,
        "calibration_raw_p05": lo,
        "calibration_raw_p50": _mid,
        "calibration_raw_p95": hi,
        "reason": "raw score inside calibration p05–p95" if inside else "raw score outside calibration p05–p95 (possible OOD)",
    }


def explain_signals(
    transaction: Transaction,
    account: Account,
    graph: DependencyGraph,
    context: EventContext,
    models: GateModels | None = None,
) -> dict[str, Any]:
    """Real anomaly/risk outputs + frozen-gate mapping for one transaction."""
    models = models or ImpactGate.models()
    X = extract_features(transaction, account, graph, context).reshape(1, -1)

    try:
        raw_a = float(models.anomaly.raw(X)[0])
        a_norm = float(np.clip(models.anomaly.score(X)[0], 0.0, 1.0))
    except ModelError as exc:
        raise InputError(f"anomaly model unavailable: {exc}") from exc

    try:
        members = models.risk._impl.member_probabilities(X)  # noqa: SLF001 - same package provenance
        p_fail = float(members.mean(axis=0)[0])
        member_std = float(members.std(axis=0)[0])
        u_norm = float(np.clip(member_std / config.UNCERTAINTY_MAX_STD, 0.0, 1.0))
    except Exception as exc:  # noqa: BLE001 - surface honestly; do not invent U
        p_fail = None
        member_std = None
        u_norm = float(np.clip(models.uncertainty_scores(X)[0], 0.0, 1.0))
        risk_note = f"member probabilities unavailable ({type(exc).__name__}); U from disagreement path only"
    else:
        risk_note = None

    m = float(np.clip(magnitude_signal(transaction, account), 0.0, 1.0))
    d = float(np.clip(dependency_signal(transaction, graph), 0.0, 1.0))
    signals = ImpactSignals(magnitude=m, dependency=d, anomaly=a_norm, uncertainty=u_norm)
    if is_enabled():
        # Same path ImpactGate.score_batch uses — batch-size invariant.
        score = float(score_feature_row(X, np.array([a_norm]), np.array([d]), FEATURE_NAMES)[0])
        wp = float(build_window_pressure(X, FEATURE_NAMES)[0])
        lp = float(build_load_pressure(X, FEATURE_NAMES)[0])
        formula = "I = 0.45*A + 0.30*W + 0.15*D + 0.10*L"
        gate_mode = "interaction_aware"
        contrib_spec = (
            ("A", "anomaly", a_norm, config.INTERACTION_AWARE_WEIGHTS["anomaly"]),
            ("W", "window_pressure", wp, config.INTERACTION_AWARE_WEIGHTS["window_pressure"]),
            ("D", "dependency", d, config.INTERACTION_AWARE_WEIGHTS["dependency"]),
            ("L", "load_pressure", lp, config.INTERACTION_AWARE_WEIGHTS["load_pressure"]),
        )
    else:
        score = float(combine(signals))
        formula = "I = 0.30*M + 0.30*D + 0.25*A + 0.15*U"
        gate_mode = "frozen"
        contrib_spec = (
            ("M", "magnitude", m, config.IMPACT_WEIGHTS["magnitude"]),
            ("D", "dependency", d, config.IMPACT_WEIGHTS["dependency"]),
            ("A", "anomaly", a_norm, config.IMPACT_WEIGHTS["anomaly"]),
            ("U", "uncertainty", u_norm, config.IMPACT_WEIGHTS["uncertainty"]),
        )
    selected = score >= config.IMPACT_THRESHOLD

    ref = getattr(models.anomaly, "_reference", np.zeros(0))
    range_info = _within_range(raw_a, ref)
    versions = models.versions()

    contributions = []
    for code, name, value, weight in contrib_spec:
        contributions.append(
            {
                "code": code,
                "name": name,
                "signal": value,
                "weight": float(weight),
                "weighted": float(weight) * value,
                "source": SIGNAL_SOURCE[code],
            }
        )

    plain = (
        f"The anomaly model scored this transaction raw={raw_a:.4f}, "
        f"calibrated to A={a_norm:.4f} on the {models.fitted_on_split} split. "
        f"Risk members predicted mean failure probability "
        + (f"{p_fail:.4f} with member std {member_std:.4f} → U={u_norm:.4f}."
           if p_fail is not None else f"with U={u_norm:.4f} from ensemble disagreement.")
        + f" Gate score I={score:.4f} "
        + ("≥" if selected else "<")
        + f" threshold {config.IMPACT_THRESHOLD:.2f} → "
        + ("SELECTED for simulation." if selected else "SKIPPED (stress not measured).")
    )
    tech = (
        f"backend={models.backend}; anomaly={versions.get('anomaly_model')}; "
        f"risk={versions.get('risk_model')}; "
        f"raw_A={raw_a:.8f}; A_ecdf={a_norm:.8f}; "
        f"p_fail_mean={p_fail}; member_std={member_std}; U=clip(std/{config.UNCERTAINTY_MAX_STD},0,1)={u_norm:.8f}; "
        f"I={score:.10f}; selected={selected}"
    )

    unknowns = []
    if p_fail is None:
        unknowns.append("risk member probability distribution unavailable on this backend path")
    if not range_info.get("within_supported_range"):
        unknowns.append("anomaly raw score outside calibrated p05–p95 span (possible out-of-distribution input)")
    unknowns.append("anomaly score is not a fraud probability")
    if models.backend == "numpy":
        unknowns.append("numpy fallback backend — not identical to sklearn published metrics")

    return {
        "available": True,
        "transaction_id": transaction.id,
        "model_backend": models.backend,
        "model_versions": versions,
        "fitted_on_split": models.fitted_on_split,
        "n_fit_samples": models.n_fit_samples,
        "n_fit_failures": models.n_fit_failures,
        "seed": models.seed,
        "anomaly": {
            "raw": raw_a,
            "normalized_a": a_norm,
            "model_name": versions.get("anomaly_model"),
            "calibration_method": config.ANOMALY_NORMALIZATION,
            "calibration_split": models.fitted_on_split,
            "range": range_info,
            "caveats": [
                "A is an empirical-CDF calibrated anomaly rank, not a fraud probability.",
                "Higher A means more unusual relative to the calibration split only.",
            ],
        },
        "risk": {
            "failure_probability_mean": p_fail,
            "member_std": member_std,
            "normalized_u": u_norm,
            "model_name": versions.get("risk_model"),
            "uncertainty_normalization": config.UNCERTAINTY_NORMALIZATION,
            "calibration_split": models.fitted_on_split,
            "note": risk_note,
            "caveats": [
                "P(fail) is the ensemble mean under synthetic stress labels from the calibration split, not real-world default/fraud risk.",
                "U is disagreement / 0.5; it is not a calibrated confidence interval.",
                "This probability has not been post-hoc calibrated on a held-out set in this build.",
            ],
        },
        "signal_sources": SIGNAL_SOURCE,
        "signals": {"M": m, "D": d, "A": a_norm, "U": u_norm},
        "contributions": contributions,
        "gate": {
            "score": score,
            "threshold": config.IMPACT_THRESHOLD,
            "selected": selected,
            "formula": formula,
            "mode": gate_mode,
            "simulation_executed": None,  # filled by caller when a certificate exists
        },
        "plain_language": plain,
        "technical_detail": tech,
        "unknowns": unknowns,
        "research_only": False,
    }


def what_if(
    transaction: Transaction,
    account: Account,
    graph: DependencyGraph,
    context: EventContext,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """Research-only hypothetical: change supported fields and re-score.

    Does not mutate production models, gate weights, or the original transaction.
    """
    allowed = {"amount", "transaction_type", "historical_avg_amount", "historical_std_amount"}
    unknown_keys = set(overrides) - allowed
    if unknown_keys:
        raise InputError(
            f"unsupported what-if fields: {', '.join(sorted(unknown_keys))}; allowed: {', '.join(sorted(allowed))}"
        )
    if not overrides:
        raise InputError("what-if requires at least one field override")

    tx = transaction
    ac = account
    if "amount" in overrides:
        try:
            amt = float(overrides["amount"])
        except (TypeError, ValueError) as exc:
            raise InputError("amount override must be a number") from exc
        if not np.isfinite(amt) or amt <= 0:
            raise InputError("amount override must be a finite number > 0")
        tx = tx.model_copy(update={"amount": amt})
    if "transaction_type" in overrides:
        ttype = str(overrides["transaction_type"])
        if ttype not in config.TRANSACTION_TYPES:
            raise InputError(
                f"unsupported transaction_type {ttype!r}; supported: {', '.join(config.TRANSACTION_TYPES)}"
            )
        tx = tx.model_copy(update={"transaction_type": ttype})
    updates = {}
    for field in ("historical_avg_amount", "historical_std_amount"):
        if field in overrides:
            try:
                val = float(overrides[field])
            except (TypeError, ValueError) as exc:
                raise InputError(f"{field} override must be a number") from exc
            if not np.isfinite(val) or val <= 0:
                raise InputError(f"{field} override must be a finite number > 0")
            updates[field] = val
    if updates:
        ac = ac.model_copy(update=updates)

    # Graph must be rebuilt if transaction type changed (different footprint).
    # Keep the original graph for the baseline so "original" D is the true D.
    base_graph = graph
    if "transaction_type" in overrides:
        from backend.data.repository import build_graph

        graph = build_graph(tx, ac)

    base_signals = explain_signals(transaction, account, base_graph, context)
    hypo_signals = explain_signals(tx, ac, graph, context)

    # Simulate execution status for the hypothetical (deterministic gate only).
    hypo_score = hypo_signals["gate"]["score"]
    hypo_selected = hypo_score >= config.IMPACT_THRESHOLD

    return {
        "research_only": True,
        "disclaimer": (
            "Hypothetical result only. This is not a real transaction outcome and does "
            "not change production gate policy or any stored certificate."
        ),
        "original": {
            "transaction": transaction.model_dump(mode="json"),
            "account_baseline": {
                "historical_avg_amount": account.historical_avg_amount,
                "historical_std_amount": account.historical_std_amount,
            },
            "gate": base_signals["gate"],
            "signals": base_signals["signals"],
        },
        "hypothetical": {
            "transaction": tx.model_dump(mode="json"),
            "account_baseline": {
                "historical_avg_amount": ac.historical_avg_amount,
                "historical_std_amount": ac.historical_std_amount,
            },
            "gate": hypo_signals["gate"],
            "signals": hypo_signals["signals"],
            "anomaly": hypo_signals["anomaly"],
            "risk": hypo_signals["risk"],
            "contributions": hypo_signals["contributions"],
            "plain_language": hypo_signals["plain_language"],
        },
        "changes": {k: overrides[k] for k in overrides},
        "delta": {
            "score": hypo_score - base_signals["gate"]["score"],
            "selected_before": base_signals["gate"]["selected"],
            "selected_after": hypo_selected,
            "A": hypo_signals["signals"]["A"] - base_signals["signals"]["A"],
            "M": hypo_signals["signals"]["M"] - base_signals["signals"]["M"],
        },
    }
