from __future__ import annotations

import io
import json

import numpy as np
from fastapi.testclient import TestClient

from backend.eval.benchmark import _false_negative_analysis, _metrics_from_labels
from backend.main import app

# --- reference confusion matrix logic (EX-0702bb6eb4 shape) ---
y = np.array([1.0, 1.0, 1.0] + [0.0] * 10)
sel = np.array([False] * 13)
m = _metrics_from_labels(y, sel)
assert m["fn_skipped_labeled_positive"] == 3
assert m["tp_selected_labeled_positive"] == 0
assert m["tn_skipped_labeled_negative"] == 10
assert m["selection_recall_positive_label"] == 0.0  # 0/3
assert m["selection_precision_positive_label"] is None  # undefined, not 0.0
print("reference_cm_logic OK", {k: m[k] for k in ("tp_selected_labeled_positive", "fn_skipped_labeled_positive", "selection_recall_positive_label", "selection_precision_positive_label")})

# --- live Challenge Lab HTTP workflow ---
csv_lines = ["tx_id,acct,amt,ts,ttype,label"]
for i in range(10):
    csv_lines.append(f"N{i},A{i % 2},10{i},2026-01-01T00:00:00Z,card_payment,0")
for i in range(3):
    csv_lines.append(f"P{i},A0,50{i},2026-01-01T00:01:00Z,wire_transfer,1")
csv = "\n".join(csv_lines) + "\n"

with TestClient(app) as c:
    up = c.post("/datasets/upload", files={"file": ("cl.csv", io.BytesIO(csv.encode()), "text/csv")})
    assert up.status_code == 200, up.text
    ds = up.json()
    mp = c.post(
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
    assert mp.status_code == 200, mp.text
    ev1 = c.post(f"/datasets/{ds['dataset_id']}/evaluate", json={"max_rows": 50})
    assert ev1.status_code == 200, ev1.text
    rep1 = ev1.json()
    ev2 = c.post(f"/datasets/{ds['dataset_id']}/evaluate", json={"max_rows": 50})
    rep2 = ev2.json()

    met = rep1["metrics"]
    print("lab_run1", rep1["run_id"], "selected", rep1["gate_selected_count"], "skipped", rep1["gate_skipped_count"])
    print("lab_metrics", {k: met.get(k) for k in (
        "tp_selected_labeled_positive", "fn_skipped_labeled_positive",
        "selection_recall_positive_label", "selection_precision_positive_label")})
    # precision null when nothing selected
    if rep1["gate_selected_count"] == 0:
        assert met.get("selection_precision_positive_label") is None
        print("precision_null_when_none_selected OK")
    # separate run ids, historical not overwritten (in-memory ring + unique ids)
    assert rep1["run_id"] != rep2["run_id"]
    print("distinct_run_ids OK", rep1["run_id"], rep2["run_id"])
    assert rep1["dataset_sha256"] == ds["sha256"] == rep2["dataset_sha256"]
    fn = rep1["false_negative_analysis"]
    assert fn["research_only"] is True and fn["never_changes_production_gate"] is True
    # stress sample isolation: request stress sample; stress failures must be its own field
    ev3 = c.post(f"/datasets/{ds['dataset_id']}/evaluate", json={"max_rows": 50, "run_stress_sample": True})
    rep3 = ev3.json()
    print("stress_sample keys", [k for k in rep3 if "stress" in k])
    ss = rep3.get("stress_sample")
    if ss:
        print("stress_sample", {k: ss.get(k) for k in ("rows_sampled", "measured_stress_failures", "note")})
    # label semantics preserved
    assert rep1["label_semantics"] == "fraud"
    # experiments ring
    exps = c.get("/experiments").json()
    assert isinstance(exps, list) and len(exps) >= 3
    print("experiments_ring", len(exps))
    # experiments distinguish measured vs hypothetical
    top = exps[0]
    print("exp_keys", sorted(top.keys()))

    # counterexample showcase
    ce = c.get("/counterexample/TX-00108-B")
    assert ce.status_code == 200, ce.text
    body = ce.json()
    print("counterexample keys", sorted(body.keys())[:12])
    print("counterexample", {k: body.get(k) for k in ("transaction_id", "gate_selected", "stress_failure", "missed_failure") if k in body})
