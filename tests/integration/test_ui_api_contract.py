"""UI <-> API field contract: every field path the frontend renders must exist
in real API responses. Regression for the silent-undefined render bug class
(e.g. hypothetical.signals was missing and crashed runWhatIf)."""
from __future__ import annotations

import io
import re

from fastapi.testclient import TestClient

from backend.main import app
from backend.shared import config


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


def test_explain_response_fields_used_by_ui():
    with TestClient(app) as c:
        explain = c.post("/explain", json={"demo_mode": True}).json()
    for p in (
        ["certificate", "impact_score", "score"],
        ["certificate", "status"],
        ["certificate", "recommended_action"],
        ["certificate", "certificate_id"],
        ["certificate", "trace_id"],
        ["contributions"],
        ["ai_signals", "anomaly", "normalized_a"],
        ["ai_signals", "risk", "normalized_u"],
        ["ai_signals", "gate", "simulation_executed"],
        ["ai_signals", "signal_sources", "M"],
        ["ai_signals", "available"],
        ["policy_version"],
        ["technical_detail"],
    ):
        assert deep_has(explain, p), f"/explain missing {'.'.join(p)}"
    assert explain["contributions"], "contributions empty"
    for key in ("code", "name", "signal", "weight", "weighted"):
        assert key in explain["contributions"][0], f"contributions missing {key}"


def test_what_if_response_fields_used_by_ui():
    """UI reads original+hypothetical gates/signals symmetrically."""
    with TestClient(app) as c:
        wi = c.post(
            "/research/what-if",
            json={"demo_mode": True, "overrides": {"amount": 99999.0}},
        ).json()
    for p in (
        ["research_only"],
        ["changes"],
        ["original", "gate", "score"],
        ["original", "gate", "selected"],
        ["original", "signals", "A"],
        ["hypothetical", "gate", "score"],
        ["hypothetical", "gate", "selected"],
        ["hypothetical", "signals", "A"],
        ["hypothetical", "plain_language"],
        ["delta", "score"],
    ):
        assert deep_has(wi, p), f"/research/what-if missing {'.'.join(p)}"
    assert set(wi["hypothetical"]["signals"]) == {"M", "D", "A", "U"}


def test_health_and_transactions_fields_used_by_ui():
    with TestClient(app) as c:
        h = c.get("/health").json()
        txs = c.get("/transactions").json()
    for key in (
        "status",
        "runtime",
        "architecture",
        "model_backend",
        # F-036: the policy card renders from /health on first paint.
        "policy_version",
        "policy_mode",
        "policy_formula",
    ):
        assert key in h, f"/health missing {key}"
    assert h["policy_version"] == config.POLICY_VERSION
    assert h["policy_mode"] in {"interaction_aware", "frozen"}
    assert h["policy_formula"].startswith("I = ")
    # The advertised formula must match the mode actually reported (no drift).
    if h["policy_mode"] == "interaction_aware":
        assert "0.45*A" in h["policy_formula"], h["policy_formula"]
    else:
        assert "0.30*M" in h["policy_formula"], h["policy_formula"]
    assert txs and "transaction" in txs[0] and "hint" in txs[0]
    for key in ("id", "amount", "transaction_type"):
        assert key in txs[0]["transaction"], f"transaction missing {key}"


def test_counterexample_fields_used_by_ui():
    with TestClient(app) as c:
        ce = c.get("/counterexample/TX-00108-B").json()
    for key in (
        "transaction_id",
        "gate_selected",
        "missed_failure",
        "certificate",
        "kind",
        "note",
        "stress_measured",
    ):
        assert key in ce, f"/counterexample missing {key}"


def test_dataset_list_and_detail_fields_used_by_ui():
    csv = "tx_id,acct,amt,ts,ttype,label\nN0,A0,100,2026-01-01T00:00:00Z,card_payment,0\n"
    with TestClient(app) as c:
        up = c.post(
            "/datasets/upload",
            files={"file": ("c.csv", io.BytesIO(csv.encode()), "text/csv")},
        ).json()
        ds_list = c.get("/datasets").json()
        detail = c.get(f"/datasets/{up['dataset_id']}").json()
        reg = c.get("/datasets/registry").json()
    for prop in ("dataset_id", "display_name", "row_count", "mapping", "imported_at"):
        assert prop in ds_list[0], f"/datasets list missing {prop}"
    for prop in ("preview_rows", "sha256", "row_count", "display_name", "mapping"):
        assert prop in detail, f"/datasets detail missing {prop}"
    assert isinstance(reg, dict) and "entries" in reg


def test_experiments_fields_used_by_ui():
    csv = (
        "tx_id,acct,amt,ts,ttype,label\n"
        "N0,A0,100,2026-01-01T00:00:00Z,card_payment,0\n"
        "P0,A0,900,2026-01-01T00:01:00Z,wire_transfer,1\n"
    )
    with TestClient(app) as c:
        up = c.post(
            "/datasets/upload",
            files={"file": ("f.csv", io.BytesIO(csv.encode()), "text/csv")},
        ).json()
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
        c.post(f"/datasets/{up['dataset_id']}/evaluate", json={"max_rows": 10})
        exps = c.get("/experiments").json()
        detail = c.get(f"/experiments/{exps[0]['run_id']}")
    assert detail.status_code == 200
    for prop in (
        "run_id",
        "dataset_id",
        "label_semantics",
        "rows_scored",
        "simulation_rate",
        "metrics",
        "timestamp",
    ):
        assert prop in exps[0], f"/experiments item missing {prop}"


def test_app_js_fetch_paths_match_backend_routes():
    import pathlib

    js = pathlib.Path("frontend/static/app.js").read_text(encoding="utf-8")
    main_py = pathlib.Path("backend/main.py").read_text(encoding="utf-8")
    route_paths = set(re.findall(r'@app\.(?:get|post|delete|put)\(\s*"([^"]+)"', main_py))
    fetches = set(re.findall(r'fetch\(\s*["\']([^"\']+)["\']', js))
    for path in fetches:
        ok = path in route_paths
        if not ok and path.endswith("/"):
            base = path.rstrip("/")
            ok = any(rp == base or rp.startswith(base + "/{") for rp in route_paths)
        if not ok:
            for rp in route_paths:
                pat = "^" + re.sub(r"\{[^}]+\}", "[^/]+", rp) + "$"
                if re.match(pat, path):
                    ok = True
                    break
        assert ok, f"frontend fetch path has no backend route: {path}"
