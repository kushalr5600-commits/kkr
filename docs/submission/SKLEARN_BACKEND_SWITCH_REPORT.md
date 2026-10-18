# Scikit-learn Backend Switch & Re-Verification Report

**Date:** 2026-10-15
**Host:** AMD64 Windows (10.0.19045) · CPython 3.12.10 · machine `AMD64` (not LinuxONE)
**Backend now active:** `sklearn` (scikit-learn 1.9.1) with NumPy fallback retained
**Trigger:** explicit human approval to make scikit-learn the primary model backend and re-verify.

---

## 1. What changed

The model backend was always `auto` (`backend/gate/models.py:94`): use scikit-learn
if importable, else the documented NumPy fallback. scikit-learn was simply **not
installed** on this host, so every prior local certificate/evidence bundle was
`model_backend=numpy`. On human approval we:

1. `pip install scikit-learn` → **scikit-learn 1.9.1** (+ scipy 1.18.1, joblib 1.6.0,
   threadpoolctl 3.7.0, cloudpickle 3.1.2) alongside existing **numpy 2.5.2**.
2. Restarted the server; `/health` now reports **`model_backend=sklearn`**.
3. Re-ran the **entire** verification surface (tests, smoke, sweeps, behavioral
   harness, live HTTP) and captured a fresh evidence bundle.

**No frozen artifact was edited.** Weights, threshold, schemas, scenarios,
`POLICY_VERSION`, the Phase-2 numpy evidence bundle, and all prior evidence
records are untouched.

## 2. Active models

| Signal | sklearn (now active) | NumPy fallback (retained) |
|---|---|---|
| A – anomaly | IsolationForest | Robust Mahalanobis + empirical-CDF |
| U – uncertainty | RandomForest per-tree P(fail) std | bagged logistic regression member std |

Both fit on the **calibration split only**; gate formula and 0.60 threshold unchanged.

## 3. Test results

| Check | Result |
|---|---|
| `scripts/run_tests.py` | **130 passed, 0 failed** (95.8 s) — was 130/130 on numpy |
| `scripts/smoke_test.py` | exit **0** |
| `node --check frontend/static/app.js` | exit **0** |
| `scripts/sweep_handlers.py` | PROBLEMS **none** (11 handlers, bindings 1/1/1) |
| `scripts/sweep_frontend_consistency.py` | PROBLEMS **none** |
| `scripts/sweep_api_contract.py` | PROBLEMS **none** (8 endpoint groups) |
| `scripts/behavioral_dom_harness.js` | **ALL_FLOWS_OK** |
| `scripts/live_ui_contract_check.py` | **LIVE_VERIFICATION: PASS** (backend=sklearn) |

### 3.1 Two defects surfaced by the switch (both fixed)

| ID | Type | Detail | Fix |
|----|------|--------|-----|
| F-003 | **real backend bug** | `_false_negative_analysis` empty branch (no missed positives) omitted `never_changes_production_gate` and returned a different dict shape than the populated branch. sklearn produced zero FNs on the small test dataset → hit the empty branch → `KeyError`. | `backend/eval/benchmark.py`: empty branch now returns `findings: []`, `missed_transaction_types: {}`, `missed_score_stats`, and **`never_changes_production_gate: True`** — same contract as the populated branch. |
| F-004 | **backend-sensitive test** | `test_explain_signals_consistent_with_gate_score_for_showcase` hard-coded numpy's chosen showcase id `TX-00300`; sklearn selects a different validation id → `StopIteration`. Product behavior correct (showcase still has 5 items covering every outcome). | Test rewritten to assert the explain-vs-analyze consistency invariant for **all 5** showcase items (stronger, backend-agnostic). |

## 4. Post-switch baselines (sklearn 1.9.1, AMD64)

Evidence: `evidence/results/local_readiness/run_20261015T125935Z_AMD64_local/`
(`health.json`, `demo_api.json`, `simulated_api.json`, `api_summary.json`,
`integrity.json`, `environment.json`, `run_tests.txt`, `smoke_test.txt`).

| Transaction | Status | Action | Score | Forks |
|---|---|---|---|---|
| **TX-DEMO-0001** (fixed demo) | `NO_SIMULATION` | `ALLOW_NORMAL_PATH` | **0.582418** | 0 |
| TX-00154 (selected, fails stress) | `SIMULATED` | `BLOCK_OR_HOLD` | 0.653743 | 6 |
| TX-00008 (selected, survives) | `SIMULATED` | `REVIEW` | 0.679679 | 6 |
| TX-00001 (skipped, survives) | `NO_SIMULATION` | `ALLOW_NORMAL_PATH` | 0.202577 | 0 |
| TX-00108-B (skipped, **missed failure**) | `NO_SIMULATION` | `ALLOW_NORMAL_PATH` | 0.522935 | 0 |

- The fixed demo stays **below 0.60 → NO_SIMULATION** (honest, as before; score
  differs from the numpy 0.413874 because A/U come from different models).
- The demonstration "gate selects it; fails a stress" showcase slot is now
  **TX-00154** (was TX-00300 on numpy). The missed-failure counterexample
  **TX-00108-B** is unchanged.

## 5. Frozen integrity (unchanged)

`integrity.json` in the new bundle:

```
impact_weights  {magnitude:0.30, dependency:0.30, anomaly:0.25, uncertainty:0.15}
impact_threshold 0.60
phase2_sha256  README.md   99dbe510…f601a   MATCH
               results.json 3e26d127…2ff52   MATCH
interaction_hits_in_backend_py 0
```

## 6. Backend selection & fallback (how to switch)

| Env / call | Behavior |
|---|---|
| unset / `auto` | sklearn if importable, else numpy |
| `BLACKBOX_MODEL_BACKEND=sklearn` | force sklearn (error if not importable, with numpy recovery hint) |
| `BLACKBOX_MODEL_BACKEND=numpy` | force numpy fallback |

`requirements.txt` already lists `scikit-learn>=1.4` (primary);
`requirements-numpy.txt` is the sklearn-free fallback install.

## 7. Deviations / honesty notes

- **Historical numpy evidence is retained, not overwritten.** Reports dated before
  2026-10-15 that cite `model_backend=numpy`, TX-00300, or score 0.413874 describe
  the numpy run and remain accurate for that run; this report supersedes the
  **current host** numbers. Do not mix numpy and sklearn labels.
- The gate under-performance open issue (docs/STATUS.md Open issue 1) is unchanged
  in kind; recomputing the full validation recall table under sklearn is a separate
  research task, not part of this switch.
- **LinuxONE / s390x remains NOT VERIFIED.** The locked `test` split remains unused.
  Browser visual click-through remains human-only.

## 8. Verdict

**SKLEARN_BACKEND_SWITCH: LOCAL_ALL_PASS** — 130/130 tests, smoke 0, all sweeps
clean, behavioral harness ALL_FLOWS_OK, live contract PASS on `backend=sklearn`;
F-003/F-004 fixed; frozen integrity MATCH; `GIT_MUTATION: NONE` (no repository).
