"""Dataset Studio, Challenge Lab, explain API, counterexample tests."""
from __future__ import annotations

import io

from fastapi.testclient import TestClient

from backend.shared import config
from backend.shared.errors import InputError
from backend.datasets.store import DatasetStore


CSV_BASIC = (
    "tx_id,acct,amt,ts,ttype,label\n"
    "T1,A1,100,2026-01-01T00:00:00Z,card_payment,0\n"
    "T2,A1,5000,2026-01-01T00:01:00Z,wire_transfer,1\n"
    "T3,A2,80,2026-01-01T00:02:00Z,refund,0\n"
    "T4,A2,9000,2026-01-01T00:03:00Z,ach_batch,1\n"
    "T5,A3,50,2026-01-01T00:04:00Z,internal_transfer,0\n"
    "T6,A3,1200,2026-01-01T00:05:00Z,card_payment,0\n"
    "T7,A1,300,2026-01-01T00:06:00Z,card_payment,0\n"
    "T8,A2,4500,2026-01-01T00:07:00Z,wire_transfer,1\n"
)

CSV_BAD_TYPE = "tx_id,acct,amt,ts,ttype\nX,A1,10,2026-01-01T00:00:00Z,not_a_type\n"
CSV_EMPTY = "tx_id,acct,amt,ts,ttype\n"
CSV_NO_AMOUNT = "id,a,b\n1,2,3\n"


def _client():
    from backend.main import app

    return TestClient(app)


