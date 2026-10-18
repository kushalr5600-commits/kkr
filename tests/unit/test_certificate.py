"""P4 tests: certificate policy matrix and evidence traceability."""
from __future__ import annotations

from tests.fixtures import expect_raises

from backend.certificate.certificate import LIMITATION_PREFIX, CertificateGenerator, decide_action
from backend.shared import config
from backend.shared.errors import CertificateError
from backend.shared.schemas import (
    ForkResult, FragilityResult, ImpactScore, ImpactSignals, RuntimeMetadata, Transaction,
)

TX = Transaction(id="T-1", account_id="A-1", amount=1234.5, timestamp="2026-03-02T09:00:00Z",
                 transaction_type="wire_transfer")
RUNTIME = RuntimeMetadata(runtime="test", architecture="x86_64")


def impact(selected: bool, score: float | None = None) -> ImpactScore:
    value = score if score is not None else (0.7 if selected else 0.2)
    return ImpactScore(transaction_id="T-1", signals=ImpactSignals(magnitude=0.5, dependency=0.5, anomaly=0.5, uncertainty=0.5),
                       score=value, gate_decision=selected)


def pair(scenario: str, stress_survives: bool = True, peak: float = 0.5) -> list[ForkResult]:
    intensity = config.SCENARIO_DEFAULT_INTENSITY[scenario]
    if scenario == "service_latency":
        def metrics(i, latency):
            return {"intensity": i, "end_to_end_latency_ms": latency, "latency_budget_ms": 1100.0, "max_utilization": 0.3}
        return [
            ForkResult(fork_name="normal", scenario=scenario, survived=True, metrics=metrics(1.0, 400.0)),
            ForkResult(fork_name="stress", scenario=scenario, survived=stress_survives,
                       metrics=metrics(intensity, 900.0 if stress_survives else 1500.0)),
        ]
    def m(i, p):
        return {"intensity": i, "max_utilization": p, "utilization_limit": 1.0, "util_ledger": p,
                "recent_transactions_in_window": 1.0, "defaulted_load_services": 0.0}
    return [
        ForkResult(fork_name="normal", scenario=scenario, survived=True, metrics=m(1.0, peak / intensity)),
        ForkResult(fork_name="stress", scenario=scenario, survived=stress_survives, metrics=m(intensity, peak)),
    ]


def frag(scenario: str, threshold: float, lower_bound: bool = False) -> FragilityResult:
    return FragilityResult(
        scenario=scenario, breaking_threshold=threshold, resolution=config.FRAGILITY_RESOLUTION,
        unit=config.FRAGILITY_UNIT_LOWER_BOUND if lower_bound else config.FRAGILITY_UNIT,
    )


def all_pairs(failing: str | None = None):
    out = []
    for s in config.SCENARIOS:
        out += pair(s, stress_survives=(s != failing))
    return out


def comfortable():
    return [frag(s, config.SCENARIO_DEFAULT_INTENSITY[s] * 2.0) for s in config.SCENARIOS]


def paired(results):
    from backend.certificate.certificate import _pair_by_scenario
    return _pair_by_scenario(results)


# ------------------------------------------------------------------ policy matrix
def test_policy_low_impact_allows_normal_path():
    action, _ = decide_action(impact(False), {}, [])
    assert action == "ALLOW_NORMAL_PATH"


def test_policy_any_stress_failure_blocks():
    for failing in config.SCENARIOS:
        action, reason = decide_action(impact(True), paired(all_pairs(failing)), comfortable())
        assert action == "BLOCK_OR_HOLD" and failing in reason


def test_policy_thin_margin_reviews():
    thin = comfortable()
    thin[0] = frag(config.SCENARIOS[0], config.SCENARIO_DEFAULT_INTENSITY[config.SCENARIOS[0]] * (1 + config.REVIEW_MARGIN / 2))
    action, reason = decide_action(impact(True), paired(all_pairs()), thin)
    assert action == "REVIEW" and config.SCENARIOS[0] in reason


