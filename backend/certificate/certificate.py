"""Decision Certificate generator (P4).

``CertificateGenerator.generate`` turns the outputs of the other components into
an evidence object. Every evidence sentence is built from an actual metric or
configuration value; nothing here is hard-coded example text.

Deterministic PROTOTYPE policy (not a production authorization rule):

    gate did not select the transaction           -> ALLOW_NORMAL_PATH   (NO_SIMULATION)
    any stress scenario fails                     -> BLOCK_OR_HOLD
    no failure, but a scenario's fragility margin
        (breaking_threshold / tested_intensity - 1) < REVIEW_MARGIN   -> REVIEW
    no failure and adequate margin                -> ALLOW_NORMAL_PATH
    internal processing failure                   -> REVIEW             (via ``generate_review``)

The v4 schema has no ``limitations`` field, so limitations are appended to
``evidence`` with the prefix ``"LIMITATION: "`` for the UI to render separately.
"""
from __future__ import annotations

import uuid

from backend.shared import config, diagnostics
from backend.shared.errors import CertificateError
from backend.gate.interaction_aware import is_enabled as _interaction_enabled
from backend.shared.schemas import (
    DecisionCertificate,
    ForkResult,
    FragilityResult,
    ImpactScore,
    ImpactSignals,
    RuntimeMetadata,
    Transaction,
)

LIMITATION_PREFIX = "LIMITATION: "

LIMITATIONS = (
    "Synthetic data and a modelled enterprise: results describe the simulated system, "
    "not a real institution.",
    "Demo policy only: the recommended action is a deterministic prototype rule, "
    "not production authorization.",
    "Gate weights, threshold and failure limits are declared MVP parameters, "
    "not claimed optimal.",
    "Fragility is a bounded interval at the stated resolution, not an exact physical boundary.",
)


# ---------------------------------------------------------------------------
# Interpretation helpers
# ---------------------------------------------------------------------------
def _pair_by_scenario(fork_results: list[ForkResult]) -> dict[str, dict[str, ForkResult]]:
    paired: dict[str, dict[str, ForkResult]] = {}
    for result in fork_results:
        paired.setdefault(result.scenario, {})[result.fork_name] = result
    for scenario, pair in paired.items():
        if set(pair) != {"normal", "stress"}:
            raise CertificateError(
                f"scenario {scenario!r} must have exactly one normal and one stress result, got {sorted(pair)}"
            )
    return paired


def is_lower_bound(fragility: FragilityResult) -> bool:
    """True when the search never saw a failure (threshold is only a lower bound)."""
    return fragility.unit == config.FRAGILITY_UNIT_LOWER_BOUND


def fragility_margin(fragility: FragilityResult) -> float:
    """Relative headroom over the default tested intensity of the scenario."""
    try:
        tested = config.SCENARIO_DEFAULT_INTENSITY[fragility.scenario]
    except KeyError:
        raise CertificateError(
            f"unknown scenario {fragility.scenario!r} in fragility result"
        ) from None
    return fragility.breaking_threshold / tested - 1.0


def decide_action(
    impact_score: ImpactScore,
    paired: dict[str, dict[str, ForkResult]],
    fragility: list[FragilityResult],
) -> tuple[str, str]:
    """Apply the prototype policy; returns ``(action, reason)``."""
    # Check measured stress failures FIRST, before any gate short-circuit: a
    # certificate that carries a measured FAILED fork must never recommend
    # ALLOW_NORMAL_PATH just because the gate did not select it.
    if paired:
        failed = [s for s, pair in paired.items() if not pair["stress"].survived]
        if failed:
            return "BLOCK_OR_HOLD", "stress failure in: " + ", ".join(sorted(failed))
    if not impact_score.gate_decision or not paired:
        return "ALLOW_NORMAL_PATH", "gate did not select the transaction for deep simulation"
    thin = [
        f.scenario for f in fragility
        if not is_lower_bound(f) and fragility_margin(f) < config.REVIEW_MARGIN
    ]
    if thin:
        return "REVIEW", f"fragility margin below {config.REVIEW_MARGIN:.0%} in: " + ", ".join(sorted(thin))
    return "ALLOW_NORMAL_PATH", "all scenarios survived with adequate fragility margin"


def _hottest_service(metrics: dict[str, float]) -> tuple[str, float]:
    utils = {k[len("util_"):]: v for k, v in metrics.items() if k.startswith("util_")}
    if not utils:
        return "n/a", 0.0
    name = max(utils, key=utils.__getitem__)
    return name, utils[name]


