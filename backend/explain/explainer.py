"""Explainable Decision Explorer helpers.

Produces plain-language and technical explanations from an actual
DecisionCertificate / ImpactScore — no hardcoded per-transaction text.
Contributions must always sum to the certificate's impact score: frozen
weights in frozen mode, interaction weights (with W/L from the feature row)
in interaction-aware mode.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from backend.gate.interaction_aware import build_load_pressure, build_window_pressure, is_enabled
from backend.gate.models import FEATURE_NAMES
from backend.shared import config, diagnostics
from backend.shared.schemas import DecisionCertificate, ImpactScore, Transaction

FROZEN_FORMULA = "I = 0.30*M + 0.30*D + 0.25*A + 0.15*U"
INTERACTION_FORMULA = "I = 0.45*A + 0.30*W + 0.15*D + 0.10*L"


def active_formula() -> str:
    return INTERACTION_FORMULA if is_enabled() else FROZEN_FORMULA


def contributions(impact: ImpactScore, features: np.ndarray | None = None) -> list[dict[str, Any]]:
    if is_enabled() and features is not None:
        w = config.INTERACTION_AWARE_WEIGHTS
        wp = float(build_window_pressure(features, FEATURE_NAMES)[0])
        lp = float(build_load_pressure(features, FEATURE_NAMES)[0])
        pairs = [
            ("A", "anomaly", impact.signals.anomaly, w["anomaly"]),
            ("W", "window_pressure", wp, w["window_pressure"]),
            ("D", "dependency", impact.signals.dependency, w["dependency"]),
            ("L", "load_pressure", lp, w["load_pressure"]),
        ]
    else:
        w = config.IMPACT_WEIGHTS
        pairs = [
            ("M", "magnitude", impact.signals.magnitude, w["magnitude"]),
            ("D", "dependency", impact.signals.dependency, w["dependency"]),
            ("A", "anomaly", impact.signals.anomaly, w["anomaly"]),
            ("U", "uncertainty", impact.signals.uncertainty, w["uncertainty"]),
        ]
    out = []
    for code, name, value, weight in pairs:
        out.append(
            {
                "code": code,
                "name": name,
                "signal": float(value),
                "weight": float(weight),
                "weighted": float(weight) * float(value),
                "formula_term": f"{weight:.2f}*{float(value):.4f}",
            }
        )
    return out


def explain_certificate(
    certificate: DecisionCertificate,
    transaction: Transaction | None = None,
    features: np.ndarray | None = None,
) -> dict[str, Any]:
    impact = certificate.impact_score
    contribs = contributions(impact, features)
    thr = config.IMPACT_THRESHOLD
    selected = bool(impact.gate_decision)
    sim_ran = certificate.status == "SIMULATED"
    score = float(impact.score)

    plain_parts = [
        f"Impact score is {score:.4f} against threshold {thr:.2f}.",
        (
            "The gate SELECTED this transaction for deep simulation."
            if selected
            else "The gate SKIPPED deep simulation because the score is below the threshold."
        ),
    ]
    plain_parts.append(
        "Deep simulation actually ran and stress scenarios are reported."
        if sim_ran
        else (
            "No deep simulation ran — an empty stress table is NOT evidence of safety."
            if certificate.status == "NO_SIMULATION"
            else "Preflight did not complete into a full simulation suite (REVIEW)."
        )
    )
    top = max(contribs, key=lambda c: c["weighted"])
    plain_parts.append(
        f"Largest weighted contribution: {top['code']} "
        f"({top['name']}) at {top['weighted']:.4f}."
    )

    tech = (
        f"{active_formula()} "
        f"= {' + '.join(c['formula_term'] for c in contribs)} = {score:.10f}; "
        f"gate_decision = (I >= {thr:.2f}) = {selected}"
    )

    why = (
        "Selected for simulation because score >= threshold."
        if selected
        else "Skipped because score < threshold; stress outcomes are unmeasured."
    )

    timeline = []
    for ev in list(diagnostics.RECENT_EVENTS):
        if ev.get("trace_id") == certificate.trace_id:
            timeline.append(dict(ev))

    tx_block = None
    if transaction is not None:
        tx_block = {
            "facts": {
                "id": transaction.id,
                "account_id": transaction.account_id,
                "amount": transaction.amount,
                "transaction_type": transaction.transaction_type,
                "timestamp": transaction.timestamp.isoformat()
                if hasattr(transaction.timestamp, "isoformat")
                else str(transaction.timestamp),
            },
            "kind": "fact",
        }

    return {
        "transaction_id": certificate.transaction_id,
        "certificate_id": certificate.certificate_id,
        "policy_version": certificate.runtime.model_versions.get("policy_version", config.POLICY_VERSION),
        "threshold": thr,
        "score": score,
        "gate_selected": selected,
        "formula": active_formula(),
        "policy_mode": "interaction_aware" if is_enabled() else "frozen_reference",
        "simulation_status": certificate.status,
        "simulation_ran": sim_ran,
        "contributions": contribs,
        "why": why,
        "plain_language": " ".join(plain_parts),
        "technical_detail": tech,
        "transaction": tx_block,
        "scenarios_ran": sorted({f.scenario for f in certificate.forks_tested}),
        "fork_count": len(certificate.forks_tested),
        "timeline": timeline,
        "fact_model_label_interpretation": {
            "facts": "transaction attributes and runtime metadata as returned by the backend",
            "model_outputs": "M/D/A/U, score, gate_decision, stress outcomes",
            "benchmark_labels": "external dataset labels only — never mixed into certificates",
            "interpretations": "plain_language and why fields",
        },
        "unknowns": [],
    }


def counterexample_from_certificate(certificate: DecisionCertificate) -> dict[str, Any]:
    """Independent benchmark-style view: gate decision vs known stress outcome.

    Used for the showcase missed-failure (TX-00108-B) after simulation has been
    run explicitly. Never infers stress outcome from the gate decision alone.
    """
    stress_failed = any(
        f.fork_name == "stress" and not f.survived for f in certificate.forks_tested
    )
    gate_selected = bool(certificate.impact_score.gate_decision)
    return {
        "transaction_id": certificate.transaction_id,
        "gate_selected": gate_selected,
        "stress_failure_observed": stress_failed,
        "stress_measured": len(certificate.forks_tested) > 0,
        "missed_failure": (not gate_selected) and stress_failed,
        "kind": "measured_stress_vs_gate_decision",
        "note": (
            "Stress outcome comes from crash-test metrics on this run, "
            "not from the gate decision."
        ),
        "score": float(certificate.impact_score.score),
        "threshold": config.IMPACT_THRESHOLD,
    }
