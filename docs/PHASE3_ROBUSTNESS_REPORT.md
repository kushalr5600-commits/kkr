# PHASE3_ROBUSTNESS_REPORT

**Mission §4, §6** — multi-seed robustness, uncertainty, scenario analysis, adoption criteria.  
**Split:** validation only · **Backend:** numpy · **Evidence:** `evidence/results/analysis/phase3_20261013T204244Z_reproduction/`

---

## 1. Experiment design (predeclared)

- **Command:** `python scripts/phase3_reproduce_and_robustness.py --seeds 0,1,2,3,4,42 --bootstrap 500`
- **Seeds:** model-fit seeds passed to `fit_models(repo, seed=s)` (calibration fit only).  
- **Ranking seeds:** frozen gate / anomaly / interaction ranking are deterministic given scores; random baseline not re-used in the primary tables (Phase 2 already reported it).
- **Data:** identical validation records and simulator labels for every method and seed (`labels_stable_all=True`).
- **Negative control:** optional shuffled-W/L not required for A-criteria (omitted from primary tables).
- **Uncertainty:** (a) Wilson binomial intervals (as Phase 2; assumes independent failures); (b) **account-cluster bootstrap** (500 replicates, resample 150 validation accounts with replacement; fixed ranking masks; skip zero-failure draws). Cluster bootstrap is the primary uncertainty statement because transactions share accounts and jointly-dangerous pairs.

**What multi-seed actually varies on this backend** (recorded in `results.json`):

| Component | Seed-dependent on numpy? |
|---|---|
| `RobustMahalanobis` (A / anomaly_raw) | **No** (deterministic; seed ignored) |
| Window/load interaction features | **No** (feature arithmetic) |
| `interaction_aware` ranking | **No** (`interaction_ranking_seed_invariant=True` for all 6 seeds) |
| `BaggedLogisticRegression` (U) | **Yes** (bootstrap RNG) |
| `BLACKBOX_frozen_gate` score | **Yes** via U (`gate_score_seed_invariant=False` except seed=42 baseline) |
| Simulator labels | **No** (stable) |

So “model-fit seed variation” stresses the **frozen gate**; anomaly-only and interaction-aware rankings are **structurally seed-invariant** on numpy. On sklearn, IsolationForest **is** seed-dependent — cross-backend run required before claiming seed-robustness of A (see BLOCKED).

---

## 2. Primary results (base seed 42, validation, n=1000, failures=102)

| budget | k | anomaly_only | BLACKBOX frozen | interaction_aware | Δ inter−anomaly (cluster boot CI95) | P(Δ≤0) |
|---|---|---|---|---|---|---|
| 1% | 10 | 0.059 | 0.039 | **0.098** | +0.038 [−0.030, +0.108] | 0.154 |
| 5% | 50 | 0.324 | 0.137 | **0.412** | +0.087 [+0.018, +0.159] | 0.010 |
| 10% | 100 | 0.529 | 0.196 | **0.627** | +0.097 [+0.041, +0.162] | 0.002 |

At 5% and 10% the account-cluster bootstrap CI for (interaction − anomaly) **excludes 0**. At 1% the CI includes 0 (small k, 10 failures available). **No claim of statistical significance is made beyond these bootstrap intervals**; the unit of resampling is the account, not the transaction.

Precision / FN / FP at base seed (deterministic ranking):

| budget | policy | found | recall | precision | FN | FP |
|---|---|---|---|---|---|---|
| 1% | anomaly | 6 | 0.059 | 0.600 | 96 | 4 |
| 1% | gate | 4 | 0.039 | 0.400 | 98 | 6 |
| 1% | interaction | 10 | 0.098 | 1.000 | 92 | 0 |
| 5% | anomaly | 33 | 0.324 | 0.660 | 69 | 17 |
| 5% | gate | 14 | 0.137 | 0.280 | 88 | 36 |
| 5% | interaction | 42 | 0.412 | 0.840 | 60 | 8 |
| 10% | anomaly | 54 | 0.529 | 0.540 | 48 | 46 |
| 10% | gate | 20 | 0.196 | 0.200 | 82 | 80 |
| 10% | interaction | 64 | 0.627 | 0.640 | 38 | 36 |

Frozen **threshold** operating point (not a ranking budget): 114 sims (11.4%), recall **0.216**, precision **0.193** — unchanged from Phase 1/2.

Simulation runtime totals are proportional to k (`sim_ms` summed on selected set); gate batch ≈ **0.172 ms/tx** on this host.

