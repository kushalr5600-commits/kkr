# Honesty disclosures (must appear in slides / video / submission form)

Use these statements verbatim or as close paraphrases. Do **not** drop any of them because they are inconvenient.

## 1. Gate underperformance (KNOWN ISSUE)

> On the validation split, the frozen Impact Gateâ€™s failure recall at fixed simulation budgets is **worse than the anomaly-only baseline** (NumPy backend: e.g. ~0.20 vs ~0.53 at a 10% budget; published sklearn table shows the same ranking problem). The open issue is documented in `docs/STATUS.md` (Open issue 1) and diagnosed in `docs/GATE_DIAGNOSTIC_REPORT.md`. Weights and the 0.60 threshold are **declared MVP parameters**, not claimed optimal.

## 2. Interaction-aware gate activation (2026-10-16, human-authorized)

> An interaction-aware ranking candidate beats anomaly-only on the **validation**
> split (reproduced independently; Phase 3). On **2026-10-16** the user explicitly
> authorized activating it, and it is now **wired into the production gate**:
> `I = 0.45*A + 0.30*W + 0.15*D + 0.10*L` (W/L = dataset-context pressure
> features; threshold unchanged at 0.60; `config.INTERACTION_AWARE_ENABLED`).
> Certificates self-describe via `policy_formula â€¦;mode=interaction_aware`;
> `/explain` contributions show the active terms and always sum to the score.
> The frozen weights (`0.30/0.30/0.25/0.15`) are **retained unchanged** in
> `config.IMPACT_WEIGHTS` with `combine()` as a reference implementation;
> contract tests still pin them. **config.py bytes changed** by the activation
> (SHA-256 was `f4b186a0â€¦d31c` after the interaction activation; a further human-authorized
> change on 2026-10-17 â€” hybrid risk ensemble + LLM narrative keys â€” moved it through
> `c6228f18â€¦6cfd` to `7c38c455â€¦e100` (final: LLM CPU timeout raised 20sâ†’120s after the
> live s390x Granite run measured ~48.7s/narrative). The older `433cd998â€¦` predates all.
> Frozen weights, threshold,
> scenarios, POLICY_VERSION and the dataset SHA are byte-identical throughout;
> contract tests pin them.)
> Showcase ids follow live gate decisions (2026-10-16 sklearn: TX-DEMO-0001,
> TX-00154, TX-01623, TX-00001, TX-00108-B); trust hints, not hardcoded ids.

## 3. Scikit-learn is now the active backend (2026-10-15)

> As of 2026-10-15 the development host has **scikit-learn 1.9.1** installed and runtime
> certificates report backend **`sklearn`** (IsolationForest A, RandomForest-disagreement U).
> Since 2026-10-17 the risk ensemble is **hybrid** when xgboost is installed
> (`hybrid_risk: on`, RF trees + 8 XGBoost bootstrap models; xgboost 3.4.1 AMD64
> wheel / s390x source build). Gate scores are unchanged (interaction formula has
> no U term). Hosts without xgboost report `hybrid_risk: off` and use the plain
> RandomForest â€” never silently relabel one as the other.
> The documented **NumPy fallback** is retained for hosts without scikit-learn
> (`requirements-numpy.txt`, `BLACKBOX_MODEL_BACKEND=numpy`). Evidence dated before
> 2026-10-15 remains **NumPy-labeled** and must not be relabeled as sklearn; the two
> backends produce different scores. See `docs/submission/SKLEARN_BACKEND_SWITCH_REPORT.md`.
> LinuxONE/s390x has since been verified with **both** backends (numpy 2026-10-16;
> sklearn post-activation 2026-10-16) â€” see disclosure 4.

## 4. LinuxONE / s390x IS VERIFIED (2026-10-16)

> Real s390x guest (Ubuntu 24.04.5, `platform.machine() == "s390x"`,
> `/health` â†’ `runtime:linuxone`). Pre-activation numpy run: 133/133
> (`run_20261016T113630Z_s390x_numpy/`). **Post-activation interaction-aware
> sklearn run: 141/141 + smoke + live HTTP PASS**
> (`run_20261016T185139Z_s390x_sklearn/`), with showcase scores **identical**
> to AMD64/sklearn (demo 0.516452; TX-00154 0.661589; TX-01623 0.600031;
> TX-00001 0.232720; TX-00108-B 0.457158). Only claims backed by these
> evidence bundles are made; the demo video (if recorded on AMD64) must be
> labeled with its host.
## 5. Docker: s390x image built on the target; AMD64 host still has no Docker

