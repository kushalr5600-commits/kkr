# LinuxONE / s390x Validation Report

**Date:** 2026-10-16 · **Target:** IBM Z Datathon Community Cloud, s390x guest
**Status:** **LINUXONE_PASS** — `overall_status: PASS`, `runtime_label: linuxone`

---

## 1. Target environment

| Field | Value |
|---|---|
| IP | 148.100.78.185 |
| SSH user | linux1 |
| Image | Ubuntu24.04-Datathon |
| OS | Ubuntu 24.04.5 LTS |
| Kernel | Linux 6.8.0-147-generic-s390x |
| Architecture | **s390x** (confirmed via `uname -m`) |
| Python | 3.12.3 |
| Flavor | AI_LAB (3 vCPU / 8192 MB RAM / 50 GB disk) |
| Model backend | numpy (documented fallback; sklearn not installed) |

## 2. Evidence bundle

`evidence/results/validation_runs/run_20261016T113630Z_s390x_numpy/`

| File | Contents |
|---|---|
| `validation_report.json` | Full step-by-step results with exit codes, durations, stdout/stderr tails |
| `README.md` | Human-readable summary |

## 3. Validation steps and results

| Step | Command | Result |
|---|---|---|
| Environment diagnostics | `diagnose_env.py` | PASS — `runtime_label=linuxone`, `process_is_s390x=true` |
| Dataset integrity | SHA-256 vs manifest | PASS — `546f57ce…d5c3` matches |
| Test suite | `scripts/run_tests.py` | PASS — **133 passed, 0 failed** (24.4s) |
| Pytest | `python -m pytest -q` | PASS — 133 passed, 1 warning (25.3s) |
| Smoke test | `scripts/smoke_test.py` | PASS — all checks including HTTP |
| Live HTTP | uvicorn + `/health` + `/analyze` | PASS — `runtime:linuxone`, `architecture:s390x` |
| Schema export | `export_certificate_schema.py` | PASS — exit 0 |
| Gate trace | `trace_gate.py` | PASS — score 0.413874, matches numpy baseline |
| One-shot runner | `validate_runtime.py --include-optional` | **PASS** — `overall_status: PASS` |

## 4. Key `/health` response (s390x)

```json
{
  "status": "ok",
  "runtime": "linuxone",
  "architecture": "s390x",
  "version": "0.1.0-prebuild",
  "model_backend": "numpy",
  "gate_threshold": "0.60",
  "python": "3.12.3"
}
```

## 5. Demo transaction (numpy backend, s390x)

| Field | Value |
|---|---|
| Transaction | TX-DEMO-0001 |
| Status | NO_SIMULATION |
| Action | ALLOW_NORMAL_PATH |
| Score | 0.413874 |
| Forks | 0 |
| Signals | M=0.1323 D=0.8000 A=0.4754 U=0.1022 |

Matches the AMD64 numpy baseline exactly.

## 6. Dependencies installed on target

| Package | Version | Notes |
|---|---|---|
| numpy | 2.5.4 | Built from source (no s390x wheel) |
| fastapi | 0.143.2 | |
| uvicorn | 0.54.0 | |
| pydantic | 2.14.1 | |
| pydantic-core | 2.50.1 | |
| starlette | 1.8.0 | |
| pytest | 9.1.1 | test-only |
| httpx | 0.28.1 | test-only |
| python-multipart | 0.0.32 | missing from requirements-numpy.txt |

System packages: `python3.12-venv`, `build-essential`, `python3.12-dev`, `nodejs`

## 7. Defects / gaps found

