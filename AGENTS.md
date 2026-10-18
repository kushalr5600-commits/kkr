# AGENTS.md - BLACKBOX build instructions for coding agents (OpenCode)

> **BANNER (2026-10-17):** Read `HANDOFF.md` FIRST â€” it has the current verified state
> (161/161 tests, LinuxONE PASS, hybrid risk, Granite LLM). Sections 2â€“3 below are
> stale (still say "67 tests" / "LinuxONE unverified"); trust `HANDOFF.md`,
> `docs/STATUS.md`, and `docs/DEBUG_LOG.md` over anything below.

You are continuing a half-built project. Read this file completely, then `docs/STATUS.md`
and `docs/TASKS.md`, before editing anything. The authoritative specification is
`docs/manuals/BLACKBOX_AI_Agent_Execution_Manual_v4.md`; the human-side plan is
`docs/manuals/BLACKBOX_Team_Manual_v4.md`. If this file and a manual disagree, stop and write
`docs/CONTRACT_CHANGE_REQUEST.md` (see section 7) instead of choosing silently.

## 1. What BLACKBOX is (one paragraph)

BLACKBOX is an enterprise decision-preflight engine for the IBM Z Datathon 2026. A calibrated
**Impact Gate** `I = 0.30 M + 0.30 D + 0.25 A + 0.15 U` (threshold 0.60) decides which
transactions deserve expensive counterfactual simulation. Selected transactions get a **Local State
Graph**, two **Reality Forks** (normal / stress), a **Crash Test Engine** (exactly three scenarios:
`3x_volume`, `fraud_spike`, `service_latency`), a **Fragility Search** (how much more stress before
it fails) and a **Decision Certificate** with evidence and a deterministic demo-policy action.
Tagline: "Don't predict the future. Test it first." Demo button: **BREAK MY DECISION**.
It must run, and its AI inference + simulation must be demonstrated, on IBM LinuxONE (`s390x`).

## 2. Current state (summary - details in docs/STATUS.md)

* Done and tested (67 tests pass as of the LinuxONE-tooling session): shared contract, data
  generator, simulator, gate + models, certificate, orchestration pipeline, FastAPI wrapper,
  plain HTML/CSS/JS frontend, scripts, Dockerfile, experiment runner, environment diagnostics,
  validation runner, gate-trace tool.
* VERIFIED on AMD64 (CPython 3.12.10): full suite (run_tests + pytest), smoke test with real
  HTTP routes, dataset SHA-256 integrity, live uvicorn `/health` + `/analyze` + 422 path.
* NOT VERIFIED: LinuxONE/s390x execution, Docker build, interactive browser UI. Use
  `docs/LINUXONE_RUNBOOK.md` + `scripts/validate_runtime.py` on the target; do not claim
  LinuxONE until a `validation_runs` bundle with `runtime_label=linuxone` exists.
* One serious open result (KNOWN ISSUE): with the frozen formula the gate ranks failures worse
  than a plain anomaly-score baseline on validation, and the fixed demo transaction scores below
  the 0.60 threshold. This needs a HUMAN decision (TASKS T1/T2). Do not "fix" it on your own.
  Plan and demo trace: `docs/GATE_PERF_DIAGNOSTIC_PLAN.md`.
* Evidence provenance (KNOWN ISSUE): published validation numbers came from the sklearn backend;
  the numpy fallback produces different A/U metrics â€” see `docs/BACKEND_EVIDENCE.md`. Never
  overwrite `evidence/results/validation/`.

## 3. Commands

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

python -m pytest -q                                      # full suite (67 tests)
python scripts/run_tests.py                              # same tests, no pytest needed
python scripts/smoke_test.py                             # pipeline + HTTP routes (needs fastapi)
python scripts/diagnose_env.py                           # offline env + selected model backend
python scripts/validate_runtime.py --include-optional     # full validation + evidence bundle
python scripts/trace_gate.py [TX_ID]                     # read-only Impact Gate explanation
python scripts/build_dataset.py                          # regenerate sample_dataset.json + manifest.json
python scripts/run_experiment.py                         # fixed-budget experiment, VALIDATION split
python scripts/run_demo.py [TX_ID]                       # print one certificate as JSON

