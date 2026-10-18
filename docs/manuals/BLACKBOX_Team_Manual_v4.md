# BLACKBOX — Human Master Team Runbook v4
### IBM Z Datathon 2026 · 4-Laptop Parallel Build · Human Step-by-Step Control Manual

---

## 0. Purpose and Operating Rule

This is the **human control manual**.

Use it to answer five questions without debate:

1. What exactly are we building?
2. Which person/agent owns each part?
3. What does the backend and frontend actually do?
4. What must be tested before moving forward?
5. What happens when something breaks?

The AI Agent Execution Manual is the implementation manual. This document is the **team-level source of truth for scope, sequencing, decisions, evidence, and recovery**.

### Frozen concept

> **BLACKBOX is an enterprise decision preflight engine.** It uses a calibrated Impact Gate to decide which transactions deserve expensive counterfactual simulation, tests selected transactions against adversarial stress scenarios, measures how close each decision is to failing, and produces an evidence-backed Decision Certificate before the enterprise commits.

**Tagline:** Don't predict the future. Test it first.

**Demo feature:** BREAK MY DECISION

### Frozen scope

There are six product components:

1. Impact Gate
2. Local State Graph
3. Reality Forks
4. Crash Test Engine
5. Fragility Search
6. Decision Certificate

Supporting infrastructure such as FastAPI, validation, logging, tests, Docker, and the browser UI is **not a seventh product component**. It is implementation plumbing.

---

# 1. Rules and Pre-Event Boundary

The official rules define the event as October 17–18, 2026 and require the project to be built during the official hacking period. They also require the submission to include a demo video, complete codebase, open-source links, and an explicit LinuxONE/model demonstration.

## 1.1 Before the event: allowed preparation

Prepare only non-solution artifacts:

- architecture diagrams
- written specifications
- interface contracts
- test-case specifications
- demo storyboard
- scenario definitions
- experiment protocol
- compliance checklist
- visual wireframes/mockups
- account/access setup
- mandatory IBM AI/ML labs
- LinuxONE access and environment verification

**Do not pre-write the actual BLACKBOX application implementation.** Do not pre-build the final application repository and then present it as event-built.

A visual mockup is not the application. An implementation file is.

### The pre-written-code decision is CLOSED as follows

> **Use reference-only preparation before the event. During the event, agents create the implementation files from the written specification.**

Do not seek to justify pre-written application code by calling it a “template.”

---

# 2. BLACKBOX: Complete System Picture

This is the picture every human and every AI agent must understand before coding.

```text
                         ┌───────────────────────────┐
                         │         FRONTEND           │
                         │  Plain HTML/CSS/JS         │
                         │                           │
                         │  Transaction view         │
                         │  Impact score              │
                         │  BREAK MY DECISION        │
                         │  Certificate view         │
                         │  Error/status view        │
                         └─────────────┬─────────────┘
                                       │ HTTP/JSON
                                       ▼
                         ┌───────────────────────────┐
                         │        FASTAPI API         │
                         │                           │
                         │ GET  /health               │
                         │ GET  /dashboard            │
                         │ POST /analyze               │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │     ORCHESTRATION          │
                         │  validate → gate → route   │
                         │  → simulate → certify      │
                         └───────┬─────────┬─────────┘
                                 │         │
                         low impact        │ high impact
                                 │         ▼
                                 │  ┌───────────────────┐
                                 │  │    IMPACT GATE    │
                                 │  │ M D A U → score   │
                                 │  └────────┬──────────┘
                                 │           │
                                 │           ▼
                                 │  ┌───────────────────┐
                                 │  │ LOCAL STATE GRAPH │
                                 │  └────────┬──────────┘
                                 │           │
                                 │           ▼
                                 │  ┌───────────────────┐
                                 │  │   REALITY FORK    │
                                 │  │  baseline state   │
                                 │  └────────┬──────────┘
                                 │           │
                                 │           ▼
                                 │  ┌───────────────────┐
                                 │  │  CRASH TEST       │
                                 │  │  3 scenarios      │
                                 │  └────────┬──────────┘
                                 │           │
                                 │           ▼
                                 │  ┌───────────────────┐
                                 │  │ FRAGILITY SEARCH  │
                                 │  └────────┬──────────┘
                                 │           │
                                 └───────────┴───────────┐
                                                         ▼
                                               ┌─────────────────────┐
                                               │ DECISION CERTIFICATE│
                                               │ evidence + action   │
                                               └──────────┬──────────┘
                                                          │ JSON
                                                          ▼
                                                    FRONTEND RESULT
```

### One-sentence backend flow

> **Request enters → validate → build local context → Impact Gate → optionally simulate → search fragility → build certificate → return JSON.**

### One-sentence frontend flow

> **User selects transaction → browser sends JSON → backend processes it → browser renders the returned certificate; the frontend never implements business logic.**

---

# 3. Backend Architecture — Exact Responsibilities

The backend is Python/FastAPI. It is the only place where BLACKBOX logic executes.

## 3.1 Repository structure

