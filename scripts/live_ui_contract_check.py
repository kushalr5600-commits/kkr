import json
import sys

sys.path.insert(0, ".")

import urllib.request

BASE = "http://127.0.0.1:8000"

with urllib.request.urlopen(BASE + "/health", timeout=10) as r:
    h = json.loads(r.read())
print("health:", h.get("status"), h.get("runtime"), h.get("model_backend"))

with urllib.request.urlopen(BASE + "/static/app.js", timeout=10) as r:
    js = r.read().decode("utf-8")
checks = {
    "served_defense_numOrUnknown": "numOrUnknown" in js,
    "served_no_bare_signals_chain": "res.d.hypothetical.signals.A" not in js,
    "served_init_bound_wi": "runWhatIf(selected)" in js,
    "served_no_tx_closure": "runWhatIf(tx); }" not in js,
}
print("app.js:", json.dumps(checks))

req = urllib.request.Request(
    BASE + "/research/what-if",
    data=json.dumps({"demo_mode": True, "overrides": {"amount": 99999.0}}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=20) as r:
    wi = json.loads(r.read())
sig = wi.get("hypothetical", {}).get("signals", {})
print("live what-if hypothetical.signals:", sig)
assert all(checks.values()), checks
assert set(sig) == {"M", "D", "A", "U"}, sig
assert 0.0 <= sig["A"] <= 1.0, sig
print("LIVE_VERIFICATION: PASS")
