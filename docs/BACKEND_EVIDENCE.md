# Backend-dependent evidence (scikit-learn vs NumPy fallback)

**Status: KNOWN ISSUE (documented, not a defect to hide).** The gate’s learned
signals (A anomaly, U uncertainty) are produced by different algorithms
depending on which model backend is installed. Validation metrics therefore
depend on the backend. Both backends are legitimate under the frozen contract;
they are **not** interchangeable for comparing published numbers.

## 1. Which backend generated the published evidence?

Published artifacts in `evidence/results/validation/` (untouched by this
update):

| Field | Value | Source |
|---|---|---|
| backend | `sklearn` | `model_metadata.json` → `models.backend` |
| anomaly model | `IsolationForest [scikit-learn-1.9.1]` | same file |
| risk model | `RandomForestClassifier (std of per-tree P(fail)) [scikit-learn-1.9.1]` | same file |
| evaluated_at_utc | `2026-10-13T02:28:31+00:00` | same file |
| python | `3.13.16` | same file |
| architecture | `x86_64` | same file |
| dataset seed / split | `42` / calibration 2501, validation 1000, test 1499 | same file |
| dataset SHA-256 | `546f57ce91292214e813e7fd7f7004c32188da54e8a952894076a0e5a8d2d5c3` | `manifest.json` (verified) |

Published headline numbers (sklearn backend), failure recall at budget:

| budget | random | amount_only | anomaly_only | BLACKBOX |
|---|---|---|---|---|
| 1% | 0.010 | 0.020 | 0.098 | 0.059 |
| 5% | 0.049 | 0.020 | 0.422 | 0.167 |
| 10% | 0.102 | 0.039 | 0.696 | 0.245 |

Threshold operating point (score ≥ 0.60): simulates 16.5%, recall 0.314,
precision 0.194.

## 2. Reproduction status of that exact run

| Environment | Reproducible? | Notes |
|---|---|---|
| Original (Python 3.13.16, sklearn 1.9.1, x86_64, 2026-10-13) | NOT re-run here | original machine not this host |
| This host (Python 3.12.10, **sklearn MISSING**, AMD64 Windows) | numbers **differ** | numpy fallback selected automatically |
| LinuxONE / s390x | **VERIFIED** (numpy 133/133, sklearn 141/141, hybrid 155/155 + validation PASS 2026-10-17) | `evidence/results/validation_runs/run_20261016T203734Z_s390x_sklearn/`, `docs/LINUXONE_RUNBOOK.md` |

A development re-run on this host (numpy backend) was saved **beside** the
published evidence, never over it:

```text
evidence/results/validation_rerun_2026-10-14_amd64_numpy/
```

numpy-backend numbers (same frozen dataset, seeds, split, weights, threshold):

| budget | random | amount_only | anomaly_only | BLACKBOX |
|---|---|---|---|---|
| 1% | 0.010 | 0.020 | 0.059 | 0.039 |
| 5% | 0.049 | 0.020 | 0.324 | 0.137 |
| 10% | 0.102 | 0.039 | 0.529 | 0.196 |

Threshold operating point: simulates 11.4%, recall 0.216, precision 0.193.

Deterministic baselines (`random`, `amount_only`) match across backends.
Learned policies (`anomaly_only`, `BLACKBOX`) do not.

## 3. Which backend is selected on LinuxONE?

Unknown until a real install is attempted on the target. Selection logic
(`backend.gate.models.resolve_backend`):

1. `BLACKBOX_MODEL_BACKEND=numpy` → force numpy.
2. `BLACKBOX_MODEL_BACKEND=sklearn` → require sklearn (hard error if missing).
3. Default `auto`: use sklearn when `import sklearn` succeeds, else numpy.

`scripts/diagnose_env.py` and `validate_runtime.py` record the *selected*
backend. `GET /health` also reports `model_backend`.

## 4. What backend differences affect

| Surface | Affected? | Evidence |
|---|---|---|
| M (magnitude) and D (dependency) signals | **No** — deterministic statistics/graph features | `impact_gate.magnitude_signal` / `dependency_signal` |
| A (anomaly) and U (uncertainty) | **Yes** — IsolationForest vs RobustMahalanobis; RF tree-std vs bagged logistic std | `backend/gate/models.py` |
| Gate score I and rank order | **Yes** | validation curves above |
| Set selected at a budget / at threshold 0.60 | **Yes** | 16.5% vs 11.4% simulated |
| Final action given a *selected* certificate | Same policy code | `certificate.decide_action` (frozen) |
| Simulation physics / failure predicates | **No** | `backend/simulation/*` |
| Dataset, splits, seeds, weights, threshold | **No** | frozen `config.py`, verified SHA-256 |
| Qualitative finding “gate underperforms anomaly-only on validation” | **Holds on both backends** | 10% budget: sklearn 0.245 vs 0.696; numpy 0.196 vs 0.529 |

## 5. Rules when comparing results

1. Never compare a sklearn metric table to a numpy metric table without
   labeling both.
2. Never replace the published sklearn evidence with numpy numbers in place.
   Add a new timestamped directory under `evidence/results/validation_runs/`.
3. On LinuxONE, if sklearn cannot install, state that explicitly and report
   numpy-backend metrics as such.
4. Do not tune weights/threshold to close a backend gap without a human
   decision under `AGENTS.md` §5 / TASKS T1.
