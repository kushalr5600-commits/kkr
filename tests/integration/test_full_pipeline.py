"""Integration tests: the real components, wired together exactly as in production."""
from __future__ import annotations

import platform

from tests.fixtures import expect_raises, repo, service

from backend.gate.impact_gate import ImpactGate
from backend.pipeline import BlackboxService
from backend.shared import config, diagnostics
from backend.shared.errors import InputError
from backend.shared.schemas import DecisionCertificate, Transaction


def _find(selected: bool, fails: bool) -> Transaction:
    svc = service()
    for item in svc.demo_transactions():
        tx = Transaction.model_validate(item["transaction"])
        cert = svc.analyze(tx)
        failed = cert.status == "SIMULATED" and cert.recommended_action == "BLOCK_OR_HOLD"
        if (cert.status == "SIMULATED") == selected and (failed == fails or not selected):
            return tx
    raise AssertionError(f"no example with selected={selected}, fails={fails}")


def test_full_pipeline_gate_selected_and_failing():
    cert = service().analyze(_find(selected=True, fails=True))
    DecisionCertificate.model_validate(cert.model_dump())
    assert cert.status == "SIMULATED" and cert.recommended_action == "BLOCK_OR_HOLD"
    assert len(cert.forks_tested) == 6                        # normal + stress for each of 3 scenarios
    assert {f.scenario for f in cert.forks_tested} == set(config.SCENARIOS)
    assert [f.fork_name for f in cert.forks_tested] == ["normal", "stress"] * 3
    assert {f.scenario for f in cert.fragility} == set(config.SCENARIOS)
    assert cert.impact_score.gate_decision is True and cert.impact_score.score >= config.IMPACT_THRESHOLD
    assert any("FAILED" in line for line in cert.evidence)
    assert cert.trace_id.startswith("TR-")


def test_full_pipeline_low_impact_path_runs_no_simulation():
    cert = service().analyze(_find(selected=False, fails=False))
    assert cert.status == "NO_SIMULATION" and cert.recommended_action == "ALLOW_NORMAL_PATH"
    assert cert.forks_tested == [] and cert.fragility == []


def test_selected_and_surviving_transaction_is_allowed_with_margin():
    svc = service()
    for item in svc.demo_transactions():
        cert = svc.analyze(Transaction.model_validate(item["transaction"]))
        if cert.status == "SIMULATED" and cert.recommended_action != "BLOCK_OR_HOLD":
            assert all(f.survived for f in cert.forks_tested if f.fork_name == "stress")
            return
    raise AssertionError("no selected-and-surviving example available")


def test_demo_mode_is_deterministic_and_uses_the_fixed_transaction():
    a = service().analyze(demo_mode=True)
    b = service().analyze(demo_mode=True)
    assert a.transaction_id == b.transaction_id == config.DEMO_TRANSACTION_ID
    assert a.impact_score == b.impact_score
    assert a.forks_tested == b.forks_tested and a.fragility == b.fragility
    assert a.trace_id != b.trace_id                          # every request gets its own trace


def test_input_errors_run_no_business_logic():
    svc = service()
    expect_raises(InputError, svc.analyze)                   # no transaction, not demo mode
    bad_account = repo().demo_transaction().model_copy(update={"account_id": "ACC-NOPE"})
    expect_raises(InputError, svc.analyze, bad_account)
    bad_type = repo().demo_transaction().model_copy(update={"transaction_type": "crypto_swap"})
    expect_raises(InputError, svc.analyze, bad_type)


def test_internal_gate_failure_degrades_to_review_not_to_safety():
    svc = BlackboxService(repo(), service().models)
    original = ImpactGate.score_batch

    def boom(cls, items, models=None):
        raise RuntimeError("model exploded")

    ImpactGate.score_batch = classmethod(boom)
    try:
        cert = svc.analyze(demo_mode=True)
    finally:
        ImpactGate.score_batch = original
        ImpactGate.use_models(service().models)
    assert cert.status == "REVIEW" and cert.recommended_action == "REVIEW"
    assert any("model exploded" in line for line in cert.evidence)


def test_internal_simulation_failure_degrades_to_review_and_keeps_the_score():
    svc = service()
    tx = _find(selected=True, fails=False)
    from backend.simulation import crash_test

    original = crash_test.CrashTestEngine.attack

    def boom(baseline_fork, scenario):
        raise RuntimeError("simulator down")

    crash_test.CrashTestEngine.attack = staticmethod(boom)
    import backend.pipeline as pipeline
    pipeline.CrashTestEngine.attack = staticmethod(boom)
    try:
        cert = svc.analyze(tx)
    finally:
        crash_test.CrashTestEngine.attack = original
        pipeline.CrashTestEngine.attack = original
    assert cert.status == "REVIEW" and cert.recommended_action == "REVIEW"
    assert cert.impact_score.gate_decision is True and cert.impact_score.score > 0
    assert any("simulator down" in line for line in cert.evidence)


def test_trace_and_stage_timing_diagnostics():
    diagnostics.RECENT_EVENTS.clear()
    cert = service().analyze(_find(selected=True, fails=True))
    events = [e for e in diagnostics.RECENT_EVENTS if e["trace_id"] == cert.trace_id]
    stages = [e["stage"] for e in events]
    for needed in ("request_received", "context_loaded", "gate_scored", "simulation_started",
                   "scenario_completed", "fragility_completed", "certificate_generated", "response_sent"):
        assert needed in stages, f"missing stage {needed}"
    assert stages.count("scenario_completed") == 3
    for event in events:
        assert {"trace_id", "transaction_id", "stage", "status", "elapsed_ms"} <= set(event)
        assert event["transaction_id"] == cert.transaction_id and event["elapsed_ms"] >= 0


def test_health_reports_the_real_architecture():
    health = service().health()
    assert health["status"] == "ok"
    assert health["architecture"] == (platform.machine() or "unknown")
    assert (health["runtime"] == "linuxone") == (platform.machine() == "s390x")


def test_showcase_covers_gate_outcomes_and_never_uses_the_test_split():
    items = service().demo_transactions()
    assert items[0]["transaction"]["id"] == config.DEMO_TRANSACTION_ID
    test_ids = {r.transaction.id for r in repo().records_for_split("test")}
    assert not ({i["transaction"]["id"] for i in items} & test_ids)
    assert len(items) >= 4


def test_http_routes_when_fastapi_is_available():
    try:
        from fastapi.testclient import TestClient
        from backend.main import app
    except Exception:  # noqa: BLE001 - FastAPI not installed in this environment
        return
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/dashboard").status_code == 200
        assert len(client.get("/transactions").json()) >= 4
        ok = client.post("/analyze", json={"demo_mode": True})
        assert ok.status_code == 200 and ok.json()["transaction_id"] == config.DEMO_TRANSACTION_ID
        assert client.post("/analyze", json={}).status_code == 422
        bad = client.post("/analyze", json={"transaction": {"id": "", "account_id": "x", "amount": 5,
                          "timestamp": "2026-03-02T09:00:00Z", "transaction_type": "card_payment"}})
        assert bad.status_code == 422