```text
blackbox/
├── backend/
│   ├── main.py                         # FastAPI entrypoint; P4 owns
│   │
│   ├── shared/
│   │   ├── schemas.py                  # FROZEN typed interfaces
│   │   ├── config.py                   # thresholds, scenario constants, seeds
│   │   ├── errors.py                   # shared error types
│   │   └── diagnostics.py              # trace IDs, stage timing, safe logging
│   │
│   ├── data/                           # P1
│   │   ├── generator.py
│   │   ├── scenarios.py
│   │   ├── repository.py               # dataset/context loading
│   │   └── sample_dataset.json
│   │
│   ├── gate/                           # P3
│   │   ├── impact_gate.py
│   │   ├── models.py
│   │   └── calibration.py
│   │
│   ├── simulation/                     # P2
│   │   ├── forks.py
│   │   ├── crash_test.py
│   │   └── fragility.py
│   │
│   └── certificate/                    # P4
│       └── certificate.py
│
├── frontend/
│   └── static/
│       ├── index.html
│       ├── style.css
│       └── app.js
│
├── tests/
│   ├── unit/
│   │   ├── test_data.py
│   │   ├── test_gate.py
│   │   ├── test_simulation.py
│   │   └── test_certificate.py
│   ├── contract/
│   │   └── test_schemas_and_interfaces.py
│   └── integration/
│       └── test_full_pipeline.py
│
├── scripts/
│   ├── smoke_test.py
│   ├── run_experiment.py
│   └── run_demo.py
│
├── evidence/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CONTRACTS.md
│   └── DEBUG_LOG.md
├── requirements.txt
├── Dockerfile
└── README.md
```

### Ownership

| Area | Human | AI agent |
|---|---|---|
| `backend/shared/*` | Team lead freezes contracts | Any agent may read; only designated lead edits after freeze |
| `backend/data/*` | P1 | P1 agent |
| `backend/gate/*` | P3 | P3 agent |
| `backend/simulation/*` | P2 | P2 agent |
| `backend/certificate/*` | P4 | P4 agent |
| `frontend/*` | P4 | P4 agent |
| `backend/main.py` | P4 | P4 agent |
| `tests/*` | Shared | Each owner writes own tests; P4 maintains integration test |
| `docs/*` | Shared | Each agent updates only its handoff/debug records |

---

# 4. Frontend Architecture — Exact Responsibilities

The frontend is deliberately boring.

## 4.1 What the browser does

The browser:

1. Loads `/dashboard`.
2. Displays known/demo transactions.
3. Sends a transaction to `POST /analyze`.
4. Shows a progress state.
5. Renders the returned `DecisionCertificate`.
6. Shows the evidence, scenario outcomes, fragility interval, and recommendation.
7. Shows a clear error state when backend processing fails.

## 4.2 What the browser NEVER does

The frontend does not:

- calculate M/D/A/U
- calculate the Impact Gate score
- run an anomaly model
- decide whether simulation is required
- calculate fragility
- create evidence claims
- generate a recommendation independently

The backend response is authoritative.

## 4.3 UI states

```text
IDLE
  ↓ click Analyze / BREAK MY DECISION
ANALYZING
  ↓ success
RESULT
  ├── low-impact certificate
  ├── simulated certificate
  └── review/failure certificate

ANALYZING
  ↓ HTTP/runtime failure
ERROR
  ↓ retry
IDLE
```

The UI must never show a stale previous certificate as though it belongs to the current transaction. Display the current `transaction_id` and `trace_id` with every result.

---

# 5. API Contract — Frozen at Hour 1

The HTTP routes below are the external API. The internal Python method names below are the internal integration contract.

### Frozen internal callable names

```text
ImpactGate.score(...)
ImpactGate.should_simulate(...)
RealityForkGenerator.generate_baseline(...)
CrashTestEngine.attack(...)
FragilitySearch.find_threshold(...)
CertificateGenerator.generate(...)
```

These names are authoritative. If an AI agent finds a mismatch, it must stop at the boundary and use the autonomous debugging/contract-change procedure rather than inventing an alias.

The following routes are the only required runtime API for the MVP.

## `GET /health`

Purpose: deployment and debugging.

Return:

```json
{
  "status": "ok",
  "runtime": "linuxone",
  "architecture": "s390x",
  "version": "event-build"
}
```

The exact runtime values must be truthful. Do not fake “LinuxONE” when running locally.

## `GET /dashboard`

Purpose: serve `frontend/static/index.html`.

## `POST /analyze`

Purpose: run the complete BLACKBOX decision-preflight pipeline.

Conceptual request:

```json
{
  "transaction": { "...": "Transaction fields" },
  "context": { "...": "local event context" },
  "demo_mode": false
}
```

Response:

```json
{
  "certificate_id": "...",
  "trace_id": "...",
  "status": "SIMULATED",
  "transaction_id": "...",
  "impact_score": { "...": "ImpactScore" },
  "forks_tested": [],
  "fragility": [],
  "recommended_action": "...",
  "evidence": [],
  "runtime": { "...": "RuntimeMetadata" }
}
```

A malformed request returns a standard validation error. A valid request that fails internally must produce a **safe REVIEW certificate** rather than silently claiming safety.

---

# 6. Shared Schema — Single Source of Truth

`backend/shared/schemas.py` is the contract. Every agent builds against it.

```python
Transaction
Account
EventContext
GraphNode
GraphEdge
DependencyGraph
ImpactSignals
ImpactScore
ForkResult
FragilityResult
RuntimeMetadata
DecisionCertificate
```

### Required semantic rules

- `fork_name="normal"` means nominal execution.
- `fork_name="stress"` means the same scenario applied to the nominal local state.
- These Fork A/B names are **not** related to Scenario A/B/C lettering.
- Scenario identifiers are code-level strings:
  - `3x_volume`
  - `fraud_spike`
  - `service_latency`
- All signal values are normalized to `[0,1]` before combining.
- `ImpactScore.score` is always `[0,1]`.
- `gate_decision=True` means deep simulation is selected.
- Fragility reports a bounded interval/resolution, not false exact precision.

### Event context is part of the gate input

Jointly dangerous cases require temporal/local state. Therefore `EventContext` may contain a small recent-event window and local dependency load. The gate must not pretend to reason about a co-occurrence that it was never given.

---

# 7. Impact Gate — Frozen Mathematical Contract

```text
I(T) = 0.30M + 0.30D + 0.25A + 0.15U
threshold = 0.60
```

### M — Magnitude

Explainable statistical feature. Compare amount with account baseline, normalize to `[0,1]`.

