# Advanced Prototype Sprint — Explainable UI + Open Dataset Workbench

**Date:** 2026-10-14  
**Host:** AMD64 · CPython 3.12.10 · backend **numpy**  
**Overall label:** **LOCAL PROJECT COMPLETE — READY FOR TARGET VALIDATION**  
**LinuxONE / s390x:** **NOT VERIFIED**

---

## Status labels

| Label | Value |
|---|---|
| Local AMD64 validation | **PASSED** — **112/112** tests |
| Smoke (HTTP incl.) | **PASS** |
| Frozen gate / threshold / Phase 2 | **UNCHANGED** |
| Interaction ranking in production | **ABSENT** |
| Locked test | **NOT RUN** |
| LinuxONE | **NOT VERIFIED** |
| Overall | **LOCAL PROJECT COMPLETE — READY FOR TARGET VALIDATION** |

---

## What was implemented (not mocked)

### A — Explainable Decision Explorer
- `POST /explain` → contributions `0.30M/0.30D/0.25A/0.15U`, threshold, why, plain + technical text, timeline, certificate payload (`backend/explain/explainer.py`, `backend/main.py`).
- UI: Decision Explorer tab with plain/technical toggle, fact/model/label/interpretation legend, scenario table, timeline, certificate link (`frontend/static/app.js`).
- Explanations are generated from the live `ImpactScore` / certificate — no hardcoded per-tx strings.

### B — Dataset Studio
- Upload **CSV** (stdlib) and **Parquet** (optional pandas; fails closed if missing).
- Limits: 5 MiB, 50 k rows, path-safe ids, no code execution (`backend/datasets/store.py`).
- Preview: columns, inferred types, missing, duplicates, numeric summaries.
- Column mapping + optional label semantics (`fraud|default|operational_failure|other`).
- Remove without touching frozen fixtures/evidence.

### C — Open datasets registry
- Metadata-only registry: ULB fraud, PaySim, UCI credit default (`backend/datasets/registry.py`).
- No bytes bundled; OpenML package **not installed**; network download **disabled**.
- Local upload is the import path.

### D — Challenge Lab
- `POST /datasets/{id}/evaluate` scores rows with the **frozen** gate and reports:
  - rows scored/excluded, simulation rate, skips
  - label prevalence, selection recall/precision/FPR vs external labels
  - confusion matrix **labeled as selection vs external label**, not stress survival
- Optional capped stress sample (explicit flag only).
- Fraud/default/stress labels **never equated**.

### E — Reproducibility
- Experiments carry dataset id + SHA-256, mapping, policy version, weights, threshold, backend versions, run id, timestamp, limitations.
- `GET /experiments` + `GET /experiments/{run_id}`.

### F — OSS evaluation
- Frictionless / Evidently / SHAP / OpenML: **evaluated, not adopted** (not installed; not required). Inventory updated.
- Gate explanation is direct math, not SHAP.

### G — Tests
- New `tests/integration/test_dataset_studio.py` (8 tests): upload/map/evaluate/remove, malformed/oversized/empty, registry, explain, counterexample TX-00108-B, path traversal, imbalance.
- Full suite: **112 passed, 0 failed**.

---

## Counterexample TX-00108-B
- Showcase hint: *Gate skips it; would FAIL stress (missed failure)*.
- `GET /counterexample/TX-00108-B`:
  - `gate_selected: false`
  - `stress_measured: true` (crash-test engine, independent of gate)
  - `stress_failure_observed: true`
  - `missed_failure: true`
- Stress outcome is **measured**, not inferred from the gate decision.

---

## Commands executed

```text
python scripts/run_tests.py     -> 112 passed, 0 failed
python scripts/smoke_test.py    -> all PASS including HTTP
# ad-hoc: /health, /explain, /counterexample/TX-00108-B verified via TestClient
```

| Check | Result |
|---|---|
| Tests | **112 passed** |
| Demo TX-DEMO-0001 | **NO_SIMULATION**, score **0.413874**, forks **0** |
| TX-00300 | **SIMULATED**, **6** forks (unchanged) |
| Weights / threshold | **0.30/0.30/0.25/0.15**, **0.60** |
| Phase 2 SHA | `3e26d127…` unchanged |

---

## Files changed (principal)

| Path | Role |
|---|---|
| `backend/datasets/store.py` | Safe upload/preview/map/remove |
| `backend/datasets/registry.py` | Open dataset registry + OpenML status |
| `backend/eval/benchmark.py` | Challenge Lab metrics |
| `backend/explain/explainer.py` | Math explanations |
| `backend/main.py` | New HTTP routes |
| `backend/shared/config.py` | Studio limits only (not gate policy) |
| `frontend/static/{index.html,app.js,style.css}` | Explorer / Studio / Lab / Counterexample UI |
| `tests/integration/test_dataset_studio.py` | New regression suite |
| `docs/submission/OPEN_SOURCE_COMPONENTS.md` | OSS decisions |
| `docs/submission/PROTOTYPE_SPRINT_REPORT.md` | This report |
| `docs/DEBUG_LOG.md` | Append-only log |

---

## Known limitations / unverified

1. **LinuxONE / s390x** — not run.  
2. **Organizer rules, video, screenshots** — HUMAN.  
3. **OpenML / Frictionless / Evidently / SHAP** — not installed; optional paths document unavailability.  
4. **Parquet** — requires host pandas (present here; **not** in lean `requirements-numpy.txt`).  
5. **Uploaded CSV amount baselines** — per-account mean/std from the file itself (not production account history).  
6. **Models on Challenge Lab** — production gate models (synthetic calibration); not refit on uploads (documented in report limitations).  
7. **Gate performance T1** — still open; interaction ranking not in production.

---

## STOP

Scope ends at local prototype completeness. Do **not** claim `LINUXONE VERIFIED`.
Do not run the locked test. Do not change frozen gate weights/threshold.
Do not equate external fraud/default labels with synthetic stress failures.