---

## 3. Multi-seed (model-fit seeds 0,1,2,3,4,42)

| seed | anomaly@10% | interaction@10% | gate@10% | labels stable | inter invariant |
|---|---|---|---|---|---|
| 0 | 0.529 | 0.627 | 0.196 | True | True |
| 1 | 0.529 | 0.627 | 0.196 | True | True |
| 2 | 0.529 | 0.627 | 0.196 | True | True |
| 3 | 0.529 | 0.627 | 0.186 | True | True |
| 4 | 0.529 | 0.627 | 0.186 | True | True |
| 42 | 0.529 | 0.627 | 0.196 | True | True |

- **A3:** interaction > anomaly at **5% and 10% for every seed** — **PASS** (trivially for interaction/anomaly on numpy; gate varies slightly via U).
- Gate recall@10% range across seeds: **0.186–0.196** (small U-driven wobble).

---

## 4. Scenario-level recall @ 10%

| scenario | n_failures | anomaly | gate | interaction |
|---|---|---|---|---|
| 3x_volume | 101 | 0.535 | 0.198 | **0.634** |
| fraud_spike | 57 | 0.702 | 0.333 | **0.737** |
| service_latency | 39 | 0.410 | 0.179 | **0.641** |

No scenario where interaction is worse than anomaly by > 0.05 → **A5 PASS**.

## 5. Category-level recall @ 10% (selected)

| category | n_fail | anomaly | interaction | note |
|---|---|---|---|---|
| low_value_high_blast_radius | 20 | 0.10 | **0.45** | interaction recovers load-driven failures |
| dependency_chain_failures | 17 | 0.647 | **0.706** | improved |
| jointly_dangerous | 15 | 0.133 | 0.133 | **tie — still poor for both** |
| correlated_anomalies | 20 | 1.00 | 1.00 | ceiling |
| obvious_single_signal_danger | 16 | 1.00 | 1.00 | ceiling |
| normal (sim-failing subset) | 10 | 0.10 | 0.20 | small n |

Jointly-dangerous failures remain a **hard residual** for all ranking policies; report this limitation, do not hide it.

---

## 6. Runtime overhead (A6)

| metric | value |
|---|---|
| Gate batch total | ≈ 172 ms / 1000 tx |
| Interaction arithmetic total | ≈ **0.04 ms** |
| Ratio (arith / gate) | ≈ **0.00024** ≪ 2.0 |
| Full extras build (load_context+features) | already required for gate scoring path in production feature extraction; not a new sim |

**A6 PASS.**

---

## 7. Adoption criteria (predeclared in `docs/PHASE3_ADOPTION_CRITERIA.md`, frozen before this run)

| ID | Criterion | Result |
|---|---|---|
| A1 | Reproduce Phase 2 within 1e-9 | **PASS** |
| A2 | Beat anomaly at 1/5/10% | **PASS** |
| A3 | Beat anomaly at 5/10% every seed | **PASS** |
| A4 | No leakage | **PASS** (static audit + tests) |
| A5 | Scenario not worse by >0.05 | **PASS** |
| A6 | Overhead ≤ 2× gate | **PASS** |
| A7 | Honest skips | **PASS** (production path untouched) |
| A8 | Backend contract | **FAIL — sklearn BLOCKED** |
| A9 | Human authorization | **FAIL — not available in Phase 3** |
| A10 | Evidence integrity | **PASS** |

**Pre-authorization verdict: `BACKEND-CONDITIONAL`**  
(= A1–A7 + A10 met on numpy/validation; adoption **not** approved; needs sklearn/s390x run + human A9.)

---

## 8. Limitations (explicit)

1. **Validation only** — locked test split unused; no generalization claim beyond this split.  
2. **numpy backend only** — sklearn IsolationForest ranking may differ; A8 open.  
3. **AMD64 only** — LinuxONE NOT VERIFIED.  
4. Interaction weights (0.45/0.30/0.15/0.10) remain **pre-specified**, not calibration-optimal; no further tuning performed.  
5. Jointly-dangerous category still ~0.13 recall — method does not solve that regime.  
6. Cluster bootstrap uses accounts as clusters; jointly-dangerous cross-account structure not modeled beyond shared account IDs.  
7. Production gate weights/threshold **unchanged**; interaction ranking **not** merged into `ImpactGate`.

STOP — robustness scope ends here. Change report: `docs/PHASE3_CHANGE_REPORT.md`.