### D — Dependency

Deterministic graph feature. Compute normalized downstream dependency exposure in the transaction's local graph.

### A — Anomaly

Output of the selected anomaly model, normalized to `[0,1]`, where larger means more anomalous.

### U — Uncertainty

Use predictive disagreement/variance from a defined risk model. The exact model and normalization must be written into `backend/shared/config.py` before final evaluation.

### Important experiment rule

The weights and threshold are **MVP parameters**, not universal truths. Do not describe `0.30/0.30/0.25/0.15` or `0.60` as scientifically optimal unless the team's experiment actually demonstrates that claim.

Pitch line:

> “We use AI where AI adds value. Everything else is transparent math.”

---

# 8. Reality Forks and Crash Tests — Exact Semantics

There are exactly three stress scenarios:

1. `3x_volume`
2. `fraud_spike`
3. `service_latency`

There are conceptually two fork states for each scenario:

```text
normal = nominal local state
stress = the SAME local state after ONE specified scenario is applied
```

### Required execution pattern

```text
baseline = RealityForkGenerator.generate_baseline(...)

for scenario in SCENARIOS:
    results = CrashTestEngine.attack(baseline, scenario)
    # results contains one normal result + one stressed result
```

This prevents accidentally applying “stress” twice.

### Scenario identifiers and human labels

Use this mapping everywhere so slide labels and code identifiers cannot drift:

| Human label | Code identifier | Meaning |
|---|---|---|
| Scenario A | `3x_volume` | transaction volume stress |
| Scenario B | `fraud_spike` | anomaly/fraud load spike |
| Scenario C | `service_latency` | downstream latency/outage |

Fork A/B is a separate concept: Fork A is the normal/nominal result and Fork B is the stress result. Never use “Fork A” to mean Scenario A.

### Scenario failure definitions

The exact threshold values must be frozen in `backend/shared/config.py` before the locked test run.

Do not change a threshold after seeing final test results merely to improve the curve.

---

# 9. Fragility Search

BLACKBOX must answer both:

> “Does it fail?”

and:

> “How much additional stress is required before it fails?”

Use a grid/binary search only when the failure predicate is sufficiently monotonic.

Report a bounded result such as:

```text
survives through 2.40×
fails by 2.45×
resolution = 0.05×
```

Do not present `2.44×` as an exact scientific boundary if the implementation only resolved the interval to `0.05×`.

---

# 10. Certificate — What the User Must See

The Decision Certificate is not an opaque “AI says reject.”

It should show:

```text
Transaction
  ↓
Impact score + M/D/A/U
  ↓
Gate decision
  ↓
Scenarios tested
  ↓
Normal vs stress outcomes
  ↓
Fragility interval
  ↓
Evidence bullets
  ↓
Recommended action
```

Add reproducibility metadata:

- certificate ID
- trace ID
- timestamp
- random seed when applicable
- model version(s)
- configuration version
- runtime architecture
- application/git version if available

### Safe actions

At minimum:

- `ALLOW_NORMAL_PATH`
- `REVIEW`
- `BLOCK_OR_HOLD`

Use one deterministic prototype policy:

```text
LOW IMPACT
  -> ALLOW_NORMAL_PATH

HIGH IMPACT + any stressed scenario fails
  -> BLOCK_OR_HOLD

HIGH IMPACT + no failure + fragility margin below review threshold
  -> REVIEW

HIGH IMPACT + all tests survive with adequate margin
  -> ALLOW_NORMAL_PATH

ANY INTERNAL SIMULATION/MODEL FAILURE
  -> REVIEW
```

The review-margin value belongs in `backend/shared/config.py` and is frozen before the locked test evaluation. These are prototype actions, not production authorization logic.

---

# 11. Experiment Design — Scientifically Defensible MVP

## Research question

> Can BLACKBOX use a calibrated Impact Gate to reduce the number of transactions requiring expensive counterfactual simulation while retaining high recall of transactions that would actually fail under stress?

## Required categories

- normal
- unusual-but-harmless
- obvious single-signal danger
- high-value / low-blast-radius
- low-value / high-blast-radius
- correlated anomalies
- dependency-chain failures
- jointly dangerous co-occurrence cases

The jointly-dangerous examples must be deliberately constructed rather than left to chance.

## Dataset split

Use three logical sets:

```text
CALIBRATION
  ↓ weights / normalization / model fitting

VALIDATION
  ↓ development decisions

LOCKED TEST
  ↓ final published curve
```

Never tune on the locked test set.

## Ground truth

Ground truth is produced by full stress simulation of the evaluation transactions. The simulator is not being “trained.” It is being used as the evaluation oracle for the synthetic environment.

## Primary metric

**Failure recall at fixed simulation budget.**

Recommended budgets:

- 0.5%
- 1%
- 2%
- 5%
- 10%
- 100%

## Baselines

Compare BLACKBOX with:

- random selection
- amount-only selection
- anomaly-only selection
- BLACKBOX Impact Gate
- 100% simulation

Report actual results.

If the results are weak, keep them. A measured blind spot is more credible than invented success.

---

# 12. Debugging Philosophy — Humans Should Not Chase Symptoms

Whenever something fails, follow the pipeline in order.

```text
BROWSER
  ↓
HTTP request
  ↓
API validation
  ↓
ORCHESTRATION
  ↓
GATE
  ↓
SIMULATION
  ↓
CERTIFICATE
  ↓
HTTP response
  ↓
BROWSER rendering
```

### Diagnostic rule

Never change multiple layers at once.

Find the **first failing stage**, reproduce it with the smallest input, repair the owning module, run its tests, then rerun the next layer.

### Standard trace fields

Every backend request should carry:

```text
trace_id
transaction_id
stage
status
elapsed_ms
```