def _scenario_evidence(scenario: str, pair: dict[str, ForkResult]) -> str:
    normal, stress = pair["normal"], pair["stress"]
    m = stress.metrics
    intensity = m.get("intensity", float("nan"))
    if "end_to_end_latency_ms" in m:
        measured = (
            f"end-to-end latency {normal.metrics['end_to_end_latency_ms']:.0f} ms nominal -> "
            f"{m['end_to_end_latency_ms']:.0f} ms stressed (budget {m['latency_budget_ms']:.0f} ms)"
        )
    else:
        svc, _util = _hottest_service(m)
        measured = (
            f"peak utilization {normal.metrics['max_utilization']:.2f} nominal -> "
            f"{m['max_utilization']:.2f} stressed at {svc} (limit {m['utilization_limit']:.2f})"
        )
    verdict = "survived" if stress.survived else "FAILED"
    nominal = "" if normal.survived else " [already failing at nominal load]"
    return f"{scenario} at {intensity:.1f}x: {verdict}{nominal}; {measured}."


def _fragility_evidence(f: FragilityResult) -> str:
    if is_lower_bound(f):
        return (
            f"{f.scenario}: not broken within the tested range; survives through "
            f"{f.breaking_threshold:.2f}x (search bound, resolution {f.resolution:.2f}x)."
        )
    if f.breaking_threshold <= config.MIN_INTENSITY + 1e-9:
        return f"{f.scenario}: already fails at nominal intensity ({f.breaking_threshold:.2f}x)."
    return (
        f"{f.scenario}: survives through {f.breaking_threshold - f.resolution:.2f}x, "
        f"fails by {f.breaking_threshold:.2f}x (resolution {f.resolution:.2f}x)."
    )


def _gate_evidence(score: ImpactScore) -> str:
    """One evidence line describing the gate's decision, citing the formula that
    actually produced ``score``.

    The active policy (frozen vs interaction-aware) determines which signals and
    weights are shown, so a reader can always recompute the score from the
    evidence. W/L (window/load pressure) are deterministic dataset-context
    features that are not stored on the frozen ``ImpactSignals`` schema, so they
    are named rather than valued.
    """
    s = score.signals
    relation = ">=" if score.gate_decision else "<"
    head = (
        f"Impact Gate: score {score.score:.4f} {relation} threshold {config.IMPACT_THRESHOLD:.2f}"
    )
    if _interaction_enabled():
        w = config.INTERACTION_AWARE_WEIGHTS
        return (
            f"{head} (interaction-aware ranking I = {w['anomaly']:.2f}*A + "
            f"{w['window_pressure']:.2f}*W + {w['dependency']:.2f}*D + {w['load_pressure']:.2f}*L; "
            f"A={s.anomaly:.2f}, D={s.dependency:.2f} are the stored signals; "
            f"W/L window-load pressure are dataset-context features, not stored on ImpactSignals)."
        )
    return (
        f"{head} (M={s.magnitude:.2f}, D={s.dependency:.2f}, A={s.anomaly:.2f}, U={s.uncertainty:.2f}; "
        f"weights {config.IMPACT_WEIGHTS['magnitude']:.2f}/{config.IMPACT_WEIGHTS['dependency']:.2f}/"
        f"{config.IMPACT_WEIGHTS['anomaly']:.2f}/{config.IMPACT_WEIGHTS['uncertainty']:.2f})."
    )


def _runtime_evidence(runtime: RuntimeMetadata) -> str:
    """One evidence line tying the certificate to the observed runtime.

    Fills only existing RuntimeMetadata fields; never invents a LinuxONE claim.
    """
    mv = runtime.model_versions or {}
    backend = mv.get("backend", "unknown")
    git = runtime.git_revision or "unavailable"
    parts = [
        f"Runtime: {runtime.runtime} on {runtime.architecture}",
        f"model backend {backend}",
        f"git {git}",
        f"config {mv.get('blackbox', config.VERSION)}",
    ]
    if mv.get("config_sha256"):
        parts.append(f"config_sha256 {mv['config_sha256'][:12]}")
    if mv.get("dataset_sha256"):
        parts.append(f"dataset_sha256 {mv['dataset_sha256'][:12]}")
    if runtime.random_seed is not None:
        parts.append(f"seed {runtime.random_seed}")
    return "; ".join(parts) + "."


