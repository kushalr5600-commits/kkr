# Gate diagnostic report — BLACKBOX Phase 2

**Date:** 2026-10-13/14 UTC (host clock)  
**Host:** AMD64 Windows, CPython 3.12.10 — **not LinuxONE**  
**Model backend for all numbers below:** NumPy fallback (`RobustMahalanobis` + `BaggedLogisticRegression`), `MODEL_SEED=42`  
**Split:** validation (1,000 tx, 102 simulator-true failures). **Test split not used.**  
**Published sklearn evidence** (`evidence/results/validation/`, 2026-10-13) was **not** overwritten.

Reproduce:

```bash
python scripts/phase2_research_experiment.py
# artifacts: evidence/results/analysis/phase2_<UTC>_<backend>_validation/
```

---

## 1. What was inspected

| Area | Files |
|---|---|
| Feature extraction | `backend/gate/models.py` `extract_features`, `FEATURE_NAMES` |
| Impact scoring | `backend/gate/impact_gate.py` (`magnitude_signal`, `dependency_signal`, `combine`) |
| Models A/U | `backend/gate/models.py` (sklearn + numpy backends, ECDF normalization) |
| Experiment / baselines | `backend/gate/calibration.py` (`evaluate_split`, `budget_curve`, `threshold_operating_point`, `_top_k_mask`) |
| Ground truth | `label_record` → `CrashTestEngine.attack` (simulator, not gate) |
| Demo path | `scripts/trace_gate.py`, Phase 2 `demo_tx` breakdown |
| Certificate skip path | `backend/certificate/certificate.py` (`NO_SIMULATION` when gate does not select) |
| Splits / leak guards | `GateModels.fit` `DataLeakError`; `run_experiment.py` `--confirm-frozen` |
| Prior OSS assessment | `docs/OPEN_SOURCE_COMPONENT_ASSESSMENT.md` |

Git history: **unavailable** (tree is not a git checkout).

## 2. Baseline comparison integrity — VERIFIED

| Check | Result |
|---|---|
| Same labels for all policies? | **Yes** — one `SplitEvaluation.failed` from `label_record` |
| Same split / n / n_failures? | **Yes** — validation, n=1000, failures=102 |
| Same budget definition? | **Yes** — `k = ceil(budget * n)`, identical k for every policy |
| Ranking semantics? | **Yes** — stable `argsort` descending, top-k simulated |
| Test split leakage? | **No** — models fitted on calibration only; Phase 2 script forbids test |
| `anomaly_only` vs gate’s A fairness? | **Fair for ranking** — raw A vs ECDF-A top-k **Jaccard = 1.0** at 1%, 5%, 10% (monotone transform) |
| Feature leakage into gate? | **No** — `extract_features` uses amount/window/load/graph/type only; no `category` / `split` / `joint_*` / labels |

**No implementation defect found in the experiment harness.** The published and reproduced underperformance is a **parameter/feature problem**, not a metric bug.

## 3. Why the frozen gate loses to anomaly-only

Point-biserial correlation with failure (validation, numpy backend):

| signal | r (failure) | frozen weight |
|---|---|---|
| anomaly_raw (used by `anomaly_only`) | **+0.430** | — |
| A (ECDF-normalized anomaly) | **+0.376** | 0.25 |
| **gate score I** | **+0.273** | — |
| D dependency | +0.216 | 0.30 |
| U uncertainty | +0.186 | 0.15 |
| M magnitude | **−0.008** | 0.30 |
| amount_z (amount_only) | −0.032 | — |

**Confirmed mechanism:** ranking by `I` is less aligned with simulator failures than ranking by A alone because **M carries almost no failure signal (r≈0) yet takes 30% of the weight**, and D/U dilute A further. Gate score correlation (0.27) sits well below raw A (0.43). This matches STATUS Open issue 1 and is **not** a ranking-methodology artifact.

Score distributions (failures vs non-failures) and full FN profiles: `results.json` in the analysis bundle.

## 4. False negatives at 10% budget (numpy validation)

| Policy | failures found / 102 | missed | recall |
|---|---|---|---|
| anomaly_only | 54 | 48 | 0.529 |
| BLACKBOX frozen gate | 20 | 82 | 0.196 |
| interaction_aware (candidate) | 64 | 38 | 0.627 |

### Misses by category (gate at 10%)

