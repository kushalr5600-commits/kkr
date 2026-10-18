# BLACKBOX — Comprehensive End-to-End Verification Report

**Date:** 2026-10-15 (UTC stamp `20261015T002445Z`)  
**Sprint type:** Verification-first (defect hunt + fix, no feature work)  
**Working tree:** `C:\Users\user\AppData\Local\Temp\opencode\blackbox_work\blackbox` (no `.git`)  
**Evidence:** `evidence/results/verification/run_20261015T002445Z_AMD64_verification/`

---

## 1. Final status

| Target | Status |
|---|---|
| **AMD64 (this session)** | **PASS_WITH_LIMITATIONS** — all permitted checks passed; identified non-blocking items remain unverified (browser visual, sklearn backend, LinuxONE) |
| **LinuxONE / s390x** | **BLOCKED** — not connected to the authorized target in this session; runbook commands prepared (§13) |

Frozen gate invariants: **UNCHANGED**. Locked test: **NOT RUN**. Phase 2 hashes: **MATCH**.

---

## 2. Environment and architecture (verified at runtime, not inferred)

| Item | Value |
|---|---|
| Python | CPython 3.12.10, 64-bit, AMD64 (`platform.machine()`) |
| Runtime target reported by `/health` | `local` / `AMD64` (truthful; `linuxone` only on s390x) |
| ML backend actually exercised | **NumPy** (`model_backend=numpy`) |
| scikit-learn | **NOT installed** — sklearn path not exercised |
| Installed | numpy 2.5.2, fastapi 0.141.1, uvicorn 0.52.4, pydantic 2.13.4, httpx 0.28.1, pytest 9.1.1, jsonschema 4.26.0, pandas 3.0.5, pyarrow 25.0.1 |
| Absent | sklearn, frictionless, openml, evidently, shap, **opentelemetry** (`otel_enabled=0`, `otel_package=0`) |
| Server | uvicorn PID 6412, `http://127.0.0.1:8000` |

---

## 3. Baseline → final test results

| Check | Baseline (before edits) | Final (after fix) |
|---|---|---|
| `python scripts/run_tests.py` | **119 passed / 0 failed** (46.7 s, exit 0) | **120 passed / 0 failed** (48.7 s, exit 0) — +1 regression test |
| `BLACKBOX_REQUIRE_HTTP=1 python scripts/smoke_test.py` | (carried from prior sprint) | **exit 0**, all checks PASS including HTTP |
| Live HTTP workflow suite (`_verify_live.py`) | n/a (new) | **19/19 PASS** |
| Certificate JSON Schema validation | n/a (new) | demo + SIMULATED certs **validate** (Draft 2020-12) |
| `node --check frontend/static/app.js` | n/a | **exit 0** (syntax OK) |

Evidence files: `run_tests.txt`, `smoke_test.txt`, `live_http_checks.txt`, `certificate_schema_checks.txt`.

---

## 4. Commands actually executed

```
python scripts/run_tests.py                          # 120/120, exit 0
BLACKBOX_REQUIRE_HTTP=1 python scripts/smoke_test.py # exit 0
python _verify_probe.py        # NaN/Inf/extra-field/what-if probes
python _verify_probe2.py       # certificate schema + explain reconcile
python _verify_probe3.py       # Challenge Lab reference-CM logic + workflows
python _verify_probe4.py       # upload security probes
python _verify_probe5.py       # ML signal integrity probes
python _verify_live.py         # 19 live HTTP checks vs uvicorn :8000
node --check frontend/static/app.js
python _capture_meta.py <evidence dir>   # environment/integrity/health capture
```

Live server: `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` (detached).

---

## 5. Frozen gate integrity (§3)

| Check | Result |
|---|---|
| Weights in `config.py` | `{0.30, 0.30, 0.25, 0.15}`, sum asserted == 1 at import |
| Threshold | `0.60`, `simulate iff I >= 0.60` (`impact_gate.py:126,143`) |
| `combine()` vs hand formula | max abs error **< 1e-12** over 50 random vectors (`test_gate.py`) |
| Boundary: 0.60 selects; 0.5999999 does not | PASS (`test_threshold_routing_boundary_is_0_60_inclusive`) |
| Certificate score vs weighted signals | reconciled **1.1e-16** (TX-00300) |
| API `/analyze` vs `/explain` score | delta **0.0** |
| Frontend recompute | none — `0.30` absent from `app.js`; formula string comes from `/explain` |
| Non-finite inputs | Pydantic `finite_number` rejects `amount=inf`; `combine(NaN)` raises `GateError`; HTTP raw `NaN`/`Infinity` → **422** |
| Demo score unchanged | `0.41387409174663015` NO_SIMULATION ALLOW_NORMAL_PATH (live) |
| Showcase TX-00300 | `0.718654` SIMULATED BLOCK_OR_HOLD, 6 forks (live) |
| POLICY_VERSION | `1.0.0` |
| Phase 2 `results.json` | sha256 `3e26d127…fd2ff52` **MATCH**; README `99dbe510…f601a` **MATCH** (`integrity.json`) |