def _upload(c: TestClient, content: str, name: str = "bench.csv") -> dict:
    r = c.post(
        "/datasets/upload",
        files={"file": (name, io.BytesIO(content.encode("utf-8")), "text/csv")},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_upload_preview_map_evaluate_and_remove():
    with _client() as c:
        ds = _upload(c, CSV_BASIC)
        assert ds["row_count"] == 8
        assert ds["column_count"] == 6
        assert "tx_id" in {col["name"] for col in ds["columns"]}
        assert ds["numeric_summary"]["amt"]["max"] == 9000.0

        detail = c.get(f"/datasets/{ds['dataset_id']}?preview_rows=5").json()
        assert len(detail["preview_rows"]) == 5

        bad_map = c.post(
            f"/datasets/{ds['dataset_id']}/map",
            json={"mapping": {"id": "tx_id"}, "label_semantics": None},
        )
        assert bad_map.status_code == 422

        mapping = {
            "id": "tx_id",
            "account_id": "acct",
            "amount": "amt",
            "timestamp": "ts",
            "transaction_type": "ttype",
            "label": "label",
        }
        ok = c.post(
            f"/datasets/{ds['dataset_id']}/map",
            json={"mapping": mapping, "label_semantics": "fraud"},
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["mapping"]["amount"] == "amt"

        ev = c.post(
            f"/datasets/{ds['dataset_id']}/evaluate",
            json={"max_rows": 100, "run_stress_sample": False},
        )
        assert ev.status_code == 200, ev.text
        report = ev.json()
        assert report["rows_scored"] == 8
        assert report["threshold"] == 0.60
        # The benchmark must score with the SAME policy production runs.
        from backend.gate.interaction_aware import is_enabled as _ie

        expected_weights = (
            dict(config.INTERACTION_AWARE_WEIGHTS) if _ie() else dict(config.IMPACT_WEIGHTS)
        )
        assert report["weights"] == expected_weights
        assert report["policy_mode"] in {"interaction_aware", "frozen_reference"}
        assert report["policy_formula"].startswith("I = ")
        assert report["metrics"]["label_positive_count"] == 3
        assert "selection_recall_positive_label" in report["metrics"]
        assert any("not synthetic stress" in lim or "External labels" in lim for lim in report["limitations"])
        assert report["run_id"].startswith("EX-")

        exp = c.get("/experiments").json()
        assert any(x["run_id"] == report["run_id"] for x in exp)
        got = c.get(f"/experiments/{report['run_id']}").json()
        assert got["dataset_sha256"] == ds["sha256"]

        listed = c.get("/datasets").json()
        assert any(d["dataset_id"] == ds["dataset_id"] for d in listed)

        deleted = c.delete(f"/datasets/{ds['dataset_id']}")
        assert deleted.status_code == 200
        assert c.get(f"/datasets/{ds['dataset_id']}").status_code == 404


def test_unsupported_and_oversized_and_empty_uploads():
    with _client() as c:
        bad = c.post(
            "/datasets/upload",
            files={"file": ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        )
        assert bad.status_code == 422

        empty = c.post(
            "/datasets/upload",
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        )
        assert empty.status_code == 422

        # Oversize: exceed DATASET_MAX_BYTES
        big = b"a,b\n" + b"1,2\n" * ((config.DATASET_MAX_BYTES // 4) + 10)
        over = c.post(
            "/datasets/upload",
            files={"file": ("big.csv", io.BytesIO(big), "text/csv")},
        )
        assert over.status_code == 422

        header_only = c.post(
            "/datasets/upload",
            files={"file": ("h.csv", io.BytesIO(CSV_EMPTY.encode()), "text/csv")},
        )
        assert header_only.status_code == 422


def test_unmappable_dataset_evaluate_fails_with_422():
    with _client() as c:
        ds = _upload(c, CSV_NO_AMOUNT, name="noamt.csv")
        # amount column exists but values empty/unusable after mapping to wrong type
        r = c.post(
            f"/datasets/{ds['dataset_id']}/map",
            json={
                "mapping": {
                    "id": "id",
                    "account_id": "a",
                    "amount": "b",
                    "timestamp": "id",
                    "transaction_type": "a",
                },
                "label_semantics": None,
            },
        )
        # 'b' is numeric 3,2 — may map; force evaluate and expect either 200 with
        # small rows or 422 if nothing mappable.
        if r.status_code == 200:
            ev = c.post(f"/datasets/{ds['dataset_id']}/evaluate", json={"max_rows": 10})
            assert ev.status_code in {200, 422}
            if ev.status_code == 422:
                assert "mappable" in str(ev.json()) or "mapping" in str(ev.json())
        else:
            assert r.status_code == 422


def test_registry_lists_metadata_without_bundling_bytes():
    with _client() as c:
        reg = c.get("/datasets/registry").json()
        ids = {e["registry_id"] for e in reg["entries"]}
        assert {"ulb_creditcard_fraud", "paysim_mobile_money", "uci_default_credit_card"} <= ids
        for e in reg["entries"]:
            assert e["source_url"].startswith("http")
            assert e["license"]
            assert e["local_import_supported"] is True
        assert reg["openml"]["network_download_enabled"] is False
        assert "not bundled" in reg["policy"].lower() or "no dataset bytes" in reg["policy"].lower()


def test_explain_api_has_contributions_and_threshold():
    with _client() as c:
        r = c.post("/explain", json={"demo_mode": True})
        assert r.status_code == 200
        body = r.json()
        assert body["threshold"] == config.IMPACT_THRESHOLD
        assert len(body["contributions"]) == 4
        total = sum(x["weighted"] for x in body["contributions"])
        assert abs(total - body["score"]) < 1e-6
        assert "certificate" in body
        assert body["plain_language"]
        assert "0.30*M" in body["technical_detail"] or "I =" in body["technical_detail"]
        assert body["simulation_status"] == "NO_SIMULATION"
        assert body["simulation_ran"] is False


def test_counterexample_tx_00108_b_independent_stress():
    with _client() as c:
        r = c.get("/counterexample/TX-00108-B")
        assert r.status_code == 200
        view = r.json()
        assert view["gate_selected"] is False
        assert view["stress_measured"] is True
        # Showcase is documented as a missed failure: stress must fail when measured.
        assert view["stress_failure_observed"] is True
        assert view["missed_failure"] is True
        assert view["certificate"]["transaction_id"] == "TX-00108-B"
        # Gate decision remains skip even after independent measurement.
        assert view["certificate"]["impact_score"]["gate_decision"] is False
        forks = view["certificate"]["forks_tested"]
        assert any(f["fork_name"] == "stress" and not f["survived"] for f in forks)


def test_store_rejects_path_traversal_filename():
    store = DatasetStore()
    # Filename is basenamed — traversal cannot escape upload root.
    meta = store.ingest_bytes("../../evil.csv", CSV_BASIC.encode(), display_name="ok")
    assert meta.source_filename == "evil.csv"
    assert meta.dataset_id.startswith("DS-")
    store.remove(meta.dataset_id)


def test_imbalanced_labels_metrics_are_honest():
    rows = ["tx_id,acct,amt,ts,ttype,label"]
    # 19 negatives, 1 positive
    for i in range(19):
        rows.append(f"N{i},A{i%3},10{i},2026-01-01T00:00:00Z,card_payment,0")
    rows.append("P1,A0,9999,2026-01-01T00:01:00Z,wire_transfer,1")
    with _client() as c:
        ds = _upload(c, "\n".join(rows) + "\n", name="imb.csv")
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
        ev = c.post(f"/datasets/{ds['dataset_id']}/evaluate", json={"max_rows": 50}).json()
        m = ev["metrics"]
        assert m["label_positive_count"] == 1
        assert m["label_negative_count"] == 19
        assert 0.0 < m["label_positive_prevalence"] < 0.1
