# Open-source component assessment — BLACKBOX

**Scope:** assessment only. No new runtime dependency is introduced by this
document. Frozen gate behavior (`IMPACT_WEIGHTS`, `IMPACT_THRESHOLD`,
scenarios, schemas, decision policy) is unchanged. Integrating any candidate
into the scoring path requires explicit human authorization (`AGENTS.md` §5,
§6: no new dependencies without a change request).

**Prepared for:** external code review / open-source integration assessment
(IBM Z Datathon 2026, Theme 1).  
**Host of analysis:** AMD64 Windows, CPython 3.12.10, scikit-learn **not**
installed on this host (NumPy model backend selected automatically).  
**LinuxONE/s390x execution: NOT VERIFIED** for the project and for every
candidate below unless noted. Mentions of s390x in Dockerfiles or package
READMEs are not evidence of a successful local s390x install.

Existing project licenses posture (see `README.md`): FastAPI (MIT), Uvicorn
(BSD-3-Clause), Pydantic (MIT), NumPy (BSD-3-Clause), scikit-learn (BSD-3),
pytest (MIT), httpx (BSD-3-Clause). Verify license strings against upstream
project pages before submission and record the date in `evidence/claims.md`.

---

## Candidate 1 — NetworkX (dependency graph algorithms)

| Field | Assessment |
|---|---|
| License | BSD-3-Clause |
| What it would touch | `backend/shared/context_utils.py` (`reachable_services`, `reachable_accounts`), `backend/gate/models.py` (`criticality_share`), graph construction in `backend/data/repository.py` / generator |
| Current implementation | Frozen `DependencyGraph` schema is a plain list of `GraphNode` / `GraphEdge`. Reachability is a small custom BFS/DFS over those lists. Criticality share is a deterministic weighted sum over reachable service names using `config.CRITICALITY`. |
| Benefit | Richer algorithms (centrality, community, path enumeration) *if* a future T1 option needs them. Marginal for current D, which only needs reachable sets + weights. |
| LinuxONE/s390x | Pure Python; expected to import on s390x where CPython runs. **Not demonstrated on this host against s390x.** No official s390x wheel guarantee; pure-Python sdists typically install. Uncertainty remains until a real s390x `pip install networkx` is logged. |
| Performance / deployment | Adds a dependency for O(V+E) work that is already cheap at this scale (single-transaction local graph, tens of nodes). Slight import-time cost. |
| Output / decision risk | **Medium-high if D is recomputed differently.** Even a “correct” graph library can change traversal order or tie-breaking and alter D floats, which changes gate scores and ranking. Must be gated behind a human T1 decision and proven with validation-only experiments. |
| Recommendation | **DEFER.** Useful later for experimental graph features (T1 option A), not justified now. If adopted later: pin a version, keep the frozen schema, wrap reachability behind a pure function with golden tests on fixed graphs. |

## Candidate 2 — scikit-learn (anomaly detection + classification)

| Field | Assessment |
|---|---|
| License | BSD-3-Clause |
| What it would touch | Already integrated: `backend/gate/models.py` (`_SklearnAnomaly` IsolationForest, `_SklearnRisk` RandomForestClassifier) behind `resolve_backend()` |
| Current implementation | First-class backend when `import sklearn` succeeds; NumPy fallback (`RobustMahalanobis`, `BaggedLogisticRegression`) when it does not. `GateModels.fit` refuses non-calibration splits (`DataLeakError`). |
| Benefit | Already the backend behind the **published** validation evidence (`evidence/results/validation/model_metadata.json`: scikit-learn 1.9.1). Better-established models for A/U than the fallback. |
| LinuxONE/s390x | **Partially evidenced, not project-verified.** Upstream scikit-learn publishes Linux s390x support in some release lines (conda-forge / distro packages appear for s390x), but **this project has never installed or run scikit-learn on s390x**. Dockerfile already documents the failure mode and `BLACKBOX_MODEL_BACKEND=numpy` fallback. Uncertainty: wheel availability for the exact Python version on the target VM. |
| Performance / deployment | Heavier install (compilation possible on s390x if no wheel). Fit time on 2,501 calibration rows is small (sub-second to a few seconds). Must report which backend ran in every certificate (`model_versions.backend`) — already done. |
| Output / decision risk | **High if the active backend changes.** sklearn vs numpy already produce different A/U, rankings, and threshold-selected sets (`docs/BACKEND_EVIDENCE.md`). Switching backends without labeling misleads comparisons. Decision *policy* code is backend-independent; scores are not. |
| Recommendation | **ADOPT (already adopted) / keep dual-backend.** On LinuxONE, attempt sklearn install; if blocked, use the documented NumPy fallback and say so in evidence. Never silently treat fallback metrics as sklearn metrics. Pin `scikit-learn>=1.4` as today; record exact version in certificates. |

## Candidate 3 — OpenTelemetry (runtime tracing / observability)