The same `trace_id` must appear in the certificate and browser error state.

---

# 13. Autonomous Recovery Policy

An AI agent that finds a problem must follow this order:

### Step 1 — Reproduce

Run the smallest command that demonstrates the failure.

### Step 2 — Classify

Choose exactly one:

- contract/schema mismatch
- local logic bug
- model/data bug
- integration wiring bug
- environment/dependency bug
- LinuxONE/s390x compatibility bug
- frontend rendering bug

### Step 3 — Locate owner

Do not modify another person's component merely because the symptom appears there.

### Step 4 — Repair locally

Change the smallest number of files necessary.

### Step 5 — Test

Run:

1. unit test
2. contract test if an interface is involved
3. integration test if the pipeline boundary is involved

### Step 6 — Handoff

Record the problem, fix, tests, and remaining risk in `docs/DEBUG_LOG.md`.

Only ask a human when the problem requires a **scope decision, contract change, or external access/credential action**.

---

# 14. Human Interaction Budget

The team should operate with four mandatory human checkpoints, not continuous supervision.

### Human checkpoint 1 — Hour 1

Freeze:

- schemas
- API signatures
- ownership
- scenario semantics
- threshold definition placeholders

### Human checkpoint 2 — Hour 3

Verify:

- frontend loads
- `/health` works
- `/analyze` works with mocks
- LinuxONE stub deploy works

### Human checkpoint 3 — Hour 14

Verify:

- real data + gate + simulation run together
- one full certificate is generated
- no contract drift

### Human checkpoint 4 — Final 2 hours

Verify:

- experiment results frozen
- evidence captured
- LinuxONE demo works
- video and repository are compliant

Everything else should be handled by the four agents within their ownership boundaries.

---

# 15. 24-Hour Execution Timeline

The actual event plan is **H0–H24 only**.

| Time | Milestone | Primary owners | Gate to continue |
|---|---|---|---|
| H0–0:30 | Repo/branches/environment/rules check | All | all environments usable |
| H0:30–1 | **Sync 1: schema + contract freeze** | All | `schemas.py` and API contract frozen |
| H1–3 | **Sync 2: dumb end-to-end pipeline** | All / P4 integration | `/health`, `/dashboard`, `/analyze` work |
| H2–4 | first LinuxONE stub deployment | P4 | app executes on s390x |
| H3–8 | real data + real gate + simulation implementation | P1/P2/P3 | unit tests green |
| H3–10 | frontend + certificate implementation | P4 | mocked certificate renders |
| H8 | Sync 3: data + gate | All | dangerous/joint cases behave plausibly |
| H10–14 | real simulation + fragility + integration | P2/P4 | 3 scenarios work end-to-end |
| H14 | Sync 4: full pipeline | All | one real certificate generated |
| H14–18 | experiment/calibration + baseline comparison | P1/P3, P2 support | results reproducible |
| H18 | **Sync 5: experiment freeze** | All | test set locked; no more tuning |
| H18–20 | certificate polish + UI evidence + final deployment | P4 | demo transaction works on LinuxONE |
| H20 | **Sync 6: certificate + IBM Z freeze** | All | final architecture demonstrated |
| H20–22 | hardening, failure injection, evidence | All | no critical failures |
| H22–23 | demo rehearsal + recording | All | ≤3 min, complete required content |
| H23–24 | final README/repo/submission checks | All | submit before deadline |

**No Hour 28/30/40 phases exist.**

---

# 16. Sync Rules

At each sync:

1. stop feature development
2. merge only working commits
3. run contract test
4. run full integration test
5. record current commit/version
6. record any known defects
7. only then resume parallel work

If an agent is late:

> The agent hands over a tested stub implementing the frozen interface. Integration continues. The agent continues in parallel.

Never wait for unfinished internal logic when the contract can already be exercised.

---

# 17. Deployment — LinuxONE Strategy

IBM documents LinuxONE/Linux on IBM Z around the `s390x` architecture and the LinuxONE Community Cloud as a no-charge shared environment. Current IBM community materials also describe the Community Cloud as a place to test applications on LinuxONE and identify architecture-specific compatibility issues.

## Deployment order

```text
laptop
  ↓ git push
LinuxONE
  ↓ git pull
install/verify dependencies
  ↓
start app
  ↓
GET /health
  ↓
POST /analyze
  ↓
open /dashboard
```

### Never assume x86 compatibility

Check:

```bash
uname -m
python3 --version
python3 -c "import numpy, pandas, sklearn, fastapi; print('OK')"
```

Then run the actual BLACKBOX smoke test.

### Deployment evidence

Capture:

- `uname -m` showing the real architecture
- running container/process
- `/health`
- actual `POST /analyze`
- browser dashboard
- model inference occurring on LinuxONE
- resource/simulation activity

A Docker container existing on LinuxONE is not sufficient evidence by itself; the AI workload must actually run there for the technical story.

---

# 18. Cut Order

### Cut first

1. advanced calibration/adaptation
2. baseline comparison visualization
3. fragility resolution precision

### Cut second

4. one optional stress scenario only if necessary to preserve a coherent MVP
5. fancy frontend animation

### Never cut

1. Impact Gate
2. at least one real normal-vs-stress comparison
3. Decision Certificate
4. real LinuxONE execution
5. truthful evidence
6. integration tests

If time is collapsing, make every component simpler rather than deleting the story.

---

# 19. Demo Story

The judge should understand this without reading the code:

```text
Problem
  ↓
Simulating everything is expensive
  ↓
Impact Gate selects what matters
  ↓
BLACKBOX builds local context
  ↓
BREAK MY DECISION applies stress
  ↓
Fragility shows how close failure is
  ↓
Certificate explains why
  ↓
AI inference + simulation run on LinuxONE
```

### Demo transaction

