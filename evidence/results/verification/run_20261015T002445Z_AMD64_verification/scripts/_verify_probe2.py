from __future__ import annotations

import json
import pathlib

import jsonschema
from fastapi.testclient import TestClient

from backend.main import app

schema = json.loads(pathlib.Path("schemas/decision_certificate.v1.schema.json").read_text(encoding="utf-8"))

with TestClient(app) as c:
    r = c.post("/analyze", json={"demo_mode": True})
    cert = r.json()
    jsonschema.Draft202012Validator(schema).validate(cert)
    print("demo_cert_schema OK", cert["status"])

    tx300 = next(i["transaction"] for i in c.get("/transactions").json() if i["transaction"]["id"] == "TX-00300")
    r = c.post("/analyze", json={"transaction": tx300})
    cert2 = r.json()
    jsonschema.Draft202012Validator(schema).validate(cert2)
    print("sim_cert_schema OK", cert2["status"], "forks", len(cert2["forks_tested"]))

    s = cert2["impact_score"]
    w = [0.30, 0.30, 0.25, 0.15]
    vals = [s["signals"]["magnitude"], s["signals"]["dependency"], s["signals"]["anomaly"], s["signals"]["uncertainty"]]
    print("cert_reconcile", abs(sum(wi * vi for wi, vi in zip(w, vals)) - s["score"]))
    print("decision_agrees", (s["score"] >= 0.60) == s["gate_decision"])

    e = c.post("/explain", json={"transaction": tx300}).json()
    print("explain_vs_analyze", abs(e["certificate"]["impact_score"]["score"] - cert2["impact_score"]["score"]))

    demo = c.post("/analyze", json={"demo_mode": True}).json()
    assert demo["status"] == "NO_SIMULATION"
    assert demo["forks_tested"] == [] and demo["fragility"] == []
    assert any(l.startswith("LIMITATION: ") for l in demo["evidence"])
    print("demo_honesty OK")

    h = c.get("/health").json()
    print("health", h)
    assert h["architecture"] == "AMD64" and h["runtime"] == "local"
    assert h["model_backend"] == "numpy"
