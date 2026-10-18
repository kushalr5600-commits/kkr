# Gate tradeoff — failure recall at fixed simulation budget (frozen NumPy validation evidence)

**Source artifact:** `evidence/results/analysis/phase2_20261013T202326Z_numpy_validation/results.json`
**Split:** validation (1,000 transactions, 102 true failures) · **Backend:** NumPy · **Architecture:** AMD64
**Frozen:** YES — do not overwrite. Historical NumPy evidence, NOT current scikit-learn runtime.

## Recall at fixed simulation budget

| Budget (fraction simulated) | Random | Amount-only | Anomaly-only | **Frozen gate (production)** | Interaction-aware (research-only) |
|---:|---:|---:|---:|---:|---:|
| 1%  | 0.010 | 0.020 | 0.059 | **0.039** | 0.098 |
| 5%  | 0.049 | 0.020 | 0.324 | **0.137** | 0.412 |
| 10% | 0.102 | 0.039 | 0.529 | **0.196** | 0.627 |

## Frozen gate operating point (threshold = 0.60)

| Metric | Value |
|---|---:|
| Simulation fraction (share selected for stress testing) | 11.4% |
| Failure recall | 0.216 |
| Precision | 0.193 |
| Transactions not selected for simulation | 88.6% |

## Key observations (plain language)

1. **The frozen gate trails anomaly-only at every reported budget.** At 10% budget the gate
   catches 19.6% of failures while anomaly-only catches 52.9%.
2. **The interaction-aware ranking candidate beats anomaly-only at all three budgets** but is
   research-only — not wired into production, not independently replicated.
3. **Root cause (measured):** signal M (magnitude) has point-biserial correlation ≈ −0.008 with
   failure yet carries 30% weight; signal A (anomaly) is the strongest predictor (r ≈ 0.376) but
   carries only 25% weight.
4. **No statistical significance or real-world financial performance is claimed** — these are
   synthetic/benchmark results on a 1,000-transaction validation split.

## Labels

- **Frozen NumPy validation evidence** (this table): produced 2026-10-13/14, AMD64, NumPy backend.
- **Current scikit-learn AMD64 runtime** (separate): produced 2026-10-15, scores/rankings differ.
- **LinuxONE / s390x:** NOT VERIFIED — pending authorized Oct 16 session.
- **Interaction-aware:** research-only, NOT production-approved.
