from __future__ import annotations

import io

from fastapi.testclient import TestClient

from backend.main import app

csv = (
    "tx_id,acct,amt,ts,ttype,label\n"
    + "\n".join(
        [f"N{i},A{i % 2},10{i},2026-01-01T00:00:00Z,card_payment,0" for i in range(10)]
        + [f"P{i},A0,50{i},2026-01-01T00:01:00Z,wire_transfer,1" for i in range(3)]
    )
    + "\n"
)

with TestClient(app) as c:
    up = c.post("/datasets/upload", files={"file": ("s.csv", io.BytesIO(csv.encode()), "text/csv")}).json()
    c.post(
        f"/datasets/{up['dataset_id']}/map",
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
    r = c.post(
        f"/datasets/{up['dataset_id']}/evaluate",
        json={"max_rows": 50, "run_stress_sample": True},
    ).json()
    ss = r["stress_sample"]
    print("sample_size", ss["sample_size"], "fail_count", ss["stress_failure_count"], "outcomes", len(ss["outcomes"]))
    assert r["metrics"]["label_positive_count"] == 3
    print("labels_intact OK")
    print(
        "gate_selected",
        r["gate_selected_count"],
        "recall",
        r["metrics"]["selection_recall_positive_label"],
        "precision",
        r["metrics"]["selection_precision_positive_label"],
    )

    # --- upload security probes ---
    bad = c.post("/datasets/upload", files={"file": ("../../evil.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")})
    print("traversal_name", bad.status_code, bad.json().get("detail", {}).get("error_message", "")[:80] if isinstance(bad.json(), dict) else bad.text[:80])
    bad2 = c.post("/datasets/upload", files={"file": ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream")})
    print("exe_upload", bad2.status_code)
    big = c.post("/datasets/upload", files={"file": ("big.csv", io.BytesIO(b"x" * (6 * 1024 * 1024)), "text/csv")})
    print("oversize", big.status_code)

    # path traversal on dataset id
    r404 = c.get("/datasets/..%2F..%2Fetc%2Fpasswd")
    print("traversal_id", r404.status_code)

    # malformed mapping
    r422 = c.post(f"/datasets/{up['dataset_id']}/map", json={"mapping": {}, "label_semantics": "fraud"})
    print("empty_mapping", r422.status_code)

    # counterexample unknown id
    ce = c.get("/counterexample/NOPE")
    print("unknown_counterexample", ce.status_code)