def _description(transaction: Transaction) -> str:
    return (
        f"Preflight of {transaction.transaction_type} {transaction.id}: amount "
        f"{transaction.amount:,.2f} on account {transaction.account_id}"
    )


def _new_certificate_id() -> str:
    return "CERT-" + uuid.uuid4().hex[:12].upper()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
class CertificateGenerator:
    @staticmethod
    def generate(
        transaction: Transaction,
        impact_score: ImpactScore,
        fork_results: list[ForkResult],
        fragility: list[FragilityResult],
        runtime: RuntimeMetadata,
    ) -> DecisionCertificate:
        if impact_score.transaction_id != transaction.id:
            raise CertificateError(
                f"impact score belongs to {impact_score.transaction_id!r}, not {transaction.id!r}"
            )

        evidence = [_gate_evidence(impact_score)]
        evidence.append(_runtime_evidence(runtime))

        if not fork_results:
            if impact_score.gate_decision:
                raise CertificateError("gate selected the transaction but no simulation results were supplied")
            evidence.append(
                "No deep simulation was run: the score is below the gate threshold, so the "
                "transaction continues on the normal path."
            )
            action, reason = decide_action(impact_score, {}, [])
            status = "NO_SIMULATION"
        else:
            paired = _pair_by_scenario(fork_results)
            by_scenario = {f.scenario: f for f in fragility}
            missing = [s for s in paired if s not in by_scenario]
            if missing:
                raise CertificateError(f"missing fragility result for: {', '.join(missing)}")
            for scenario in config.SCENARIOS:
                if scenario in paired:
                    evidence.append(_scenario_evidence(scenario, paired[scenario]))
            for scenario in config.SCENARIOS:
                if scenario in by_scenario:
                    evidence.append(_fragility_evidence(by_scenario[scenario]))
            ctx = next(iter(paired.values()))["stress"].metrics
            if "recent_transactions_in_window" in ctx:
                evidence.append(
                    f"Local context: {int(ctx['recent_transactions_in_window'])} other transaction(s) in the "
                    f"{config.WINDOW_SECONDS}s window; {int(ctx.get('defaulted_load_services', 0))} service(s) "
                    f"used the default background load."
                )
            action, reason = decide_action(impact_score, paired, list(by_scenario.values()))
            status = "SIMULATED"

        evidence.append(f"Demo policy: {action} - {reason}.")
        evidence += [LIMITATION_PREFIX + text for text in LIMITATIONS]

        return DecisionCertificate(
            certificate_id=_new_certificate_id(),
            trace_id=diagnostics.get_trace_id(),
            status=status,
            transaction_id=transaction.id,
            decision_description=_description(transaction),
            impact_score=impact_score,
            forks_tested=list(fork_results),
            fragility=list(fragility),
            recommended_action=action,
            evidence=evidence,
            runtime=runtime,
        )

    @staticmethod
    def generate_review(
        transaction: Transaction,
        impact_score: ImpactScore | None,
        reason: str,
        runtime: RuntimeMetadata,
        partial_forks: list[ForkResult] | None = None,
        partial_fragility: list[FragilityResult] | None = None,
    ) -> DecisionCertificate:
        """Truthful degraded certificate for an internal processing failure.

        Never claims safety: the action is always REVIEW. If the gate itself
        failed, the score is a zero placeholder and the evidence says so.
        """
        evidence: list[str] = []
        if impact_score is None:
            impact_score = ImpactScore(
                transaction_id=transaction.id,
                signals=ImpactSignals(magnitude=0.0, dependency=0.0, anomaly=0.0, uncertainty=0.0),
                score=0.0,
                gate_decision=False,
            )
            evidence.append(
                "Impact Gate result unavailable: the zero score and signals shown are placeholders, "
                "not measurements."
            )
        else:
            evidence.append(_gate_evidence(impact_score))
        evidence.append(_runtime_evidence(runtime))
        evidence.append(f"Internal processing failure: {reason}")
        evidence.append("Demo policy: REVIEW - BLACKBOX could not complete the preflight, so it does not claim safety.")
        evidence += [LIMITATION_PREFIX + text for text in LIMITATIONS]

        return DecisionCertificate(
            certificate_id=_new_certificate_id(),
            trace_id=diagnostics.get_trace_id(),
            status="REVIEW",
            transaction_id=transaction.id,
            decision_description=_description(transaction),
            impact_score=impact_score,
            forks_tested=list(partial_forks or []),
            fragility=list(partial_fragility or []),
            recommended_action="REVIEW",
            evidence=evidence,
            runtime=runtime,
        )
