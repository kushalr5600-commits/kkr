# STATUS - read this first

Snapshot at handoff. Update it at the end of every session.

Legend: **VERIFIED** = recorded command output on the stated environment Â·
**NOT VERIFIED** = not executed or not demonstrated Â· **BLOCKED** = attempted
but prevented by a documented environment/dependency issue Â·
**KNOWN ISSUE** = observed defect or limitation that remains unresolved.

**Host of this snapshot:** AMD64 Windows, CPython 3.12.10, scikit-learn 1.9.1
**installed** (NumPy model backend still available as fallback). This is **not**
LinuxONE. AMD64 results do **not** establish LinuxONE results.

**LinuxONE / s390x: VERIFIED 2026-10-16 (twice).** Real s390x guest (Ubuntu
24.04.5, Python 3.12.3). Pre-activation (numpy): 133/133,
`evidence/results/validation_runs/run_20261016T113630Z_s390x_numpy/` (+ re-run
`...132444Z...`). **Post-activation (sklearn): 141/141 + smoke + live HTTP PASS,
`runtime_label=linuxone`, `model_backend=sklearn` â€”
`evidence/results/validation_runs/run_20261016T185139Z_s390x_sklearn/`.**
Showcase scores on s390x are **identical** to AMD64/sklearn
(demo 0.516452, TX-00154 0.661589, TX-01623 0.600031, TX-00001 0.232720,
TX-00108-B 0.457158) â€” cross-arch reproducibility of the active gate.

**Post-validation cleanup (2026-10-16):** F-006 (`python-multipart` added to
`requirements-numpy.txt`), F-007 (showcase test fixed â€” already applied),
F-008 (runbook Â§4a documents `python3-venv` prerequisite),
F-009 (runbook Â§2 documents tarball workflow). 133/133 re-verified on AMD64.

**Interaction-aware gate activation (2026-10-16, human-authorized â€” VERIFIED on AMD64):**
`config.INTERACTION_AWARE_ENABLED = True` and the module is now wired into the
production path: `ImpactGate.score_batch`, `explain_signals`, `/explain`
explainer contributions, what-if, and `runtime.policy_formula`
(`;mode=interaction_aware`). Active formula:
`I = 0.45*A + 0.30*W + 0.15*D + 0.10*L`, threshold unchanged at 0.60.
W/L are dataset-context features from `extract_features` (research formula,
batch-size invariant â€” regression test in `tests/unit/test_interaction_aware.py`).
Full suite **141/141 PASS** (scikit-learn, 2026-10-16, 111s).
Showcase ids (dynamic slots, hints computed): TX-DEMO-0001 0.516452 NO_SIMULATION,
TX-00154 0.661589 SIMULATED/BLOCK (fails stress), TX-01623 0.600031 SIMULATED/REVIEW
(survives stress), TX-00001 0.232720 skipped, TX-00108-B 0.457158 skipped
(missed-failure counterexample) â€” all five outcome slots preserved.
Frozen integrity: `IMPACT_WEIGHTS`/`IMPACT_THRESHOLD`/`SCENARIOS`/`POLICY_VERSION`/
dataset SHA byte-identical (contract tests). **config.py bytes changed** by the
authorized activation â€” SHA-256 now `f4b186a0â€¦d31c` (older frozen-list value
`433cd998â€¦` predates activation). `combine()` retained as frozen reference. Target revalidation **DONE**
(141/141 + live HTTP on s390x/sklearn, `run_20261016T185139Z_s390x_sklearn/`;
see disclosures D-1 in `docs/DEBUG_LOG.md`).

