# BLACKBOX — AI Agent Execution Manual v4
### 4 Windows OpenCode + MiMo V2.6 Flash Agents · Frozen Contracts · Autonomous Debugging · 24-Hour Build

---

# PART 0 — How This Manual Works

This document is the **machine-execution manual**.

It is written so an AI coding agent can:

- understand the complete system
- work independently inside a strict ownership boundary
- build against mocks before upstream components exist
- test its own work
- diagnose failures without waiting for a human
- hand over a stable interface to the next agent
- recover from integration failures in a deterministic way

## Golden rule

Every agent receives **Part 1 — Shared Runtime Contract** first.

Then it receives **only its own Part 2 role block**.

No agent is allowed to invent its own architecture, API names, schemas, scenario identifiers, or return types.

---

# PART 1 — SHARED RUNTIME CONTRACT

## 1.1 Frozen product

PROJECT: BLACKBOX — Enterprise Decision Preflight Engine

THEME: IBM Z Datathon 2026 — Theme 1, Real-Time AI for Critical Decisions

CORE IDEA:

> Score incoming transactions with a calibrated Impact Gate, selectively run counterfactual stress tests, measure fragility, and return an evidence-backed Decision Certificate.

TAGLINE:

> Don't predict the future. Test it first.

DEMO FEATURE:

> BREAK MY DECISION

---

# 1.2 Full Runtime Map

Every agent must understand this exact data flow.

```text
Browser
  │
  │ HTTP JSON
  ▼
GET /health       POST /analyze       GET /dashboard
  │                    │
  │                    ▼
  │              validate request
  │                    │
  │                    ▼
  │              build local context
  │                    │
  │                    ▼
  │              ImpactGate.score()
  │                    │
  │             ┌──────┴──────┐
  │             │             │
  │          low impact    high impact
  │             │             │
  │             │             ▼
  │             │      Local State Graph
  │             │             │
  │             │             ▼
  │             │    RealityForkGenerator
  │             │             │
  │             │             ▼
  │             │     CrashTestEngine.attack()
  │             │             │
  │             │             ▼
  │             │ FragilitySearch.find_threshold()
  │             │             │
  │             └──────┬──────┘
  │                    ▼
  │          Certificate.generate()
  │                    │
  │                    ▼
  └──────────── JSON DecisionCertificate
```

### Critical invariant

**Frontend never implements backend decision logic.**

**P4 orchestration never reimplements P1/P2/P3 algorithms.**

**P1/P2/P3 never modify P4's UI to compensate for an interface mismatch.**

A contract mismatch is fixed at the contract boundary, not hidden inside another component.

---

# 1.3 Repository Map

