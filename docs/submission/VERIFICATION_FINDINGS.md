# Verification Findings — BLACKBOX E2E Verification Sprint (2026-10-15)

Classification: **P0** security/data-corruption/frozen-semantics · **P1** core decision/simulation/certificate/data workflow · **P2** misleading explanation/metric/UI/ops · **P3** cosmetic.

---

## F-001 — What-If original baseline used rebuilt graph (P2) — **FIXED**

**Severity:** P2 (misleading research comparison; production gate never affected)  
**Status:** Fixed + regression test, suite green.

**Reproduction (before fix):**
```text
base D for demo transaction            = 0.8
what_if(..., {"transaction_type": "refund"})["original"]["signals"]["D"] = 0.45714285714285713
```
The original baseline D was computed against the **hypothetically rebuilt** graph, so the
"original" score/delta shown in the What-If workspace did not match the real original
decision inputs.

**Root cause:** `backend/intelligence/signals.py` reassigned `graph = build_graph(tx, ac)`
on type override, then passed the same `graph` into `explain_signals(...)` for **both**
the original and the hypothetical.

**Fix (minimal):** keep `base_graph = graph` before rebuild; original uses `base_graph`,
hypothetical uses the rebuilt `graph`.

**Reproduction (after fix):**
```text
base D = 0.8;  what_if original D = 0.8   → WHATIF_D_OK
```

**Regression test:** `tests/unit/test_ai_intelligence.py::test_what_if_type_change_keeps_original_baseline_graph`
asserts original D == true baseline D and original transaction fields unchanged.

**Production impact:** none — gate scoring path does not use `what_if`.

---

## F-002 — Probe/test-harness defects found during verification (not product defects)

These were **bugs in the verification scripts**, recorded for honesty:

| ID | Symptom | Cause | Resolution |
|---|---|---|---|
| P-a | Live upload returned FAIL | f-string interpolated **bytes** boundary → `boundary=b'----bb'` in Content-Type | Probe fixed; product upload OK |
| P-b | Registry check failed | Endpoint returns `{entries, openml, policy}` dict, probe expected list | Probe expectation corrected |
| P-c | `TestClient(app)` without context manager → 500 `State has no attribute service` | Lifespan not run (framework behavior); production uses lifespan | Probe uses `with TestClient(app)`; not a product defect |
| P-d | Stress-sample printed `None` keys | Probe looked up `rows_sampled`/`measured_stress_failures`; real keys are `sample_size`/`stress_failure_count` | Probe corrected; product keys consistent |

---

## F-003 — Observations (no action required)

| ID | Observation | Why acceptable |
|---|---|---|
| O-1 | Upload accepts `../../evil.csv` with HTTP 200 | `_safe_stem` reduces to `evil.csv` (`Path.name` + sanitizer); stored path is safe |
| O-2 | Backend source contains 3 external URLs (UCI/Kaggle) | Registry metadata citations only; never fetched (`openml_client=0`, metadata-only policy) |
| O-3 | Generic 500 on missing `app.state.service` | Only reachable if lifespan is bypassed; lifespan raises a clear RuntimeError at startup instead |
| O-4 | sklearn path unexercised | Package absent; backend honestly reports `numpy`; no parity claimed |
| O-5 | Challenge Lab live scores differ from reference run `EX-0702bb6eb4` | Reference used for **logic** regression (CM/precision/recall/FN), not score reproduction; dataset/calibration differ by design |

---

## Frozen-invariant audit (all PASS)

- Weights `0.30/0.30/0.25/0.15`, threshold `0.60`, `I>=0.60` simulate — unchanged.
- `POLICY_VERSION=1.0.0` — unchanged.
- Phase 2 hashes `3e26d127…` / `99dbe510…` — **match**.
- Locked test — not run.
- No test weakened/deleted/skipped; suite grew 119 → **120**.
- No fabricated evidence; NO_SIMULATION keeps empty forks.

---

## Summary table

| ID | Severity | Area | Status |
|---|---|---|---|
| F-001 | P2 | What-If research | **FIXED** + regression test |
| F-002 (P-a…P-d) | n/a | Verification harness | Probe corrected |
| F-003 (O-1…O-5) | n/a | Security/metrics | Accepted, documented |

**P0 count: 0. P1 count: 0. P2 count: 1 (fixed). P3 count: 0.**
