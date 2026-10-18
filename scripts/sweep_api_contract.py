"""Contract check: every field path app.js reads from key endpoints must exist
in the real API responses (TestClient). Catches silent undefined renders."""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from backend.main import app

js = pathlib.Path("frontend/static/app.js").read_text(encoding="utf-8")
problems: list[str] = []


def deep_has(obj, path: list[str]) -> bool:
    cur = obj
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        elif isinstance(cur, list) and cur and isinstance(cur[0], dict) and p in cur[0]:
            cur = cur[0]
        else:
            return False
    return True


with TestClient(app) as c:
    # ---- /explain (frontend: payload.* / cert.* / ai_signals.*) ----
    explain = c.post("/explain", json={"demo_mode": True}).json()
    for p in [
        ["certificate", "impact_score", "score"],
        ["certificate", "status"],
        ["certificate", "recommended_action"],
        ["certificate", "certificate_id"],
        ["contributions"],
        ["ai_signals", "anomaly", "normalized_a"],
        ["ai_signals", "risk", "normalized_u"],
        ["ai_signals", "gate", "simulation_executed"],
        ["ai_signals", "signal_sources", "M"],
        ["policy_version"],
        ["technical_detail"],
    ]:
        if not deep_has(explain, p):
            problems.append(f"/explain missing {'.'.join(p)}")

    # contributions item fields used by UI
    for key in ("code", "name", "signal", "weight", "weighted"):
        if explain["contributions"] and key not in explain["contributions"][0]:
            problems.append(f"/explain contributions[0] missing {key}")

    # ---- /research/what-if ----
    wi = c.post("/research/what-if", json={"demo_mode": True, "overrides": {"amount": 99999.0}}).json()
    for p in [
        ["research_only"], ["changes"],
        ["original", "gate", "score"], ["original", "gate", "selected"], ["original", "signals", "A"],
        ["hypothetical", "gate", "score"], ["hypothetical", "gate", "selected"],
        ["hypothetical", "signals", "A"], ["hypothetical", "plain_language"],
        ["delta", "score"],
    ]:
        if not deep_has(wi, p):
            problems.append(f"/research/what-if missing {'.'.join(p)}")

    # ---- /transactions ----
    txs = c.get("/transactions").json()
    if not txs or "transaction" not in txs[0] or "hint" not in txs[0]:
        problems.append("/transactions shape wrong")
    for key in ("id", "amount", "transaction_type"):
        if key not in txs[0]["transaction"]:
            problems.append(f"/transactions transaction missing {key}")

    # ---- /health fields UI reads ----
    h = c.get("/health").json()
    for key in ("status", "runtime", "architecture", "model_backend"):
        if key not in h:
            problems.append(f"/health missing {key}")

    # ---- /counterexample ----
    ce = c.get("/counterexample/TX-00108-B").json()
    for key in ("transaction_id", "gate_selected", "missed_failure", "certificate", "kind", "note", "stress_measured"):
        if key not in ce:
            problems.append(f"/counterexample missing {key}")

    # ---- /datasets (list) + detail UI item fields ----
    import io

    csv = "tx_id,acct,amt,ts,ttype,label\nN0,A0,100,2026-01-01T00:00:00Z,card_payment,0\n"
    up = c.post("/datasets/upload", files={"file": ("c.csv", io.BytesIO(csv.encode()), "text/csv")}).json()
    ds_list = c.get("/datasets").json()
    # list-item fields used in list rendering (guard `ds.` accesses that appear
    # inside loadDatasets' items.forEach, not openDataset's detail render)
    list_fn = re.search(r"function loadDatasets\(\)(.*?)function openDataset", js, re.S)
    list_body = list_fn.group(1) if list_fn else ""
    ds_list_props = sorted(set(re.findall(r"\bds\.([A-Za-z_][\w]*)", list_body)))
    for prop in ds_list_props:
        if prop not in ds_list[0]:
            problems.append(f"/datasets list item missing UI field {prop}")
    # detail fields used by openDataset
    detail = c.get(f"/datasets/{up['dataset_id']}").json()
    open_fn = re.search(r"function openDataset\(id\) \{(.*?)\n  function ", js, re.S)
    open_body = open_fn.group(1) if open_fn else ""
    ds_detail_props = sorted(set(re.findall(r"\bds\.([A-Za-z_][\w]*)", open_body)))
    for prop in ds_detail_props:
        if prop not in detail:
            problems.append(f"/datasets detail missing UI field {prop}")

    # ---- /experiments UI fields ----
    c.post(
        f"/datasets/{up['dataset_id']}/map",
        json={
            "mapping": {"id": "tx_id", "account_id": "acct", "amount": "amt", "timestamp": "ts", "transaction_type": "ttype", "label": "label"},
            "label_semantics": "fraud",
        },
    )
    c.post(f"/datasets/{up['dataset_id']}/evaluate", json={"max_rows": 10})
    exps = c.get("/experiments").json()
    ex_props = sorted(set(re.findall(r"\bex\.([A-Za-z_]+)", js)))
    for prop in ex_props:
        if prop not in exps[0]:
            problems.append(f"/experiments item missing UI field {prop}")

    # ---- evaluate report fields UI (eval-out JSON) reads ----
    rep = exps[0]
    for key in ("run_id", "dataset_id", "rows_scored", "simulation_rate", "label_semantics", "metrics"):
        if key not in rep:
            problems.append(f"evaluate report missing {key}")

    # ---- registry UI fields ----
    reg = c.get("/datasets/registry").json()
    reg_js = pathlib.Path("frontend/static/app.js").read_text(encoding="utf-8")
    entry_props = sorted(set(re.findall(r"\bentry\.([A-Za-z_]+)", reg_js)))
    if reg["entries"]:
        for prop in entry_props:
            if prop not in reg["entries"][0]:
                problems.append(f"registry entry missing UI field {prop}")

print("=== CONTRACT PROBLEMS ===")
for p in problems:
    print("P:", p)
if not problems:
    print("none")
print(f"checked explain/what-if/transactions/health/counterexample/datasets/experiments/registry")
