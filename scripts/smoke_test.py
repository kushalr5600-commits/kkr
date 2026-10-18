"""Tiny deterministic smoke test of the whole pipeline (no web server needed).

    python scripts/smoke_test.py

Exits non-zero on any failure. When FastAPI and httpx are available it also
exercises HTTP routes through the Starlette test client (full documented
workflow: ``pip install -r requirements-numpy.txt -r requirements-test.txt``).

Set ``BLACKBOX_REQUIRE_HTTP=1`` to FAIL (exit 1) instead of SKIP when the HTTP
client stack is missing — use this on LinuxONE / CI where HTTP checks are
required evidence.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.pipeline import BlackboxService  # noqa: E402
from backend.shared import config  # noqa: E402
from backend.shared.schemas import DecisionCertificate, Transaction  # noqa: E402


def check(cond: bool, message: str) -> None:
    print(("PASS  " if cond else "FAIL  ") + message)
    if not cond:
        sys.exit(1)


def _http_smoke() -> None:
    require = os.environ.get("BLACKBOX_REQUIRE_HTTP", "").strip().lower() in {"1", "true", "yes"}
    try:
        from fastapi.testclient import TestClient
        from backend.main import app
    except Exception as exc:  # noqa: BLE001
        msg = f"HTTP client stack unavailable: {type(exc).__name__}: {exc}"
        if require:
            print(f"FAIL  {msg}")
            print("      install test deps: pip install -r requirements-test.txt")
            sys.exit(1)
        print(f"SKIP  HTTP routes ({msg})")
        print("      full workflow: pip install -r requirements-numpy.txt -r requirements-test.txt")
        return

    with TestClient(app) as client:
        h = client.get("/health").json()
        check(h["status"] == "ok", "GET /health")
        check(h["model_backend"] in {"numpy", "sklearn"}, "GET /health reports model backend")
        check(h.get("otel_enabled") in {"0", "1"}, "GET /health reports otel_enabled truthfully")
        check(client.get("/dashboard").status_code == 200, "GET /dashboard")
        r = client.post("/analyze", json={"demo_mode": True})
        check(
            r.status_code == 200 and r.json()["transaction_id"] == config.DEMO_TRANSACTION_ID,
            "POST /analyze (demo)",
        )
        body = r.json()
        check(body["status"] in {"NO_SIMULATION", "SIMULATED", "REVIEW"}, f"HTTP demo status {body['status']}")
        check(
            body["runtime"]["model_versions"].get("policy_version") == config.POLICY_VERSION,
            "HTTP certificate carries policy_version",
        )
        if body["status"] == "NO_SIMULATION":
            check(body["forks_tested"] == [], "HTTP demo has zero forks")
        check(client.post("/analyze", json={}).status_code == 422, "POST /analyze rejects an empty request")
        check(
            client.post("/analyze", json={"demo_mode": True, "unexpected": True}).status_code == 422,
            "POST /analyze rejects unknown top-level fields",
        )
        txs = client.get("/transactions").json()
        check(isinstance(txs, list) and len(txs) >= 1, "GET /transactions non-empty")
        sim = next((t for t in txs if "fails a stress" in t.get("hint", "")), None)
        check(sim is not None, "showcase includes gate-selected failing example")
        if sim is not None:
            r2 = client.post("/analyze", json={"transaction": sim["transaction"]})
            check(r2.status_code == 200, "POST /analyze (simulated example)")
            b2 = r2.json()
            check(b2["status"] == "SIMULATED", f"simulated example status {b2['status']}")
            check(len(b2["forks_tested"]) == 6, "HTTP simulated example has 6 forks")


def main() -> None:
    service = BlackboxService.build()
    health = service.health()
    print("health:", health)
    check(health["status"] == "ok", "service reports ok")

    demo = service.analyze(demo_mode=True)
    DecisionCertificate.model_validate(demo.model_dump())
    check(demo.transaction_id == config.DEMO_TRANSACTION_ID, "demo mode analyzes the fixed demo transaction")
    check(demo.status in {"NO_SIMULATION", "SIMULATED", "REVIEW"}, f"demo certificate status = {demo.status}")
    again = service.analyze(demo_mode=True)
    check(demo.impact_score == again.impact_score, "demo impact score is deterministic")
    if demo.status == "NO_SIMULATION":
        check(demo.forks_tested == [] and demo.fragility == [], "NO_SIMULATION has zero forks/fragility")
        check(
            any("No deep simulation was run" in line for line in demo.evidence),
            "NO_SIMULATION evidence states no deep simulation was run",
        )
    check(
        demo.runtime.model_versions.get("backend") in {"numpy", "sklearn"},
        "certificate reports model backend identity",
    )

    simulated = None
    for item in service.demo_transactions():
        cert = service.analyze(Transaction.model_validate(item["transaction"]))
        if cert.status == "SIMULATED":
            simulated = cert
            break
    check(simulated is not None, "at least one example transaction is selected for simulation")
    check(len(simulated.forks_tested) == 2 * len(config.SCENARIOS), "6 fork results (normal+stress x 3 scenarios)")
    check(len(simulated.fragility) == len(config.SCENARIOS), "3 fragility results")
    check(
        any(f.scenario for f in simulated.forks_tested) and all(
            {f.fork_name for f in simulated.forks_tested if f.scenario == s} == {"normal", "stress"}
            for s in config.SCENARIOS
        ),
        "every simulated scenario has a normal+stress pair",
    )
    print("simulated example:", simulated.transaction_id, simulated.recommended_action)

    _http_smoke()
    print("smoke test complete")


if __name__ == "__main__":
    main()