uvicorn backend.main:app --host 0.0.0.0 --port 8000      # then open http://127.0.0.1:8000/dashboard
```

**Evidence rules (audit-safe):**

* Never overwrite `evidence/results/validation/` (published sklearn-backend
  run). New runs go to `evidence/results/validation_runs/run_<UTC>_<arch>_<backend>/`
  via `scripts/validate_runtime.py`.
* Metrics are backend-dependent (sklearn vs numpy fallback) â€” always label the
  backend; see `docs/BACKEND_EVIDENCE.md`.
* LinuxONE is verified only by a real s390x process (`scripts/diagnose_env.py`
  â†’ `Runtime label: linuxone`). AMD64/x86_64 output is never LinuxONE evidence.
  Procedure: `docs/LINUXONE_RUNBOOK.md`.
* Gate under-performance on validation and the skipped demo transaction are
  KNOWN ISSUES (`docs/STATUS.md`); diagnostic plan:
  `docs/GATE_PERF_DIAGNOSTIC_PLAN.md`. Do not â€œfixâ€ them without a human T1/T2
  decision.

Windows note: the human team uses PowerShell; keep scripts cross-platform (`pathlib`, no bash-isms
in Python). Do not add shell-only tooling to the Python path.

## 4. Repository map and ownership

```
backend/
  shared/    schemas.py (FROZEN) config.py (FROZEN values) errors.py diagnostics.py context_utils.py
  data/      generator.py scenarios.py repository.py sample_dataset.json manifest.json   [P1]
  gate/      impact_gate.py models.py calibration.py                                     [P3]
  simulation/ forks.py crash_test.py fragility.py physics.py                             [P2]
  certificate/certificate.py   pipeline.py   main.py                                     [P4]
