# LinuxONE execution readiness (as of 2026-10-14, integration sprint)

**LinuxONE / s390x execution: NOT VERIFIED — pending authorized Oct 16 run.**  
**Local AMD64 validation: PASSED** (see evidence bundle below).  
**Overall: LOCAL PROJECT COMPLETE — READY FOR TARGET VALIDATION** (local checks genuine; target still pending).

---

## 1. Checks completed (final sprint, 2026-10-14)

| Check | Result | Exit |
|---|---|---|
| Primary env `scripts/run_tests.py` | **104 passed, 0 failed** | **0** |
| Primary env `scripts/smoke_test.py` (httpx present) | all PASS **including HTTP + policy_version + unknown-key 422** | **0** |
| `scripts/export_certificate_schema.py` | wrote `schemas/decision_certificate.v1.schema.json` | **0** |
| Clean venv: `requirements-numpy.txt` + `requirements-test.txt` | install OK | **0** |
| Clean venv + `BLACKBOX_REQUIRE_HTTP=1` full suite | **100 passed** (pre-integration baseline) | **0** |
| Clean venv smoke with HTTP (demo + TX-00300 + 422 + transactions) | all PASS | **0** |
| Evidence capture `scripts/capture_evidence.py` | bundle written, overall **0** | **0** |
| Frozen weights / threshold | **unchanged** | — |
| Phase 2 SHA-256 | **unchanged** | — |
| Interaction ranking in `backend/` | **0 hits** | — |

### Evidence bundle (genuine, AMD64)

`evidence/results/local_readiness/run_20261014T040122Z_AMD64_local/`

| File | Contents |
|---|---|
| `environment.json` | machine AMD64, Python 3.12.10, numpy, httpx |
| `run_tests.txt` / `.exit` | full suite log, exit 0 |
| `smoke_test.txt` / `.exit` | smoke log, exit 0 |
| `health.json` | `/health` real JSON |
| `demo_api.json` / `simulated_api.json` | full DecisionCertificates |
| `api_summary.json` | demos: 0.413874 NO_SIMULATION forks 0; TX-00300 0.718654 SIMULATED forks 6 |
| `integrity.json` | weights, threshold, Phase 2 hashes, interaction=0 |
| `README.md` | summary — labeled **local host only** |

### Clean full-test venv (Task: reliable HTTP tests)

| Item | Value |
|---|---|
| Path | `%TEMP%\opencode\blackbox_full_test_venv` |
| Install | `requirements-numpy.txt` + `requirements-test.txt` (**no sklearn**) |
| Backend | **numpy** |
| HTTP | **PASS** (not SKIP) with `BLACKBOX_REQUIRE_HTTP=1` |

**NumPy-only runtime without test packages:** still verified earlier
(`blackbox_numpy_venv` — HTTP SKIP by design; use `requirements-test.txt` for full HTTP).

---

## 2. Dependency groups (final)

| File | Use |
|---|---|
| `requirements-numpy.txt` | Production runtime without sklearn |
| `requirements-test.txt` | **pytest + httpx** (test-only) |
| `requirements-dev.txt` | Full stack for AMD64/CI |
| `requirements.txt` | Runtime including sklearn |

---

## 3. Exact Oct 16 first commands (authorized s390x guest only)

```bash
uname -m | tee /tmp/bb_uname.txt          # MUST be s390x or STOP
cat /etc/os-release | tee /tmp/bb_osrelease.txt
python3 --version | tee /tmp/bb_python.txt
python3 -m pip --version | tee /tmp/bb_pip.txt
cd <repo>
python3 scripts/diagnose_env.py | tee /tmp/bb_diagnose_pre.txt
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-numpy.txt | tee /tmp/bb_pip_numpy.log
pip install -r requirements-test.txt | tee /tmp/bb_pip_test.log
export BLACKBOX_MODEL_BACKEND=numpy
export BLACKBOX_REQUIRE_HTTP=1
python3 scripts/run_tests.py | tee /tmp/bb_run_tests.log; echo exit=$?
python3 scripts/smoke_test.py | tee /tmp/bb_smoke.log; echo exit=$?
python3 scripts/export_certificate_schema.py | tee /tmp/bb_export_schema.log
uvicorn backend.main:app --host 127.0.0.1 --port 8000 | tee /tmp/bb_uvicorn.log &
curl -s http://127.0.0.1:8000/health | tee /tmp/bb_health.json
# optional only: pip install -r requirements-observability.txt && export BLACKBOX_OTEL=1
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/dashboard
python3 scripts/capture_evidence.py | tee /tmp/bb_capture.log
```

If `uname` is not `s390x`, stop. Evidence under
`evidence/results/local_readiness/` on the guest is still labeled by machine
string; only mark LinuxONE when `architecture=s390x` and `runtime=linuxone`.

---

## 4. Remaining target-specific unknowns

| Unknown | Status |
|---|---|
| s390x wheels (numpy, pydantic-core, fastapi) | **UNVERIFIED** |
| scikit-learn on s390x | **UNVERIFIED** (numpy fallback ready) |
| Real guest `/health` s390x | **PENDING SSH Oct 16** |
| Interactive browser video/screenshots | **HUMAN** (AMD64 Edge headless only so far) |

---

## 5. Status labels

| Label | Value |
|---|---|
| Local AMD64 validation | **PASSED** |
| Open-source integration + license review | **DONE** (`OPEN_SOURCE_COMPONENTS.md`; httpx test-only BSD-3) |
| Submission evidence completeness | **PARTIAL** — local readiness bundle present; media + organizer rules still HUMAN |
| **LinuxONE target validation** | **NOT VERIFIED** (pending Oct 16) |
| **Overall** | **READY FOR LINUXONE EXECUTION** — not `LINUXONE VERIFIED`; not full submission-ready until media/rules |

**No** gate policy, schema, dataset, locked test, or interaction-ranking changes.

