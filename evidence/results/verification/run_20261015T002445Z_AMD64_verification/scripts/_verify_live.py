from __future__ import annotations

import io
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def get(path: str):
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except Exception:  # noqa: BLE001
            return e.code, {"raw": body[:200].decode("utf-8", "replace")}


def post(path: str, obj=None, raw: bytes | None = None, ctype="application/json"):
    data = raw if raw is not None else json.dumps(obj).encode()
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": ctype}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except Exception:  # noqa: BLE001
            return e.code, {"raw": body[:200].decode("utf-8", "replace")}


checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, ok, detail))
    print(("PASS" if ok else "FAIL"), name, detail)


# 1. health
st, h = get("/health")
check("health", st == 200 and h.get("model_backend") == "numpy" and h.get("architecture") == "AMD64", f"{h.get('runtime')}/{h.get('architecture')}/{h.get('model_backend')}/otel={h.get('otel_enabled')}")

# 2. dashboard + static assets
st, _ = get("/dashboard") if False else (0, None)
with urllib.request.urlopen(BASE + "/dashboard", timeout=10) as r:
    html = r.read().decode()
check("dashboard", "BREAK MY DECISION" in html and 'src="/static/assets/logo.svg"' in html)
with urllib.request.urlopen(BASE + "/static/assets/logo.svg", timeout=10) as r:
    check("logo_asset", r.status == 200)

# 3. transactions
st, txs = get("/transactions")
ids = [t["transaction"]["id"] for t in txs]
check("transactions", st == 200 and len(ids) >= 5, ",".join(ids))

# 4. analyze demo
st, demo = post("/analyze", {"demo_mode": True})
check(
    "analyze_demo",
    st == 200
    and demo["status"] == "NO_SIMULATION"
    and demo["forks_tested"] == []
    and any(l.startswith("LIMITATION: ") for l in demo["evidence"]),
    demo["status"],
)

# 5. analyze simulated
tx300 = next(t["transaction"] for t in txs if t["transaction"]["id"] == "TX-00300")
st, sim = post("/analyze", {"transaction": tx300})
check(
    "analyze_sim",
    st == 200
    and sim["status"] == "SIMULATED"
    and len(sim["forks_tested"]) == 6
    and len(sim["fragility"]) == 3
    and sim["impact_score"]["gate_decision"] is True,
    f"{sim['status']} score={sim['impact_score']['score']}",
)

# 6. explain
st, ex = post("/explain", {"transaction": tx300})
contrib_sum = sum(c["weighted"] for c in ex["contributions"])
ai = ex.get("ai_signals", {})
check(
    "explain",
    st == 200
    and abs(contrib_sum - ex["certificate"]["impact_score"]["score"]) < 1e-9
    and abs(ai.get("gate", {}).get("score", -1) - ex["certificate"]["impact_score"]["score"]) < 1e-9
    and ai.get("gate", {}).get("simulation_executed") is True,
    f"sum_ok ai_backend={ai.get('model_backend')}",
)

# 7. what-if
st, wi = post("/research/what-if", {"demo_mode": True, "overrides": {"amount": 50000.0}})
check("what_if", st == 200 and wi.get("research_only") is True and wi["original"]["transaction"]["amount"] != 50000.0, f"dScore={wi.get('delta', {}).get('score')}")
st, wi_bad = post("/research/what-if", {"demo_mode": True, "overrides": {"bogus": 1}})
check("what_if_unknown_key_422", st == 422, str(st))

# 8. counterexample
st, ce = get("/counterexample/TX-00108-B")
check("counterexample", st == 200 and ce.get("missed_failure") is True and ce.get("gate_selected") is False, f"measured={ce.get('stress_measured')}")
st, ce_bad = get("/counterexample/UNKNOWN")
check("counterexample_unknown_404", st == 404, str(st))

# 9. dataset studio full workflow
csv = "tx_id,acct,amt,ts,ttype,label\n" + "\n".join(
    [f"N{i},A{i % 2},10{i},2026-01-01T00:00:00Z,card_payment,0" for i in range(10)]
    + [f"P{i},A0,50{i},2026-01-01T00:01:00Z,wire_transfer,1" for i in range(3)]
) + "\n"
boundary = "----bb"
body = (
    ("--" + boundary + "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"verify.csv\"\r\nContent-Type: text/csv\r\n\r\n").encode()
    + csv.encode()
    + ("\r\n--" + boundary + "--\r\n").encode()
)
st, ds = post("/datasets/upload", raw=body, ctype=f"multipart/form-data; boundary={boundary}")
check("upload", st == 200 and ds.get("dataset_id", "").startswith("DS-"), ds.get("dataset_id", ""))
did = ds.get("dataset_id", "")
st, mp = post(
    f"/datasets/{did}/map",
    {"mapping": {"id": "tx_id", "account_id": "acct", "amount": "amt", "timestamp": "ts", "transaction_type": "ttype", "label": "label"}, "label_semantics": "fraud"},
)
check("map", st == 200, str(st))
st, ev = post(f"/datasets/{did}/evaluate", {"max_rows": 50})
prec = ev.get("metrics", {}).get("selection_precision_positive_label")
fn = ev.get("false_negative_analysis", {})
check(
    "evaluate",
    st == 200
    and ev.get("metrics", {}).get("label_positive_count") == 3
    and (prec is None or isinstance(prec, float))
    and fn.get("research_only") is True
    and ev.get("dataset_sha256") == ds.get("sha256"),
    f"recall={ev.get('metrics', {}).get('selection_recall_positive_label')} precision={prec} fn={fn.get('finding_count')}",
)
st, _ = post(f"/datasets/{did}/evaluate", {"max_rows": 50})
check("evaluate_new_run_id", st == 200)
st, exps = get("/experiments")
ids = [e.get("run_id") for e in exps]
check("experiments_ring", st == 200 and len(ids) >= 2 and len(set(ids)) == len(ids), f"n={len(ids)}")

# 10. malformed analyze controlled error
st, err = post("/analyze", raw=b"not json")
check("malformed_analyze_422", st == 422, str(st))

# 11. registry
st, reg = get("/datasets/registry")
check("registry", st == 200 and isinstance(reg, dict) and len(reg.get("entries", [])) >= 3, f"n={len(reg.get('entries', []))}")

# 12. schema export file exists
import pathlib

check("schema_file", pathlib.Path("schemas/decision_certificate.v1.schema.json").is_file())

failed = [c for c in checks if not c[1]]
print(f"\nRESULT {len(checks) - len(failed)}/{len(checks)} passed")
if failed:
    raise SystemExit(1)