| category | n_failures | gate recall | anomaly recall | interaction recall |
|---|---|---|---|---|
| correlated_anomalies | 20 | 0.65 | 1.00 | 1.00 |
| dependency_chain_failures | 17 | **0.00** | 0.65 | 0.71 |
| jointly_dangerous | 15 | **0.00** | 0.13 | 0.13 |
| low_value_high_blast_radius | 20 | **0.00** | 0.10 | **0.45** |
| obvious_single_signal_danger | 16 | 0.25 | 1.00 | 1.00 |
| normal (failing under stress) | 10 | 0.00 | 0.10 | 0.20 |
| unusual_but_harmless (fail label) | 4 | 0.75 | 0.50 | 0.75 |

The frozen gate **misses entire high-value failure modes** (`dependency_chain`, `jointly_dangerous`, `low_value_high_blast`) at 10% budget. Anomaly-only and the interaction candidate recover large parts of `low_value_high_blast` and `dependency_chain`.

**Methodology limit (documented, not a code bug):** ranking is **per transaction**. Jointly dangerous *pairs* fail from co-occurrence; selecting only one half may not surface the pair failure in a per-tx ground-truth label (labels already encode the stored context window). Pair-aware selection would need a different experiment design.

## 5. Window / interaction signal (validation, read-only)

| feature | mean failures | mean non-failures | r(failure) |
|---|---|---|---|
| window_pressure (recent_count + recent_amount_ratio + same_type) | 0.096 | 0.043 | **+0.237** |

Window co-occurrence context is a real, label-free correlate of failure — stronger than M — and is already available in `extract_features` but **unused** by the frozen gate (only A’s model sees it indirectly).

## 6. TX-DEMO-0001 decision path (numpy backend)

| Item | Value |
|---|---|
| amount / avg / std | 2406.59 / 1966.70 / 831.23 |
| M | 0.132 (z≈0.53 → clip(z/4)) |
| D | 0.800 |
| A | 0.475 |
| U | 0.102 |
| contributions | 0.040 + 0.240 + 0.119 + 0.015 |
| **score** | **0.414 < 0.60** |
| decision | gate does not select → `NO_SIMULATION` / `ALLOW_NORMAL_PATH` |
| label (not used by gate) | `jointly_dangerous` |

Published sklearn score for the same ID: **0.503 < 0.60** — same skip. Root cause: low M, moderate A, high D diluted under frozen weights; threshold 0.60 never reached. **Not tuned** (frozen; human T1/T2).

## 7. Defects vs hypotheses

| Finding | Classification |
|---|---|
| Experiment harness unfairness / leakage | **Not found** |
| `anomaly_only` ranking mismatch vs gate A | **Not a defect** (Jaccard=1.0) |
| M non-informative (r≈0) with weight 0.30 | **Confirmed parameter issue** — changing weights requires **human authorization** (AGENTS §5) |
| Gate misses dependency_chain / joint / low_value_high_blast at 10% | **Confirmed behavior** on validation+numpy |
| Window pressure predictive (r=0.24) | **Confirmed observation**; not yet a production feature |
| Interaction-aware ranking beats anomaly-only at 1/5/10% | **Experimentally verified on validation+numpy** (see Phase 3 report) |
| Same results on sklearn / LinuxONE | **NOT VERIFIED** |

No frozen constant was changed. No regression “fix” was applied to gate math; instead a **methodology regression test** was added (`tests/unit/test_phase2_diagnostics.py`) so future ranking-harness changes cannot silently break budget fairness or interaction-score purity.

## 8. Recommendations (for humans — not implemented here)

1. **T1 decision:** treat M’s 0.30 weight as the primary dilution lever; options remain in `docs/TASKS.md` T1 (load-aware D, two-sided M, or honest blind-spot story).
2. Consider **ranking-only** use of window_pressure (as in Phase 3 candidate) only after validation of weights on **calibration** and a labeled experiment under human approval — **not** as a silent frozen-gate change.
3. Re-run the Phase 2 script on a **sklearn** host and on **s390x** before generalizing beyond numpy/AMD64.
4. Keep published sklearn evidence intact; store new runs under `evidence/results/analysis/`.

## 9. Evidence index

| Artifact | Path |
|---|---|
| Full Phase 2/3 JSON + README | `evidence/results/analysis/phase2_20261013T202326Z_numpy_validation/` |
| Experiment driver | `scripts/phase2_research_experiment.py` |
| Demo trace (gate) | `scripts/trace_gate.py` |
| Prior backend provenance | `docs/BACKEND_EVIDENCE.md` |
| Frozen contract | `backend/shared/config.py`, `backend/shared/schemas.py` |