```text
blackbox/
├── backend/
│   ├── main.py
│   ├── shared/
│   │   ├── schemas.py
│   │   ├── config.py
│   │   ├── errors.py
│   │   └── diagnostics.py
│   ├── data/
│   │   ├── generator.py
│   │   ├── scenarios.py
│   │   ├── repository.py
│   │   └── sample_dataset.json
│   ├── gate/
│   │   ├── impact_gate.py
│   │   ├── models.py
│   │   └── calibration.py
│   ├── simulation/
│   │   ├── forks.py
│   │   ├── crash_test.py
│   │   └── fragility.py
│   └── certificate/
│       └── certificate.py
├── frontend/
│   └── static/
│       ├── index.html
│       ├── style.css
│       └── app.js
├── tests/
│   ├── unit/
│   ├── contract/
│   └── integration/
├── scripts/
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

P1 → `backend/data/*`

P2 → `backend/simulation/*`

P3 → `backend/gate/*`

P4 → `backend/certificate/*`, `frontend/*`, `backend/main.py`, Docker/deployment integration

Shared → `backend/shared/*`, contract tests, integration tests

---

# 1.4 Frozen Technology Constraints

Use:

- Python 3.11+
- FastAPI
- Pydantic v2
- NumPy/Pandas as required
- scikit-learn if the selected models install/run correctly on the LinuxONE environment
- plain HTML/CSS/JS
- JSON or SQLite only
- one application container

Do not introduce:

- frontend frameworks
- authentication
- accounts/login
- payment processing
- message queues
- Kubernetes
- microservices
- cloud databases
- LLM dependencies
- extra product components

The goal is integration reliability, not architectural complexity.

---

# 1.5 API Contract

### Local start command

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## `GET /health`

Return truthful runtime diagnostics.

Required fields:

```json
{
  "status": "ok",
  "runtime": "...",
  "architecture": "...",
  "version": "..."
}
```

## `GET /dashboard`

Return the frontend entrypoint.

## `POST /analyze`

Request contains:

```text
Transaction
EventContext
Demo mode flag
```

Response is:

```text
DecisionCertificate
```

All valid processing errors that prevent simulation/certification must degrade to a truthful `REVIEW` certificate rather than silently return a safe decision.

HTTP validation errors are handled separately.

---

# 1.6 Shared Schema Contract

Implement in `backend/shared/schemas.py`.

The exact model names are frozen:

```text
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

### Field-level reference implementation

The implementation may use equivalent Pydantic syntax, but these semantics and field names are frozen:

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class Transaction(BaseModel):
    id: str
    account_id: str
    amount: float
    timestamp: datetime
    transaction_type: str

class Account(BaseModel):
    id: str
    historical_avg_amount: float
    historical_std_amount: float
    related_account_ids: list[str] = Field(default_factory=list)

class EventContext(BaseModel):
    recent_transactions: list[Transaction] = Field(default_factory=list)
    local_dependency_load: dict[str, float] = Field(default_factory=dict)
    window_seconds: int = 60

class GraphNode(BaseModel):
    id: str
    node_type: Literal[
        "account", "transaction", "fraud_engine", "ledger",
        "payment_gateway", "risk_model", "notification",
        "settlement", "reporting"
    ]

class GraphEdge(BaseModel):
    source: str
    target: str

class DependencyGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]

class ImpactSignals(BaseModel):
    magnitude: float
    dependency: float
    anomaly: float
    uncertainty: float

class ImpactScore(BaseModel):
    transaction_id: str
    signals: ImpactSignals
    score: float
    gate_decision: bool

class ForkResult(BaseModel):
    fork_name: Literal["normal", "stress"]
    scenario: str
    survived: bool
    metrics: dict[str, float]

class FragilityResult(BaseModel):
    scenario: str
    breaking_threshold: float
    unit: str
    resolution: float

class RuntimeMetadata(BaseModel):
    runtime: str
    architecture: str
    model_versions: dict[str, str] = Field(default_factory=dict)
    random_seed: int | None = None
    git_revision: str | None = None

class DecisionCertificate(BaseModel):
    certificate_id: str
    trace_id: str
    status: Literal["NO_SIMULATION", "SIMULATED", "REVIEW"]
    transaction_id: str
    decision_description: str
    impact_score: ImpactScore
    forks_tested: list[ForkResult]
    fragility: list[FragilityResult]
    recommended_action: Literal[
        "ALLOW_NORMAL_PATH", "REVIEW", "BLOCK_OR_HOLD"
    ]
    evidence: list[str]
    runtime: RuntimeMetadata
```

If a field must change, treat that as a contract change and run the contract-change protocol. Do not patch around it silently.

## Graph node types

Use a single literal vocabulary. It must include every node type referenced by P1 scenario generation and simulation. Recommended frozen MVP vocabulary:

```text
account
transaction
fraud_engine
ledger
payment_gateway
risk_model
notification
settlement
reporting
```

Do not silently invent another spelling such as `fraud-service` or `payment-gw`.

## Fork semantics

`fork_name="normal"` = nominal execution.

`fork_name="stress"` = the same scenario applied to that nominal state.

These values are unrelated to the labels “Scenario A/B/C”.

## Scenario IDs

```text
3x_volume
fraud_spike
service_latency
```

## Important

Never use human prose as a protocol identifier when a frozen string exists.

---

# 1.7 Exact Backend Interfaces

These signatures are authoritative.

## P1

```python
DataRepository.load_context(transaction: Transaction) -> tuple[Account, DependencyGraph, EventContext]
```

```python
DatasetGenerator.generate_accounts(n: int) -> list[Account]
```

```python
DatasetGenerator.generate_transactions(accounts: list[Account], n: int) -> list[Transaction]
```

## P3

```python
ImpactGate.score(
    transaction: Transaction,
    account: Account,
    graph: DependencyGraph,
    context: EventContext,
) -> ImpactScore
```

```python
ImpactGate.should_simulate(score: ImpactScore) -> bool
```

## P2

```python
RealityForkGenerator.generate_baseline(
    transaction: Transaction,
    graph: DependencyGraph,
    context: EventContext,
) -> object
```

The returned baseline object is an internal simulation object. Do not make it an extra public API schema unless required.

```python
CrashTestEngine.attack(
    baseline_fork: object,
    scenario: str,
) -> list[ForkResult]
```

This returns exactly two logical outcomes for one scenario:

```text
normal
stress
```

```python
FragilitySearch.find_threshold(
    baseline_fork: object,
    scenario: str,
) -> FragilityResult
```

## P4

```python
CertificateGenerator.generate(
    transaction: Transaction,
    impact_score: ImpactScore,
    fork_results: list[ForkResult],
    fragility: list[FragilityResult],
    runtime: RuntimeMetadata,
) -> DecisionCertificate
```

All four agents must use these exact names.

---

# 1.8 Impact Gate Contract

Frozen formula:

```text
I(T) = 0.30M + 0.30D + 0.25A + 0.15U
threshold = 0.60
```

M = normalized transaction magnitude against account baseline.

D = normalized downstream dependency exposure.

A = normalized anomaly model output where larger = more anomalous.

U = normalized predictive disagreement/variance from a defined risk model.

All four signals must be `[0,1]` before weighting.

No agent may change weights or threshold without a synchronized team decision.

---

# 1.9 Simulation Contract

Exactly three scenarios:

```python
SCENARIOS = [
    "3x_volume",
    "fraud_spike",
    "service_latency",
]
```

For each scenario:

```text
baseline
   ↓
attack(baseline, scenario)
   ↓
normal result + stress result
```

Do not stress the state twice.

Failure thresholds live in `backend/shared/config.py`.

Threshold values must be frozen before the locked test evaluation.

---

# 1.10 Fragility Contract

A `FragilityResult` must communicate bounded knowledge:

```text
scenario
breaking_threshold
unit
resolution
```

Acceptable evidence:

```text
survives through 2.40x
fails by 2.45x
resolution 0.05x
```

Do not claim unsupported numerical precision.

---

# 1.11 Certificate Contract

The certificate is an evidence object.

Minimum content:

```text
certificate_id
trace_id
status
transaction_id
decision_description
impact_score
forks_tested
fragility
recommended_action
evidence
runtime metadata
```

Possible statuses:

```text
NO_SIMULATION
SIMULATED
REVIEW
```

Possible actions:

```text
ALLOW_NORMAL_PATH
REVIEW
BLOCK_OR_HOLD
```

Use this deterministic prototype policy:

```text
low-impact                    -> ALLOW_NORMAL_PATH
stress failure                -> BLOCK_OR_HOLD
no failure + low margin       -> REVIEW
no failure + adequate margin  -> ALLOW_NORMAL_PATH
internal processing failure   -> REVIEW
```

The review-margin value lives in `backend/shared/config.py`. The frontend only renders the returned action.

---

# 1.12 Diagnostics Contract

Every request receives a `trace_id`.

Every stage logs:

```text
trace_id
transaction_id
stage
status
elapsed_ms
```

Suggested stages:

```text
request_received
context_loaded
gate_scored
simulation_started
scenario_completed
fragility_completed
certificate_generated
response_sent
```

Errors should additionally record:

```text
error_type
error_message
owner
recovery_action
```

Do not log secrets or credentials.

---

# 1.13 Error Semantics

## Type A — Input validation

Examples:

- missing transaction ID
- invalid amount
- invalid timestamp

Result: HTTP validation error. Do not run business logic.

## Type B — Component failure

Examples:

- anomaly model unavailable
- simulation exception
- certificate construction exception

Result: create a truthful `REVIEW` certificate when enough information exists; otherwise return a structured 5xx response with `trace_id`.

## Type C — Contract mismatch

Examples:

- wrong argument name
- missing field
- enum mismatch
- wrong return type

Result: stop integration. Fix the interface owner. Do not write an adapter that permanently hides the mismatch unless the team explicitly approves it.

## Type D — Environment failure

Examples:

- package unavailable on s390x
- Docker build failure
- port unavailable

Result: classify as environment issue, run the prescribed compatibility checks, then apply the approved fallback.

---

# 1.14 Deterministic Demo Contract

The demo must be reproducible.

Use:

```text
fixed transaction ID
fixed random seed
fixed demo scenario
fixed configuration
```

The browser button `BREAK MY DECISION` must call the backend demo transaction; it must not create a new random transaction on every click.

---

# PART 2 — AGENT ROLES

Each agent receives the shared contract above plus ONE role below.

---

## P1 — DATA & CONTEXT AGENT

### Ownership

```text
backend/data/*
```

### Mission

Create deterministic synthetic enterprise state rich enough to test both obvious failures and jointly dangerous cases.

### Build order

1. `generator.py`
2. `scenarios.py`
3. `repository.py`
4. dataset validation tests
5. checked-in deterministic sample dataset

### Required data categories

- normal
- unusual-but-harmless
- obvious single-signal danger
- high-value / low-blast-radius
- low-value / high-blast-radius
- correlated anomalies
- dependency-chain failures
- jointly dangerous co-occurrences

### Jointly dangerous requirement

Explicitly construct cases where:

```text
transaction A individually looks normal
transaction B individually looks normal
A + B within the same local dependency/time window → stress failure
```

Do not rely on random generation.

### Acceptance tests

- schema validation passes
- generator is deterministic under a fixed seed
- graph contains all referenced node types
- jointly dangerous examples actually exist
- at least 5 hand-inspected jointly-dangerous cases do not have an obviously extreme single signal
- `EventContext` exposes enough recent state for the gate to reason about co-occurrence

### Do not

- implement the Impact Gate
- implement simulations
- change shared schemas without synchronization

### Handoff

Write `docs/P1_HANDOFF.md` containing:

```text
files
public APIs
seed
sample dataset size
category counts
tests run
known assumptions
known limitations
```

---

## P2 — FORKS & SIMULATION AGENT

### Ownership

```text
backend/simulation/*
```

### Mission

Turn a local baseline state into deterministic normal/stress comparisons and measurable fragility.

### Build order

1. baseline fork object
2. scenario attack
3. failure predicates
4. fragility search
5. unit tests

### Required interface

```python
RealityForkGenerator.generate_baseline(...)
CrashTestEngine.attack(...)
FragilitySearch.find_threshold(...)
```

### Attack semantics

For a single scenario:

```text
baseline
  ├── normal outcome
  └── one stressed outcome
```

Return exactly two logical `ForkResult` records.

### Acceptance tests

- one baseline can be attacked under all three scenarios
- six results exist for three scenarios
- normal and stress are distinct
- failure predicates are deterministic
- fragility search terminates
- fragility interval is honest about resolution

### Do not

- decide whether a transaction should be simulated
- modify the Impact Gate
- modify frontend logic

### Handoff

Write `docs/P2_HANDOFF.md` with:

```text
scenario definitions
failure thresholds
execution times
fragility resolution
unit tests
known limitations
```

---

## P3 — IMPACT GATE & AI AGENT

### Ownership

```text
backend/gate/*
```

### Mission

Implement the selective simulation policy and the models behind A/U without leaking test information.

### Build order

1. M
2. D
3. anomaly model A
4. uncertainty U
5. `ImpactGate.score()`
6. `should_simulate()`
7. calibration/evaluation tooling

### Model rules

A must be normalized to `[0,1]` with larger = more anomalous.

U must be derived from a defined predictive disagreement/variance procedure.

The normalization method must be frozen before the locked evaluation.

### Data discipline

Separate:

```text
calibration
validation
test
```

Never fit/tune on the locked test set.

### Acceptance tests

- score always `[0,1]`
- all four signals populated
- threshold logic deterministic
- same input + same seed → same result
- calibration/evaluation code records which split it used

### Experiment outputs

Produce:

```text
simulation_budget
failure_recall
false_negative_rate
simulation_avoidance
runtime
```

for:

```text
0.5%
1%
2%
5%
10%
100%
```

Also run baseline policies:

```text
random
amount_only
anomaly_only
BLACKBOX
```

### Do not

- modify the simulator to make the result look better
- tune weights after seeing locked-test results
- claim the weights are globally optimal

### Handoff

Write `docs/P3_HANDOFF.md` containing:

```text
model names
training/calibration split
normalization method
weights
threshold
experiment command
results location
known blind spots
```

---

## P4 — CERTIFICATE, FRONTEND & DEPLOYMENT AGENT

### Ownership

```text
backend/certificate/*
backend/main.py
frontend/*
Dockerfile
deployment notes
```

### Mission

Assemble the whole system without duplicating the algorithms of P1/P2/P3.

### Build order

1. static frontend shell
2. mock `/analyze`
3. certificate renderer
4. orchestration
5. integration test
6. Docker
7. LinuxONE deploy
8. evidence capture

### Frontend rules

The frontend only:

```text
collects
sends
renders
```

It does not decide.

### Required UI elements

- transaction identity
- Impact score
- M/D/A/U
- simulation decision
- BREAK MY DECISION
- scenario results
- fragility interval
- recommendation
- evidence
- trace ID
- runtime architecture

### Orchestration pseudocode

```python
validate_request()
context = load_context()
score = ImpactGate.score(...)

if not ImpactGate.should_simulate(score):
    return CertificateGenerator.generate(
        transaction,
        score,
        fork_results=[],
        fragility=[],
        runtime=runtime,
    )

baseline = RealityForkGenerator.generate_baseline(...)
all_results = []
fragility = []

for scenario in SCENARIOS:
    all_results.extend(CrashTestEngine.attack(baseline, scenario))
    fragility.append(FragilitySearch.find_threshold(baseline, scenario))

return CertificateGenerator.generate(...)
```

If any simulation stage fails, use the safe-review path and preserve the `trace_id`.

### Acceptance test

`POST /analyze` on the deterministic demo transaction must produce a valid `DecisionCertificate`.

### Deployment

Verify on LinuxONE:

```bash
uname -m
python3 --version
python3 -c "import numpy, pandas, sklearn, fastapi; print('OK')"
```

Then:

```text
build
start
/health
/analyze
/dashboard
```

Capture evidence only after the actual model path works.

### Do not

- reimplement P1/P2/P3 logic
- change schemas just to make orchestration easier
- hide exceptions with empty/default results

### Handoff

Write `docs/P4_HANDOFF.md` containing:

```text
routes
UI controls
container status
LinuxONE architecture proof
model inference proof
known deployment issues
```

---

# PART 3 — AUTONOMOUS DEBUGGING PROTOCOL

## 3.0 First-60-seconds diagnostic commands

From the repository root:

```bash
python -m pytest tests/contract -q
python -m pytest tests/integration -q
python scripts/smoke_test.py
```

When the app is running locally:

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/dashboard | head
```

On LinuxONE first check:

```bash
uname -m
python3 --version
python3 -c "import numpy, pandas, sklearn, fastapi; print('imports: OK')"
```

Then run the deterministic `/analyze` smoke test. Do not start changing code until the first failing command is known.


This protocol applies to every agent.

## Step 1 — Reproduce

Never patch based on a screenshot alone.

Create a minimal failing command/test.

## Step 2 — Find the first failing boundary

Use this order:

```text
browser
→ HTTP
→ validation
→ context
→ gate
→ simulation
→ certificate
→ response
```

The first failure is the target. Later failures may merely be symptoms.

## Step 3 — Classify

```text
SCHEMA
LOGIC
MODEL/DATA
INTEGRATION
DEPENDENCY
S390X/LINUXONE
FRONTEND
```

## Step 4 — Fix only your ownership

Do not edit another agent's component to work around a bug.

If a contract is genuinely wrong, stop and produce a contract-change request containing:

```text
current contract
observed failure
proposed change
affected agents/tests
```

## Step 5 — Test locally

Required sequence:

```text
unit test
→ contract test if interface touched
→ integration test if boundary touched
```

## Step 6 — Record

Append to `docs/DEBUG_LOG.md`:

```text
timestamp
trace_id
symptom
first failing stage
root cause
fix
files changed
tests passed
remaining risk
```

## Step 7 — Resume

Do not continue feature work until the test suite returns to green for the affected boundary.

---

# PART 4 — CONTRACT TESTS

The contract tests are the team's integration firewall.

At minimum test:

```text
Transaction validates
Account validates
Graph validates
ImpactScore stays in [0,1]
Gate decision matches threshold
ForkResult has normal/stress values
Scenario identifiers are exact
FragilityResult includes resolution
DecisionCertificate validates
```

## Full pipeline contract test

The canonical test shape is:

```python
transaction = demo_transaction()
account, graph, context = repository.load_context(transaction)

score = ImpactGate.score(transaction, account, graph, context)
assert 0 <= score.score <= 1

if score.gate_decision:
    baseline = RealityForkGenerator.generate_baseline(
        transaction, graph, context
    )
    results = []
    fragility = []

    for scenario in SCENARIOS:
        pair = CrashTestEngine.attack(baseline, scenario)
        assert len(pair) == 2
        results.extend(pair)
        fragility.append(
            FragilitySearch.find_threshold(baseline, scenario)
        )

cert = CertificateGenerator.generate(
    transaction,
    score,
    results if score.gate_decision else [],
    fragility if score.gate_decision else [],
    runtime_metadata(),
)

assert cert.transaction_id == transaction.id
assert cert.trace_id
assert cert.status in {"NO_SIMULATION", "SIMULATED", "REVIEW"}
if score.gate_decision:
    assert len(results) == len(SCENARIOS) * 2
    assert len(fragility) == len(SCENARIOS)
```

Run this after every synchronization point.

---

# PART 5 — 24-HOUR SYNCHRONIZATION PROTOCOL

The event is treated as exactly H0–H24.

**Authoritative sync rule:** the Sync 1–6 sequence and order in this section is the implementation authority for AI agents. The Team Manual describes the same sequence at human level. If the two manuals ever disagree, do not guess or silently choose one; stop, report the discrepancy, and resolve it before changing the contract.

| Sync | Time | Required state |
|---|---|---|
| Sync 1 | H1 | schemas + APIs frozen |
| Sync 2 | H3 | stub backend/frontend pipeline works |
| Sync 3 | H8 | data + gate integrated |
| Sync 4 | H14 | real simulation integrated |
| **Sync 5** | **H18** | **experiment frozen; locked test not changed after this point** |
| **Sync 6** | **H20** | **certificate + frontend + LinuxONE demo path frozen** |
| Final | H24 | submission-ready |

### Merge order

```text
shared contracts
→ data
→ gate
→ simulation
→ certificate
→ frontend
→ main/orchestration
→ deployment
```

Never merge a component that does not pass its acceptance test.

---

# PART 6 — AGENT RECOVERY MATRIX

## Symptom: `POST /analyze` returns 500

1. reproduce with deterministic demo
2. inspect `trace_id`
3. inspect first failing stage
4. run the owning unit test
5. rerun integration test

## Symptom: frontend displays stale result

Check:

```text
transaction_id binding
request lifecycle state
response replacement
loading flag reset
error state reset
```

Do not modify backend logic for a frontend state bug.

## Symptom: score is outside [0,1]

Check in order:

```text
M normalization
D normalization
A normalization
U normalization
weighting
clipping
```

Do not “fix” this in the frontend.

## Symptom: scenario name mismatch

Use exact IDs:

```text
3x_volume
fraud_spike
service_latency
```

Fix the caller or contract owner. Do not add aliases silently.

## Symptom: LinuxONE package failure

Check:

```bash
uname -m
python3 --version
python3 -m pip show <package>
```

Then test whether a supported package build exists for s390x. If not, activate the approved simpler statistical fallback and document it.

## Symptom: Docker works locally but fails on LinuxONE

Classify as architecture/environment failure first. Do not rewrite application logic until the container/runtime issue is proven.

---

# PART 7 — ENVIRONMENT / LINUXONE RULES

IBM materials describe IBM Z/LinuxONE as `s390x` and document active effort around s390x support across open-source software. The LinuxONE Community Cloud is described as a no-charge shared environment for testing applications on LinuxONE.

Therefore:

> **Laptop success does not prove LinuxONE success.**

The deployment smoke test is mandatory.

The actual application and its AI inference path must execute on the LinuxONE environment used for the demo.

Do not claim a runtime property you have not observed.

---

# PART 8 — EXPERIMENT EXECUTION

## Locked sequence

```text
build models
  ↓
calibrate using calibration split
  ↓
check validation split
  ↓
freeze configuration
  ↓
run locked test
  ↓
produce recall/budget results
```

After the locked test begins, do not modify:

- weights
- threshold
- model hyperparameters
- normalization method
- scenario thresholds

A result may be bad. It must still be reported accurately.

## Required baselines

Run:

```text
random selection
amount-only
anomaly-only
BLACKBOX
100% simulation
```

At fixed simulation budgets.

## Required outputs

```text
results.csv
recall_vs_budget.png
baseline_comparison.png
experiment_config.json
```

Record the random seed and git revision.

---

# PART 9 — TEST LAYERS

Every component should have three layers where applicable.

### Unit

Does the function work alone?

### Contract

Does it accept/return the frozen interface?

### Integration

Does it work when connected to the actual upstream/downstream stage?

No agent should report “done” because a unit test passes while integration is broken.

---

# PART 10 — GIT RULES

Branches:

```text
main
p1-data
p2-simulation
p3-gate
p4-certificate
```

Rules:

- small commits
- meaningful commit messages
- no force-push during event
- no merge with failing tests
- no edits outside ownership unless contract change is explicitly synchronized

Suggested commit format:

```text
P1: add deterministic transaction generator
P2: implement fraud spike attack
P3: normalize anomaly score
P4: wire analyze endpoint
```

---

# PART 11 — MINIMUM-HUMAN-INTERACTION POLICY

An agent may continue independently when:

- the problem is inside its ownership
- the contract is unchanged
- tests can verify the repair

A human is required only for:

1. contract/schema change
2. scope change
3. external credential/access failure
4. rules/compliance ambiguity
5. final submission decision

Everything else follows the autonomous debugging protocol.

---

# PART 12 — FINAL DEFINITION OF DONE

The AI team is done when:

```text
[ ] schemas frozen and validated
[ ] backend imports successfully
[ ] /health works
[ ] /dashboard works
[ ] deterministic demo transaction works
[ ] ImpactGate.score works
[ ] three scenarios work
[ ] fragility returns bounded result
[ ] certificate validates
[ ] frontend renders certificate
[ ] contract test passes
[ ] full integration test passes
[ ] experiment is locked and reproducible
[ ] LinuxONE runs actual backend/model path
[ ] evidence captured
[ ] README/architecture/library links complete
[ ] no hidden hardcoded safety claims
[ ] no known contract drift
```

---

# PART 13 — FINAL AGENT COMMANDMENT

> **Never guess the architecture. Never guess the contract. Never hide a failure. Reproduce it, locate the first failing boundary, repair the owning module, test it, record it, and continue.**

That is the operating system for the four-agent build.


---

# PART 14 — COMPLETE AGENT STARTUP PROTOCOL

Every coding agent must perform this sequence before editing implementation code.

## 14.1 Read order

```text
1. Shared Runtime Contract
2. Repository state
3. Your ownership block
4. Current tests
5. Current handoff/debug notes
```

Do not start by opening a random source file and guessing the architecture from it.

## 14.2 Repository inspection

Run:

```bash
git status --short
git branch --show-current
find backend frontend tests scripts docs -maxdepth 3 -type f | sort
python --version
```

Then run the smallest available contract test.

## 14.3 Baseline declaration

Before making changes, record mentally or in the handoff:

```text
CURRENT BRANCH
CURRENT TEST STATUS
FILES OWNED
UPSTREAM CONTRACTS REQUIRED
DOWNSTREAM CONTRACTS PROVIDED
```

If the baseline is already failing outside your ownership, do not silently claim your task caused or fixed it.

---

# PART 15 — COMPLETE AGENT STATE MACHINE

An agent always occupies one of these states:

```text
START
  ↓
INSPECT
  ↓
IMPLEMENT
  ↓
TEST
  ↓
READY

TEST FAILURE
  ↓
DIAGNOSE
  ↓
REPAIR
  ↓
TEST

CONTRACT CONFLICT
  ↓
BLOCKED_FOR_HUMAN

ENVIRONMENT FAILURE
  ↓
RECOVERY_ATTEMPT
  ↓
TEST
  ↓
BLOCKED_FOR_HUMAN if unresolved
```

An agent must never silently transition from `CONTRACT CONFLICT` to `IMPLEMENT`.

---

# PART 16 — DEFINITION OF READY FOR EACH COMPONENT

A component is not “done” merely because its main function exists.

## P1 Ready

```text
[ ] deterministic generator
[ ] schema-valid output
[ ] required scenario categories
[ ] jointly-dangerous cases
[ ] context loader
[ ] unit tests
[ ] contract tests
[ ] handoff
```

## P2 Ready

```text
[ ] baseline generation
[ ] all three exact scenario IDs
[ ] normal/stress pair for every scenario
[ ] deterministic failure predicates
[ ] bounded fragility result
[ ] unit tests
[ ] contract tests
[ ] handoff
```

## P3 Ready

```text
[ ] M
[ ] D
[ ] A
[ ] U
[ ] exact frozen formula
[ ] score range validation
[ ] calibration/validation/test separation
[ ] baseline experiment implementation
[ ] reproducible seed/config
[ ] handoff
```

## P4 Ready

```text
[ ] /health
[ ] /dashboard
[ ] /analyze
[ ] frontend state machine
[ ] certificate rendering
[ ] safe REVIEW path
[ ] deterministic demo
[ ] local container
[ ] LinuxONE verification
[ ] handoff
```

---

# PART 17 — COMPLETE FAILURE TAXONOMY

Use one category for every failure.

| Code | Category | Meaning | First owner |
|---|---|---|---|
| E001 | INPUT | invalid request/data | boundary owner |
| E002 | SCHEMA | Pydantic/contract mismatch | shared contract owner |
| E003 | GATE | M/D/A/U calculation failure | P3 |
| E004 | MODEL | model load/fit/inference failure | P3 |
| E005 | SIM | scenario/fork failure | P2 |
| E006 | FRAGILITY | threshold search failure | P2 |
| E007 | CERT | certificate construction failure | P4 |
| E008 | API | HTTP/orchestration failure | P4 |
| E009 | UI | browser rendering/state failure | P4 |
| E010 | DEP | package/runtime failure | environment owner |
| E011 | S390X | architecture-specific failure | P4 + owning component |
| E012 | DATA_LEAK | experiment contamination | P3 |
| E013 | CONTRACT_CHANGE | requested interface modification | human |
| E014 | ACCESS | credential/network/account issue | human |

Every logged failure should include the code and `trace_id` when applicable.

---

# PART 18 — COMPLETE DEBUGGING COMMAND LADDER

Agents must escalate diagnostics in this order.

## Level 0 — Static

```bash
python -m compileall backend
```

## Level 1 — Import

```bash
python -c "from backend.shared.schemas import *; print('schemas: OK')"
```

## Level 2 — Contract

```bash
python -m pytest tests/contract -q
```

## Level 3 — Unit

```bash
python -m pytest tests/unit -q
```

## Level 4 — Integration

```bash
python -m pytest tests/integration -q
```

## Level 5 — HTTP

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
curl -s http://127.0.0.1:8000/health
```

## Level 6 — deterministic transaction

Run the canonical demo script.

## Level 7 — container

```bash
docker build -t blackbox .
docker run --rm -p 8000:8000 blackbox
```

## Level 8 — LinuxONE

```bash
uname -m
```

Then repeat Levels 0–6 on the actual target environment.

Never jump directly to Level 8 when a Level 2 contract test already identifies the problem.

---

# PART 19 — CONTRACT-CHANGE PROTOCOL

A contract change is a controlled event.

The agent must create:

```text
CONTRACT_CHANGE_REQUEST.md
```

with:

```text
CURRENT CONTRACT:
WHY IT FAILS:
PROPOSED CONTRACT:
ALTERNATIVES CONSIDERED:
FILES AFFECTED:
TESTS AFFECTED:
WHY THE CHANGE IS NECESSARY:
```

Then stop.

Only the human team can authorize a contract change.

After approval:

```text
edit schemas
→ update contract tests
→ update all affected agent implementations
→ run full integration suite
→ record new contract version
```

No silent aliases. No compatibility hacks that hide a disagreement.

---

# PART 20 — HANDOFF PROTOCOL

Every agent must leave a machine-readable handoff.

File:

```text
/docs/P<N>_HANDOFF.md
```

Required sections:

```text
STATUS
FILES OWNED
FILES CHANGED
PUBLIC INTERFACES
INPUT ASSUMPTIONS
OUTPUT GUARANTEES
TEST COMMANDS
TEST RESULTS
KNOWN LIMITATIONS
KNOWN FAILURES
DEPENDENCIES
NEXT AGENT ACTION
CONTRACT CHANGE REQUESTS
```

The final line must be one of:

```text
READY_FOR_INTEGRATION
BLOCKED_BY_UPSTREAM
BLOCKED_BY_ENVIRONMENT
BLOCKED_BY_CONTRACT
```

---

# PART 21 — NO-HUMAN-INTERACTION RULES

An agent may autonomously:

- inspect its owned code;
- create/update its owned implementation;
- add tests;
- run tests;
- fix local bugs;
- inspect logs;
- reproduce failures;
- retry deterministic environment commands;
- update its handoff;
- prepare a contract-change request.

An agent must stop for a human when:

- a schema/API must change;
- a product component must be added/removed;
- the event rules may be violated;
- credentials/access must be provided;
- an external service requires authorization;
- the team must choose between incompatible architectural options;
- the agent cannot establish a reproducible failure after bounded diagnostics.

“Ask the human” is a terminal state, not the first debugging step.

---

# PART 22 — BOUNDED AUTONOMOUS RECOVERY

An agent may attempt at most three materially different local repairs for the same reproducible failure.

Each attempt must:

1. change one hypothesis, not random code;
2. run the smallest relevant test;
3. record the result.

After three failed hypotheses:

```text
STOP
→ classify
→ handoff
→ human escalation if required
```

This prevents an AI agent from endlessly rewriting working code while “trying things.”

---

# PART 23 — EXPERIMENT INTEGRITY LOCK

Once the team declares `EXPERIMENT_LOCKED`, agents are prohibited from modifying:

```text
Impact Gate weights
threshold
model hyperparameters
normalization procedure
scenario failure thresholds
test-set membership
random seed for published result
```

Allowed after lock:

- bug fixes that do not alter the experiment definition;
- presentation changes;
- logging;
- deployment fixes;
- README/evidence work.

If a bug changes an experimental result, the result must be regenerated and labeled as a new run. Never overwrite a published number silently.

---

# PART 24 — DETERMINISTIC ARTIFACTS

The following artifacts must be reproducible from a fixed seed/configuration:

```text
sample dataset
jointly-dangerous cases
model fitting where randomness exists
demo transaction
experiment results
```

Store the corresponding configuration/seed with the result.

The purpose is debugging, not merely presentation.

---

# PART 25 — OBSERVABILITY REQUIREMENTS

Every `/analyze` request should make it possible to answer:

```text
Which transaction?
Which trace?
Which gate score?
Which branch?
Which scenarios ran?
Which scenario failed?
What was the fragility interval?
Which model/configuration was used?
Where did time go?
Did an error occur?
```

The diagnostic record should contain stage timings approximately like:

```text
request_validation_ms
gate_ms
simulation_ms
fragility_ms
certificate_ms
total_ms
```

Do not log sensitive payloads unnecessarily.

---

# PART 26 — FRONTEND DEBUG CONTRACT

Frontend bugs must be diagnosable without guessing backend behavior.

The UI must expose in developer/debug view:

```text
transaction_id
trace_id
request status
HTTP status
certificate status
```

Frontend state must have one active request at a time for the MVP.

When a new request begins:

```text
clear old result
set loading=true
store current transaction_id
```

When it succeeds:

```text
loading=false
render only matching transaction_id
```

When it fails:

```text
loading=false
show error + trace_id
never display stale success data
```

---

# PART 27 — DEPLOYMENT RECOVERY PLAYBOOK

## Failure: image build fails

```text
capture exact package/error
→ identify architecture
→ check package availability
→ try supported dependency version
→ if approved fallback exists, use it
→ rerun build
```

## Failure: container starts but `/health` fails

```text
inspect logs
→ verify entrypoint
→ verify port
→ verify import path
→ run application directly
```

## Failure: `/health` works but `/analyze` fails

This is an application failure, not a deployment success. Return to the first failing backend stage.

## Failure: app works locally but model fails on LinuxONE

Classify as `E011 S390X` or `E010 DEP`. Do not rewrite unrelated application logic.

---

# PART 28 — FINAL AGENT EXIT CHECK

Before an agent stops, it must answer:

```text
1. What did I change?
2. Why did I change it?
3. What contract do I provide?
4. What tests prove it?
5. What is still uncertain?
6. Can another agent integrate me without asking questions?
```

If question 6 is “no,” improve the handoff before stopping.

---

# PART 29 — FINAL AI RULE

> **The agent manual is not a suggestion list. It is the executable specification. When implementation and manual disagree, the agent does not improvise: it stops at the boundary, records the discrepancy, and follows the contract-change protocol.**


---

# V4 FREEZE ADDENDUM — CURRENT MACHINE EXECUTION AUTHORITY

This addendum supersedes conflicting operational details in older versions of this manual.

## V4.1 Read order on every laptop

Before writing code, the agent must read in this exact order:

```text
1. .opencodeconfig
2. HUMAN_TEAM_RUNBOOK.md
3. backend/shared/schemas.py
4. backend/shared/config.py
5. tests/contract/test_schemas_and_interfaces.py
6. your role manual:
   P1_DATA_AGENT.md
   P2_SIMULATION_AGENT.md
   P3_GATE_AGENT.md
   P4_ORCHESTRATION_AGENT.md
7. existing owned source files
8. tests relevant to the owned component
```

The agent must not skip the shared contract because its own task appears simple.

## V4.2 Absolute frozen foundation

The following are protected during normal agent execution:

```text
backend/shared/schemas.py
backend/shared/config.py
tests/contract/test_schemas_and_interfaces.py
```

The agent may read them, import them, test against them, and report incompatibilities.

The agent may not:

- add fields;
- rename fields;
- change Literals;
- change validation rules;
- change mathematical weights;
- change the impact threshold;
- change the random seed;
- change scenario identifiers;
- add hidden aliases;
- monkey-patch the shared schema;
- bypass validation.

If the shared contract appears wrong, create `CONTRACT_CHANGE_REQUEST.md` and enter `BLOCKED_FOR_HUMAN`.

## V4.3 Exact frozen configuration

```text
IMPACT_WEIGHTS =
  magnitude: 0.30
  dependency: 0.30
  anomaly: 0.25
  uncertainty: 0.15

IMPACT_THRESHOLD = 0.60
CONTEXT_WINDOW_SECONDS = 60
FRAGILITY_SEARCH_MIN = 1.0
FRAGILITY_SEARCH_MAX = 5.0
FRAGILITY_SEARCH_RESOLUTION = 0.05
REVIEW_MARGIN_THRESHOLD = 0.15
GLOBAL_RANDOM_SEED = 2026

SCENARIOS =
  3x_volume
  fraud_spike
  service_latency
```

Never reconstruct these constants in individual modules.

## V4.4 Exact schema literals

```text
fork_name:
  normal | stress

scenario:
  3x_volume | fraud_spike | service_latency

certificate status:
  NO_SIMULATION | SIMULATED | REVIEW

recommended action:
  ALLOW_NORMAL_PATH | REVIEW | BLOCK_OR_HOLD
```

A string variation is a contract error, not a cosmetic difference.

## V4.5 Runtime truth rule

`VERSION_METADATA` must not be copied as if it were runtime detection.

Runtime code must obtain actual values using standard Python/platform inspection. Examples:

```python
platform.system()
platform.machine()
```

Local Windows may report an x86/x64 Windows architecture. LinuxONE should report the actual host architecture, typically `s390x` when that is what the target host returns.

Never fabricate `s390x` in `/health` or in evidence.

## V4.6 Fragility output rule

The frozen `FragilityResult` contains numeric fields only:

```text
scenario
breaking_threshold
unit
resolution
```

Do not add a `summary` field without a contract-change approval.

Presentation code may construct a bounded sentence from the numeric result, for example:

```text
survives through 2.40x, fails by 2.45x, resolution 0.05x
```

Never output false exactness when the search only establishes an interval.

## V4.7 Repository and ownership rules

```text
P1 → backend/data/*
P2 → backend/simulation/*
P3 → backend/gate/*
P4 → backend/certificate/*, frontend/*, backend/main.py
```

Permitted operational handoff paths:

```text
docs/P1_DATA_HANDOFF.md
docs/P2_SIMULATION_HANDOFF.md
docs/P3_GATE_HANDOFF.md
docs/P4_ORCHESTRATION_HANDOFF.md
CONTRACT_CHANGE_REQUEST.md
```

An agent must not modify another agent's implementation directory merely because a test fails there.

## V4.8 Git synchronization execution contract

The file may be named `git_stealth_sync.py`, but the behavior is ordinary and auditable.

The agent may run it only after its own acceptance tests pass.

Required behavior:

```text
branch detection
→ boundary filtering
→ explicit staging
→ fixed commit message
→ push origin HEAD
```

Credentials are supplied by the local Git credential manager/environment.

The script must never:

- embed credentials;
- print tokens;
- spoof author identity;
- alter timestamps to disguise activity;
- stage arbitrary out-of-boundary files;
- force-push;
- rewrite unrelated history.

## V4.9 Four-laptop preflight gate

Every agent must assume the human has run the shared preflight. If the agent is asked to proceed anyway, independently verify the foundation:

```powershell
git branch --show-current
python --version
python -m compileall backend
python -m pytest tests/contract/test_schemas_and_interfaces.py -q
python -c "from backend.shared.schemas import *; from backend.shared.config import *; print('FOUNDATION: OK')"
```

Expected branches:

```text
P1 → p1-data
P2 → p2-simulation
P3 → p3-gate
P4 → p4-certificate
```

If the branch is wrong, do not begin feature work.

## V4.10 Test ladder for every agent

Minimum before `READY`:

```text
python -m compileall backend
python -m pytest tests/contract/test_schemas_and_interfaces.py -q
python -m pytest tests/unit/<owned-test>.py -q
```

P4 additionally runs:

```text
python -m pytest tests/integration/test_full_pipeline.py -q
```

After integration, run all relevant test layers.

## V4.11 No placeholder completion

A test containing only:

```python
assert True
```

is a scaffold, not evidence of completion.

Before handoff, replace all owned placeholders with behaviorally meaningful assertions.

## V4.12 P1 execution contract

Implement only:

```text
backend/data/generator.py
backend/data/scenarios.py
backend/data/repository.py
backend/data/sample_dataset.json
```

Required behavior:

- deterministic generation from `GLOBAL_RANDOM_SEED`;
- account baseline information sufficient for M;
- graph/context information sufficient for D;
- realistic event-window context;
- exactly five distinct jointly-dangerous transaction profiles;
- each jointly-dangerous pair is individually plausible;
- paired danger is activated only under the intended 60-second context relationship;
- no schema invention to represent joint cases.

Acceptance evidence must show deterministic regeneration and the five required profiles.

## V4.13 P2 execution contract

Implement only:

```text
backend/simulation/forks.py
backend/simulation/crash_test.py
backend/simulation/fragility.py
```

For each scenario:

```text
one baseline
→ normal result
→ stress result
```

Never feed the stressed output back into another stress operation for the same attack.

Scenario IDs are exactly:

```text
3x_volume
fraud_spike
service_latency
```

Fragility search must remain bounded by config and return numeric `breaking_threshold` and `resolution` values that accurately reflect search resolution.

If the failure predicate is not monotonic enough to justify binary search, use the safest bounded search permitted by the configuration rather than inventing monotonicity.

## V4.14 P3 execution contract

Implement only:

```text
backend/gate/impact_gate.py
backend/gate/models.py
backend/gate/calibration.py
```

Required equation:

```text
I(T) = 0.30M + 0.30D + 0.25A + 0.15U
```

Required routing:

```text
score >= 0.60 → simulate
score <  0.60 → normal path
```

M, D, A, and U must be explicitly normalized to `[0,1]` before weighting.

The anomaly and uncertainty methods must be deterministic under the recorded configuration/seed when used for reproducible evaluation.

Do not claim weights or threshold are scientifically optimal. They are frozen prototype parameters.

## V4.15 P4 execution contract

Implement:

```text
backend/certificate/certificate.py
backend/main.py
frontend/static/index.html
frontend/static/style.css
frontend/static/app.js
```

The real production path is:

```text
request validation
→ DataRepository.load_context
→ ImpactGate.score
→ branch on should_simulate
→ if high impact:
      RealityForkGenerator.generate_baseline
      CrashTestEngine.attack for all 3 scenarios
      FragilitySearch.find_threshold for all 3 scenarios
→ CertificateGenerator.generate
→ response
```

The frontend must call the backend and render returned values. It may not calculate the decision itself.

`GET /health` must be truthful.

`GET /dashboard` must serve the actual generated frontend.

`POST /analyze` must return a valid `DecisionCertificate` when processing succeeds.

When an internal component fails but enough context exists, return a truthful `REVIEW` certificate rather than falsely returning `ALLOW_NORMAL_PATH`.

## V4.16 P4 startup dependency rule

Before P1/P2/P3 branches are merged, P4 may use mocks to build and test its own frontend/orchestration shell.

After the branches are merged:

```text
remove production-path mocks
→ import actual implementations
→ run contract tests
→ run integration test
→ run deterministic demo
```

A mock that remains on the demonstrated production path is a release blocker.

---

# V4.17 MACHINE-SIDE LAUNCH PROMPTS

Use the corresponding block as the final OpenCode launch instruction.

## P1 launch prompt

```text
You are P1, the Data & Context Agent on branch p1-data.
Read .opencodeconfig, HUMAN_TEAM_RUNBOOK.md, backend/shared/schemas.py, backend/shared/config.py, tests/contract/test_schemas_and_interfaces.py, and P1_DATA_AGENT.md before editing.

Frozen files are read-only: backend/shared/schemas.py, backend/shared/config.py, tests/contract/test_schemas_and_interfaces.py.

Own only backend/data/* plus your handoff document and CONTRACT_CHANGE_REQUEST.md when needed.

Implement generator.py, scenarios.py, repository.py, and sample_dataset.json.
Use GLOBAL_RANDOM_SEED for deterministic generation.
Create exactly five distinct jointly-dangerous transaction profiles whose isolated observations are plausible and whose paired behavior is activated by the intended 60-second context relationship.

Test in this order:
1. python -m compileall backend
2. python -m pytest tests/contract/test_schemas_and_interfaces.py -q
3. python -m pytest tests/unit/test_data.py -q
4. add/re-run focused deterministic tests for the five profiles

Do not alter the shared contract. On a true contract conflict, create CONTRACT_CHANGE_REQUEST.md and stop.

Only after tests are green, update docs/P1_DATA_HANDOFF.md and run python git_stealth_sync.py.
```

## P2 launch prompt

```text
You are P2, the Forks & Simulation Agent on branch p2-simulation.
Read .opencodeconfig, HUMAN_TEAM_RUNBOOK.md, backend/shared/schemas.py, backend/shared/config.py, tests/contract/test_schemas_and_interfaces.py, and P2_SIMULATION_AGENT.md before editing.

Frozen files are read-only.
Own only backend/simulation/* plus your handoff document and CONTRACT_CHANGE_REQUEST.md when needed.

Implement forks.py, crash_test.py, and fragility.py.
Support exactly 3x_volume, fraud_spike, service_latency.
For each scenario return one normal result and one stress result from the same baseline. Do not double-stress.
Keep fragility bounds and resolution controlled by config.py and never claim unsupported precision.

Test in this order:
1. compileall
2. contract tests
3. unit simulation tests
4. deterministic scenario tests
5. fragility boundary tests

On contract conflict, create CONTRACT_CHANGE_REQUEST.md and stop.
Only after tests are green, update docs/P2_SIMULATION_HANDOFF.md and run python git_stealth_sync.py.
```

## P3 launch prompt

```text
You are P3, the Impact Gate & AI Agent on branch p3-gate.
Read .opencodeconfig, HUMAN_TEAM_RUNBOOK.md, backend/shared/schemas.py, backend/shared/config.py, tests/contract/test_schemas_and_interfaces.py, and P3_GATE_AGENT.md before editing.

Frozen files are read-only.
Own only backend/gate/* plus your handoff document and CONTRACT_CHANGE_REQUEST.md when needed.

Implement impact_gate.py, models.py, and calibration.py.
Use the exact equation I(T)=0.30M+0.30D+0.25A+0.15U and the 0.60 routing threshold.
Normalize each signal to [0,1] before applying weights. Do not hide unbounded values behind schema clipping.

Test in this order:
1. compileall
2. contract tests
3. unit gate tests
4. exact weighted equation tests
5. boundary tests around 0.60
6. deterministic model/calibration tests

Do not silently tune weights, threshold, or normalization after experiment lock.
On contract conflict, create CONTRACT_CHANGE_REQUEST.md and stop.
Only after tests are green, update docs/P3_GATE_HANDOFF.md and run python git_stealth_sync.py.
```

## P4 launch prompt

```text
You are P4, the Master Orchestration Agent on branch p4-certificate.
Read .opencodeconfig, HUMAN_TEAM_RUNBOOK.md, backend/shared/schemas.py, backend/shared/config.py, tests/contract/test_schemas_and_interfaces.py, and P4_ORCHESTRATION_AGENT.md before editing.

Frozen files are read-only.
Own backend/certificate/*, frontend/*, and backend/main.py plus your handoff document and CONTRACT_CHANGE_REQUEST.md when needed.

Build the orchestration and UI against the frozen interfaces. Use platform.machine() and platform.system() for truthful runtime diagnostics. Never claim s390x on a non-s390x host.

Before P1/P2/P3 merge, use mocks only in isolated development/tests.
After their branches merge, remove production-path mocks and wire the real implementations.

Build GET /health, GET /dashboard, POST /analyze.
The analyze path must validate, load context, score, branch, simulate when required, run fragility, generate a certificate, and return truthful output.
Internal processing failures should degrade to REVIEW when a valid certificate can still be constructed.

Test in this order:
1. compileall
2. contract tests
3. certificate unit tests
4. integration tests
5. local HTTP smoke test
6. deterministic demo
7. Docker smoke test when available
8. LinuxONE verification after deployment

On contract conflict, create CONTRACT_CHANGE_REQUEST.md and stop.
Only after tests are green, update docs/P4_ORCHESTRATION_HANDOFF.md and run python git_stealth_sync.py.
```

---

# V4.18 AGENT EXIT REPORT

Before stopping, every agent must produce its handoff document with:

```text
STATUS
FILES OWNED
FILES CHANGED
PUBLIC INTERFACES
INPUT ASSUMPTIONS
OUTPUT GUARANTEES
TEST COMMANDS
TEST RESULTS
KNOWN LIMITATIONS
KNOWN FAILURES
DEPENDENCIES
NEXT AGENT ACTION
CONTRACT CHANGE REQUESTS
COMMIT
```

Final status line must be exactly one of:

```text
READY_FOR_INTEGRATION
BLOCKED_BY_UPSTREAM
BLOCKED_BY_ENVIRONMENT
BLOCKED_BY_CONTRACT
```

---

# V4.19 RELEASE-BLOCKING CONDITIONS

The agent must not report `READY_FOR_INTEGRATION` when:

- its unit tests only contain placeholders;
- a frozen schema/config was changed;
- a public interface differs from the contract;
- a failure is hidden with a broad exception that reports success;
- a mock remains on the demonstrated production path;
- runtime metadata is fabricated;
- a deterministic artifact cannot be reproduced;
- the branch contains unowned implementation changes;
- a test was skipped solely because it was inconvenient.

---

# V4.20 FINAL MACHINE COMMANDMENT

> **Read the contract. Own the boundary. Implement deterministically. Test the smallest failing layer first. Repair only inside ownership. Never conceal a contract conflict. Never fabricate runtime evidence. Never call a placeholder a finished feature.**
