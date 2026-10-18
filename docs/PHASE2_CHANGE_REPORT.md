# Phase 2 change report — research validation, gate diagnostics, integration

**Host:** AMD64 Windows, CPython 3.12.10 · **Backend:** numpy fallback · **Git:** unavailable  
**LinuxONE:** NOT VERIFIED (unchanged)

## What was inspected

- Full gate/experiment stack: `impact_gate.py`, `models.py`, `calibration.py`, `certificate.py`, `pipeline.py`, `schemas.py`, `config.py`
- Published evidence provenance (`evidence/results/validation/model_metadata.json` — sklearn, 2026-10-13)
- Prior OSS assessment, LinuxONE runbook, diagnostic scripts
- Reproduced: methodology fairness (same labels/k; raw-A vs ECDF-A top-k Jaccard=1.0)

## What was experimentally verified (validation only, numpy)

| Claim | Result |
|---|---|
| Gate underperforms anomaly-only | **Reproduced** (10%: 0.196 vs 0.529) |
| M non-informative (r≈0) at weight 0.30 | **Verified** (r=−0.008) |
| Window pressure predictive of failure | **Verified** (r=+0.237) |
| Interaction-aware candidate beats anomaly-only at 1/5/10% | **Verified** (0.098/0.412/0.627 vs 0.059/0.324/0.529) |
| Hypothesis (same budget, interaction-aware > anomaly-only) | **SUPPORTED_on_validation** (numpy only) |
| Harness leakage / metric bug | **Not found** |

Artifacts: `evidence/results/analysis/phase2_20261013T202326Z_numpy_validation/`

## Concrete defect?

**No frozen-math or harness defect.** Confirmed **parameter issue**: M weight 0.30 with zero failure correlation dilutes ranking. Changing weights requires **human T1 authorization** — not done.

## Files modified / added

| File | Change |
|---|---|
| `scripts/phase2_research_experiment.py` | **NEW** — diagnosis + interaction-aware experiment (validation/calibration CLI only) |
| `docs/GATE_DIAGNOSTIC_REPORT.md` | **NEW** — Phase 2 findings |
| `docs/RESEARCH_EXPERIMENT_PLAN.md` | **NEW** — hypothesis design + results |
| `docs/OPEN_SOURCE_COMPONENT_ASSESSMENT.md` | Phase 2 addendum (no new runtime deps) |
| `docs/STATUS.md` | Open issue 1 updated with Phase 2 verification labels |
| `tests/unit/test_phase2_diagnostics.py` | **NEW** — 8 methodology/regression tests |
| `evidence/results/analysis/phase2_*/` | **NEW** timestamped experiment bundle |
| `docs/DEBUG_LOG.md` | Session append |

**Not modified:** frozen weights/threshold/scenarios, schemas, published `evidence/results/validation/`, existing tests, production gate code paths.

## Commands and exit codes

| Command | Exit | Result |
|---|---|---|
| `python scripts/phase2_research_experiment.py` | 0 | SUPPORTED_on_validation |
| `python scripts/run_tests.py` | 0 | **75 passed, 0 failed** |
| `python -m pytest -q` | 0 | **75 passed**, 1 env warning |
| `python scripts/smoke_test.py` | 0 | all PASS incl. HTTP |
| Frozen + published evidence asserts | 0 | UNCHANGED / INTACT |

## Open-source components justified

**None new.** NetworkX/OpenTelemetry/Hypothesis remain defer/optional-dev per addendum. scikit-learn stays as already-integrated dual backend.

## LinuxONE

Still **NOT VERIFIED**. Phase 2 numbers are AMD64+numpy only. Target steps unchanged: `docs/LINUXONE_RUNBOOK.md`.

## Outstanding blockers / human authorization

1. **T1** — decide whether to change M/D definitions or weights (diagnosis provides evidence; no silent change).
2. **T2** — demo transaction story after T1.
3. Re-run Phase 2 driver on **sklearn** and **s390x** before generalizing.
4. Interaction-aware policy is **ranking research only** — not in production gate; adopting it needs explicit authorization and calibration-only protocol.
5. Git history still unavailable in the handoff tree.
