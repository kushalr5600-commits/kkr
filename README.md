# BLACKBOX

**Enterprise decision preflight engine** - IBM Z Datathon 2026. *Don't predict the future. Test it first.*

A calibrated Impact Gate decides which transactions deserve expensive counterfactual simulation. Selected
transactions are stress-tested under three scenarios, the distance to failure is measured, and a Decision
Certificate with real evidence is issued before the decision is committed. Synthetic data only; research
prototype; the recommended action is a *demo policy*, not production authorization.

> Working on this with a coding agent? Start with `AGENTS.md`, then `docs/STATUS.md` and `docs/TASKS.md`.

## Run

```bash
python -m venv .venv && source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt                        # runtime + pytest + httpx
python -m pytest -q
python scripts/run_tests.py
python scripts/smoke_test.py                               # HTTP checks PASS with httpx
uvicorn backend.main:app --host 0.0.0.0 --port 8000        # open http://127.0.0.1:8000/dashboard
```

Lean NumPy-only production runtime (no scikit-learn, no test packages):
`pip install -r requirements-numpy.txt` â€” then set `BLACKBOX_MODEL_BACKEND=numpy` if needed.
Full HTTP smoke without sklearn: `pip install -r requirements-numpy.txt -r requirements-test.txt`.
Models are fitted at start-up (a few seconds) on the calibration split, in whatever environment runs the app.

### Validation and diagnostics

```bash
python scripts/diagnose_env.py        # offline environment + backend report (no secrets)
python scripts/validate_runtime.py --include-optional   # full suite + smoke + evidence bundle
python scripts/trace_gate.py          # read-only Impact Gate explanation for one transaction
```

LinuxONE / s390x procedure: `docs/LINUXONE_RUNBOOK.md`.
Backend-dependent metrics: `docs/BACKEND_EVIDENCE.md`.
Verification status of this handoff: `docs/STATUS.md`.

### Verification status (honest)

| Claim | Status |
|---|---|
| 161/161 unit/contract/integration tests (`pytest`; 155 frozen-pinned + 4 reverse doc-contract + 2 C1/disclosure regression tests added in the 2026-10-17 audit-fix session) | **VERIFIED** on AMD64 (CPython 3.12.10, sklearn 1.9.1 + xgboost 3.4.1), 2026-10-17 |
| Same suite on LinuxONE / s390x (141/141 pre-LLM; 155 re-run after LLM sync) | **VERIFIED** on s390x guest (Ubuntu 24.04.5, `run_20261016T185139Z_s390x_sklearn/` for the 141-run; post-hybrid target run recorded separately) |
| FastAPI routes + smoke test (HTTP PASS, not SKIP) | **VERIFIED** on AMD64 and s390x (live uvicorn HTTP on the guest) |
| Dataset SHA-256 matches `manifest.json` | **VERIFIED** (`546f57ceâ€¦d5c3`) |
| Cross-arch gate-score reproducibility (sklearn) | **VERIFIED** â€” showcase scores byte-identical AMD64 <-> s390x |
| Docker image build on the s390x target (INSTALL_BUILD_TOOLS=1) | **VERIFIED** â€” `blackbox:latest` built and run on the LinuxONE guest; container `/health` returns `runtime:linuxone`, `architecture:s390x`, status healthy (AMD64 host Docker still not installed) |
| IBM Granite LLM narrative on the target | **VERIFIED** â€” service `/health` loaded=true; `/explain` returns `llm_narrative.available=true` (57s CPU) with the certificate score unchanged; evidence in `evidence/capture/` |
| Browser click-through of the dashboard UI | **PARTIALLY VERIFIED** (Edge headless load + DOM list population; interactive click-through performed 2026-10-18 via the agent browser - certificate + LLM narrative card rendered, `evidence/capture/llm_narrative_card.png`) |

AMD64 results do **not** establish LinuxONE results. Do not describe an x86
run as LinuxONE.

Demo and submission materials: `docs/submission/DEMO_SCRIPT.md`,
`docs/submission/SUBMISSION_CHECKLIST.md`, honesty disclosures in
`docs/submission/DISCLOSURES.md`, packaging inventory in
`docs/submission/FINAL_PACKAGE_CHECKLIST.md`, and official-rules handoff in
`docs/submission/HUMAN_HANDOFF.md` (rules still **HUMAN REQUIRED**).

## How it works

```
POST /analyze -> validate -> load context -> IMPACT GATE (M,D,A,U -> score)
   score < 0.60 : certificate NO_SIMULATION (normal path)
   score >= 0.60: LOCAL STATE GRAPH -> REALITY FORK (baseline) -> CRASH TEST x3 (normal + stress each)
                  -> FRAGILITY SEARCH x3 -> DECISION CERTIFICATE
   any internal failure -> REVIEW certificate (never a silent "safe")
```

| Signal | What it is | Learned? |
|---|---|---|
| M magnitude | amount vs the account's own baseline | no (explainable statistic) |
| D dependency | downstream exposure in the local graph | no (deterministic graph feature) |
| A anomaly | IsolationForest score, empirical-CDF normalized on the calibration split | yes (scikit-learn) |
| U uncertainty | disagreement (std) of the failure ensemble's member P(fail), /0.5 â€” members are the random-forest trees **plus XGBoost bootstrap models** when xgboost is installed (hybrid, two frameworks) | yes (scikit-learn + XGBoost) |
| W window pressure / L load pressure | dataset-context features (recent activity, background load) used by the active ranking | no (deterministic context features) |