**Hybrid risk ensemble + LLM narrative + container deployment (2026-10-17, human-authorized "start" â€” VERIFIED on AMD64):**
Rubric-driven upgrades (2+ AI frameworks, LLM pairing, containerized deployment):
1. **Hybrid risk ensemble (sklearn + XGBoost):** `config.UNCERTAINTY_HYBRID_MODEL`,
   `HYBRID_RISK_ENV=BLACKBOX_HYBRID_RISK` (auto|on|off, default auto). When the
   sklearn backend is active and xgboost imports, U = std across the 100 RF trees
   PLUS 8 XGBoost bootstrap models (`RISK_XGB_*` hyper-parameters in config).
   `versions()` reports `hybrid_risk=on/off` and
   `risk_model="HybridTreeEnsemble (RF trees + XGBoost models) [scikit-learn-1.9.1 + xgboost-3.4.1]"`.
   **Gate scores are UNchanged** (interaction-aware formula has no U term â€”
   regression test `test_gate_scores_ignore_hybrid_in_interaction_mode`);
   showcase scores stay 0.516452/0.661589/0.600031/0.232720/0.457158.
   Numpy backend never touches xgboost. xgboost 3.4.1 installed AMD64 (wheel)
   and s390x (source build, guest venv).
2. **LLM narrative (advisory, IBM Granite):** `backend/intelligence/llm_explain.py`,
   `config.LLM_*` keys. `/explain` responses now carry `llm_narrative`
   (`available/text/model/latency_ms/reason/advisory_only`). Availability chain:
   `BLACKBOX_LLM_URL` HTTP service (showcase: `scripts/llm_service.py` runs
   `ibm-granite/granite-3.0-1b-a400m-instruct` in the LinuxONE Jupyter container,
   model cached at guest `~/shared/hf_cache`, DOWNLOAD_OK) â†’ local transformers
   via `BLACKBOX_LLM_MODEL` â†’ honest `available=false` + reason. Frontend card
   "LLM Narrative (advisory)". **Never changes scores or decisions.**
3. **Containerized deployment:** Dockerfile gains `INSTALL_BUILD_TOOLS` build
   arg (cmake/g++/gfortran/libopenblas for s390x source builds); s390x recipe:
   `docker build --build-arg BASE_IMAGE=s390x/python:3.11-bookworm
   --build-arg INSTALL_BUILD_TOOLS=1 -t blackbox .`. Guest Docker 29.8.0
   (s390x daemon, linux1 in docker group) â€” build in progress on the target.
Suite **155/155 PASS** (AMD64/sklearn+xgboost, 2026-10-17, 181s: prior 149 +
6 new LLM tests). New config SHA-256 `7c38c455â€¦e100` (hybrid + LLM keys + LLM
CPU timeout 120s;
weights/threshold/scenarios/POLICY_VERSION/dataset SHA byte-identical â€”
contract tests).

## What exists and was verified here

| Area | State | Evidence |
|---|---|---|
| Shared contract (`schemas.py`, `config.py`, errors, diagnostics) | done, frozen | contract tests |
| Data (5,002 synthetic transactions, 8 categories, 5 joint-danger profiles, demo pair) | done | `tests/unit/test_data.py`, `backend/data/manifest.json` |
| Simulation (forks, 3 scenarios, bounded fragility search) | done | `tests/unit/test_simulation.py` |
| Impact Gate + models (IsolationForest A, **hybrid RF+XGBoost U** when xgboost present, numpy fallback) | done | `tests/unit/test_gate.py`, `tests/unit/test_hybrid_risk.py` |
| LLM narrative layer (Granite via URL/local transformers; advisory only) | done | `tests/unit/test_llm_explain.py`, `scripts/llm_service.py` |
| Certificate + prototype policy + REVIEW degradation | done | `tests/unit/test_certificate.py` |
| Pipeline orchestration (`backend/pipeline.py`) | done | `tests/integration/test_full_pipeline.py` |
| Full suite via `scripts/run_tests.py` | **VERIFIED** **161/161** (AMD64, sklearn+xgboost, interaction-aware, 2026-10-17 post-audit fixes; 155-subset prior runs below) | ~180s |
| `python -m pytest -q` | **VERIFIED** **161 passed** (2026-10-17 post-audit fixes) | 1 env deprecation warning (httpx/starlette) |
| `scripts/smoke_test.py` incl. HTTP routes | **VERIFIED** all PASS, HTTP PASS not SKIP | 2026-10-14 on AMD64 with FastAPI installed |
| Live uvicorn `/health`, `/analyze` demo, empty-body 422 | **VERIFIED** on AMD64 | smoke + ad-hoc curl/TestClient |
| Dataset SHA-256 vs manifest | **VERIFIED** match `546f57ceâ€¦d5c3` | `diagnose_env` / validation runner |
| Validation-split experiment | run once for development (sklearn, 2026-10-13) | `evidence/results/validation/` (**do not overwrite**) |
| Env diagnostics + validation runner + runbook | **VERIFIED** scripts run on AMD64 | `scripts/diagnose_env.py`, `scripts/validate_runtime.py`, `docs/LINUXONE_RUNBOOK.md` |
| Gate score trace for TX-DEMO-0001 | **VERIFIED** | interaction-aware active 2026-10-16: score 0.516452 < 0.60 (frozen mode was 0.582418; numpy frozen was 0.414) |

