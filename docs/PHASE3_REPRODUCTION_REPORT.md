# PHASE3_REPRODUCTION_REPORT

**Mission §1–§3, §5** — preserve baseline, audit Phase 2, reproduce unchanged, cross-backend.  
**Host:** AMD64 Windows · CPython 3.12.10 · **backend:** numpy · **Git:** unavailable  
**LinuxONE:** NOT VERIFIED · **Evidence:** `evidence/results/analysis/phase3_20261013T204244Z_reproduction/`

---

## 1. Baseline preservation (VERIFIED)

| Check | Result |
|---|---|
| `IMPACT_WEIGHTS` | `{magnitude: 0.30, dependency: 0.30, anomaly: 0.25, uncertainty: 0.15}` **unchanged** |
| `IMPACT_THRESHOLD` | `0.60` **unchanged** |
| Dataset SHA-256 | `546f57ce…8d2d5c3` matches `backend/data/manifest.json` **before & after** |
| Published `evidence/results/validation/` | not written |
| Phase 2 bundle hashes | `README.md 99dbe510…`, `results.json 3e26d127…` **identical before/after** |
| Locked test split | not used (experiment split=`validation` only) |
| New evidence dir | `phase3_20261013T204244Z_reproduction/` **created** (does not touch Phase 2) |

Source revision: **Git unavailable** (`git` / `.git` absent). Fingerprints (dataset SHA, Phase 2 file SHA-256s, raw prediction SHA) are recorded in `results.json` → `integrity_before` / `integrity_after` / `raw_artifacts`.

---

## 2. Phase 2 audit findings

Each item labeled from **code + artifact inspection**, not from “tests pass”.

| # | Item | Label | Evidence |
|---|---|---|---|
| U1 | Interaction formula | **VERIFIED** | `phase2_research_experiment.py:109–119`: `clip01(0.45*A + 0.30*wp + 0.15*D + 0.10*lp)` with A=`ev.signals["anomaly"]` (frozen CDF-A), D=dependency, wp/lp from `extract_features` window/load. Constants hard-coded in source (not grid-searched in the script). |
| U2 | Pre-specified before labels | **VERIFIED (process)** | Formula does not read `failed` / `failed_scenarios` / `categories`; Phase 2 `results.json` records only post-hoc scoring. No label-driven search loop exists in the Phase 2 driver. |
| U3 | Feature provenance | **VERIFIED** | `backend/gate/models.py:54–88` `extract_features` uses transaction/account/graph/context only. No outcome fields. |
| U4 | Label provenance | **VERIFIED** | `calibration.label_record` → `CrashTestEngine.attack` simulator; independent of gate scores. |
| U5 | Identical examples & budgets | **VERIFIED** | Single `SplitEvaluation` for all policies; `_budget_count(1000, b)` → k=10/50/100 at 1/5/10%. |
| U6 | Top-k / ties | **VERIFIED** | `calibration._top_k_mask`: `np.argsort(-key, kind="stable")` — descending score, original index order on ties. Phase 3 `stable_topk_mask` matches on tied keys (test). |
| U7 | Recall denominator | **VERIFIED** | `failures_found / n_failures` with `n_failures = failed.sum()` (any failing scenario counts once). Jointly-dangerous pairs are **two transactions**; both count in the denominator if both fail. |
| U8 | Duplicate / joint cases | **VERIFIED** | Validation has 15 joint pairs (30 txs). No de-duplication applied — consistent ranking metric. Cluster bootstrap (Phase 3) accounts for non-independence. |
| U9 | Leakage | **VERIFIED (none)** | Static audit of `build_interaction_features`, `interaction_aware_score`, `extract_features`: no labels/outcomes/future data. |
| U10 | Metrics recalculable | **VERIFIED** (Phase 3 adds raw artifacts) | Phase 2 bundle stored **aggregates only** (limitation documented). Phase 3 dumps full per-tx predictions and recalculates independently → **exact match** (§3). |

**Audit verdict: no FAILED items. Phase 2 methodology is sound for a validation-only ranking study.**

---

## 3. Reproduction (unchanged Phase 2 run + independent recalculation)