**Active decision policy (human-authorized 2026-10-16):** interaction-aware
`I = 0.45 A + 0.30 W + 0.15 D + 0.10 L`, simulate iff `I >= 0.60`
(`runtime.model_versions.policy_formula` carries the live formula string with
`;mode=interaction_aware`). The frozen reference formula
`I = 0.30 M + 0.30 D + 0.25 A + 0.15 U` remains implemented (`combine()`),
contract-pinned, and is what the numpy/`BLACKBOX_INTERACTION`-off ablation
reports. Weights and threshold are declared MVP parameters, not claimed
optimal. Scenarios: `3x_volume`, `fraud_spike`, `service_latency`.

An optional **LLM narrative** (IBM Granite via `scripts/llm_service.py`, or any
`BLACKBOX_LLM_URL` service) attaches plain-language context to `/explain`.
It is **advisory only** â€” scores and decisions never depend on it, and the API
returns an honest "unavailable" reason when no LLM is configured.

The narrate service auto-detects its backend: a `.gguf` model runs IBM Granite
locally through llama.cpp (`pip install -r requirements-llm.txt`; CPU, no
torch), anything else through transformers+torch. Verified on AMD64 with
`granite-4.2-3b Q4_K_M`: `/explain` returns a grounded narrative with the
certificate score unchanged (`docs/DEBUG_LOG.md`, F-044).

Prototype action policy: gate skips -> `ALLOW_NORMAL_PATH`; any stress failure -> `BLOCK_OR_HOLD`; no failure but
a thin fragility margin (< `REVIEW_MARGIN`) -> `REVIEW`; otherwise `ALLOW_NORMAL_PATH`; internal failure -> `REVIEW`.

## Evaluation

Ground truth is the full stress simulation. Primary metric: **failure recall at a fixed simulation budget**
(0.5%, 1%, 2%, 5%, 10%, 100%) against random, amount-only and anomaly-only baselines. Data are split
calibration / validation / locked test; models are fitted on calibration only and the locked test is evaluated once
after freezing (`scripts/run_experiment.py`). Current honest numbers and the open issue are in `docs/STATUS.md`.

## IBM LinuxONE (s390x)

LinuxONE is a **target platform**, not a wish. Build and run on the target
machine; `GET /health` reports the real `platform.machine()` and says
`linuxone` only on `s390x`. Full procedure, evidence checklist and
acceptance criteria: `docs/LINUXONE_RUNBOOK.md`. Environment diagnostics:
`python scripts/diagnose_env.py`. **VERIFIED on the real s390x guest**
(Ubuntu 24.04.5): validation runs under `evidence/results/validation_runs/`
with `runtime_label=linuxone`, including sklearn-mode 141/141 + live HTTP
(`run_20261016T185139Z_s390x_sklearn/`). Docker on the guest builds the app
container natively on s390x (`INSTALL_BUILD_TOOLS=1`; see Dockerfile header).

## Open-source libraries

| Library | Use | License |
|---|---|---|
| FastAPI - https://github.com/fastapi/fastapi | HTTP API | MIT |
| Uvicorn - https://github.com/encode/uvicorn | ASGI server | BSD-3-Clause |
| Pydantic - https://github.com/pydantic/pydantic | schemas/validation | MIT |
| NumPy - https://github.com/numpy/numpy | numerics | BSD-3-Clause |
| scikit-learn - https://github.com/scikit-learn/scikit-learn | anomaly (IsolationForest) + risk (RandomForest) models | BSD-3-Clause |
| XGBoost - https://github.com/dmlc/xgboost | hybrid risk-ensemble members (second AI framework) | Apache-2.0 |
| IBM Granite (via transformers, showcase container) - https://huggingface.co/ibm-granite | advisory LLM narrative | Apache-2.0 |
| pytest / httpx (dev only) | tests | MIT / BSD-3-Clause |

(Verify license strings against the project pages before submission and record the date in `evidence/claims.md`.)

## Datathon alignment (IBM Z Datathon 2026)

**Primary theme: Real-Time AI for Critical Decisions.** The Impact Gate is a
real-time decision layer: it ranks live payment traffic in milliseconds and
decides, per transaction, whether the expensive counterfactual simulation
earns its cost. Secondary fit: **AI Secured: Innovation Without Exposure** â€”
every decision ships as a Decision Certificate whose model provenance,
config-file SHA-256 and dataset SHA-256 are self-describing (the config and
dataset are content-hashed; certificate ids are identifiers, not hashes of the
certificate body); the LLM layer is
advisory-only by construction and cannot alter scores. Overarching mission:
**AI for Good** â€” trustworthy, auditable AI in high-stakes operational
decisions.

**Why IBM Z / LinuxONE is the right platform:** the workload is exactly the
enterprise shape Z is built for â€” many small in-process inferences at
throughput with strong operational guarantees, next to systems of record.
VERIFIED on a real LinuxONE guest (`148.100.78.185`, s390x): full suite,
live HTTP, hybrid sklearn+XGBoost models, and the Granite narrative cache all
run on the target, with gate scores byte-identical to the AMD64 development
host.

**Quantified beneficiary:** payment-operations and SRE teams at mid-size
payment processors (~10-50 operators). At the 5% simulation budget the
interaction gate roughly **doubles failure recall vs random triage** and
beats anomaly-only ranking (frozen-benchmark table in `docs/STATUS.md`);
the gate itself adds milliseconds per transaction while simulation runs only
for selected items. Synthetic data â€” the numbers bound the idea, not a real
institution.

**Roles (solo submission):** one author â€” architecture, RTL-free Python
implementation, evaluation design, LinuxONE bring-up, documentation and demo.
No team members, no external code vendored.

## Limitations

Synthetic data and a modelled enterprise; results describe the simulation, not a real institution. Failure limits,
gate weights and the review margin are declared parameters. Fragility is a bounded interval at stated resolution,
not an exact boundary. Not a production authorization system.