| ID | Severity | Description |
|---|---|---|
| F-006 | P3 | `requirements-numpy.txt` missing `python-multipart` (FastAPI form/file upload). Installed manually. |
| F-007 | P3 | `test_certificate_reproducibility.py` `_SHOWCASE_IDS` included `TX-00154` (sklearn-only) but not `TX-00300` (numpy-only). Fixed: added `TX-00300`. |
| F-008 | P3 | Runbook §4a assumes `python3-venv` preinstalled; Ubuntu 24.04 requires `apt install python3.12-venv` first. Also needs `build-essential` + `python3.12-dev` for numpy source build. |
| F-009 | P3 | Runbook §2 uses `git clone`; working tree has no `.git`. Code transferred via tar.gz archive. |

## 8. Integrity

- Frozen Phase 2 `results.json` SHA-256: `3e26d127…2ff52` — **unchanged**
- Weights: `{magnitude:0.30, dependency:0.30, anomaly:0.25, uncertainty:0.15}` — **unchanged**
- Threshold: `0.60` — **unchanged**
- Dataset SHA-256: `546f57ce…d5c3` — **matches manifest**
- `POLICY_VERSION`: `1.0.0` — **unchanged**

## 9. Not tested / open items

| Item | Status |
|---|---|
| scikit-learn backend on s390x | NOT TESTED (numpy path used per runbook §6b) |
| T1 gate-weight decision | OPEN (human owner) |
| Locked test split | UNUSED (by design) |
| Browser interactive click-through | NOT VERIFIED (human-only) |
| Docker | BLOCKED (CLI not available) |

## 10. Verdict

**LINUXONE_PASS.** The project runs correctly on real s390x hardware with the numpy backend. All 133 tests pass, all smoke checks pass, live HTTP works, and the demo transaction produces the expected result. The evidence bundle is complete and stored in `evidence/results/validation_runs/run_20261016T113630Z_s390x_numpy/`.

---

# Update 2026-10-16 (post-activation, scikit-learn) �?" LINUXONE_PASS

The interaction-aware gate was activated later on 2026-10-16 under explicit human
authorization (`docs/submission/DISCLOSURES.md` §2). The target was revalidated
with the updated tree and the scikit-learn backend built on the guest.

## Run summary

| Item | Result |
|---|---|
| Evidence bundle | `evidence/results/validation_runs/run_20261016T185139Z_s390x_sklearn/` |
| `overall_status` | **PASS** |
| `runtime_label` / arch | `linuxone` / `s390x` (`linuxone_verified=true`) |
| `model_backend` | **sklearn** (IsolationForest A, RandomForest-disagreement U; guest-built 1.9.1) |
| Full suite | **141 passed, 0 failed** (`scripts/run_tests.py`, 26.9s) |
| pytest + smoke + live HTTP | **PASS** (demo `NO_SIMULATION` through real uvicorn HTTP) |
| Dataset SHA-256 | matches frozen `546f57ce…d5c3` |
| Showcase scores | **identical to AMD64/sklearn**: TX-DEMO-0001 `0.516452` NO_SIMULATION; TX-00154 `0.661589` SIMULATED/BLOCK (fails stress); TX-01623 `0.600031` SIMULATED/REVIEW (survives); TX-00001 `0.232720` skipped; TX-00108-B `0.457158` skipped (missed failure) |
| Certificate `policy_formula` | `I=0.45*A+0.30*W+0.15*D+0.10*L;threshold=0.60;mode=interaction_aware` |

## Cross-arch claim

Interaction-aware gate scores are **reproducible between AMD64 and s390x**
(same sklearn 1.9.1, same dataset SHA, same seeds). This supersedes §9's
"scikit-learn backend on s390x NOT TESTED" row.

## Remaining open (unchanged)

Browser interactive click-through (human-only) �?" Docker BLOCKED (CLI) �?"
locked test split UNUSED (by design) �?" organizer compliance still HUMAN REQUIRED.

# Update 2026-10-17 (hybrid + LLM + container) � partial: suite VERIFIED, container REBUILD pending