### 3a. Original experiment re-run (subprocess, exit code captured)

| Item | Value |
|---|---|
| Command | `python scripts/phase2_research_experiment.py` (cwd=repo root) |
| Exit code | **0** |
| Rerun bundle | newest `evidence/results/analysis/phase2_*` (copied aggregates into Phase 3 dir as `phase2_rerun_results.json`; original Phase 2 dir **not** modified) |
| Rerun vs published primary budgets | **all \|Δ\| ≤ 1e-9** |

### 3b. Independent recalculation from raw predictions

Phase 3 regenerated evaluation (models seed=`config.MODEL_SEED`=42), dumped `raw_predictions.csv` (1000 rows, SHA-256 in `results.json`), and recalculated recall@k with a **separate** pure-Python top-k path (`stable_topk_mask` / `recalc_metrics_from_raw`), not `calibration._top_k_mask`.

| policy | budget | published | recalculated | ok |
|---|---|---|---|---|
| anomaly_only | 0.01 | 0.0588235294 | 0.0588235294 | True |
| anomaly_only | 0.05 | 0.3235294118 | 0.3235294118 | True |
| anomaly_only | 0.10 | 0.5294117647 | 0.5294117647 | True |
| BLACKBOX_frozen_gate | 0.01 | 0.0392156863 | 0.0392156863 | True |
| BLACKBOX_frozen_gate | 0.05 | 0.1372549020 | 0.1372549020 | True |
| BLACKBOX_frozen_gate | 0.10 | 0.1960784314 | 0.1960784314 | True |
| interaction_aware | 0.01 | 0.0980392157 | 0.0980392157 | True |
| interaction_aware | 0.05 | 0.4117647059 | 0.4117647059 | True |
| interaction_aware | 0.10 | 0.6274509804 | 0.6274509804 | True |

**Phase 2 interaction recalls 0.098 / 0.412 / 0.627 REPRODUCED exactly (within 1e-9).**

Difference explanation: **none observed**. Backend=numpy, dataset hash identical, labels simulator-deterministic (`labels_stable_all=True` across 6 seeds), Python 3.12.10 on AMD64.

Raw-artifact limitation of Phase 2: aggregates only → Phase 3 adds `raw_predictions.csv` **without** altering the published Phase 2 or validation bundles.

---

## 4. Cross-backend reproduction

| Item | Value |
|---|---|
| `import sklearn` | **ModuleNotFoundError** |
| `find_spec("sklearn")` | None |
| Status | **BLOCKED** (not substituted) |

Instructions (for a host that has wheels):

```text
python -m pip install scikit-learn==1.9.1
set BLACKBOX_MODEL_BACKEND=sklearn
python scripts/phase3_reproduce_and_robustness.py --skip-repro
# compare primary budgets to docs/PHASE3_ADOPTION_CRITERIA.md criterion A8
```

NumPy results are **not** reported as sklearn results. LinuxONE/s390x remains **NOT VERIFIED** from AMD64.

---

## 5. Commands & exit codes

| Command | Exit | Result |
|---|---|---|
| `python scripts/phase3_reproduce_and_robustness.py` | **0** | repro + raw + multi-seed + BLOCKED sklearn + BACKEND-CONDITIONAL |
| `python -m pytest tests/unit/test_phase3_ranking.py -q` | 0 | 12 passed |
| Phase 2 rerun (subprocess) | **0** | metrics match published |

## 6. Reproduction verdict

| Claim | Verdict |
|---|---|
| Interaction-aware 0.098 / 0.412 / 0.627 at 1 / 5 / 10 % | **REPRODUCED** (numpy, validation) |
| Anomaly-only 0.059 / 0.324 / 0.529 | **REPRODUCED** |
| Frozen gate 0.039 / 0.137 / 0.196 | **REPRODUCED** |
| Harness integrity | **REPRODUCED / VERIFIED** |
| sklearn equivalence | **BLOCKED** |
| LinuxONE | **NOT VERIFIED** |

STOP — scope of this report ends at reproduction/cross-backend. Robustness metrics: `docs/PHASE3_ROBUSTNESS_REPORT.md`.