Use a deterministic demo transaction with a fixed seed and stable ID. The demo must produce the same output every rehearsal.

### Three strongest visual moments

1. Impact score crossing the simulation threshold.
2. BREAK MY DECISION showing normal vs stress.
3. Certificate showing evidence + fragility interval + runtime metadata.

---

# 20. Submission Evidence Map

The official submission requires a ≤3-minute demo covering the problem, supporting data, solution, IBM Z use, tech stack, and LinuxONE/model demonstration.

Capture the following:

| Evidence | Artifact |
|---|---|
| Rules readiness | `evidence/rules_checklist.png` |
| Mandatory labs | screenshots for each required completion |
| s390x runtime | `evidence/runtime_architecture.png` |
| container/app | `evidence/container_running.png` |
| model inference | `evidence/model_inference.png` |
| dashboard | `evidence/dashboard.png` |
| experiment | `evidence/recall_budget.csv` + chart |
| certificate | `evidence/demo_certificate.png` |
| repo | final README + architecture + library links |

---

# 21. Definition of Done

BLACKBOX is done only when all of these are true:

- [ ] all six product components exist
- [ ] frontend talks to backend through the frozen API
- [ ] all schemas validate
- [ ] unit tests pass
- [ ] contract tests pass
- [ ] full integration test passes
- [ ] deterministic demo works
- [ ] locked experiment produces reproducible results
- [ ] Decision Certificate explains the evidence
- [ ] LinuxONE executes the real backend/model path
- [ ] trace IDs connect UI → API → backend → certificate
- [ ] known failure modes have deterministic recovery behavior
- [ ] README explains architecture and setup
- [ ] open-source libraries are documented
- [ ] demo video fits the official limit
- [ ] submission links are verified

---

# 22. Final Team Rule

> **Do not ask “Who can fix this?” first. Ask “What is the first failing stage, what contract should have held, and which owner controls that stage?”**

That question is the operating principle of the entire build.


---

# 23. HUMAN STEP-BY-STEP RUNBOOK — FOLLOW THIS LITERALLY

This section converts the architecture into actions. A team member should be able to open this section at the start of the event and proceed line by line without inventing a workflow.

## 23.1 Before event day

### Step 1 — Compliance

- [ ] Confirm every participant is registered.
- [ ] Confirm the required labs have been completed according to the current organizer instructions.
- [ ] Save proof/screenshots.
- [ ] Confirm the latest official rules have been checked.
- [ ] Do not place application implementation code in the event repository before the hacking period.

### Step 2 — Access

- [ ] Confirm every required account works.
- [ ] Confirm LinuxONE access.
- [ ] Record the VM address and SSH key location privately.
- [ ] Do not put credentials in Git.

### Step 3 — Architecture rehearsal

Every person must be able to explain this without opening the manual:

```text
Browser
→ FastAPI
→ local context
→ Impact Gate
→ if high impact: simulation
→ fragility
→ Decision Certificate
→ browser
```

If someone cannot explain this, stop. Do not start implementation training for that person yet.

### Step 4 — Role rehearsal

Each person confirms:

```text
P1 = data/context
P2 = simulation
P3 = gate/models/experiment
P4 = certificate/frontend/deployment
```

No one owns another person's implementation area.

---

# 24. EVENT-DAY OPERATING PROCEDURE

## H0–H1 — Freeze the contract

### Human actions

1. Create the fresh repository.
2. Create the directory structure from the manual.
3. Create `shared/schemas.py`, `config.py`, `errors.py`, and diagnostics.
4. Review every frozen field and method name together.
5. Run contract tests.
6. Freeze the contract.

### Do not leave H1 until

```text
[ ] repository exists
[ ] all four agents can import schemas
[ ] contract tests pass
[ ] exact scenario IDs pass
[ ] exact method names are recorded
[ ] all four humans agree what each endpoint does
```

If anything fails, H1 remains a contract/debugging period. Do not compensate by starting feature work.

---

## H1–H3 — Build the skeleton

The goal is NOT to have intelligent behavior.

The goal is to prove that the entire product can communicate.

Build:

```text
browser
→ POST /analyze
→ fake transaction
→ fake gate
→ fake simulation result
→ fake certificate
→ browser
```

### Human verification

Click the UI yourself.

Do not accept “the endpoint works” as equivalent to “the product works.”

At H3:

- [ ] `/health` works.
- [ ] `/dashboard` works.
- [ ] `POST /analyze` works.
- [ ] browser displays a certificate.
- [ ] integration test passes.

Capture the first successful screenshot.

---

## H3–H8 — Data + Gate

P1 and P3 work in parallel.

### P1 human checklist

- [ ] Generate accounts.
- [ ] Generate transactions.
- [ ] Build dependency graphs.
- [ ] Create jointly-dangerous cases deliberately.
- [ ] Validate all data against schemas.
- [ ] Save deterministic seed/config.

### P3 human checklist

- [ ] Implement M.
- [ ] Implement D.
- [ ] Train/fit A according to the frozen protocol.
- [ ] Implement U according to the frozen protocol.
- [ ] Normalize all signals to `[0,1]`.
- [ ] Implement the frozen weighted score.
- [ ] Test obvious-dangerous and jointly-dangerous cases.

### At H8

Run the real gate against known examples.

Ask only:

> “Does the gate behave according to the specification?”

Do not ask whether the result is already “good enough.” That belongs to experiment evaluation later.

---

## H8–H14 — Simulation

P2 integrates against the real data/context.

### Human checklist

- [ ] Baseline state can be generated.
- [ ] `3x_volume` works.
- [ ] `fraud_spike` works.
- [ ] `service_latency` works.
- [ ] Each scenario produces exactly normal + stress results.
- [ ] No scenario is applied twice.
- [ ] Failure predicates are deterministic.
- [ ] Fragility returns a bounded interval/resolution.

