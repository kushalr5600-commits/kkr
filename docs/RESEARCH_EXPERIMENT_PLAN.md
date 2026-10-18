# Research experiment plan and results — interaction-aware selection

## Hypothesis

> **Interaction-aware, budget-constrained simulation selection can detect
> dangerous transaction interactions more effectively than anomaly-only
> ranking or a fixed simulation policy at the same simulation budget.**

## Design (pre-registered structure)

| Element | Choice |
|---|---|
| Split | **validation only** for policy comparison; models fit on **calibration** only |
| Test split | **Inaccessible** (never opened; `--confirm-frozen` not used) |
| Labels | Simulator ground truth (`label_record` / CrashTestEngine), identical for all policies |
| Budgets | 0.5%, 1%, 2%, 5%, 10%, 100% (existing `EXPERIMENT_BUDGETS`) |
| k | `ceil(budget * n)` — same for every policy |
| Seeds | `MODEL_SEED=42`, `DATASET_SEED=42` |
| Backend | whatever `resolve_backend()` selects (this run: **numpy**) |
| Primary metric | failure recall at fixed budget |
| Secondary | precision, FN/FP counts, category recall, CI (Wilson), sim runtime share |

### Policies compared

| Policy | Ranking key | Role |
|---|---|---|
| `random` | permutation (200 draws, averaged) | fixed/deterministic-stochastic baseline |
| `amount_only` | amount z-score | weak baseline |
| `anomaly_only` | raw anomaly score | **strong published baseline** |
| `BLACKBOX_frozen_gate` | frozen `I = 0.30M+0.30D+0.25A+0.15U` | current system |
| `interaction_aware` | `0.45 A + 0.30 W + 0.15 D + 0.10 L` | **research candidate (ranking only)** |

Where (all label-free, from existing `extract_features`):

- `A` = ECDF-normalized anomaly signal from the fitted gate models  
- `W` = window pressure = clip(0.45·recent_count/10 + 0.35·clip(recent_amount_ratio/50) + 0.20·recent_same_type/10)  
- `D` = frozen dependency signal  
- `L` = load pressure = clip(0.5·max_bg + 0.5·path_max_bg)

**Interaction weights were fixed a priori** from the research narrative
(window co-occurrence + anomaly + dependency), **not** by grid-searching
validation labels. That limits claims: this is a **single pre-specified
candidate**, not an optimized policy. A full search would require fitting on
calibration only (future work; needs human-approved protocol).

**The production gate, threshold, schemas and decision policy were not modified.**

## Results — validation, numpy backend, 2026-10-13T20:23:26Z

Bundle: `evidence/results/analysis/phase2_20261013T202326Z_numpy_validation/`

### Failure recall at budget

| budget | random | amount_only | anomaly_only | BLACKBOX frozen | interaction_aware |
|---|---|---|---|---|---|
| 0.5% | ~0.005 | 0.010 | 0.020 | 0.020 | 0.029 |
| **1%** | 0.010 | 0.020 | **0.059** | 0.039 | **0.098** |
| 2% | 0.019 | 0.020 | 0.147 | 0.078 | 0.196 |
| **5%** | 0.049 | 0.020 | **0.324** | 0.137 | **0.412** |
| **10%** | 0.102 | 0.039 | **0.529** | 0.196 | **0.627** |
| 100% | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

Exact floats and Wilson CI bounds: `results.json` → `budget_curve`.

### Primary comparison (hypothesis gate)

| budget | interaction | anomaly_only | frozen gate | beats anomaly? |
|---|---|---|---|---|
| 1% | 0.098 | 0.059 | 0.039 | **yes** |
| 5% | 0.412 | 0.324 | 0.137 | **yes** |
| 10% | 0.627 | 0.529 | 0.196 | **yes** |

**Hypothesis verdict on this run: `SUPPORTED_on_validation`**  
(3/3 primary budgets; interaction also beats the frozen gate everywhere shown).

### Matched selection rate (≈ gate threshold operating point)

Gate threshold selects **11.4%** of validation tx, recall **0.216**, precision **0.193**.  
Same count ranked by `interaction_aware`: recall **0.667**, precision **0.596**.

### Category highlights at 10%

| category | anomaly_only | frozen gate | interaction_aware |
|---|---|---|---|
| low_value_high_blast_radius | 0.10 | 0.00 | **0.45** |
| dependency_chain_failures | 0.65 | 0.00 | **0.71** |
| jointly_dangerous | 0.13 | 0.00 | 0.13 |
| obvious_single_signal_danger | 1.00 | 0.25 | 1.00 |

Jointly dangerous pairs remain hard for **all** ranking policies (per-tx ranking
limitation; see diagnostic report §4).

### Runtime overhead

Phase 2 driver elapsed ≈ **3.0 s** for full validation labeling + scoring +
curves on AMD64 numpy (one-time experiment cost, not per-request latency).
Per-transaction gate latency unchanged (production path untouched).

### Uncertainty

Wilson 95% CI on recall at each budget is stored per row. With 102 failures,
differences of ~0.1 recall are meaningful at 10% but small budgets (n_found
< 10) have wide intervals — treat 0.5–2% rankings cautiously.

## What would falsify or weaken the claim

1. Same protocol on **sklearn** backend reversing the ordering.  
2. Same protocol on a **second seed** or regenerated dataset reversing ordering.  
3. **Locked test** (only after human freeze) reversing ordering.  
4. Showing window_pressure was accidentally label-leaky (audit: it is not —
   only recent window / load features).

## Out of scope / not claimed

- Statistical significance across multiple independent datasets  
- Production adoption of `interaction_aware` weights  
- LinuxONE performance  
- Changing frozen `IMPACT_WEIGHTS` / threshold  

## How to re-run

```bash
python scripts/phase2_research_experiment.py --split validation
python -m pytest tests/unit/test_phase2_diagnostics.py -q
```

Do not point this driver at `--split test` without an authorized freeze
workflow (the CLI currently allows only calibration/validation).
