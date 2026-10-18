"""AI intelligence layer tests: real model outputs, what-if isolation, explain consistency."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.data.repository import DataRepository
from backend.intelligence.signals import explain_signals, what_if
from backend.main import app
from backend.pipeline import BlackboxService
from backend.shared import config
from backend.shared.errors import InputError
from backend.shared.schemas import Transaction
from tests.fixtures import expect_raises


def _svc() -> BlackboxService:
    return BlackboxService.build()


def test_explain_signals_exposes_real_anomaly_and_risk_outputs():
    repo = DataRepository.default()
    tx = repo.demo_transaction()
    account, graph, context = repo.load_context(tx)
    out = explain_signals(tx, account, graph, context)
    assert out["model_backend"] in {"numpy", "sklearn"}
    assert out["fitted_on_split"] == "calibration"
    a = out["anomaly"]
    assert a["raw"] is not None and a["normalized_a"] is not None
    assert 0.0 <= a["normalized_a"] <= 1.0
    assert "empirical_cdf" in a["calibration_method"]
    assert "not a fraud probability" in " ".join(a["caveats"]).lower() or "fraud" in " ".join(a["caveats"]).lower()
    r = out["risk"]
    assert r["normalized_u"] is not None and 0.0 <= r["normalized_u"] <= 1.0
    assert r["failure_probability_mean"] is None or 0.0 <= r["failure_probability_mean"] <= 1.0
    # Contributions must match the ACTIVE gate weights and sum to the score
    from backend.gate.interaction_aware import is_enabled

    by = {c["code"]: c for c in out["contributions"]}
    if is_enabled():
        assert by["A"]["weight"] == 0.45
        assert by["W"]["weight"] == 0.30
        assert by["D"]["weight"] == 0.15
        assert by["L"]["weight"] == 0.10
        assert out["gate"]["formula"] == "I = 0.45*A + 0.30*W + 0.15*D + 0.10*L"
    else:
        assert by["M"]["weight"] == 0.30
        assert by["A"]["weight"] == 0.25
    assert abs(out["gate"]["score"] - sum(c["weighted"] for c in out["contributions"])) < 1e-9
    assert out["gate"]["threshold"] == 0.60
    assert out["signal_sources"]["A"] == "ml_model"
    assert out["signal_sources"]["D"] == "graph_derived"


def test_explain_signals_consistent_with_gate_score_for_showcase():
    svc = _svc()
    repo = DataRepository.default()
    checked = 0
    for item in svc.demo_transactions():
        tx = Transaction.model_validate(item["transaction"])
        cert = svc.analyze(transaction=tx)
        account, graph, context = repo.load_context(tx)
        ai = explain_signals(tx, account, graph, context)
        assert abs(ai["gate"]["score"] - cert.impact_score.score) < 1e-9
        assert ai["gate"]["selected"] is cert.impact_score.gate_decision
        checked += 1
    assert checked >= 5


def test_what_if_isolated_and_rejects_bad_overrides():
    repo = DataRepository.default()
    tx = repo.demo_transaction()
    account, graph, context = repo.load_context(tx)
    result = what_if(tx, account, graph, context, {"amount": float(tx.amount) * 3})
    assert result["research_only"] is True
    assert result["original"]["transaction"]["amount"] == tx.amount
    assert result["hypothetical"]["transaction"]["amount"] != tx.amount
    # Original transaction object unchanged
    assert tx.amount == repo.demo_transaction().amount
    assert "delta" in result
    # Backend symmetry: hypothetical exposes signals like original (UI depends on it)
    assert set(result["hypothetical"]["signals"]) == {"M", "D", "A", "U"}
    for code in ("M", "D", "A", "U"):
        v = result["hypothetical"]["signals"][code]
        assert 0.0 <= v <= 1.0
    assert abs(result["delta"]["score"] - (
        result["hypothetical"]["gate"]["score"] - result["original"]["gate"]["score"]
    )) < 1e-9

    expect_raises(InputError, what_if, tx, account, graph, context, {"nope": 1})
    expect_raises(InputError, what_if, tx, account, graph, context, {"amount": -5})
    expect_raises(InputError, what_if, tx, account, graph, context, {"transaction_type": "crypto_swap"})
    expect_raises(InputError, what_if, tx, account, graph, context, {})


def test_what_if_type_change_keeps_original_baseline_graph():
    """Regression: type override must not rebuild D for the original baseline."""
    repo = DataRepository.default()
    tx = repo.demo_transaction()
    account, graph, context = repo.load_context(tx)
    base_d = explain_signals(tx, account, graph, context)["signals"]["D"]
    result = what_if(tx, account, graph, context, {"transaction_type": "refund"})
    assert abs(result["original"]["signals"]["D"] - base_d) < 1e-12
    # And the original transaction baseline values are untouched
    assert result["original"]["transaction"]["amount"] == tx.amount
    assert result["original"]["transaction"]["transaction_type"] == tx.transaction_type


def test_http_explain_includes_ai_signals_and_what_if():
    with TestClient(app) as c:
        r = c.post("/explain", json={"demo_mode": True})
        assert r.status_code == 200
        body = r.json()
        assert "ai_signals" in body
        ai = body["ai_signals"]
        assert ai.get("available", True) is not False
        assert ai["anomaly"]["normalized_a"] is not None
        assert ai["risk"]["normalized_u"] is not None
        # Demo may be NO_SIMULATION or SIMULATED depending on scoring mode
        assert ai["gate"]["simulation_executed"] is (ai["gate"]["selected"])
        if not ai["gate"]["selected"]:
            assert ai["measured_stress_failures"] is None
        assert any("fraud" in c.lower() or "probability" in c.lower() for c in ai["anomaly"]["caveats"])

        w = c.post("/research/what-if", json={"demo_mode": True, "overrides": {"amount": 99999.0}})
        assert w.status_code == 200
        assert w.json()["research_only"] is True

        bad = c.post("/research/what-if", json={"demo_mode": True, "overrides": {"bogus": 1}})
        assert bad.status_code == 422


def test_http_challenge_lab_false_negative_analysis_present():
    import io

    csv = (
        "tx_id,acct,amt,ts,ttype,label\n"
        + "\n".join(
            [f"N{i},A{i%2},10{i},2026-01-01T00:00:00Z,card_payment,0" for i in range(10)]
            + [f"P{i},A0,50{i},2026-01-01T00:01:00Z,wire_transfer,1" for i in range(3)]
        )
        + "\n"
    )
    with TestClient(app) as c:
        up = c.post(
            "/datasets/upload",
            files={"file": ("fn.csv", io.BytesIO(csv.encode()), "text/csv")},
        )
        assert up.status_code == 200
        ds = up.json()
        c.post(
            f"/datasets/{ds['dataset_id']}/map",
            json={
                "mapping": {
                    "id": "tx_id",
                    "account_id": "acct",
                    "amount": "amt",
                    "timestamp": "ts",
                    "transaction_type": "ttype",
                    "label": "label",
                },
                "label_semantics": "fraud",
            },
        )
        ev = c.post(f"/datasets/{ds['dataset_id']}/evaluate", json={"max_rows": 50})
        assert ev.status_code == 200
        report = ev.json()
        assert "false_negative_analysis" in report
        fn = report["false_negative_analysis"]
        assert fn["research_only"] is True
        assert fn["never_changes_production_gate"] is True
        assert fn["dataset_sha256"] == ds["sha256"]
        if fn["finding_count"] == 0:
            assert "No false negatives" in fn["note"]
        else:
            assert all(f["finding_type"] == "descriptive" for f in fn["findings"])
            assert all(f["validated"] is False for f in fn["findings"])