At H14 run 3–5 real end-to-end transactions manually.

If the pipeline fails, fix integration before improving the UI.

---

## H14–H18 — Certificate + Experiment Freeze

P4 completes certificate/frontend integration.

The team then freezes:

- model configuration
- normalization
- scenario thresholds
- gate threshold
- experiment protocol

After the experiment freeze, do not tune the system to improve the final result.

---

## H18–H20 — Experiment + deployment

Run the locked experiment.

At the same time, P4 verifies LinuxONE.

### Human rule

Never wait until H23 to discover that a dependency does not run on s390x.

The LinuxONE smoke path is:

```text
SSH
→ uname -m
→ imports
→ start app
→ /health
→ /analyze
→ /dashboard
```

Only after the actual model path works should evidence be captured.

---

## H20–H24 — Submission mode

No new features.

### H20–H21

- [ ] final bug fixing
- [ ] rerun integration tests
- [ ] rerun deterministic demo

### H21–H22

- [ ] capture LinuxONE evidence
- [ ] capture experiment results
- [ ] finalize architecture diagram
- [ ] finalize README

### H22–H23

- [ ] rehearse demo three times
- [ ] record final demo
- [ ] verify video duration
- [ ] verify repository access

### H23–H24

- [ ] final submission checklist
- [ ] open every required link from a clean browser/session
- [ ] submit before the final minute
- [ ] preserve the submitted commit/tag and evidence

---

# 25. HUMAN DECISION TREE — WHEN SOMETHING BREAKS

Use this instead of randomly asking an AI agent to “fix everything.”

```text
Something is broken
        ↓
Can it be reproduced?
   NO → collect exact steps/logs first
   YES
        ↓
Which boundary fails first?
        ↓
Browser / API / Context / Gate / Simulation / Certificate / Deployment
        ↓
Which owner owns that boundary?
        ↓
Ask that agent to diagnose only that boundary
        ↓
Run the smallest relevant test
        ↓
Green?
  YES → continue
  NO  → repeat diagnosis
```

### Human escalation is required only when

- the schema must change;
- the scope must change;
- an external account/credential/access problem exists;
- the official rules are ambiguous;
- the team must decide whether to cut a feature;
- final submission requires a human action.

Everything else should be handled by the owning agent.

---

# 26. HUMAN HANDOFF FORMAT

When an agent says it is done, the human should not inspect the entire codebase first.

Require this five-line summary:

```text
STATUS: READY / BLOCKED
FILES: <files changed>
TESTS: <commands + result>
CONTRACT: UNCHANGED / CHANGE REQUEST
RISK: <one sentence>
```

If `CONTRACT: CHANGE REQUEST`, stop the merge and review it as a team.

---

# 27. HUMAN “DO NOT DEBUG THE SYMPTOM” RULE

If the frontend shows “Simulation failed,” do not immediately edit the frontend.

Find the first failing stage.

```text
UI error
→ API response?
→ trace ID?
→ backend log?
→ gate?
→ simulation?
```

The visible error is not necessarily the root cause.

---

# 28. FINAL HUMAN CONTROL CHECK

Before submission, one human should perform the entire journey as a judge would:

```text
Open dashboard
→ select transaction
→ BREAK MY DECISION
→ watch analysis
→ inspect Impact Gate
→ inspect normal/stress results
→ inspect fragility
→ inspect certificate
→ verify IBM Z/LinuxONE evidence
→ inspect experiment result
```

If the story cannot be followed without a developer explaining hidden details, the product is not presentation-ready.

---

# 29. V3 OPERATING PRINCIPLE

> **Humans make decisions; agents execute bounded work.**
>
> The human manual therefore tells the humans exactly what to check and when. The AI manual tells agents exactly what they may change, how they test it, how they recover, and when they must stop and request a human decision.


---

# V4 MASTER FREEZE — READ THIS BEFORE EVENT START

This section supersedes any conflicting operational detail elsewhere in the v3 manual.

## V4.1 Authoritative repository layout

The physical master workspace is:

```text
blackbox-datathon/
├── .opencodeconfig
├── git_stealth_sync.py
├── HUMAN_TEAM_RUNBOOK.md
├── P1_DATA_AGENT.md
├── P2_SIMULATION_AGENT.md
├── P3_GATE_AGENT.md
├── P4_ORCHESTRATION_AGENT.md
├── backend/
│   ├── main.py
│   ├── shared/
│   │   ├── schemas.py
│   │   └── config.py
│   ├── data/
│   ├── gate/
│   ├── simulation/
│   └── certificate/
├── frontend/
│   └── static/
├── tests/
│   ├── contract/
│   │   └── test_schemas_and_interfaces.py
│   ├── unit/
│   │   ├── test_data.py
│   │   ├── test_gate.py
│   │   ├── test_simulation.py
│   │   └── test_certificate.py
│   └── integration/
│       └── test_full_pipeline.py
├── docs/
├── evidence/
├── scripts/
├── requirements.txt
├── Dockerfile
└── README.md
```

The five top-level operational manuals are coordination artifacts. They do not replace the frozen runtime contracts.

## V4.2 Frozen foundation

These files are the shared source of truth and must be byte-identical across all four laptops before agents begin independent work:

```text
backend/shared/schemas.py
backend/shared/config.py
tests/contract/test_schemas_and_interfaces.py
```

### Frozen schema families

The schema authority includes:

- `Transaction`
- `Account`
- `EventContext`
- `GraphNode`
- `GraphEdge`
- `DependencyGraph`
- `ImpactSignals`
- `ImpactScore`
- `ForkResult`
- `FragilityResult`
- `RuntimeMetadata`
- `DecisionCertificate`

The frozen literals include:

