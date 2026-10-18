"""HTTP API contract for the dashboard (completion sprint).

Uses FastAPI TestClient when available; otherwise the file is skipped by
``scripts/run_tests.py`` import errors are avoided by guarding import.
"""
from __future__ import annotations

try:
    from fastapi.testclient import TestClient
except Exception:  # noqa: BLE001 - httpx/starlette optional for some hosts
    TestClient = None  # type: ignore[assignment]

from backend.shared import config


def _client():
    if TestClient is None:
        raise ImportError("fastapi/testclient unavailable")
    from backend.main import app

    return TestClient(app)


def test_http_health_dashboard_and_static_assets():
    with _client() as c:
        h = c.get("/health").json()
        assert h["status"] == "ok"
        assert h["model_backend"] in {"numpy", "sklearn"}
        assert h["gate_threshold"] == f"{config.IMPACT_THRESHOLD:.2f}"
        assert c.get("/dashboard").status_code == 200
        assert c.get("/static/app.js").status_code == 200
        assert c.get("/static/style.css").status_code == 200
        assert c.get("/").status_code in {200, 307}


def test_http_analyze_demo_and_validation_errors():
    with _client() as c:
        r = c.post("/analyze", json={"demo_mode": True})
        assert r.status_code == 200
        body = r.json()
        assert body["transaction_id"] == config.DEMO_TRANSACTION_ID
        assert body["status"] == "NO_SIMULATION"
        assert body["forks_tested"] == []
        assert any("No deep simulation was run" in line for line in body["evidence"])

        assert c.post("/analyze", json={}).status_code == 422

        txs = c.get("/transactions").json()
        assert len(txs) >= 2
        assert txs[0]["transaction"]["id"] == config.DEMO_TRANSACTION_ID
        sim = next(
            (t for t in txs if "fails a stress" in t["hint"]),
            None,
        )
        assert sim is not None, "showcase list must include a gate-selected failing example"
        r2 = c.post("/analyze", json={"transaction": sim["transaction"]})
        assert r2.status_code == 200
        b2 = r2.json()
        assert b2["status"] == "SIMULATED"
        assert len(b2["forks_tested"]) == 6
        assert b2["recommended_action"] in {"BLOCK_OR_HOLD", "REVIEW", "ALLOW_NORMAL_PATH"}

        bad = dict(sim["transaction"])
        bad["transaction_type"] = "crypto_swap"
        assert c.post("/analyze", json={"transaction": bad}).status_code == 422

        # Unknown top-level keys are rejected (strict AnalyzeRequest).
        assert c.post("/analyze", json={"demo_mode": True, "extra": 1}).status_code == 422

        # Certificate consistency: no-simulation must not claim forks or simulated status.
        r3 = c.post("/analyze", json={"demo_mode": True}).json()
        assert r3["status"] == "NO_SIMULATION"
        assert r3["forks_tested"] == []
        assert r3["fragility"] == []
        assert any("LIMITATION" in line or "No deep simulation" in line for line in r3["evidence"])
        assert r3["impact_score"]["gate_decision"] is False
        assert r3["impact_score"]["score"] < config.IMPACT_THRESHOLD
        assert r3["runtime"]["model_versions"]["policy_version"] == config.POLICY_VERSION
        assert "threshold=0.60" in r3["runtime"]["model_versions"]["policy_formula"]

        # Simulated path: scenarios match frozen set; fragility non-empty.
        assert b2["fragility"]
        scenarios = {f["scenario"] for f in b2["forks_tested"]}
        assert set(config.SCENARIOS).issubset(scenarios)
        assert b2["impact_score"]["score"] >= config.IMPACT_THRESHOLD
        assert b2["status"] == "SIMULATED"


def test_http_non_finite_context_is_structured_422_not_500():
    """C1 regression: a NaN/Infinity dependency load must be a JSON-safe 422.

    The schema constraint (allow_inf_nan=False) rejects the input, and the
    RequestValidationError handler must serialize the validation error - which
    embeds the raw non-finite INPUT value - without crashing into a raw 500.
    Before the fix, json.dumps raised "Out of range float values are not JSON
    compliant" inside the default handler and the client saw HTTP 500.
    (Raw content, not json=: httpx's own encoder rejects NaN client-side.)
    """
    import json as _json

    with _client() as c:
        tx = {
            "id": "TX-NAN-1", "account_id": "ACC-0000", "amount": 120.0,
            "timestamp": "2026-03-02T09:00:00Z", "transaction_type": "card_payment",
        }
        for bad in (float("nan"), float("inf")):
            body = {
                "transaction": tx, "demo_mode": False,
                "context": {
                    "recent_transactions": [],
                    "local_dependency_load": {"ledger": bad},
                    "window_seconds": 60,
                },
            }
            r = c.post(
                "/analyze",
                content=_json.dumps(body),
                headers={"Content-Type": "application/json"},
            )
            assert r.status_code == 422, r.text  # never 500
            payload = r.json()  # proves the 422 body itself is JSON-compliant
            assert payload["detail"], payload


def test_http_unknown_transaction_discloses_defaulted_context():
    """An unknown transaction id gets a synthesized quiet context; the
    certificate must disclose that the background load is not measured."""
    with _client() as c:
        from backend.data.repository import DataRepository

        account_id = DataRepository.default().demo_transaction().account_id
        body = {
            "demo_mode": False,
            "transaction": {
                "id": "TX-NOT-IN-DATASET", "account_id": account_id, "amount": 120.0,
                "timestamp": "2026-03-02T09:00:00Z", "transaction_type": "card_payment",
            },
        }
        r = c.post("/analyze", json=body)
        assert r.status_code == 200, r.text
        evidence = r.json()["evidence"]
        assert any("Context defaulted" in line for line in evidence), evidence