---

## 6. AI/ML signals (§4)

| Check | Result |
|---|---|
| A model output | real: RobustMahalanobis raw + empirical-CDF calibration (`fitted_on_split=calibration`) |
| A caveats | API states "not a fraud probability" (asserted) |
| U ensemble | `member_probabilities` shape ≥ 5 members; U = `clip(std/0.5, 0, 1)` — live match **1e-12** (`U=0.10220902978601719`) |
| U caveats | "not a calibrated confidence interval" (asserted) |
| Backend identity | `/health` + `versions()` + `ai_signals.model_backend` all report **numpy** truthfully |
| M/D determinism | identical across repeat calls; M saturates at 1.0 for extreme finite amounts |
| Reproducibility | same transaction → identical score/signal tuple (seeded fit) |
| sklearn backend | **not tested** (absent); no parity claim made |

---

## 7. Simulation, fragility, certificates (§5–6)

| Check | Result |
|---|---|
| Gate-selected TX-00300 | 6 forks (normal+stress × 3 scenarios), 3 fragility results, status SIMULATED |
| Demo (skipped) | `forks_tested=[]`, `fragility=[]`, status NO_SIMULATION, `LIMITATION: ` lines present |
| Scenarios | `['3x_volume','fraud_spike','service_latency']` frozen — existing `test_simulation.py` all PASS |
| Skipped sim never fabricated | PASS (empty arrays + "No deep simulation was run" evidence) |
| Certificate vs JSON Schema | **Draft 2020-12 valid** for demo + simulated certs (`jsonschema` 4.26.0) |
| Explain contributions reconcile | sum(weighted) == certificate score (**< 1e-9**) |
| AI signals tied to certificate | `ai_signals.gate.score == cert score` (**0.0** delta); `simulation_executed` follows real status |
| Malformed input | invalid JSON → **422**; unknown top-level field → **422**; partial transaction → **422** pydantic detail (no traceback) |

---

## 8. Challenge Lab reference regression (§8)

Reference: `EX-0702bb6eb4` / 13 rows / 3 positive / 0 selected / precision undefined / recall 0.

| Logic | Result |
|---|---|
| Confusion matrix = gate selection vs external label | PASS (`confusion_note` in metrics) |
| FN = skipped ∩ label-positive | PASS (reference vector: fn=3, tn=10, tp=0) |
| Precision `None` (not 0.0) when nothing selected | **PASS** — unit check + live run (`precision=None`) |
| Recall 0.0 for 0/3 | **PASS** (reference vector) |
| Live workflow reproduced the same *shape*: 13 rows, 3 positives, 0 selected, recall 0.0, precision None, fn findings | PASS (new dataset, own run IDs `EX-…`) |
| Distinct run IDs across evaluations | PASS (`EX-718d603f8a` ≠ `EX-33e603c31a`) |
| Stress sample separate from labels | PASS (`stress_sample.stress_failure_count` own field; labels untouched: positive_count still 3; note present) |
| FN analysis research-only flags | PASS (`research_only=true`, `never_changes_production_gate=true`) |
| Dataset SHA preserved | PASS (evaluate sha == upload sha) |
| Small-sample warning | PASS (`sample_size_limitation` string) |

Scores were **not** forced to match the historical run — different dataset/calibration → explained as expected (regression reference is for *logic*, not model scores).

---

## 9. What-If & Experiments (§9)

| Check | Result |
|---|---|
| Allowed overrides only | amount / transaction_type / historical_avg/std |
| Unknown key → HTTP 422 | PASS (live) |
| NaN / Infinity (raw JSON) → 422 | PASS (`must be a finite number > 0`) |
| Original transaction not mutated | PASS (unit + live) |
| `research_only: true` + disclaimer | PASS |
| Deterministic re-run | PASS (identical inputs → identical delta) |
| `/experiments` ring | PASS — unique run IDs, in-memory, no overwrite of evidence files |
| Counterexample showcase | PASS: `TX-00108-B` `gate_selected=false`, `missed_failure=true`, `stress_measured=true` (forced research measurement, gate unchanged) |
| Unknown counterexample id → 404 | PASS |

**Defect found & fixed (P2):** `what_if` with a `transaction_type` override rebuilt the dependency graph and then reused it for the **original** baseline, corrupting original D (0.457 instead of 0.8) and the delta. Fixed by keeping `base_graph` separate. Regression test: `test_what_if_type_change_keeps_original_baseline_graph`. See `VERIFICATION_FINDINGS.md` F-001.

---

## 10. Dataset Studio (§7)