```text
ForkResult.fork_name:
  normal | stress

ForkResult.scenario:
  3x_volume | fraud_spike | service_latency

DecisionCertificate.status:
  NO_SIMULATION | SIMULATED | REVIEW

DecisionCertificate.recommended_action:
  ALLOW_NORMAL_PATH | REVIEW | BLOCK_OR_HOLD
```

Transaction amounts must be strictly positive. All impact signals and the final impact score must be bounded to `[0,1]` by schema validation.

## V4.3 Frozen configuration matrix

```text
IMPACT_WEIGHTS:
  magnitude   = 0.30
  dependency = 0.30
  anomaly    = 0.25
  uncertainty= 0.15

IMPACT_THRESHOLD = 0.60
CONTEXT_WINDOW_SECONDS = 60
FRAGILITY_SEARCH_MIN = 1.0
FRAGILITY_SEARCH_MAX = 5.0
FRAGILITY_SEARCH_RESOLUTION = 0.05
REVIEW_MARGIN_THRESHOLD = 0.15
GLOBAL_RANDOM_SEED = 2026
```

The weights must sum to exactly `1.0` within the contract test.

## V4.4 Runtime metadata rule

`VERSION_METADATA` is configuration metadata. It must not be confused with the actual runtime host.

`/health` and request diagnostics must detect the active environment at runtime. A local Windows laptop must not claim `s390x`; a real LinuxONE run must report the actual architecture returned by the host.

Use platform detection such as:

```python
platform.system()
platform.machine()
```

The team must never fabricate LinuxONE evidence.

## V4.5 Fragility representation rule

The frozen `FragilityResult` schema contains numeric fields:

```text
scenario
breaking_threshold
unit
resolution
```

Therefore the core result must remain numeric and bounded. The human-readable sentence such as:

> survives through 2.40x, fails by 2.45x, resolution 0.05x

is presentation derived from those fields. Do not silently add an unapproved schema field merely to store a summary string.

## V4.6 Branch ownership

```text
p1-data:
  backend/data/
  docs/P1_DATA_HANDOFF.md
  CONTRACT_CHANGE_REQUEST.md

p2-simulation:
  backend/simulation/
  docs/P2_SIMULATION_HANDOFF.md
  CONTRACT_CHANGE_REQUEST.md

p3-gate:
  backend/gate/
  docs/P3_GATE_HANDOFF.md
  CONTRACT_CHANGE_REQUEST.md

p4-certificate:
  backend/certificate/
  frontend/
  backend/main.py
  docs/P4_ORCHESTRATION_HANDOFF.md
  CONTRACT_CHANGE_REQUEST.md
```

The shared foundation remains protected. Agents do not commit changes to `backend/shared/*` during normal feature development.

## V4.7 Git synchronization rule

The existing filename `git_stealth_sync.py` is retained for operational continuity, but its behavior is explicitly **ordinary, deterministic, and auditable**.

It must:

1. identify the current branch;
2. reject an unknown branch;
3. inspect `git status --short`;
4. stage only owned paths plus an explicitly permitted `CONTRACT_CHANGE_REQUEST.md`;
5. refuse to commit if nothing owned changed;
6. use the fixed branch-specific commit message;
7. push with `git push origin HEAD`;
8. use credentials supplied by the local Git credential system;
9. never contain passwords or tokens;
10. never spoof authorship, timestamps, or repository state.

A human must investigate unexpected out-of-boundary changes; the script must not stage them opportunistically.

## V4.8 Mandatory four-laptop preflight

Run on **all four laptops** from the repository root:

```powershell
git status
git branch --show-current
python --version
python -m compileall backend
python -m pytest tests/contract/test_schemas_and_interfaces.py -q
python -c "from backend.shared.schemas import *; from backend.shared.config import *; print('FOUNDATION: OK')"
python -c "from backend.shared.config import *; print('WEIGHTS =', IMPACT_WEIGHTS); print('THRESHOLD =', IMPACT_THRESHOLD); print('SCENARIOS =', SCENARIOS); print('SEED =', GLOBAL_RANDOM_SEED)"
```

Expected branch mapping:

```text
Laptop 1 → p1-data
Laptop 2 → p2-simulation
Laptop 3 → p3-gate
Laptop 4 → p4-certificate
```

Expected critical configuration:

```text
WEIGHTS = {'magnitude': 0.3, 'dependency': 0.3, 'anomaly': 0.25, 'uncertainty': 0.15}
THRESHOLD = 0.6
SCENARIOS = ('3x_volume', 'fraud_spike', 'service_latency')
SEED = 2026
```

If the contract test fails on any laptop, **do not launch that laptop's agent**.

## V4.9 Laptop 4 API sanity check

Before P4 begins full integration, confirm the server framework itself imports:

```powershell
python -m compileall backend
python -c "from backend.main import app; print('FASTAPI: OK')"
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

From a second PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

The response must report the actual local architecture.

The current skeleton is **not** considered the finished BLACKBOX pipeline merely because `/analyze` returns a placeholder certificate.

## V4.10 Unit-test policy

The initial test files may be scaffolds, but no agent may declare completion while substantive behavior tests remain as `assert True` placeholders.

Required real tests before integration freeze:

```text
P1:
  deterministic generation
  account/context linkage
  exactly five jointly-dangerous profiles
  60-second co-occurrence behavior

P2:
  fork isolation
  normal/stress pairing
  three scenario behaviors
  fragility bounded search

P3:
  normalization to [0,1]
  exact weighted equation
  0.60 routing boundary
  anomaly/uncertainty behavior

P4:
  certificate policy matrix
  /health
  /dashboard
  /analyze low-impact path
  /analyze simulated path
  REVIEW degradation
  trace/timing diagnostics
