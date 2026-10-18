# Final completion sprint report (2026-10-14)

**Host:** AMD64 Windows · CPython 3.12.10 · backend **numpy**  
**Git:** unavailable (no `.git` in this tree)  
**Policy:** Frozen gate unchanged · locked test not run · interaction ranking not in production

---

## Status labels

| Label | Value |
|---|---|
| **Local AMD64 validation** | **PASSED** |
| **Open-source integration & license review** | **DONE** (`docs/submission/OPEN_SOURCE_COMPONENTS.md`) |
| **Submission evidence completeness** | **PARTIAL** — local readiness bundle present; video/screenshots + organizer rules still HUMAN |
| **LinuxONE target validation** | **NOT VERIFIED** (authorized SSH window Oct 16) |
| **Overall submission readiness** | **READY FOR LINUXONE EXECUTION** — **not** `LINUXONE VERIFIED`; **not** full submission-ready |

---

## 1. Features completed

- Full FastAPI app + static dashboard (unchanged architecture)
- Lean **NumPy-only** production runtime (`requirements-numpy.txt`)
- Explicit **test dependency group** (`requirements-test.txt`: pytest + httpx)
- Smoke test: stronger HTTP path (transactions, both demo shapes, 422); `BLACKBOX_REQUIRE_HTTP=1` forces FAIL if HTTP stack missing
- `scripts/capture_evidence.py` — genuine timestamped local evidence bundle
- Frontend honesty: NO_SIMULATION / REVIEW banners; incomplete fork pairs; empty list; safer errors (from prior sprint, re-verified)

## 2. Defects fixed (this sprint)

| Defect | Fix |
|---|---|
| Packaging test still expected old smoke SKIP string | Updated `test_smoke_without_httpx_skips_http_not_fail` |
| HTTP could silently SKIP in “full” workflow | `requirements-test.txt` + runbook/`README` document full path; `BLACKBOX_REQUIRE_HTTP=1` |
| No automated local evidence bundle | `capture_evidence.py` |

## 3. Open-source components

| Component | Class | License | Why |
|---|---|---|---|
| **httpx** (test-only, pinned `>=0.27`, host 0.28.1) | test | **BSD-3-Clause** | Enables real HTTP integration tests / TestClient |
| pytest | test | MIT | Existing suite runner |
| FastAPI / Uvicorn / Pydantic / NumPy | runtime | MIT / BSD-3 / MIT / BSD-3 | Already required |
| NetworkX, new frontend stacks | **rejected/deferred** | — | See assessment + `OPEN_SOURCE_COMPONENTS.md` |

## 4. Install & demo commands

```bash
# Full local test workflow (no sklearn required for numpy backend)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-numpy.txt -r requirements-test.txt
export BLACKBOX_MODEL_BACKEND=numpy
python scripts/run_tests.py
BLACKBOX_REQUIRE_HTTP=1 python scripts/smoke_test.py
python scripts/capture_evidence.py
uvicorn backend.main:app --host 127.0.0.1 --port 8000
# demos: POST /analyze {"demo_mode":true} and TX-00300 from GET /transactions
```

## 5. Tests executed

| Environment | Command | Exit | Result |
|---|---|---|---|
| Primary | `run_tests.py` | **0** | **100 passed** |
| Primary | `smoke_test.py` | **0** | all PASS + HTTP |
| Clean full venv (numpy+test, no sklearn) | `run_tests.py` | **0** | **100 passed** |
| Clean full venv | `BLACKBOX_REQUIRE_HTTP=1 smoke_test.py` | **0** | all PASS including HTTP demos |

## 6. Evidence paths

`evidence/results/local_readiness/run_20261014T040122Z_AMD64_local/`  
(`run_tests`, `smoke_test`, `health.json`, `demo_api.json`, `simulated_api.json`, `integrity.json`, `api_summary.json`)

Demo API (numpy): **TX-DEMO-0001** NO_SIMULATION 0.413874 forks **0**; **TX-00300** SIMULATED BLOCK_OR_HOLD 0.718654 forks **6**.

## 7. Missing manual tasks

- Certificate screenshots + ≤3 min video (`EVIDENCE_CAPTURE_CHECKLIST.md`)
- Official organizer rules (`HUMAN_HANDOFF.md`)
- Interactive browser click-through (B1–B16)

## 8. LinuxONE Oct 16 procedure

`docs/LINUXONE_RUNBOOK.md` §§0b, 4a, 6b + `LINUXONE_EXECUTION_READINESS.md` §3.  
Capture: uname, OS, pip logs, tests exit codes, `/health` with real `s390x`, both demos, `capture_evidence.py` on guest.

## 9. Known limitations

- Gate underperforms anomaly-only on validation (**T1** human decision; disclosures §1)
- Demo `TX-DEMO-0001` is an honest gate blind spot (disclosures §7)
- sklearn optional; metrics differ by backend (never mix labels)
- s390x wheel builds unknown until guest run

## 10. Next concrete action

**Oct 16:** authorized operator runs runbook §6b on the s390x guest; store logs; only then use `LINUXONE VERIFIED`.  
**Parallel human:** rules + media capture for full submission package.

**STOP.** No locked test. No frozen policy change. No interaction ranking merge.
