# Phase 2/3 — Gate diagnosis and interaction-aware experiment

- created_at_utc: 2026-10-13T20:42:48.483476+00:00
- split: **validation** (test split NOT used)
- model_backend: **numpy**
- architecture: AMD64 (linuxone_verified=False)
- elapsed_s: 2.85

## Signal correlation with failure (point-biserial, validation)

| signal | r |
|---|---|
| M_magnitude | -0.0080 |
| D_dependency | 0.2158 |
| A_anomaly_norm | 0.3762 |
| U_uncertainty | 0.1857 |
| gate_score | 0.2727 |
| anomaly_raw | 0.4299 |
| amount_z | -0.0324 |

## Failure recall at fixed budget (validation)

| budget | random | amount_only | anomaly_only | BLACKBOX frozen | interaction_aware |
|---|---|---|---|---|---|
| 0.005 | 0.005 | 0.010 | 0.020 | 0.020 | 0.049 |
| 0.010 | 0.010 | 0.020 | 0.059 | 0.039 | 0.098 |
| 0.020 | 0.019 | 0.020 | 0.147 | 0.078 | 0.186 |
| 0.050 | 0.049 | 0.020 | 0.324 | 0.137 | 0.412 |
| 0.100 | 0.102 | 0.039 | 0.529 | 0.196 | 0.627 |
| 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

**Hypothesis verdict (validation only): SUPPORTED_on_validation**

## Demo TX-DEMO-0001

- score 0.413874 vs threshold 0.6
- M=0.1323 D=0.8000 A=0.4754 U=0.1022
- path: score 0.413874 < 0.60 -> SKIP NO_SIMULATION

## False negatives at 10% budget

- anomaly_only missed 48 / 102 failures
- BLACKBOX gate missed 82 / 102 failures
- interaction_aware missed 38 / 102 failures

Full JSON: `results.json` in this directory.
AMD64/numpy results do NOT establish LinuxONE or sklearn-backend equivalence.
