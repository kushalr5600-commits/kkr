# Phase 3 — Predeclared adoption criteria (written BEFORE robustness results)

**Timestamp (UTC, host clock):** 2026-10-13T20:30:00Z (approximate; file mtime authoritative)  
**Status of interaction-aware ranking:** research candidate only — **not** in the production gate.  
**This document is frozen for the duration of Phase 3.** Do not edit criteria after reading robustness outputs.

## Context

Phase 2 (AMD64, numpy, validation) reported interaction-aware failure recall **0.098 / 0.412 / 0.627** at **1% / 5% / 10%** budgets versus anomaly-only **0.059 / 0.324 / 0.529**. Phase 3 independently reproduces those claims and stress-tests them.

## Adoption criteria (all must be met before any production proposal)

| ID | Criterion | Pass rule (predeclared) |
|---|---|---|
| A1 | Independent reproduction of Phase 2 point estimates | Recalculated recall at 1/5/10% for interaction_aware matches Phase 2 bundle within **1e-9** absolute (same backend, same dataset hash, same labels). |
| A2 | Reproducible gains at matched budgets | On the **primary reproduction run**, interaction_aware recall **> anomaly_only** at **all of** 1%, 5%, 10% (strict inequality). |
| A3 | Robustness across model-fit seeds | Across **≥5** distinct `MODEL_SEED` values on the same calibration/validation data, interaction_aware **still exceeds anomaly_only** at 5% and 10% for **every** seed (1% may be noisy; report but do not require). |
| A4 | No hidden evaluation leakage | Code audit: ranking features do not use `failed`, `failed_scenarios`, `category`, `split`, or any post-hoc outcome. Labels only for scoring recall. |
| A5 | Scenario-level analysis | Per-scenario recall reported for anomaly_only vs interaction_aware at 10%; no scenario where interaction is **worse by more than 0.05 absolute** without explicit limitation text. |
| A6 | Runtime overhead | Interaction scoring overhead vs frozen gate scoring on the same validation batch **≤ 2×** gate batch time (ranking is cheap arithmetic). |
| A7 | Skipped simulations | Candidate is ranking-only; production path still uses frozen threshold policy. Any future merge must keep `NO_SIMULATION` certificates honest (empty forks, no fake passes). |
| A8 | Backend contract | If sklearn is unavailable, document **BLOCKED** cross-backend; adoption may be **numpy-specific** only with explicit contract text. Prefer gains on **both** backends. |
| A9 | Human authorization | Written human approval required before changing production `IMPACT_WEIGHTS`, ranking path, or selection logic. **Phase 3 cannot self-approve.** |
| A10 | Evidence integrity | Published `evidence/results/validation/` and Phase 2 bundle remain byte-identical; Phase 3 writes only to a new directory. |

## Outcomes allowed

- **ADOPT-NOT-YET** — criteria met, still needs A9 human sign-off  
- **BACKEND-CONDITIONAL** — met on numpy only  
- **REJECT** — A1/A2/A3 fail  
- **INCONCLUSIVE** — insufficient data or BLOCKED checks  

## What Phase 3 will not do

- Change frozen weights/threshold  
- Merge interaction ranking into `ImpactGate`  
- Tune against the locked test split  
- Claim LinuxONE compatibility from AMD64 runs  
