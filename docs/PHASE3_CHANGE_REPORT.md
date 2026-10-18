# PHASE3_CHANGE_REPORT

**Host:** AMD64 · CPython 3.12.10 · backend **numpy** · **Git:** unavailable  
**LinuxONE:** NOT VERIFIED  
**Evidence dir:** `evidence/results/analysis/phase3_20261013T204244Z_reproduction/`  
**Raw predictions SHA-256:** recorded in that dir’s `results.json` → `raw_artifacts.raw_predictions_sha256`

---

## Files added / modified

| Path | Change |
|---|---|
| `docs/PHASE3_ADOPTION_CRITERIA.md` | **NEW** — predeclared A1–A10 (written before robustness run) |
| `scripts/phase3_reproduce_and_robustness.py` | **NEW** — R1 rerun Phase 2, R2 raw dump, R3 independent recalc, R4 multi-seed + bootstrap, R5 sklearn attempt, R6 criteria |
| `tests/unit/test_phase3_ranking.py` | **NEW** — 12 tests (top-k, ties, determinism, label independence, recalc, bootstrap) |
| `docs/PHASE3_REPRODUCTION_REPORT.md` | **NEW** — audit + reproduction |
| `docs/PHASE3_ROBUSTNESS_REPORT.md` | **NEW** — multi-seed, uncertainty, criteria |
| `docs/PHASE3_CHANGE_REPORT.md` | **NEW** — this file |
| `docs/STATUS.md` | **UPDATED** — Phase 3 status block |
| `docs/DEBUG_LOG.md` | **UPDATED** — session append |
| `evidence/results/analysis/phase3_20261013T204244Z_reproduction/` | **NEW** — `results.json`, `README.md`, `raw_predictions.csv`, `phase2_rerun_results.json` |

**Not modified:** frozen weights/threshold/scenarios, schemas, `evidence/results/validation/`, Phase 2 bundle `phase2_20261013T202326Z_numpy_validation/`, production `ImpactGate` path, existing tests.

---

## Exact commands & exit codes

| # | Command | Exit | Result |
|---|---|---|---|
| 1 | `python scripts/phase3_reproduce_and_robustness.py` | **0** | 24.0s; verdict BACKEND-CONDITIONAL; Phase 2 numbers reproduced |
| 2 | `python scripts/phase2_research_experiment.py` (subprocess of #1) | **0** | rerun matches published ≤1e-9 |
| 3 | `python -m pytest tests/unit/test_phase3_ranking.py -q` | 0 | **12 passed** |
| 4 | `python scripts/run_tests.py` | **0** | **87 passed, 0 failed** |
| 5 | `python -m pytest -q` | 0 | **87 passed**, 1 env warning |
| 6 | `python scripts/smoke_test.py` | 0 | all PASS incl. HTTP |

---

## Key results (summary)

| Item | Result |
|---|---|
| Phase 2 interaction recall 0.098 / 0.412 / 0.627 | **REPRODUCED** within 1e-9 (raw recalc + unchanged rerun) |
| Cluster bootstrap inter−anomaly @ 5% | +0.087 CI [+0.018, +0.159] |
| Cluster bootstrap inter−anomaly @ 10% | +0.097 CI [+0.041, +0.162] |
| Multi-seed (6) | interaction/anomaly seed-invariant on numpy; gate wobbles via U only |
| sklearn cross-backend | **BLOCKED** (not installed; no substitution) |
| Adoption criteria | A1–A7, A10 **PASS**; A8 FAIL (backend); A9 FAIL (human) → **BACKEND-CONDITIONAL** |

---

## Unresolved / needs human or other environment

1. **A8** — re-run Phase 3 on sklearn (`pip install scikit-learn==1.9.1`, `BLACKBOX_MODEL_BACKEND=sklearn`).  
2. **A9** — human authorization before any production ranking change (T1 weight decision remains open).  
3. **LinuxONE** — runbook on real s390x; AMD64 does not establish compatibility.  
4. **Locked test** — still sealed; only after freeze rules + human unlock.  
5. Residual: jointly-dangerous recall ~0.13 for all methods at 10% budget.  
6. Git history still unavailable in handoff tree.

**No frozen constants changed. No production merge of interaction ranking.**