## Run summary
- **Suite on target:** `scripts/run_tests.py` and `python -m pytest tests -q`
  both report **155 passed, 0 failed** on the s390x guest (Ubuntu 24.04.5,
  project `.venv`, sklearn 1.9.1 + xgboost 3.4.1 source-built, 43.1s) with the
  full 2026-10-17 tree (hybrid risk ensemble + LLM narrative module). This
  supersedes the 141/141 pre-LLM target numbers for suite counting.
- **xgboost on target:** built from the PyPI sdist inside the guest venv
  (cmake 3.28.3 present); `import xgboost` OK, `hybrid_risk=on` in
  `versions()`.
- **Gate scores:** unchanged vs 2026-10-16 (interaction formula has no U term;
  regression test on both hosts).
- **IBM Granite:** model `ibm-granite/granite-3.0-1b-a400m-instruct`
  **DOWNLOADED** into the Jupyter container cache
  (`~/shared/hf_cache`, `DOWNLOAD_OK` in `~/shared/granite_download.log`).
- **Container:** first s390x image build **SUCCEEDED** (Docker 29.8.0,
  `BASE_IMAGE=s390x/python:3.11-bookworm`, `INSTALL_BUILD_TOOLS=1`;
  image `blackbox:latest`, 2.04 GB). Container **exited(1)** on startup:
  `RuntimeError: Form data requires "python-multipart"` � pre-existing
  omission from `requirements.txt` (same class as F-006 for the numpy file).
  Fix added; rebuild launched (`~/docker_build3.log`). Container `/health`
  verification will be appended when the rebuild finishes.

## Cross-arch claim
Unchanged and re-exercised: interaction-aware gate showcase scores are
byte-identical AMD64 <-> s390x. Hybrid U values are each machine's real
output (see disclosure D-5 in `docs/DEBUG_LOG.md`).

## Remaining open
- Container `/health` + `/transactions` on the rebuilt image (in progress).
- Live LLM narrate via `scripts/llm_service.py` inside the Jupyter container
  (model cached; service start + one narrated certificate pending).
- `validate_runtime.py --include-optional` re-run on the target with the
  final tree (planned after container green).

# Update 2026-10-17b (container + LLM live) � LINUXONE_PASS_FULL_STACK

## Container (rubric: demonstrate containerized deployment)
- Rebuilt image after adding `python-multipart` to `requirements.txt`
  (`~/docker_build3.log`): **DONE**, `blackbox:latest` (s390x).
- `docker run -d --name blackbox -p 8001:8000 blackbox` ->
  `GET /health` on the guest returns
  `{"status":"ok","runtime":"linuxone","architecture":"s390x","model_backend":"sklearn",...}`
  and docker reports the container **(healthy)**. Saved:
  `evidence/capture/container_health_s390x.json` (and mirrored on the guest).

## IBM Granite LLM narrative (rubric: pair predictive models with LLM reasoning)
- Service container `granite-svc` (`--network host`, Jupyter s390x image,
  model cached in `~/shared/hf_cache`):
  `/health` -> `{"status":"ok","loaded":true,
  "model":"ibm-granite/granite-3.0-1b-a400m-instruct"}`.
- App chain (guest venv uvicorn + `BLACKBOX_LLM_URL=http://127.0.0.1:38899/narrate`):
  `POST /explain` -> `llm_narrative.available=true`, `latency_ms=57209`,
  narrative text grounded on the real certificate (amount, hybrid_risk,
  score 0.516452, NO_SIMULATION); certificate score byte-unchanged.
  Saved: `evidence/capture/explain_llm_chain_s390x.json`.
- Defect fixed en route: `LLM_TIMEOUT_S` 20 -> 120 (CPU generation 48-57s);
  the earlier honest TimeoutError degradation is itself evidence of
  advisory isolation (DEBUG_LOG 2026-10-17b entry).

## Verdict
LINUXONE_PASS_FULL_STACK: suite 155/155, validate_runtime PASS, container
healthy, Granite narrative live, cross-arch gate scores unchanged.
Remaining human-only: browser click-through + demo video + compliance.
