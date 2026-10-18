# TASKS - in priority order

Rules in `AGENTS.md` apply to every task. Tick items and note results in `docs/STATUS.md`.

## T0 - Verify what was never run (do first, ~30 min)

1. `pip install -r requirements-dev.txt`; `python -m pytest -q` -> all green. Fix environment problems only;
   if a test fails, find the real cause (do not weaken the test).
2. `python scripts/smoke_test.py` with FastAPI installed -> the HTTP checks must say PASS, not SKIP.
3. `uvicorn backend.main:app --port 8000`; `curl /health`, `curl -X POST /analyze -H 'content-type: application/json' -d '{"demo_mode":true}'`,
   and `curl -X POST /analyze -d '{}'` (expect HTTP 422 with a trace_id).
4. Open `/dashboard` in a real browser (Playwright/Chromium is fine). Click every listed transaction and
   BREAK MY DECISION. Check: the busy state shows, the previous certificate is never shown for a new
   transaction, the trace_id/transaction_id appear, the error state appears when the server is stopped,
   dark and light themes are readable, the layout works at phone width. Fix frontend bugs in `frontend/static/`.
5. Confirm `/analyze` with a body that contains a `transaction` for an unknown account returns 422, and an
   unsupported `transaction_type` returns 422 (both are `InputError`).

Acceptance: all of the above pass; findings recorded in `docs/DEBUG_LOG.md`.

## T1 - Gate performance (HUMAN DECISION REQUIRED - prepare, do not decide)

Goal: a gate that selects failures better than the anomaly-only baseline *using the frozen weights* if
possible. Prepare an analysis script `scripts/analyze_gate.py` (read-only; calibration + validation only; never
`test`) that reports, for each candidate below, the recall-vs-budget table and the 0.60 operating point:

* A. Make `D` load-aware: blend the existing structural share with the normalized load of the reachable
  services (local dependency load incl. recent-window transactions), e.g. `D = w_s*structure + w_l*clip(max_path_load/L_ref)`.
  `config.py` already lists the D normalization as FROZEN-BEFORE-LOCKED-TEST, so this is allowed *with human approval*.
  `D` must stay deterministic and must not depend on the anomaly model or on labels.
* B. Change the `M` definition (it is 0 for every transaction at or below its account average; most dangerous
  cases are not high-amount). E.g. a two-sided or ratio-based magnitude, still normalized to [0,1].
* C. Re-fit the empirical-CDF normalization of A/U on the validation split instead of calibration.
* D. Keep the formula exactly as is and report the weak result honestly as a measured blind spot; change the
  *demo story* instead (T2).

Deliver: the script, its output in `evidence/results/analysis/`, and a short recommendation in `docs/STATUS.md`.
Wait for the human to pick. Weights (0.30/0.30/0.25/0.15) and threshold (0.60) change only if the human says so.
After a decision: implement it, regenerate nothing that touches the test split, update tests (e.g. a test that D
rises with background load), re-run the validation experiment, then freeze (T5).

## T2 - Make the demo transaction tell the right story (after T1)

`config.DEMO_TRANSACTION_ID` is `TX-DEMO-0001`; today it is skipped by the gate (score 0.503). Options, human chooses:
(a) after T1, if the gate selects it, keep it; (b) rebuild the demo pair (`DatasetGenerator.build_demo_records`)
so the trigger is a gate-selected failing case - still outside calibration/validation/test; (c) demo the
honest blind spot as one of two demos. Whatever is chosen, the certificate must come from the real pipeline.
Add a regression test that the demo transaction's `status` is what the demo script claims.

## T3 - Quality pass on code and docs (small, safe)

* Remove dead code (`_scenario_evidence` has unused locals in `certificate.py`).
* Write `docs/ARCHITECTURE.md` diagrams from the *actual* code; keep `docs/CONTRACTS.md` in sync with `schemas.py`.
* `README.md`: setup, run, test, LinuxONE steps, library links with licenses, honest limitations.
* Optional (cut order allows dropping): "bounded audit mode" - a ~2-5% random audit sample of below-threshold
  transactions inside `gate/calibration.py` to estimate missed failures; it must never rewrite scoring.

## T4 - LinuxONE deployment (needs the human's LinuxONE access)

Prepare, then hand the human exact commands; run them only if you have access:

```bash
uname -m                                  # must print s390x; capture it
python3 --version
git pull
docker build -t blackbox .                # or the --build-arg BASE_IMAGE fallbacks in the Dockerfile
docker run -d --name blackbox -p 8000:8000 blackbox
docker ps; docker image inspect blackbox; docker logs --tail 100 blackbox
curl -s http://127.0.0.1:8000/health      # architecture must read s390x, runtime linuxone
curl -s -X POST http://127.0.0.1:8000/analyze -H 'content-type: application/json' -d '{"demo_mode":true}'
python3 -c "import numpy, sklearn, fastapi; print('OK')"
```
Models are fitted at application start-up inside the container, so inference and simulation really run on
s390x. Evidence to capture into `evidence/`: `uname -m`, container list, `/health`, a real `/analyze` response and
log lines, the model versions in `certificate.runtime.model_versions`, dashboard screenshot. A container merely
existing is not evidence. If scikit-learn will not install, use `BLACKBOX_MODEL_BACKEND=numpy` and state that.
Never describe an x86 run as LinuxONE.

## T5 - Freeze and run the locked experiment (only after T1/T2 are decided)

1. Human confirms the configuration is frozen. 2. Record model versions, config snapshot, dataset SHA-256,
holdout IDs. 3. `python scripts/run_experiment.py --split test --confirm-frozen` **once**. 4. Commit
`evidence/results/test/`. 5. Never edit gate/simulation/config afterwards. Report real numbers, including weak ones,
and per-category misses (especially `jointly_dangerous` and `dependency_chain_failures`).

## T6 - Submission support

* Update `docs/submission/` notes: problem statement, supporting data description, solution overview,
  LinuxONE demonstration checklist, <= 3 minute demo script following `docs/manuals/BLACKBOX_Team_Manual_v4.md` section 19.
* `evidence/claims.md`: fill source and date for every external claim (rules, LinuxONE, s390x images).
* The design PDF in `docs/submission/` was written before the code; once T1/T2 are decided, correct any
  statement that no longer matches (for example the description of D) and say what changed.

## Cut order if time collapses

Cut first: audit mode, baseline-comparison visuals, fragility resolution. Never cut: Impact Gate, one real
normal-vs-stress comparison, Decision Certificate, real LinuxONE execution, truthful evidence, integration tests.
