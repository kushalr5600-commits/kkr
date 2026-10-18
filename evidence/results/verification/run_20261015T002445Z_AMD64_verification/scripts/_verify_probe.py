from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.main import app

c = TestClient(app, raise_server_exceptions=False)
r = c.post(
    "/research/what-if",
    content=b'{"demo_mode":true,"overrides":{"amount":NaN}}',
    headers={"Content-Type": "application/json"},
)
print("raw NaN", r.status_code, str(r.json())[:240])
r = c.post(
    "/research/what-if",
    content=b'{"demo_mode":true,"overrides":{"amount":Infinity}}',
    headers={"Content-Type": "application/json"},
)
print("raw Inf", r.status_code, str(r.json())[:240])
r = c.post(
    "/analyze",
    content=b'{"demo_mode":true,"bogus":1}',
    headers={"Content-Type": "application/json"},
)
print("extra", r.status_code)
r = c.post("/analyze", content=b"not json", headers={"Content-Type": "application/json"})
print("badjson", r.status_code, str(r.json())[:200])
try:
    import jsonschema

    print("jsonschema", getattr(jsonschema, "__version__", "?"))
except Exception as exc:  # noqa: BLE001
    print("jsonschema ABSENT", type(exc).__name__)

# what-if type-change original D integrity
from backend.data.repository import DataRepository
from backend.intelligence.signals import explain_signals, what_if

repo = DataRepository.default()
tx = repo.demo_transaction()
account, graph, context = repo.load_context(tx)
base_d = explain_signals(tx, account, graph, context)["contributions"][1]["signal"]
wi = what_if(tx, account, graph, context, {"transaction_type": "refund"})
print("base_d", base_d, "wi_original_D", wi["original"]["signals"]["D"])
print("WHATIF_D_BUG" if abs(base_d - wi["original"]["signals"]["D"]) > 1e-12 else "WHATIF_D_OK")