def test_policy_adequate_margin_allows_and_lower_bound_counts_as_adequate():
    assert decide_action(impact(True), paired(all_pairs()), comfortable())[0] == "ALLOW_NORMAL_PATH"
    bounds = [frag(s, config.MAX_INTENSITY, lower_bound=True) for s in config.SCENARIOS]
    assert decide_action(impact(True), paired(all_pairs()), bounds)[0] == "ALLOW_NORMAL_PATH"


def test_margin_exactly_at_review_margin_is_adequate():
    s = config.SCENARIOS[0]
    exact = [frag(s, config.SCENARIO_DEFAULT_INTENSITY[s] * (1 + config.REVIEW_MARGIN))] + comfortable()[1:]
    assert decide_action(impact(True), paired(all_pairs()), exact)[0] == "ALLOW_NORMAL_PATH"


# ----------------------------------------------------------------- generate()
def test_no_simulation_certificate():
    cert = CertificateGenerator.generate(TX, impact(False), [], [], RUNTIME)
    assert cert.status == "NO_SIMULATION" and cert.recommended_action == "ALLOW_NORMAL_PATH"
    assert cert.forks_tested == [] and cert.fragility == []
    assert cert.evidence and cert.trace_id.startswith("TR-") and cert.certificate_id.startswith("CERT-")


def test_simulated_certificate_with_failure_blocks_and_cites_metrics():
    cert = CertificateGenerator.generate(TX, impact(True), all_pairs("fraud_spike"), comfortable(), RUNTIME)
    assert cert.status == "SIMULATED" and cert.recommended_action == "BLOCK_OR_HOLD"
    assert len(cert.forks_tested) == 6 and len(cert.fragility) == 3
    text = "\n".join(cert.evidence)
    assert "fraud_spike at 3.0x: FAILED" in text
    assert "900 ms" in text                       # latency evidence comes from the metric value
    assert "Demo policy: BLOCK_OR_HOLD" in text


def test_evidence_values_come_from_the_inputs():
    results = [r.model_copy(update={"metrics": {**r.metrics, "max_utilization": 0.4321}}) if r.scenario == "3x_volume" and r.fork_name == "stress" else r
               for r in all_pairs()]
    cert = CertificateGenerator.generate(TX, impact(True, 0.7123), results, comfortable(), RUNTIME)
    text = "\n".join(cert.evidence)
    assert "0.4321" not in text and "0.43" in text    # formatted from the metric, not a template literal
    assert "0.712" in text                            # score formatted from the ImpactScore


def test_limitations_are_always_present_and_marked():
    cert = CertificateGenerator.generate(TX, impact(False), [], [], RUNTIME)
    limits = [e for e in cert.evidence if e.startswith(LIMITATION_PREFIX)]
    assert len(limits) >= 3 and any("Demo policy" in e for e in limits)


def test_review_certificate_never_claims_safety():
    cert = CertificateGenerator.generate_review(TX, None, "ModelError: boom", RUNTIME)
    assert cert.status == "REVIEW" and cert.recommended_action == "REVIEW"
    assert cert.impact_score.score == 0.0
    assert any("placeholder" in e for e in cert.evidence) and any("boom" in e for e in cert.evidence)
    with_score = CertificateGenerator.generate_review(TX, impact(True), "SimulationError: x", RUNTIME)
    assert with_score.impact_score.score == 0.7 and with_score.recommended_action == "REVIEW"


def test_inconsistent_inputs_are_rejected():
    wrong = impact(True).model_copy(update={"transaction_id": "OTHER"})
    expect_raises(CertificateError, CertificateGenerator.generate, TX, wrong, all_pairs(), comfortable(), RUNTIME)
    expect_raises(CertificateError, CertificateGenerator.generate, TX, impact(True), all_pairs(), [], RUNTIME)
    expect_raises(CertificateError, CertificateGenerator.generate, TX, impact(True), [], [], RUNTIME)
    lonely = [r for r in all_pairs() if not (r.scenario == "3x_volume" and r.fork_name == "stress")]
    expect_raises(CertificateError, CertificateGenerator.generate, TX, impact(True), lonely, comfortable(), RUNTIME)