## What was NOT verified

* **LinuxONE / s390x execution: VERIFIED 2026-10-16/17**, including the
  post-activation interaction-aware gate (141/141, sklearn,
  `run_20261016T185139Z_s390x_sklearn/`) and the **hybrid + LLM tree
  (155/155 + `validate_runtime.py --include-optional` PASS,
  `run_20261016T203734Z_s390x_sklearn/`).**
* Browser **interactive** click-through of `/dashboard`: **PERFORMED** by the
  agent browser (BREAK MY DECISION -> decision certificate + LLM narrative card
  rendered; evidence `evidence/capture/llm_narrative_card.png`, F-044).
  **Headless Edge page load + DOM list population:** **PARTIALLY VERIFIED**
  (`evidence/browser_check/`, pass 2).
* Docker image build **on the AMD64 host: BLOCKED** (no CLI). **On the s390x
  target: VERIFIED** â€” image built, container run, `/health`
  `runtime=linuxone` healthy (`evidence/capture/container_health_s390x.json`).
* IBM Granite LLM narrative on the target: **VERIFIED** â€” live `/explain`
  chain (`evidence/capture/explain_llm_chain_s390x.json`, ~57s CPU).
* Exact reproduction of the 2026-10-13 sklearn validation table on the
  original Python 3.13.16 + scikit-learn 1.9.1 environment: NOT re-run here.
* Organizer permission for pre-building: still requires a human source
  (`evidence/claims.md`).

## Open issue 1 - the gate under-performs (KNOWN ISSUE; needs a human decision; TASKS T1)

Validation split (1,000 transactions, 102 true failures). Failure recall at
fixed simulation budget â€” **published numbers used the sklearn backend**:

| budget | random | amount_only | anomaly_only | BLACKBOX (gate) |
|---|---|---|---|---|
| 1% | 0.010 | 0.020 | 0.098 | 0.059 |
| 5% | 0.049 | 0.020 | 0.422 | 0.167 |
| 10% | 0.102 | 0.039 | 0.696 | 0.245 |

Production rule (simulate iff score >= 0.60): simulates 16.5% of
transactions, recall 0.314, precision 0.194.

**NumPy fallback backend (same frozen data/seeds, 2026-10-14 re-run, stored
beside published evidence)** shows the same qualitative ranking problem
(anomaly_only 0.529 vs BLACKBOX 0.196 at 10%; threshold point 11.4% /
recall 0.216). See `docs/BACKEND_EVIDENCE.md`.

**Phase 2 diagnosis (AMD64, numpy, validation) â€” VERIFIED:** experiment
harness is fair (same labels/k; raw-A vs ECDF-A top-k Jaccard=1.0; no leak).
Root cause: M has point-biserial râ‰ˆ0 with failure at weight 0.30; gate score
r=0.27 vs raw A r=0.43. Full report: `docs/GATE_DIAGNOSTIC_REPORT.md`.
Interaction-aware **ranking candidate** beat anomaly-only at 1/5/10% on this
run (hypothesis `SUPPORTED_on_validation` for numpy only):
`docs/RESEARCH_EXPERIMENT_PLAN.md` + `evidence/results/analysis/phase2_*/`.
**Activated in production 2026-10-16 under explicit human authorization**
(see activation paragraph above); frozen `IMPACT_WEIGHTS` retained unchanged,
`combine()` kept as reference. sklearn-mode activation verified locally
(141/141 then 155/155) **and on s390x** (141/141 then 155/155 +
validate_runtime PASS).