| Check | Result |
|---|---|
| CSV upload → map → evaluate (live) | PASS (19/19 suite) |
| Quoted/missing/malformed rows | existing `test_dataset_studio.py` PASS (8 tests) |
| Parquet (pandas+pyarrow present) | exercised by existing tests — PASS |
| Size limit (5 MiB) | oversize upload → **422** |
| Row-count limit | enforced by config; tests PASS |
| Unsupported format `.exe` | **422** |
| Filename traversal `../../evil.csv` | accepted only after `_safe_stem` → stored as `evil.csv` (Path.name + sanitizer) — no path escape |
| Dataset-id traversal `..%2F..%2Fetc` | **404** |
| Empty mapping | **422** |
| No code execution | CSV/Parquet parsed to plain dicts only |
| Fingerprint | sha256 returned at upload and echoed in evaluate |
| Registry | metadata-only, 3 entries, `openml=0` |

---

## 11. Frontend & API integration (§10)

**Performed:** HTTP/static verification. **Not performed:** real-browser visual/click-through (no browser automation tool installed; not added per scope rules).

| Check | Result |
|---|---|
| Dashboard HTML | 200, contains `BREAK MY DECISION`, logo asset reference |
| `GET /static/assets/logo.svg` | 200 |
| JS syntax | `node --check` exit 0 |
| Contract tests (9) | PASS — certificate fields, honesty strings, nav, brand assets |
| No hardcoded demo scores | PASS (grep for `0.41/0.71` etc. → none) |
| Color semantics | green only on executed/simulated; amber on skip (contract test) |
| Live workflow parity | 19/19 scripted API checks (the same endpoints the UI calls) |

---

## 12. Security & operations (§11)

| Check | Result |
|---|---|
| Strict schemas | `extra="forbid"` on Analyze/Mapping/Evaluate/WhatIf requests — unknown field 422 |
| Upload limits | 5 MiB + row cap + suffix allowlist — 422s observed |
| Temp/safe storage | files under `backend/datasets/uploads/` with sanitized stems |
| Secrets scan | 2 hits, both `contextvars` token (false positives) — **no credentials** |
| Absolute dev paths in code | **0 hits** |
| External URLs in backend | 3, all registry **metadata citations** (UCI/Kaggle pages) — never fetched at runtime (`openml=0`) |
| OTel disabled | `otel_enabled=0`, no-op tracing module |
| Health accuracy | truthful runtime/arch/backend/otel |
| Startup failure | lifespan raises explicit RuntimeError with remediation (read in `main.py`) |
| Error responses | structured `{error_type, error_message, trace_id}` — no stack traces observed |

---

## 13. IBM Z / LinuxONE

`platform.machine() == AMD64` — **not** on s390x. Target validation remains **BLOCKED** pending the authorized Oct 16 window. Prepared operator commands (from runbook):

```bash
uname -m                                   # must print s390x
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-numpy.txt -r requirements-test.txt
python scripts/run_tests.py                # record pass/fail counts
BLACKBOX_REQUIRE_HTTP=1 python scripts/smoke_test.py
BLACKBOX_MODEL_BACKEND=numpy python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
curl -s localhost:8000/health              # must report architecture=s390x, truthful backend
```

Do not install/upgrade packages on the target without authorization. Keep target evidence separate.

---

## 14. Files changed (this sprint)

| File | Change |
|---|---|
| `backend/intelligence/signals.py` | **P2 fix**: `base_graph` kept for original baseline when type overridden |
| `tests/unit/test_ai_intelligence.py` | +`test_what_if_type_change_keeps_original_baseline_graph` |
| `evidence/results/verification/run_20261015T002445Z_AMD64_verification/` | NEW evidence bundle (tests, smoke, live checks, schema checks, environment, integrity, health) |
| `docs/submission/{COMPREHENSIVE_VERIFICATION_REPORT,VERIFICATION_FINDINGS,VERIFICATION_CHECKLIST}.md` | NEW |
| `docs/DEBUG_LOG.md` | appended verification entry |

No frozen config, weights, threshold, goldens, or historical evidence were modified.

---

## 15. Checks not run (and why)

| Check | Reason |
|---|---|
| Locked test | **Forbidden by policy** |
| LinuxONE/s390x | Not on authorized target (window Oct 16) |
| scikit-learn backend | Package absent; no install without authorization |
| Browser visual / video | No browser automation tool present; not installed per scope |
| OpenML network import | Network + disabled by design (metadata-only) |
| OTel-enabled path | Package absent; no-op path verified only |
| Docker packaging | BLOCKED (historical) |

---

## 16. Outstanding blockers (unchanged)

1. LinuxONE/s390x authorized run (Oct 16) — human/operator.
2. Demo video + certificate screenshots + organizer rules — HUMAN (`HUMAN_HANDOFF.md`).
3. T1 gate-performance decision — human, open.

---

**STOP.** Verification and reporting scope ends here; no feature work begun.