```

## V4.11 P4 orchestration order

P4 must not invent permanent replacements for unfinished P1/P2/P3 components.

When P1/P2/P3 have not yet merged:

```text
wait for contract-compatible branch
→ inspect actual exported interfaces
→ merge
→ run contract tests
→ integrate
→ run integration tests
```

Temporary mocks are allowed for isolated development and tests, but they must not silently remain on the production/demo path.

## V4.12 Official-rule preparation guardrail

Before the event, keep preparation limited to what the organizer's latest rules permit. Contract documentation, test specifications, environment setup, access, rehearsal, and compliance preparation are distinct from writing the substantive solution.

On the event day, implementation work must occur inside the permitted hacking window. The team must verify the latest organizer-published rules immediately before the event rather than relying on an old copy.

---

# V4.13 EVENT LAUNCH CHECKLIST — HUMAN ACTIONS ONLY

## T-60 to T-30 minutes

1. Verify the latest event rules.
2. Verify each team member is on only the intended team.
3. Verify all four laptops have power/network access.
4. Verify repository remote access.
5. Verify Git identity on every laptop.
6. Verify the four branches.
7. Verify `schemas.py`, `config.py`, and contract tests are identical.
8. Verify no unintended solution changes are already committed.

## T-30 to T-15 minutes

Run the four-laptop preflight exactly as written above.

Record:

```text
Laptop / branch / Python version / contract result / Git status
```

## T-15 to H0

1. Open OpenCode on each laptop.
2. Open the repository root.
3. Confirm the correct branch.
4. Confirm the correct agent manual is present.
5. Confirm the correct Mega-Prompt is ready.
6. Do not modify frozen shared files.
7. Launch agents only after all four foundations pass.

---

# V4.14 FOUR-LAPTOP ROLE CARD

| Laptop | Agent | Branch | Ownership | Primary proof |
|---|---|---|---|---|
| 1 | P1 | `p1-data` | `backend/data/*` | deterministic data + five joint cases |
| 2 | P2 | `p2-simulation` | `backend/simulation/*` | three attacks + fragility |
| 3 | P3 | `p3-gate` | `backend/gate/*` | exact gate math + calibration |
| 4 | P4 | `p4-certificate` | `backend/certificate/*`, `frontend/*`, `backend/main.py` | end-to-end pipeline + UI + runtime |

---

# V4.15 HUMAN MERGE PROCEDURE

When P1/P2/P3 are ready:

```powershell
git fetch --all
git checkout p4-certificate
git pull --ff-only origin p4-certificate
git merge origin/p1-data -m "Merge: integrating data module"
git merge origin/p3-gate -m "Merge: integrating gate module"
git merge origin/p2-simulation -m "Merge: integrating simulation module"
```

Then immediately run:

```powershell
python -m compileall backend
python -m pytest tests/contract/test_schemas_and_interfaces.py -q
python -m pytest tests/unit -q
python -m pytest tests/integration/test_full_pipeline.py -q
```

Only after the tests pass:

```powershell
git push origin p4-certificate
```

Do **not** have P1/P2/P3 repeatedly pull `p4-certificate` during independent development. Integrate at deliberate sync points.

---

# V4.16 FINAL MAINLINE AND LINUXONE PROCEDURE

Only after the experiment and integration are locked:

```powershell
git checkout main
git pull --ff-only origin main
git merge p4-certificate -m "release: BLACKBOX datathon prototype"
git push origin main
```

Then on LinuxONE:

```bash
uname -m
python3 --version
python3 -c "import numpy, pandas, sklearn, fastapi; print('DEPENDENCIES: OK')"
git pull --ff-only origin main
python3 -m compileall backend
python3 -m pytest tests/contract/test_schemas_and_interfaces.py -q
python3 -m pytest tests/unit -q
python3 -m pytest tests/integration/test_full_pipeline.py -q
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Verify:

```text
GET /health
GET /dashboard
POST /analyze
```

Capture the actual `uname -m` output as evidence.

---

# V4.17 HUMAN STOP CONDITIONS

Stop a sync and investigate when:

- a shared schema changes without approval;
- an agent modifies another agent's ownership directory;
- the contract suite fails after a merge;
- a test begins passing only because a placeholder/mocked component replaced the real implementation;
- LinuxONE is being represented without actual runtime evidence;
- a reproducibility seed/config changes after experiment lock;
- a submission artifact cannot be reproduced from the recorded commit.

The human manager is allowed to stop autonomous execution. Stopping an agent is not the default debugging mechanism.

---

# V4.18 HUMAN DEFINITION OF A CLEAN HANDOFF

A branch is cleanly handed over only when the human can answer:

```text
What files changed?
What interfaces changed?           → normally none
What tests passed?
What tests were not run?
What remains broken?
What assumptions does the next agent rely on?
What commit contains the work?
```

The handoff document is part of the engineering evidence, not administrative decoration.

---

# V4.19 HUMAN FINAL CONTROL CHECK

Before recording or submitting the demo, verify manually:

```text
[ ] The displayed architecture is the actual runtime architecture.
[ ] The displayed gate score came from the backend.
[ ] The selected transaction is deterministic.
[ ] The stress failure is real, not a frontend animation.
[ ] The certificate was generated by the certificate module.
[ ] BREAK MY DECISION triggers the actual /analyze route.
[ ] Fragility values match backend output.
[ ] Trace ID shown in UI matches API response.
[ ] Error path produces REVIEW or a truthful error, not fake success.
[ ] Experiment numbers correspond to the locked commit/config.
[ ] Git repository contains the exact code used for the demo.
[ ] LinuxONE evidence is from the actual target runtime.
```

# V4.20 FINAL HUMAN OPERATING PRINCIPLE

> **Humans control scope, contracts, compliance, merges, evidence, and final release. Agents control implementation, testing, diagnosis, and bounded local recovery. Neither side silently changes the contract.**