Likely cause (hypothesis, not yet tested): `D` is computed only from static
graph structure, so it does not see load, while simulator failures are driven
by load. `A` gets load features and carries that signal; `D` and `M` dilute
it. Many dangerous cases have M = 0 (amount is normal; danger is load).

Do not tune weights/threshold on your own. Diagnostic plan:
`docs/GATE_PERF_DIAGNOSTIC_PLAN.md`. Options for the human are in TASKS T1.

## Phase 3 â€” independent reproduction & robustness (VERIFIED on AMD64/numpy)

| Claim | Label | Evidence |
|---|---|---|
| Phase 2 interaction recalls 0.098 / 0.412 / 0.627 | **REPRODUCED** within 1e-9 (raw CSV recalc + unchanged Phase 2 rerun, exit 0) | `docs/PHASE3_REPRODUCTION_REPORT.md`, `phase3_20261013T204244Z_reproduction/` |
| No evaluation leakage / fair budgets | **VERIFIED** (audit U1â€“U10) | same report |
| Cluster bootstrap interâˆ’anomaly @5%/10% | **VERIFIED** CIs exclude 0 ([+0.018,+0.159], [+0.041,+0.162]) | `docs/PHASE3_ROBUSTNESS_REPORT.md` |
| Multi-seed robustness (seeds 0â€“4,42) | **VERIFIED** â€” inter/anomaly seed-invariant on numpy; gate varies via U only | Phase 3 `results.json` |
| sklearn cross-backend | **AVAILABLE** â€” scikit-learn 1.9.1 installed 2026-10-15; live backend is sklearn (Phase 3 seed-invariance table above was measured on numpy) | `docs/submission/SKLEARN_BACKEND_SWITCH_REPORT.md` |
| Adoption criteria A1â€“A7,A10 | **PASS** | `docs/PHASE3_ADOPTION_CRITERIA.md` |
| Adoption criteria A8 (backend), A9 (human) | **FAIL** â†’ verdict **BACKEND-CONDITIONAL** | Phase 3 `results.json` |
| Frozen weights / published evidence / Phase 2 bundle | **UNCHANGED** | integrity_before/after SHA-256s |

**Still not production:** interaction ranking is research-only; T1 human decision open;
LinuxONE **NOT VERIFIED**; locked test **unused**.

## Open issue 2 - the fixed demo transaction is skipped by the gate (KNOWN ISSUE)

`TX-DEMO-0001` scores **0.516452** under the active interaction-aware policy
(sklearn, re-measured 2026-10-17) and **0.580013** in frozen reference mode â€”
both < 0.60 â€” so BREAK MY DECISION returns
`NO_SIMULATION / ALLOW_NORMAL_PATH`, although it fails `3x_volume` in stress
simulation. (Older published figures â€” 0.582418 frozen pre-hybrid, 0.503
frozen in the original published docs, 0.414 numpy frozen â€” remain true for
their dated backends/policy modes; scores are always backend- and
policy-mode-labeled.) Full component breakdown: `docs/GATE_PERF_DIAGNOSTIC_PLAN.md` D8
and `python scripts/trace_gate.py`. Honest blind-spot demonstration; poor
default demo. See T2.

## Backend-dependency of evidence (KNOWN ISSUE; documented)

Published validation evidence was produced with **sklearn**
(`IsolationForest`, `RandomForestClassifier`, scikit-learn 1.9.1, Python
3.13.16, x86_64). Environments without scikit-learn automatically select the
**numpy** fallback and produce different A/U scores, rankings and selected
sets. Never compare or replace metrics across backends without labels.
Details: `docs/BACKEND_EVIDENCE.md`.

## Deviations from the v4 manual (all deliberate, all small)

* `FragilityResult` has no `status` field (the schema is frozen). "Never failed in range" is encoded as
  `unit == "x_intensity_lower_bound"` with `breaking_threshold == MAX_INTENSITY`.
* `DecisionCertificate` has no `limitations` field; limitations are evidence lines prefixed `LIMITATION: `.
* Five joint profiles were added to the existing generator (`JOINT_PROFILES`, `joint_profile` on
  `DatasetRecord`); the "A alone survives, B alone survives, A+B fails" guarantee is unchanged.
