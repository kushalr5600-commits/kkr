# Contracts (mirror of `backend/shared/schemas.py` and `config.py`)

If this file and `schemas.py` ever differ, `schemas.py` wins - then fix this file. The contract test
`tests/contract/test_schemas_and_interfaces.py` enforces names, fields, enums and callable signatures.

Models: Transaction, Account, EventContext, GraphNode, GraphEdge, DependencyGraph, ImpactSignals, ImpactScore,
ForkResult, FragilityResult, RuntimeMetadata, DecisionCertificate.

Interfaces:

```python
DataRepository.load_context(transaction) -> (Account, DependencyGraph, EventContext)
DatasetGenerator.generate_accounts(n) / generate_transactions(accounts, n)
ImpactGate.score(transaction, account, graph, context) -> ImpactScore
ImpactGate.should_simulate(score) -> bool
RealityForkGenerator.generate_baseline(transaction, graph, context) -> BaselineFork   # internal object
CrashTestEngine.attack(baseline_fork, scenario) -> [ForkResult(normal), ForkResult(stress)]
FragilitySearch.find_threshold(baseline_fork, scenario) -> FragilityResult
CertificateGenerator.generate(transaction, impact_score, fork_results, fragility, runtime) -> DecisionCertificate
CertificateGenerator.generate_review(transaction, impact_score|None, reason, runtime, ...) -> DecisionCertificate
```

## Gate policy (reverse-checked against `config.py`)

Frozen reference policy:

    I(T) = 0.30*M + 0.30*D + 0.25*A + 0.15*U      threshold = 0.60
    POLICY_VERSION = 1.0.0
    SCENARIOS = 3x_volume, fraud_spike, service_latency

Interaction-aware ranking (human-authorized 2026-10-16, disclosed in
`docs/submission/DISCLOSURES.md` section 2; now the production ranking policy):

    I(T) = 0.45*A + 0.30*W + 0.15*D + 0.10*L      threshold = 0.60

    runtime override: `BLACKBOX_INTERACTION = on | off | auto`
    (default from `config.INTERACTION_AWARE_ENABLED`; `off` reproduces the
    frozen reference gate exactly)

`tests/contract/test_docs_match_code.py` parses this section and compares every
value against `backend/shared/config.py`, and enforces the HTTP route table
below in both directions, so documentation cannot drift silently from the code.

HTTP (every route registered on `backend.main:app`):

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | redirect to `/dashboard` |
| GET | `/health` | `{status, runtime, architecture, version, model_backend, gate_threshold, policy_version, policy_mode, policy_formula, python}` (+ otel/dataset_studio/openml_client) |
| GET | `/dashboard` | static frontend |
| GET | `/transactions` | UI helper: demo + showcase transactions |
| POST | `/analyze` | `{transaction?, context?, demo_mode}` -> `DecisionCertificate` |
| POST | `/explain` | analyze + Explainable Decision Explorer payload |
| POST | `/research/what-if` | research-only hypothetical re-score (never persisted as a decision) |
| GET | `/counterexample/{transaction_id}` | showcase missed-failure with independent stress measurement |
| GET | `/datasets` | list uploaded datasets |
| POST | `/datasets/upload` | CSV/Parquet upload (multipart) |
| GET | `/datasets/registry` | curated open-dataset registry (metadata only) |
| GET | `/datasets/{dataset_id}` | metadata + preview rows |
| POST | `/datasets/{dataset_id}/map` | column mapping |
| DELETE | `/datasets/{dataset_id}` | remove upload |
| POST | `/datasets/{dataset_id}/evaluate` | Challenge Lab gate-selection benchmark |
| GET | `/experiments` | recent experiment reports (in-memory ring) |
| GET | `/experiments/{run_id}` | one experiment report |

`tests/contract/test_docs_match_code.py` enforces this table in BOTH directions
(every registered route is documented here; every route documented here is
registered). Errors: malformed input -> 422 with `trace_id`; internal failure ->
REVIEW certificate; only if even that is impossible -> 500 with `trace_id`.

Encodings that the frozen schema forces: fragility "never failed in range" = `unit == "x_intensity_lower_bound"`
with `breaking_threshold == MAX_INTENSITY`; failing at nominal load = `breaking_threshold == 1.0`; limitations =
evidence lines starting `LIMITATION: `.