frontend/static/  index.html style.css app.js                                            [P4]
tests/{contract,unit,integration}/   scripts/   docs/   evidence/
```

Ownership is a convention for keeping changes small. Work inside the area your task names; read
anything. A change outside it needs a one-line justification in `docs/DEBUG_LOG.md`.

## 5. FROZEN items - never change these without a human decision

1. Model names and field names in `backend/shared/schemas.py` (a contract test enforces this).
2. Node-type vocabulary: account, transaction, fraud_engine, ledger, payment_gateway, risk_model,
   notification, settlement, reporting.
3. Scenario identifiers `3x_volume`, `fraud_spike`, `service_latency`; exactly three; no fourth.
4. Fork names `normal` / `stress`. `attack()` returns exactly two results per scenario, so a
   simulated transaction yields 6 `ForkResult`s. "Fork A/B" is unrelated to "Scenario A/B/C".
5. Gate weights 0.30/0.30/0.25/0.15 and threshold 0.60 (`config.IMPACT_WEIGHTS`, `IMPACT_THRESHOLD`).
   They are declared MVP parameters, never described as optimal.
6. Callable names: `ImpactGate.score / should_simulate`, `RealityForkGenerator.generate_baseline`,
   `CrashTestEngine.attack`, `FragilitySearch.find_threshold`, `CertificateGenerator.generate`,
   `DataRepository.load_context`, `DatasetGenerator.generate_accounts / generate_transactions`.
7. Routes: the authoritative list is the HTTP table in `docs/CONTRACTS.md`
   (all 17 routes, both directions enforced by `tests/contract/test_docs_match_code.py`).
8. Certificate actions `ALLOW_NORMAL_PATH | REVIEW | BLOCK_OR_HOLD`; statuses
   `NO_SIMULATION | SIMULATED | REVIEW`.

Values marked FROZEN-BEFORE-LOCKED-TEST in `config.py` (signal normalization, failure limits,
review margin, model hyper-parameters) MAY be changed with human approval, using only the
calibration and validation splits, and never after the locked test has been evaluated.

## 6. Non-negotiable engineering rules

* **Never touch the locked test split for tuning.** `scripts/run_experiment.py --split test` requires
  `--confirm-frozen`; do not pass it unless the human says the configuration is frozen. Never look at
  test-split results and then change anything that influences them.
* **Ground truth comes from the simulator, never from the gate.** Models are fitted on the
  calibration split only (`GateModels.fit` raises `DataLeakError` otherwise). The gate must never
  read `DatasetRecord.category`, `split`, `joint_*` or any failure label as an input feature.
* **Never fake results.** No hard-coded certificates, evidence text, metrics, recall numbers or
  "LinuxONE" labels. Evidence strings must be built from real metrics. `/health` must report the
  real `platform.machine()`. If something is weak, report the weak number.
* **The frontend never computes** M/D/A/U, scores, fragility, evidence or actions. It renders the
  backend response only.
* **No new dependencies, frameworks, scenarios, components, forks or LLMs.** If you believe one is
  needed, write a change request.
* **Do not delete or weaken a test to make the suite pass.** Fix the code or raise the issue.
* **Smallest coherent change**, run the relevant tests after each, run the full suite before
  finishing. Keep behaviour deterministic (seeds are in `config.py`).
* **No secrets in git**: no SSH keys, VM addresses with credentials, tokens, `.env` files.
* **Rules compliance:** this project is being pre-built before the hackathon; the team states this
  is permitted (record the confirmation in `evidence/claims.md`). Keep honest, timestamped,
  small commits so authorship and timing are visible. Never hide or rewrite history. Never claim
  anything in docs that the code does not do.
* Do not run destructive git commands (`reset --hard`, force-push, history rewrite) and do not
  push: the human manages git.

## 7. When you are stuck or the spec conflicts

1. Reproduce with the smallest command. 2. Classify (contract / logic / model-data / wiring /
environment / s390x / frontend). 3. Fix inside the owning module only. 4. Test: unit, then contract,
then integration. 5. Record problem, fix and remaining risk in `docs/DEBUG_LOG.md`.

Ask the human (stop and write the question) only for: scope decisions, contract changes, anything in
section 5, credentials/network/LinuxONE access. Contract-change request format:

```
CONFLICT:
CURRENT CONTRACT:
PROPOSED CHANGE:
WHY:
FILES AFFECTED:
RISK:
```
Put it in `docs/CONTRACT_CHANGE_REQUEST.md`, continue only with work that does not depend on it.

Known environment limits: this project was built where PyPI was blocked; if `pip install` fails for
you too, do not work around network policy - report it. If scikit-learn will not install on s390x,
use `BLACKBOX_MODEL_BACKEND=numpy` (documented fallback) and say so in evidence.

## 8. Definition of done (all must be true and evidenced)

- [ ] `python -m pytest -q` passes; contract + unit + integration all real (no placeholders).
- [ ] `uvicorn` serves `/health`, `/dashboard`, `/analyze`; `scripts/smoke_test.py` passes with HTTP.
- [ ] Browser click-through works: select -> BREAK MY DECISION -> certificate; error state works.
- [ ] Gate decision (T1) resolved by a human; experiment re-run on validation; configuration frozen.
- [ ] Locked-test experiment run exactly once after freeze; real numbers in `evidence/results/test/`.
- [ ] Docker image builds and runs on LinuxONE; `uname -m` = s390x; real `POST /analyze` run there;
      model inference and simulation executed there; evidence files captured (see docs/TASKS.md T4).
- [ ] README + ARCHITECTURE accurate; open-source library links listed; limitations stated.
- [ ] Demo (<= 3 minutes) uses a deterministic transaction whose certificate was produced by the backend.

## 9. End-of-session handoff (always)

Append to `docs/DEBUG_LOG.md` and update `docs/STATUS.md`:

```
ROLE / TASK:            STATUS: COMPLETE | PARTIAL | BLOCKED
FILES CHANGED:          WHY EACH:
TESTS RUN + RESULTS:    TESTS NOT RUN:
KNOWN LIMITATIONS:      ASSUMPTIONS:
CONTRACT CHANGES REQUESTED: none | details
NEXT STEP:
```
Never write "done" without reporting test results.