* `GET /transactions` was added (read-only list for the UI).
* pandas is not used (v4 mentions it); NumPy + scikit-learn only. The LinuxONE import check in the
  manual includes pandas - use `python3 -c "import numpy, sklearn, fastapi; print('OK')"` instead.
* Runtime certificates now include one extra evidence line (runtime/backend/git/config/dataset
  fingerprints) and `model_versions` gained `config_sha256` / `dataset_sha256` keys inside the
  **existing** dict â€” no schema field was added, removed or renamed.

## Environment notes

* Built with Python 3.13 originally; Dockerfile targets Python 3.11. Keep code 3.11-compatible.
  Also exercised on Python 3.12.10 (AMD64) during the 2026-10-14 audit/validation pass.
* The dataset file is checked in (`backend/data/sample_dataset.json`, 2.8 MB) and is deterministic:
  `python scripts/build_dataset.py` must reproduce the SHA-256 in `manifest.json` (if you change the
  generator or config, regenerate it and re-run tests).
* New validation runs must go to `evidence/results/validation_runs/run_<UTC>_<arch>_<backend>/`
  via `scripts/validate_runtime.py` â€” never overwrite `evidence/results/validation/`.

## Completion pass 1 â€” demo & submission readiness (2026-10-14)

| Item | Result |
|---|---|
| Test count in README / runbook | **Updated** 57 â†’ **87/87** (re-ran `run_tests.py` exit 0) |
| Demo script â‰¤3 min | **Added** `docs/submission/DEMO_SCRIPT.md` |
| Submission checklist + disclosures | **Added** `docs/submission/SUBMISSION_CHECKLIST.md`, `DISCLOSURES.md` |
| Claims ledger | **Updated** `evidence/claims.md` with host-verified claims; organizer rules remain **HUMAN REQUIRED** |
| Browser checklist | **Added** `docs/BROWSER_VERIFICATION_CHECKLIST.md` â€” **not** a passed test (no browser on host) |
| Docker | **BLOCKED** (`docker` CLI missing) â€” no build claimed |
| Gate / interaction ranking / locked test / schemas | **UNCHANGED** |
| LinuxONE | **NOT VERIFIED** (unchanged) |

Pending human: T1 gate decision, claims.md rules source, demo recording, browser dry-run, LinuxONE access.

## Final submission audit (2026-10-14, read-only)

| Item | Result |
|---|---|
| Go/no-go | **NOT READY** â€” compliance unconfirmed; media ABSENT; interactive UI NOT VERIFIED |
| Inventory | see `docs/submission/FINAL_SUBMISSION_AUDIT.md` + `FINAL_PACKAGE_CHECKLIST.md` |
| Integrity recheck | weights/threshold/Phase 2 hashes unchanged; interaction ranking absent from `backend/` |
| Corrections only | package locked-test path; README/checklist cross-links â€” **no product/gate changes** |

## Completion pass 4 â€” rubric upgrades (2026-10-17)

| Item | Result |
|---|---|
| Second AI framework (rubric: >=2 frameworks) | **DONE** â€” hybrid RF+XGBoost risk ensemble, `hybrid_risk: on`, 155/155 AMD64 + s390x |
| LLM pairing (rubric: Granite) | **DONE** code â€” advisory `/explain.llm_narrative`; live bring-up **VERIFIED on AMD64** via llama.cpp (F-044: `available=true`, certificate score unchanged at 0.516452, evidence `evidence/capture/llm_narrative_card.png`); s390x chain VERIFIED separately |
| Containerized deployment (rubric: Docker on Z) | **DONE** image â€” s390x `blackbox:latest` built on the guest; container rerun after python-multipart fix pending |
| Theme mapping + quantified beneficiary + solo roles | **DONE** â€” README "Datathon alignment" (primary theme: Real-Time AI for Critical Decisions) |
| Config SHA | `7c38c455â€¦e100` (hybrid+LLM keys; frozen weights/threshold/scenarios/dataset unchanged) |
| Go/no-go | **TECH READY / HUMAN GATES OPEN** â€” video + browser click-through + organizer compliance remain human-only |