> The AMD64 development host still has **no Docker CLI** (BLOCKED there) â€” no
> amd64 image is claimed. On the **LinuxONE guest** (Docker 29.8.0, s390x
> daemon) the app image **builds natively on s390x** with
> `--build-arg BASE_IMAGE=s390x/python:3.11-bookworm --build-arg
> INSTALL_BUILD_TOOLS=1` (scipy/scikit-learn/xgboost compile from source inside
> the image). A first build succeeded but the container exited on the
> pre-existing missing `python-multipart` dependency (now added to
> `requirements.txt`); the rebuild and container `/health` check are recorded in
> `docs/DEBUG_LOG.md`. Container results will be labeled from the guest's own
> `/health` output, never inferred.

## 6. Locked test split is unused

> The evaluation `test` split is reserved for a single post-freeze run (`scripts/run_experiment.py --split test --confirm-frozen`) and has **not** been executed. All reported ranking numbers are **calibration / validation** (or demo). No locked-test result is claimed.

## 7. Demo transaction honesty

> The fixed demo `TX-DEMO-0001` is **skipped** by the gate (score &lt; 0.60) and returns `NO_SIMULATION / ALLOW_NORMAL_PATH` even though it can fail stress if forced. This is a **known blind spot**, kept visible on purpose (`docs/STATUS.md` Open issue 2).

## 8. Data and authorization

> Synthetic dataset only. Recommended actions are a **deterministic prototype policy**, not production authorization. Fragility is a **bounded** search, not an exact physical limit.

## 9. Test suite meaning

> 161/161 automated tests on AMD64 (2026-10-17, after the audit-fix session:
> 155 frozen-pinned + 4 reverse doc-contract + 2 C1/disclosure regression tests); the 155-subset **and** LinuxONE
> s390x both ran 155/155 on 2026-10-17,
> interaction-aware gate, scikit-learn + XGBoost hybrid backend, plus the
> advisory LLM layer; the pre-LLM target run was 141/141) verify **correctness of the
> implementation** against the frozen contracts (plus batch-invariance of the
> active gate and score-invariance of the hybrid under the interaction formula).
> They do **not** prove the gate is an optimal risk selector.

## 10. Compliance / organizer rules (HUMAN REQUIRED)

> Pre-build / hacking-period compliance has **not** been verified against a current organizer document. `evidence/claims.md` still requires a human to paste the exact rules source and date before any public claim.

## 11. LLM narrative is advisory and optional (2026-10-17)

> `/explain` may attach an `llm_narrative` produced by IBM Granite
> (`ibm-granite/granite-3.0-1b-a400m-instruct`, Apache-2.0) behind
> `scripts/llm_service.py`, or by any operator-configured `BLACKBOX_LLM_URL`
> service, or by a local `BLACKBOX_LLM_MODEL`. **The narrative never changes
> scores, gate decisions, or certificates** â€” a unit test and the code path
> enforce that. Without configuration the API returns `available: false` with
> the exact reason; the UI shows that honest state. No LLM output is quoted as
> a measured fact anywhere in the evidence.

## 12. Byte-identical cross-arch reproduction applies to the sklearn backend only

> The "byte-identical scores" claim covers the **scikit-learn backend**
> (IsolationForest / RandomForest / XGBoost â€” deterministic tree ensembles,
> pinned versions and seeds), as evidenced by the paired AMD64/s390x showcase
> pins (disclosure 4). The documented **NumPy fallback** computes anomaly
> distances with LAPACK (`np.linalg.pinv`) and Mahalanobis reductions, whose
> last bits can differ across CPU architectures and BLAS builds. NumPy-backend
> scores are therefore **not** guaranteed byte-identical cross-arch; they are
> already labeled backend-dependent (disclosure 3), and AMD64 numbers are
> never represented as LinuxONE results.
