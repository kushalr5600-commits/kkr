# Gate-performance diagnostic plan (TASKS T1 support)

**Preserved finding (KNOWN ISSUE — do not silence):** On the validation split
(1,000 transactions, 102 true failures; ground truth = full stress
simulation), the frozen BLACKBOX gate ranks failures **worse than the raw
anomaly-only baseline** at every reported fixed budget. Published numbers
(sklearn backend): at 10% budget, anomaly_only recall 0.696 vs BLACKBOX
0.245. The same qualitative gap appears on the numpy fallback (0.529 vs
0.196). Source: `evidence/results/validation/`, `docs/STATUS.md` Open issue 1.

This plan prepares analysis for a **human decision** (TASKS T1). It does not
change frozen weights, threshold, or decision rules.

## Constraints

- Read-only with respect to frozen constants and published evidence.
- Calibration + validation only. Never the locked test split.
- Any new experiment artifacts go under `evidence/results/analysis/` with
  timestamps and backend labels.
- A/U model hyper-parameters and D/M normalizations are
  FROZEN-BEFORE-LOCKED-TEST: changes require human approval.
- Do not claim improvement unless the experiment supports it.

## D1 — Feature extraction and normalization

| Check | Method | Pass criterion |
|---|---|---|
| Feature vector matches `FEATURE_NAMES` length/order | unit test + `extract_features` dump on N calibration rows | exact order match |
| All signals in [0,1] | existing `test_all_signals_and_scores_are_normalized_to_unit_interval` | stays green |
| Empirical-CDF of A/U fitted only on calibration | inspect `models.py` fit path; assert `fitted_on_split == "calibration"` | no validation/test fitting |
| M is zero for at-or-below-average amounts | `magnitude_signal` on synthetic rows | matches definition (known limitation) |
| D ignores load (hypothesis) | correlate D with `local_dependency_load` on validation | expect near-zero correlation today |

Owner area: `backend/gate/models.py`, `backend/gate/impact_gate.py`.

## D2 — Impact-score calculation and component contributions

Tool: `scripts/trace_gate.py` (read-only).

For a stratified sample (e.g. all validation failures + 50 non-failures):

1. Dump M, D, A, U, weighted contributions, score, gate_decision.
2. Compare contribution ranking: does D dilute A on load-driven failures?
3. Confirm `combine()` equals the weighted sum of scored signals
   (cross-check already in `trace_gate.py` → `cross_checks.combine_of_scored_signals`).

Expected today (numpy backend, TX-DEMO-0001):
M=0.132, D=0.800, A=0.475, U=0.102 → score 0.414 < 0.60.
With sklearn (STATUS): score 0.503 < 0.60. Both skip.

## D3 — Gate threshold application

- Verify routing is `score >= 0.60` inclusive (`test_threshold_routing_boundary_is_0_60_inclusive`).
- Report the score histogram of true failures vs non-failures on validation
  (backend-labeled). A large mass of failures just below 0.60 would indicate
  threshold placement, not feature failure.

## D4 — Simulation-selection ranking

- Reuse `budget_curve` / `evaluate_split` (already read-only on a named split).
- Produce recall-vs-budget tables for policies:
  `random`, `amount_only`, `anomaly_only`, `BLACKBOX`, and diagnostic ranks
  `A_only`, `D_only`, `0.5A+0.5D` (analysis only — not production weights).
- Selection integrity: ranks must use only gate inputs; no labels in the
  ranking signal (labels only for measuring recall).

## D5 — Backend-dependent score differences

- Run D2/D4 once per available backend (`BLACKBOX_MODEL_BACKEND=sklearn|numpy`).
- Label every table with backend + package versions (see `docs/BACKEND_EVIDENCE.md`).
- If only one backend exists on LinuxONE, state that; do not back-fill the other.

## D6 — Evaluation split integrity

| Check | How |
|---|---|
| Validation IDs disjoint from calibration/test | compare `manifest.json` split_ids sets |
| Ground truth from simulator, not gate | `calibration.label_record` runs crash tests |
| No label features in `extract_features` | code inspection + contract tests |
| Locked test untouched | no `--split test` without `--confirm-frozen` |

## D7 — Candidate directions (human chooses; analysis only until approved)

Documented in TASKS T1; listed here only as experiment targets:

- **A.** Load-aware D (blend structural criticality with reachable-service load).
- **B.** Two-sided or ratio-based M (today M=0 for at-baseline amounts).
- **C.** Refit empirical-CDF on validation (controversial; needs approval).
- **D.** Keep formula; change demo story only (T2).

Each candidate must be evaluated with the same frozen dataset/split/seeds and
reported with backend labels. No candidate is implemented by this plan.

## D8 — TX-DEMO-0001 skip path (why the demo is NO_SIMULATION)

Reproduce with:

```bash
python scripts/trace_gate.py --transaction-id TX-DEMO-0001
```

### Observed path (numpy backend, this host, 2026-10-14)

| Item | Value |
|---|---|
| transaction | TX-DEMO-0001, wire_transfer, amount 2406.59 |
| account baseline | avg 1966.70, std 831.23 |
| M magnitude | 0.1323 — z ≈ (2406.59−1966.70)/831.23 ≈ 0.53; M = clip(z/4, 0, 1) |
| D dependency | 0.8000 — criticality-weighted reachable services (high) |
| A anomaly (numpy) | 0.4754 |
| U uncertainty (numpy) | 0.1022 |
| weighted sum | 0.30·0.132 + 0.30·0.800 + 0.25·0.475 + 0.15·0.102 ≈ **0.414** |
| threshold | 0.60 |
| decision | 0.414 < 0.60 → gate does **not** select |
| pipeline | no forks, no fragility → status NO_SIMULATION, action ALLOW_NORMAL_PATH |
| ground-truth label (not used by gate) | `jointly_dangerous`; known to fail 3x_volume in stress sim |

### Published path (sklearn backend, STATUS.md)

| Item | Value |
|---|---|
| score | **0.503** < 0.60 |
| decision | same skip outcome |

### Interpretation

The demo pair is dangerous under **simulation** (load / joint effects), but
the frozen gate’s M is a one-sided amount statistic (small here), D does not
see live load, and A/U on this single row do not reach the threshold.
This is an honest blind-spot demonstration, not a simulation bug.
Forcing the demo through would require changing frozen weights/threshold or
redefining M/D — out of scope until a human picks a T1/T2 option.

## Deliverables of a completed investigation (not done here)

- `scripts/analyze_gate.py` (read-only; TASKS T1) with output under
  `evidence/results/analysis/`.
- Short recommendation in `docs/STATUS.md`.
- Human decision recorded before any frozen-parameter change.
