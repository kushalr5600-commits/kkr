# Phase 3 — reproduction + robustness (validation, numpy)

- created_at_utc: 2026-10-13T20:43:08.372519+00:00
- backend: **numpy**  machine: AMD64  linuxone_verified: False
- elapsed_s: 23.98  raw_sha256: `33b9c37c833b7bc4...`

## Reproduction (published vs recalculated from raw)

| policy | budget | published | recalculated | ok |
|---|---|---|---|---|
| anomaly_only | 0.01 | 0.0588235294 | 0.0588235294 | True |
| BLACKBOX_frozen_gate | 0.01 | 0.0392156863 | 0.0392156863 | True |
| interaction_aware | 0.01 | 0.0980392157 | 0.0980392157 | True |
| anomaly_only | 0.05 | 0.3235294118 | 0.3235294118 | True |
| BLACKBOX_frozen_gate | 0.05 | 0.1372549020 | 0.1372549020 | True |
| interaction_aware | 0.05 | 0.4117647059 | 0.4117647059 | True |
| anomaly_only | 0.1 | 0.5294117647 | 0.5294117647 | True |
| BLACKBOX_frozen_gate | 0.1 | 0.1960784314 | 0.1960784314 | True |
| interaction_aware | 0.1 | 0.6274509804 | 0.6274509804 | True |

- rerun exit: 0  rerun_vs_published_ok: True

## Primary budgets (base seed)

| budget | anomaly | gate | interaction | interaction-anomaly (cluster boot CI95) |
|---|---|---|---|---|
| 0.01 | 0.059 | 0.039 | 0.098 | +0.038 [-0.030, +0.108] |
| 0.05 | 0.324 | 0.137 | 0.412 | +0.087 [+0.018, +0.159] |
| 0.1 | 0.529 | 0.196 | 0.627 | +0.097 [+0.041, +0.162] |

## Multi-seed (6 seeds)

- labels stable: True
- interaction invariant: True
- gate invariant: False (expected False: U depends on seed)

## Cross-backend

- status: **BLOCKED**
- sklearn installed: False

## Adoption verdict (pre-authorization)

**BACKEND-CONDITIONAL** — see docs/PHASE3_ADOPTION_CRITERIA.md (A9 human sign-off required).

Full JSON: `results.json`; raw predictions: `raw_predictions.csv`.