| Field | Assessment |
|---|---|
| License | Apache-2.0 (core); exporters vary |
| What it would touch | `backend/shared/diagnostics.py` (context-var `trace_id`, `stage()` context manager, JSON lines on stderr, `RECENT_EVENTS` deque), FastAPI middleware if added |
| Current implementation | Lightweight, dependency-free tracing: every request gets `TR-…` id; stages log `trace_id, transaction_id, stage, status, elapsed_ms` as JSON; integration test `test_trace_and_stage_timing_diagnostics` asserts stage coverage. |
| Benefit | Standard spans, exporters (OTLP/Jaeger), cross-service correlation if BLACKBOX is ever embedded in a larger Z estate demo. |
| LinuxONE/s390x | OpenTelemetry Python is pure Python for the API/SDK core; expected to install where CPython works. **Not verified on s390x for this project.** Exporter binaries/OTLP endpoints are environment-dependent. |
| Performance / deployment | Adds several packages (`opentelemetry-api`, `-sdk`, possibly `-instrumentation-fastapi`). Non-trivial dependency surface for a hackathon prototype that must also run offline on a single VM. |
| Output / decision risk | **Low for gate scores** (observability only) if adapters wrap existing `stage()` calls without changing business logic. **Medium for ops**: exporters may attempt network egress; must default to console/no-op on air-gapped LinuxONE guests. |
| Recommendation | **PROTOTYPE (optional, out of band) or DEFER.** Keep the existing JSON stage log as the contract used by tests. If prototyping: add an optional extra (`requirements-observability.txt`), map `diagnostics.stage` → OTel spans, default exporter = none, do not change log fields tests rely on. Not required for Datathon scoring credibility. |

## Candidate 4 — Hypothesis (property-based testing)

| Field | Assessment |
|---|---|
| License | MPL-2.0 (Hypothesis); note copyleft-style file-level terms — acceptable in many corp policies but worth a human license review for IBM event rules |
| What it would touch | New tests under `tests/` only (e.g. `tests/property/`); does not touch backend runtime |
| Current implementation | Example-based pytest suite (67 tests) + dependency-free `scripts/run_tests.py`. Properties partially encoded as examples (normalization to [0,1], monotonicity of failure predicates, determinism under seed). |
| Benefit | Stronger guarantees for invariants: signals ∈ [0,1] for random amounts/graphs; fragility monotonicity; schema round-trips; no crash on edge amounts. Could catch rare regressions before locked-test. |
| LinuxONE/s390x | Pure Python; expected importable on s390x. **Not verified here.** Dev-only dependency — does not affect the Docker runtime image if kept out of `requirements.txt`. |
| Performance / deployment | Slower CI (example generation). Mitigate with `derandomize=True` / explicit seeds and modest `max_examples`. Must not be required for `scripts/run_tests.py` on minimal targets. |
| Output / decision risk | **None on production scores** (tests only). Risk is false confidence if properties are written loosely, or if `run_tests.py` (no Hypothesis) and pytest diverge in coverage. |
| Recommendation | **PROTOTYPE (dev-only).** Add `hypothesis` to `requirements-dev.txt` only after human license OK; write a small property module for `_clip01` / magnitude bounds / fragility monotonicity; keep core examples in the existing 67 so the minimal runner stays sufficient. Do not delete example tests. |

---

## Summary table

| Candidate | Touched code today | License | s390x evidence | Decision risk | Recommendation |
|---|---|---|---|---|---|
| NetworkX | custom BFS in `context_utils` / `criticality_share` | BSD-3 | unverified (pure Python expected) | Medium-high on D | **DEFER** |
| scikit-learn | already in `models.py` + numpy fallback | BSD-3 | unverified on *this* project’s s390x target; fallback exists | High if unlabeled backend switch | **ADOPT (already) / keep fallback** |
| OpenTelemetry | would wrap `diagnostics.py` | Apache-2.0 | unverified (pure Python expected) | Low on scores; medium on ops | **PROTOTYPE optional / DEFER** |
| Hypothesis | would add `tests/` only | MPL-2.0 (review) | unverified (pure Python expected) | None on runtime | **PROTOTYPE dev-only** |

## What was deliberately not done

- No candidate was `pip install`ed into the project environment as a new runtime dependency.
- No gate, simulation, schema, or decision-rule code path was changed for “modernization.”
- No LinuxONE compatibility claim is made for NetworkX, OpenTelemetry, Hypothesis, or a fresh scikit-learn install on s390x.
- No dependency was added solely to make the architecture look more sophisticated.

## Authorization path (if the team later wants integration)

1. Write `docs/CONTRACT_CHANGE_REQUEST.md` (AGENTS §7) naming the candidate, files, and risk to scores.
2. Human decision; pin versions; record licenses in `evidence/claims.md`.
3. Integrate behind existing seams (`resolve_backend`, diagnostics adapters, test-only).
4. Re-run validation split experiments with backend/package labels; never overwrite `evidence/results/validation/`.
5. Only after freeze rules (TASKS T5) consider locked-test impact.

---

## Phase 2 addendum (evidence from gate diagnosis — 2026-10)

Re-inspected code after `docs/GATE_DIAGNOSTIC_REPORT.md` and the interaction-aware
experiment (`scripts/phase2_research_experiment.py`):

| Candidate | Phase 2 finding | Updated recommendation |
|---|---|---|
| **NetworkX** | Interaction-aware ranking used only arithmetic on existing `extract_features` vectors (window pressure, load pressure). No graph traversal beyond the current BFS was required to beat anomaly-only on validation (numpy). | **DEFER** reinforced — no demonstrated need for mature graph algorithms in the diagnosed failure modes. |
| **scikit-learn** | Diagnosis ran on the **numpy** fallback; published evidence is sklearn. Backend gap remains material (`docs/BACKEND_EVIDENCE.md`). | **ADOPT (already)** / keep dual-backend labeling; re-run Phase 2 driver on sklearn before generalizing. |
| **OpenTelemetry** | Phase 2 experiment elapsed ~3s offline; no multi-service trace need surfaced. | **DEFER** reinforced for the prototype. |
| **Hypothesis** | New methodology tests (`tests/unit/test_phase2_diagnostics.py`) are example-based; properties like score∈[0,1] and label-independence of the interaction scorer are explicit asserts. | **PROTOTYPE dev-only** still appropriate if the team wants generated edge cases; not required for the Phase 2 conclusions. |

No Phase 2 finding justifies adding a new **runtime** dependency.

