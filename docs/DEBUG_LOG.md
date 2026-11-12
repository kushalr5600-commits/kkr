# DEBUG LOG (append only)

## 2026-10-16 LinuxONE / s390x validation â€” VERIFIED (OpenCode)

ROLE / TASK:        Authorized Oct 16 target session. Provisioned s390x guest
                    (Ubuntu24.04-Datathon, AI_LAB flavor), transferred code,
                    installed deps, ran full validation suite.
STATUS:             LINUXONE_PASS â€” overall_status=PASS, runtime_label=linuxone,
                    architecture=s390x, model_backend=numpy, 133/133 tests.
TARGET:             <redacted-linuxone-guest>, user linux1, Ubuntu 24.04.5 LTS, Python 3.12.3,
                    3 vCPU / 8 GB RAM / 50 GB disk.
EVIDENCE:           evidence/results/validation_runs/run_20261016T113630Z_s390x_numpy/
                    (validation_report.json + README.md)
STEPS EXECUTED:
  1. uname -m = s390x (CONFIRMED)
  2. diagnose_env.py â†’ runtime_label=linuxone, process_is_s390x=true
  3. apt install python3.12-venv build-essential python3.12-dev nodejs
  4. python3 -m venv .venv; pip install -r requirements-numpy.txt
     (numpy 2.5.4 built from source on s390x â€” no wheel available)
  5. pip install -r requirements-test.txt (pytest 9.1.1, httpx 0.28.1)
  6. pip install python-multipart (missing from requirements â€” FastAPI form data)
  7. run_tests.py â†’ 133 passed, 0 failed (24.4s)
  8. smoke_test.py â†’ all PASS including HTTP
  9. export_certificate_schema.py â†’ exit 0
  10. uvicorn + /health â†’ runtime:linuxone, architecture:s390x, model_backend:numpy
  11. POST /analyze demo â†’ TX-DEMO-0001 NO_SIMULATION score=0.413874
  12. trace_gate.py â†’ score 0.413874, gate_decision=False (matches numpy baseline)
  13. validate_runtime.py --include-optional â†’ overall_status=PASS
DEFECTS/GAPS FOUND:
  F-006 P3 â€” requirements-numpy.txt missing python-multipart (FastAPI form/file
    upload dependency). Installed manually; should be added to requirements.
  F-007 P3 â€” test_certificate_reproducibility.py _SHOWCASE_IDS included TX-00154
    (sklearn-only) but not TX-00300 (numpy-only) â†’ assertion failed under numpy.
    Fixed: added TX-00300 to the tuple. Test now passes on both backends.
  F-008 P3 â€” Runbook Â§4a assumes python3-venv preinstalled; Ubuntu 24.04 requires
    apt install python3.12-venv first. Also needs build-essential + python3.12-dev
    for numpy source build on s390x.
  F-009 P3 â€” Runbook Â§2 uses git clone; working tree has no .git. Code transferred
    via tar.gz archive instead.
INTEGRITY: frozen phase2 results.json SHA 3e26d127... unchanged; weights/threshold
  unchanged; dataset SHA 546f57ce... matches manifest on s390x.
OPEN: sklearn backend on s390x not tested (numpy path used per runbook Â§6b);
  T1 gate-weight decision still open; locked test split still unused.

## 2026-10-15 Read-only certificate + benchmark audit; reproducibility test (OpenCode)

ROLE / TASK:        Priority #1 â€” audit whether Decision Certificates can be
                    replayed/verified (READ-ONLY), then add a regression test.
STATUS:             AUDIT_COMPLETE â€” canonical replay PROVEN; raw replay correctly
                    NOT claimed. LinuxONE still NOT VERIFIED.
FILES CHANGED:
  tests/unit/test_certificate_reproducibility.py   NEW â€” 3 tests (canonical digest
                                                   stable on repeat + fresh model fit;
                                                   raw cert volatile; no timestamp field)
  docs/DEBUG_LOG.md                                this entry
  (no schema / gate / production / frozen-evidence change; audit probes were written
   OUTSIDE the repo in %TEMP% and deleted â€” project tree otherwise untouched)
METHOD:
  Part 1 (certificate): built 2 independent services (fresh model re-fit), issued each
    of the 5 showcase certificates 3x (2x same instance + 1x fresh) = 15 certs; field diff.
  Part 2 (benchmark): read the FROZEN phase2 numpy bundle results.json (NOT rewritten).
FINDINGS â€” CERTIFICATE DETERMINISM:
  Volatile (differ every call): certificate_id (uuid4), trace_id (per request),
    evidence[1] = "Pipeline time ... ms." (wall clock, pipeline.py:194). No timestamp
    field exists in the certificate schema.
  Deterministic: status, transaction_id, decision_description, impact_score,
    forks_tested (metrics carry NO timing), fragility, recommended_action,
    evidence[*] except index 1, runtime.model_versions (backend/versions/config_sha256/
    dataset_sha256/git_revision/seed).
  RESULT: raw full-cert SHA-256 NOT stable (by design); CANONICAL PROJECTION
    (drop id + trace + pipeline-time line) SHA-256 IDENTICAL 15/15 across repeats AND
    fresh model re-fit; CORE decision-subset IDENTICAL 15/15.
  SCOPE/CAVEAT: canonical equality holds only when backend + library versions +
    config_sha256 + dataset_sha256 match (all embedded in the certificate). This is a
    determinism (integrity) property, NOT a digital signature â€” no key/verifier present.
FINDINGS â€” GATE BENCHMARK (frozen numpy, validation, 1000 tx / 102 failures):
  gate@0.60 -> sim_fraction 0.114, failure_recall 0.216, precision 0.193, avoids 88.6%.
  Recall at fixed budget (random/amount/anomaly/gate/interaction): 1% .010/.020/.059/.039/.098;
    5% .049/.020/.324/.137/.412; 10% .102/.039/.529/.196/.627.
  The frozen gate is BEATEN BY anomaly-only at every budget (research-only
    interaction_aware beats anomaly-only; verdict SUPPORTED_on_validation, NOT wired in).
  ROOT CAUSE (measured point-biserial with failure): A 0.376 > D 0.216 > U 0.186 >
    M -0.008. Frozen formula weights the uncorrelated signal (M, ~0) at 0.30 and the
    strongest (A) at 0.25 â€” the mechanical cause of the recall gap. Human decision (T1);
    NOT tuned here.
  F-005 P3 â€” primary_budget_comparison booleans beats_anomaly/beats_gate are ambiguous
    vs the numeric recall; label-clarity flag only, no change.
TESTS RUN + RESULTS:
  test_certificate_reproducibility -> 3 passed (12.1 s)
  run_tests -> 133 passed 0 failed (101.5 s)   (was 130/130 sklearn)
INTEGRITY: frozen phase2 results.json SHA 3e26d127... re-verified MATCH; weights/
  threshold/scenarios/POLICY_VERSION unchanged; no schema change. GIT_MUTATION: NONE (no .git).
OPEN: LinuxONE/s390x validation pending (Oct 16 window); T1 gate-weight decision open.

## 2026-10-15 Scikit-learn backend switch + full re-verify (OpenCode)

ROLE / TASK:        Human-approved switch to scikit-learn as the active model
                    backend (numpy retained as documented fallback); full re-verify
STATUS:             LOCAL_ALL_PASS â€” 130/130 on sklearn; LinuxONE still NOT VERIFIED
FILES CHANGED:
  backend/eval/benchmark.py                 F-003: empty-branch of
                                            _false_negative_analysis now returns the
                                            same contract incl. never_changes_production_gate
  tests/unit/test_ai_intelligence.py        F-004: showcase-consistency test made
                                            backend-agnostic (asserts all 5 showcase items)
  docs/submission/SKLEARN_BACKEND_SWITCH_REPORT.md   NEW â€” authoritative switch record
  docs/STATUS.md                            host/backend + suite counts updated
  docs/submission/DISCLOSURES.md            Â§3 sklearn now active; Â§9 130/130
  docs/submission/DEMO_SCRIPT.md            sklearn baselines + TX-00154
  docs/submission/OPEN_SOURCE_COMPONENTS.md sklearn now runtime (active)
  docs/DEBUG_LOG.md                         this entry
WHY EACH:           resolve_backend() already prefers sklearn when importable; the
                    host simply lacked the package. Switch changes every A/U value
                    and therefore every score â€” re-verify + relabel required.
ENV:                scikit-learn 1.9.1, scipy 1.18.1, numpy 2.5.2, CPython 3.12.10, AMD64
DEFECTS SURFACED:
  F-003 P2 FIXED â€” _false_negative_analysis empty branch omitted
      never_changes_production_gate (sklearn produced 0 FNs on the small test set)
  F-004 P2 FIXED â€” test hard-coded numpy showcase id TX-00300 -> StopIteration
  P0=0 P1=0 P2=2(fixed) P3=0
NEW BASELINES (sklearn, AMD64, evidence bundle run_20261015T125935Z_AMD64_local):
  TX-DEMO-0001  0.582418  NO_SIMULATION / ALLOW_NORMAL_PATH  forks 0
  TX-00154      0.653743  SIMULATED / BLOCK_OR_HOLD          forks 6 (3x_volume+fraud_spike fail)
  TX-00008      0.679679  SIMULATED / REVIEW                 forks 6
  TX-00001      0.202577  NO_SIMULATION / ALLOW_NORMAL_PATH  forks 0
  TX-00108-B    0.522935  NO_SIMULATION (missed-failure counterexample)
TESTS RUN + RESULTS:
  run_tests -> 130 passed 0 failed (95.8 s)  (was 130/130 numpy)
  smoke_test (BLACKBOX_REQUIRE_HTTP=1) -> exit 0
  sweeps (handlers / frontend-consistency / api-contract) -> PROBLEMS none
  behavioral_dom_harness -> ALL_FLOWS_OK
  live_ui_contract_check -> LIVE_VERIFICATION: PASS (backend=sklearn)
  node --check app.js -> 0
FROZEN INTEGRITY:   weights/threshold unchanged; phase2 README 99dbe510â€¦,
                    results.json 3e26d127â€¦ MATCH; interaction hits in backend = 0
TESTS NOT RUN:      locked test; s390x; human browser click-through
KNOWN LIMITATIONS:  historical (pre-2026-10-15) evidence stays numpy-labeled and was
                    NOT rewritten; validation recall table not recomputed on sklearn
NEXT STEP:          human Ctrl+Shift+R + real click-through on sklearn host

## 2026-10-15 Frontend-wide correctness sweep (OpenCode)

ROLE / TASK:        User mandate: "check everything without mistakes like this"
                    (wi-btn class) â€” systematic frontend/backend contract sweep
STATUS:             FIXED â€” 130/130 local; LinuxONE still NOT VERIFIED
FILES CHANGED:
  backend/intelligence/signals.py           F-002: what-if response now exposes
                                            hypothetical.signals (M/D/A/U) like original
  frontend/static/app.js                    runWhatIf render defensed (numOrUnknown,
                                            no bare nested .property chains)
  tests/unit/test_ai_intelligence.py        +hypothetical.signals symmetry assertions
  tests/integration/test_ui_api_contract.py NEW â€” 7 field/route contract tests
  tests/integration/test_ui_behavioral_harness.py NEW â€” runs app.js in DOM stub
                                            (analyze->what-if->nav flows; node-gated)
  scripts/behavioral_dom_harness.js         NEW â€” executable UI flow harness
  scripts/sweep_api_contract.py             NEW â€” field contract sweep (live API)
  scripts/sweep_frontend_consistency.py     fixed false positives (strip literals,
                                            prefix routes, removed naive handler scan)
  scripts/sweep_handlers.py                 fixed false positives (alert/function)
  docs/DEBUG_LOG.md                         this entry
WHY EACH:           F-002 was the second same-class defect: runWhatIf read
                    res.d.hypothetical.signals.A but backend omitted it â†’ TypeError
                    after a successful fetch (found by the new harness, first run)
DEFECTS:
  F-002 P2 FIXED â€” hypothetical.signals missing â†’ "What-if error: Cannot read
      properties of undefined (reading 'A')" on every real what-if click
  P0=0 P1=0 P2=1(fixed) P3=0
SWEEP RESULTS (all post-fix):
  sweep_handlers               -> PROBLEMS none (11 handlers scope-clean;
                                  wi-btn/break-btn/retry-btn bound exactly once)
  sweep_frontend_consistency   -> PROBLEMS none (45 used ids; fetch paths match routes;
                                  notes: ds-detail/policy-card/whatif-box structurally
                                  referenced â€” verified not defects)
  sweep_api_contract           -> none (explain/what-if/transactions/health/
                                  counterexample/datasets list+detail/experiments/registry)
  behavioral_dom_harness       -> ALL_FLOWS_OK (init, analyze, what-if click posts
                                  correct body, empty-override msg, 6-panel nav,
                                  tx change re-enables wi-btn)
TESTS RUN + RESULTS:
  run_tests -> 130 passed 0 failed (baseline 121; +7 contract, +2 harness; none weakened)
  node --check app.js -> 0
TESTS NOT RUN:      locked test; s390x; human browser click-through
KNOWN LIMITATIONS:  browser visual click-through still human-only; harness DOM stub
                    is not a real browser
NEXT STEP:          human Ctrl+Shift+R + real click of Run what-if

## 2026-10-15 What-If button unresponsive (OpenCode)

ROLE / TASK:        P2 UI defect: Run what-if button dead on click
STATUS:             FIXED â€” 121/121 local; LinuxONE still NOT VERIFIED
FILES CHANGED:
  frontend/static/app.js                     init-time listener with module-level `selected`;
                                             removed renderExplain closure over out-of-scope `tx`;
                                             wi-btn enabled/disabled in sync with selection
  tests/unit/test_frontend_contract.py       +test_what_if_button_bound_to_selected_transaction
  docs/DEBUG_LOG.md                          this entry
WHY EACH:           Strict-mode ReferenceError on click (tx not in renderExplain scope);
                    button also stayed disabled until after a successful analysis
TESTS RUN + RESULTS:
  node --check app.js -> 0
  run_tests -> 121 passed 0 failed
  live GET /static/app.js contains runWhatIf(selected), no onclick closure
TESTS NOT RUN:      locked test; s390x; human browser click-through
KNOWN LIMITATIONS:  visual confirmation pending (human refresh)
NEXT STEP:          hard-refresh dashboard (Ctrl+Shift+R) to bypass cached app.js

## 2026-10-15 Comprehensive E2E verification sprint (OpenCode)

ROLE / TASK:        Senior QA verification of complete app; fix real defects only
STATUS:             AMD64 PASS_WITH_LIMITATIONS â€” 120/120; LinuxONE BLOCKED (not on target)
FILES CHANGED:
  backend/intelligence/signals.py           P2 fix: base_graph kept for what-if original baseline
  tests/unit/test_ai_intelligence.py        +test_what_if_type_change_keeps_original_baseline_graph
  docs/submission/COMPREHENSIVE_VERIFICATION_REPORT.md   NEW
  docs/submission/VERIFICATION_FINDINGS.md               NEW
  docs/submission/VERIFICATION_CHECKLIST.md              NEW
  evidence/results/verification/run_20261015T002445Z_AMD64_verification/  NEW bundle
  docs/DEBUG_LOG.md                         this entry
WHY EACH:           Verification-first mission Â§14: reproduce â†’ regression test â†’ minimal fix
DEFECTS:
  F-001 P2 FIXED â€” what-if type override corrupted original baseline D (0.457 vs true 0.8)
  P0=0 P1=0 P2=1(fixed) P3=0
TESTS RUN + RESULTS:
  run_tests -> 120 passed 0 failed (baseline was 119; +1 regression test; none weakened)
  smoke_test (BLACKBOX_REQUIRE_HTTP=1) -> exit 0
  live HTTP suite -> 19/19 PASS (health, dashboard, analyze, explain, what-if,
    counterexample, upload/map/evaluate, experiments, registry, malformed handling)
  certificate JSON Schema (Draft 2020-12) -> demo + SIMULATED certs valid
  Phase2 hashes -> 3e26d127â€¦ / 99dbe510â€¦ MATCH
  demo score 0.41387409174663015 / TX-00300 0.718654 unchanged
  node --check app.js -> 0
TESTS NOT RUN:      locked test (forbidden); s390x (AMD64 host); sklearn path (absent);
                    browser visual (no tool); OTel-enabled (absent); OpenML network
KNOWN LIMITATIONS:  visual UI unverified; sklearn parity unclaimed; no LinuxONE claim
NEXT STEP:          Oct 16 LinuxONE window; human media/rules
STOP:               verification scope ends; no feature sprint started

## 2026-10 Brand logo + slogan (OpenCode)

ROLE / TASK:        Add BLACKBOX cube logo and slogan to webapp
STATUS:             COMPLETE â€” 119/119 local; LinuxONE still NOT VERIFIED
FILES CHANGED:
  frontend/static/assets/logo.svg            NEW cube mark (SVG, offline)
  frontend/static/assets/wordmark.svg        NEW BLACKBOX wordmark lockup
  frontend/static/index.html                 favicon + brand-side logo/slogan + idle hero
  frontend/static/style.css                  .brand-logo .wm-black .wm-box .brand-slogan .hero-logo
  tests/unit/test_frontend_contract.py       +test_frontend_brand_logo_and_slogan_assets
WHY EACH:           User-supplied brand asset; SVG recreation keeps demo offline-safe
TESTS RUN + RESULTS:
  run_tests -> 119 passed 0 failed
  GET /static/assets/logo.svg -> 200 image/svg+xml (2897 B)
  GET /static/assets/wordmark.svg -> 200 image/svg+xml (1041 B)
  GET /dashboard -> 200
TESTS NOT RUN:      locked test; s390x; browser screenshot of rendered logo
KNOWN LIMITATIONS:  Logo is SVG recreation of user PNG (not the raster bytes);
                    slogan case-normalized in sidebar for mobile width
NEXT STEP:          human media capture; Oct 16 LinuxONE

## 2026-10 AI Intelligence Layer sprint (OpenCode)

ROLE / TASK:        Real ML signal exposure, what-if workspace, false-negative research patterns
STATUS:             COMPLETE â€” 118/118 local AMD64; LinuxONE still NOT VERIFIED
FILES CHANGED:
  backend/intelligence/{signals.py,__init__.py}   NEW explain_signals + what_if (read-only gate)
  backend/main.py                                 /explain +ai_signals; POST /research/what-if
  backend/eval/benchmark.py                       Challenge Lab false_negative_analysis (research-only)
  frontend/static/{index.html,app.js,style.css}   AI & Risk panel + What-If Research Workspace
  tests/unit/test_ai_intelligence.py              NEW 5 tests
  docs/submission/{AI_INTELLIGENCE_SPRINT_REPORT.md,OPEN_SOURCE_COMPONENTS.md}
  docs/DEBUG_LOG.md                               this entry
WHY EACH:           Mission: expose real A/U model outputs; isolated what-if; honest FN patterns;
                    never change frozen gate or Decision Certificate semantics
TESTS RUN + RESULTS:
  run_tests -> 118 passed 0 failed (113 baseline + 5 new)
  /explain demo -> ai_signals.anomaly.normalized_a real, risk.normalized_u real,
                   gate.simulation_executed=false for TX-DEMO-0001, caveats present
  /research/what-if demo -> 200 research_only=true; invalid override -> 422
  frozen weights/threshold/phase2 hashes unchanged
TESTS NOT RUN:      locked test; s390x; interactive video of AI panel
KNOWN LIMITATIONS:  sklearn absent on host -> numpy backend; U not calibrated confidence;
                    FN patterns descriptive only; what-if research-only
NEXT STEP:          Oct 16 LinuxONE; human media/rules

## 2026-10 UI refinement (OpenCode)

ROLE / TASK:        Sidebar nav, score dial, Studio/Open/Lab/Experiments/Certs panels, trust provenance
STATUS:             COMPLETE â€” 113/113 local; LinuxONE still NOT VERIFIED
FILES CHANGED:
  frontend/static/{index.html,app.js,style.css}  dark UI + 6 destinations + honesty colors
  tests/unit/test_frontend_contract.py           +nav/design/trust regression test
WHY EACH:           User visual reference + design rule (greenâ‰ safe on skip)
TESTS RUN + RESULTS:
  run_tests -> 113 passed 0 failed
  /explain + /health + dashboard 200 unchanged
TESTS NOT RUN:      locked test; s390x; browser video
KNOWN LIMITATIONS:  LinuxONE pending; formula card filled from /explain not hardcoded
NEXT STEP:          human media/rules; Oct 16 target

## 2026-10 Advanced prototype sprint (OpenCode)

ROLE / TASK:        Explainable UI, Dataset Studio, open registry, Challenge Lab, counterexample
STATUS:             COMPLETE â€” LOCAL PROJECT COMPLETE â€” READY FOR TARGET VALIDATION
FILES CHANGED:
  backend/datasets/store.py                   NEW safe CSV/Parquet studio
  backend/datasets/registry.py                NEW metadata-only open dataset registry
  backend/eval/benchmark.py                   NEW gate-selection benchmark (labels separate)
  backend/explain/explainer.py                NEW math explanations + contributions
  backend/main.py                             /explain /datasets/* /counterexample /experiments
  backend/shared/config.py                    studio limits only
  frontend/static/{index.html,app.js,style.css} tabs + explain + studio + lab + counterexample
  tests/integration/test_dataset_studio.py    NEW 8 tests
  docs/submission/{PROTOTYPE_SPRINT_REPORT.md,OPEN_SOURCE_COMPONENTS.md}
  docs/DEBUG_LOG.md                           this entry
WHY EACH:           Mission Â§Â§Aâ€“G; frozen gate unchanged
TESTS RUN + RESULTS:
  run_tests -> 112 passed 0 failed
  smoke_test -> all PASS including HTTP
  /explain demo -> score 0.413874 NO_SIMULATION 4 contributions
  /counterexample/TX-00108-B -> gate_selected False, stress_failure True, missed_failure True
  frozen weights/threshold/Phase2 unchanged
TESTS NOT RUN:      locked test; s390x; OpenML network download; interactive video
KNOWN LIMITATIONS:  Parquet needs optional pandas; OpenML/Frictionless/Evidently/SHAP not installed;
                    media+organizer rules HUMAN; T1 open
ASSUMPTIONS:        Studio limits are runtime config not gate policy; labels never mixed with stress
CONTRACT CHANGES REQUESTED: none
NEXT STEP:          human media/rules; Oct 16 LINUXONE_RUNBOOK Â§6b

## 2026-10 Mature open-source integration sprint (OpenCode)

ROLE / TASK:        Versioned cert schema; strict API; optional OTel; HTTP tests; runbook Remote-SSH
STATUS:             COMPLETE â€” LOCAL PROJECT COMPLETE â€” READY FOR TARGET VALIDATION
FILES CHANGED:
  backend/shared/config.py                     POLICY_VERSION=1.0.0
  backend/pipeline.py                          policy_version/policy_formula in runtime; tracing spans
  backend/main.py                              extra=forbid AnalyzeRequest; /health otel_*; span on analyze
  backend/shared/tracing.py                    NEW optional no-op OTel helpers
  requirements-observability.txt               NEW optional otel-api/sdk (not installed)
  scripts/export_certificate_schema.py         NEW live Pydantic -> JSON Schema
  schemas/decision_certificate.v1.schema.json  NEW generated schema
  tests/unit/test_certificate_schema_export.py NEW 4 tests
  tests/integration/test_http_api.py           cert consistency + strict request
  scripts/smoke_test.py                        otel/policy_version/unknown-key checks
  docs/LINUXONE_RUNBOOK.md                     6b VS Code Remote-SSH + schema export
  docs/submission/OPEN_SOURCE_COMPONENTS.md    OTel optional; Hypothesis deferred
  docs/submission/INTEGRATION_SPRINT_REPORT.md NEW
  docs/submission/LINUXONE_EXECUTION_READINESS.md updated labels
  docs/submission/FINAL_PACKAGE_CHECKLIST.md   new rows
  docs/DEBUG_LOG.md                            this entry
WHY EACH:           Mission Â§Â§1â€“10; no decision policy change; mature OSS only where gap proven
TESTS RUN + RESULTS:
  run_tests -> 104 passed 0 failed (~33s)
  smoke_test -> all PASS including HTTP policy_version + unknown-key 422
  export_certificate_schema -> wrote schemas/decision_certificate.v1.schema.json
  demos unchanged: TX-DEMO-0001 NO_SIMULATION forks 0; TX-00300 SIMULATED 6 forks
  frozen weights/threshold/Phase2 hashes unchanged; interaction rank backend=0
TESTS NOT RUN:      locked test; s390x; docker; OTel with real packages installed
KNOWN LIMITATIONS:  media+organizer rules HUMAN; gate T1 open; otel s390x UNVERIFIED
ASSUMPTIONS:        OTel stays optional; Hypothesis not needed this sprint
CONTRACT CHANGES REQUESTED: none (schema documents existing DecisionCertificate only)
NEXT STEP:          Oct 16 operator LINUXONE_RUNBOOK Â§6b (VS Code Remote-SSH); human media + rules

## 2026-10 Autonomous final completion + LinuxONE readiness (OpenCode)

ROLE / TASK:        Finish app workflow, httpx test integration, evidence capture, Oct 16 handoff
STATUS:             COMPLETE â€” READY FOR LINUXONE EXECUTION (local); LinuxONE still NOT VERIFIED
FILES CHANGED:
  requirements-test.txt                     NEW pytest+httpx test-only
  requirements-dev.txt                      now includes requirements-test.txt
  scripts/smoke_test.py                     richer HTTP; BLACKBOX_REQUIRE_HTTP; both demo HTTP paths
  scripts/capture_evidence.py               NEW genuine local evidence bundles
  tests/unit/test_packaging_numpy_runtime.py fixed smoke string assertion
  docs/submission/OPEN_SOURCE_COMPONENTS.md NEW adopted inventory (httpx BSD-3)
  docs/submission/FINAL_COMPLETION_SPRINT_REPORT.md NEW
  docs/submission/LINUXONE_EXECUTION_READINESS.md updated labels + evidence path
  docs/LINUXONE_RUNBOOK.md                  requirements-test + BLACKBOX_REQUIRE_HTTP
  README.md                                 install/test command clarity
  docs/DEBUG_LOG.md                         this entry
WHY EACH:           Mission Â§Â§5â€“11; no decision policy change
TESTS RUN + RESULTS:
  primary run_tests -> 100 passed exit 0; smoke PASS+HTTP exit 0
  clean venv numpy+test no sklearn -> run_tests 100 exit 0; BLACKBOX_REQUIRE_HTTP=1 smoke all PASS exit 0
  capture_evidence.py -> exit 0; bundle run_20261014T040122Z_AMD64_local
  demos numpy -> TX-DEMO-0001 0.413874 NO_SIMULATION forks 0; TX-00300 0.718654 SIMULATED forks 6
  frozen weights/threshold/Phase2 hashes unchanged; interaction backend=0
TESTS NOT RUN:      locked test; s390x; docker build; interactive browser video
KNOWN LIMITATIONS:  media+organizer rules HUMAN; gate T1 open; s390x wheels unknown
ASSUMPTIONS:        httpx is test-only; BLACKBOX_REQUIRE_HTTP for guest evidence
CONTRACT CHANGES REQUESTED: none
NEXT STEP:          Oct 16 operator LINUXONE_RUNBOOK Â§6b; human media + rules

## 2026-10 LinuxONE October 16 execution readiness (OpenCode)

ROLE / TASK:        Non-Docker path verification + Oct 16 procedure; packaging regressions
STATUS:             COMPLETE â€” clean venv numpy path VERIFIED on AMD64; LinuxONE still NOT VERIFIED
FILES CHANGED:
  tests/unit/test_packaging_numpy_runtime.py   NEW 4 packaging tests
  docs/LINUXONE_RUNBOOK.md                     Â§0b safe-now/SSH-only; Â§4a; Â§6b first commands; shutdown/rollback
  docs/submission/LINUXONE_EXECUTION_READINESS.md  readiness record
  docs/DEBUG_LOG.md                            this entry
WHY EACH:           Task 1â€“5 readiness pass; no decision policy change
TESTS RUN + RESULTS:
  primary: run_tests.py -> 100 passed, 0 failed exit 0; smoke all PASS exit 0
  clean venv %TEMP%\\opencode\\blackbox_numpy_venv: pip requirements-numpy OK; no sklearn
  clean: resolve_backend=numpy; /health+dashboard 200; DEMO 0.413874 forks 0; TX-00300 0.718654 forks 6
  clean smoke: pipeline PASS, HTTP SKIP (no httpx) exit 0
  frozen weights/threshold + Phase2 SHA-256 unchanged; interaction backend hits=0
TESTS NOT RUN:      locked test; s390x; docker; interactive browser
KNOWN LIMITATIONS:  s390x wheel availability unknown; LinuxONE claim forbidden until guest run
ASSUMPTIONS:        requirements-numpy is complete server runtime; httpx optional for HTTP smoke
CONTRACT CHANGES REQUESTED: none
NEXT STEP:          Oct 16 operator runs LINUXONE_RUNBOOK Â§6b on authorized s390x guest only

## 2026-10 Project completion sprint â€” implementation (OpenCode)

ROLE / TASK:        Finish product: honest UI, API/frontend contract tests, smoke hardening, LinuxONE non-Docker path
STATUS:             COMPLETE â€” 96/96 tests; smoke PASS; demo paths unchanged under frozen gate
FILES CHANGED:
  frontend/static/app.js, style.css, index.html   NO_SIMULATION/REVIEW banners; empty list; incomplete-pair guard; safer errors; busy label
  backend/main.py                                 clearer model-fit startup error
  scripts/smoke_test.py                           honesty + pair + backend-id asserts
  requirements-numpy.txt                          NEW sklearn-free runtime deps
  docs/LINUXONE_RUNBOOK.md                        Â§4a non-Docker install/start
  tests/unit/test_frontend_contract.py            NEW 7 tests
  tests/integration/test_http_api.py              NEW 2 HTTP tests
  docs/submission/COMPLETION_SPRINT_REPORT.md     completion report
  docs/DEBUG_LOG.md                               this entry
WHY EACH:           Sprint Phase 2â€“4; evidence-backed defects only; no decision policy change
TESTS RUN + RESULTS:
  run_tests.py -> 96 passed, 0 failed exit 0
  smoke_test.py -> exit 0 all PASS
  DEMO TX-DEMO-0001 -> NO_SIMULATION ALLOW_NORMAL_PATH 0.413874 forks 0 numpy
  TX-00300 -> SIMULATED BLOCK_OR_HOLD 0.718654 forks 6 numpy
  frozen weights/threshold + Phase2 SHA-256 -> unchanged
TESTS NOT RUN:      locked test; interactive browser; docker build; s390x; sklearn
KNOWN LIMITATIONS:  UI not click-tested; LinuxONE NOT VERIFIED; T1 still open
ASSUMPTIONS:        Frontend remains presentation-only; requirements-numpy is the supported s390x fallback
CONTRACT CHANGES REQUESTED: none
NEXT STEP:          Oct 16 operator LinuxONE runbook Â§4; human T1 decision; media capture

## 2026-10 Final submission audit (read-only) (OpenCode)

ROLE / TASK:        Final package audit: reconcile docs vs tree, inventory, integrity, smallest doc fixes, go/no-go
STATUS:             COMPLETE â€” **NOT READY** (official rules HUMAN REQUIRED; media ABSENT; interactive UI NOT VERIFIED)
FILES CHANGED:
  docs/submission/FINAL_SUBMISSION_AUDIT.md     NEW final audit
  docs/submission/FINAL_PACKAGE_CHECKLIST.md    FIX locked-test path to scripts/run_experiment.py
  docs/submission/SUBMISSION_CHECKLIST.md       cross-links only (human states unchanged)
  README.md                                     submission materials pointer
  docs/STATUS.md                                short final-audit block
  docs/DEBUG_LOG.md                             this entry
WHY EACH:           Final audit mission Â§Tasks 1â€“5; documentation-only corrections for verified path/links
TESTS RUN + RESULTS:
  not re-run this audit â€” last recorded 2026-10-14: run_tests.py 87/87 exit 0; smoke all PASS
  integrity recheck -> weights/threshold unchanged; Phase2 SHA-256 unchanged; interaction in backend=0; docker=None
  inventory -> docs/submission listed; evidence/capture MISSING; browser_check PNG/DOM PRESENT; design PDF valid
TESTS NOT RUN:      locked test; interactive browser; docker build; s390x; sklearn
KNOWN LIMITATIONS:  no video/screenshots; organizer primary source absent; T1 open
ASSUMPTIONS:        Audit is read-only except minimal doc path/link fixes; no media fabricated
CONTRACT CHANGES REQUESTED: none
NEXT STEP:          TEAM MEMBER completes HUMAN_HANDOFF + EVIDENCE_CAPTURE_CHECKLIST + compliance review

## 2026-10 Submission unblock pass â€” handoff & packaging (OpenCode)

ROLE / TASK:        Official-rules handoff, evidence-capture checklist, final package inventory, safe integrity recheck, go/no-go
STATUS:             COMPLETE â€” recommendation remains **NOT READY** (compliance unconfirmed until official rules + human media)
FILES CHANGED:
  docs/submission/HUMAN_HANDOFF.md             NEW official-rules human handoff (HUMAN REQUIRED)
  docs/submission/EVIDENCE_CAPTURE_CHECKLIST.md NEW browser/video/screenshot capture (open for human)
  docs/submission/FINAL_PACKAGE_CHECKLIST.md   NEW packaging inventory
  docs/submission/SUBMISSION_UNBLOCK_REPORT.md NEW go/no-go
  docs/DEBUG_LOG.md                            this entry
WHY EACH:           Unblock mission Â§Tasks 1â€“5; no product code changes
TESTS RUN + RESULTS:
  run_tests.py -> 87/87 exit 0
  smoke_test.py -> exit 0 all PASS
  integrity -> weights/threshold unchanged; Phase2 SHA-256 unchanged; interaction_in_backend_py=0; docker=None
TESTS NOT RUN:      locked test; interactive browser click-through; docker build; s390x; sklearn
KNOWN LIMITATIONS:  no video; no cert screenshots; organizer primary source not in tree; T1 open
ASSUMPTIONS:        Required-vs-recommended for video/LinuxONE is UNKNOWN RULE until official source reviewed
CONTRACT CHANGES REQUESTED: none
NEXT STEP:          TEAM MEMBER fills HUMAN_HANDOFF from official rules, completes EVIDENCE_CAPTURE_CHECKLIST, then re-score packaging

## 2026-10 Completion pass 3 â€” final submission readiness / go-no-go (OpenCode)

ROLE / TASK:        Evidence matrix, integrity recheck, submission inventory, go/no-go
STATUS:             COMPLETE â€” recommendation **NOT READY** (organizer rules + media gaps)
FILES CHANGED:
  docs/submission/COMPLETION_PASS_3_REPORT.md  NEW go/no-go
  docs/submission/DEMO_SCRIPT.md               manual capture list made explicit
  docs/STATUS.md                               aligned browser PARTIAL / Docker BLOCKED
  docs/DEBUG_LOG.md                            this entry
WHY EACH:           Mission Â§6â€“Â§7; no product expansion
TESTS RUN + RESULTS:
  run_tests.py -> 87/87 exit 0
  smoke_test.py -> exit 0 all PASS
  TX-DEMO-0001 -> NO_SIMULATION 0.413874 forks 0 numpy
  TX-00300 -> SIMULATED BLOCK_OR_HOLD 0.718654 forks 6; 3 stress failed numpy
  frozen weights/threshold + Phase2 SHA-256 -> unchanged
  docker -> BLOCKED; official rules URL in tree -> none (HUMAN REQUIRED)
TESTS NOT RUN:      locked test; interactive browser; docker build; s390x
KNOWN LIMITATIONS:  no video; no cert screenshots; organizer compliance open
ASSUMPTIONS:        Pass 3 is docs+verification only
CONTRACT CHANGES REQUESTED: none
NEXT STEP:          TEAM MEMBER supplies rules URL/fields, records video/screenshots, optional LinuxONE/Docker

## 2026-10 Completion pass 2 â€” submission rehearsal & evidence closure (OpenCode)

ROLE / TASK:        Demo reproducibility, Edge partial browser check, integrity recheck, claims honesty
STATUS:             COMPLETE (no gate/schema/evidence policy changes)
FILES CHANGED:
  docs/submission/DEMO_SCRIPT.md            operationalized (prereqs, readiness, shutdown, expected scores)
  docs/BROWSER_VERIFICATION_CHECKLIST.md    Edge headless partial VERIFIED section
  docs/submission/SUBMISSION_CHECKLIST.md   pass 2 rows
  docs/submission/COMPLETION_PASS_2_REPORT.md NEW
  evidence/claims.md                        organizer-rules secondary note + HUMAN supply list
  evidence/browser_check/*                  DOM + PNG from Edge headless
  docs/DEBUG_LOG.md                         this entry
WHY EACH:           Mission tasks 1â€“6; close evidence gaps without T1
TESTS RUN + RESULTS:
  run_tests.py -> 87/87 exit 0
  smoke_test.py -> all PASS
  API/HTTP demo TX-DEMO-0001 -> NO_SIMULATION 0.413874 forks 0 numpy
  API/HTTP demo TX-00300 -> SIMULATED BLOCK_OR_HOLD 0.718654 forks 6; all 3 stress failed
  Edge headless dump-dom -> TX-DEMO-0001 present; screenshot 47785 bytes
  docker -> BLOCKED; playwright/selenium -> absent
  frozen weights/threshold + Phase2 SHA-256 -> unchanged
TESTS NOT RUN:      locked test; interactive browser clicks; docker build; s390x
KNOWN LIMITATIONS:  interactive UI still NOT VERIFIED; no cert screenshots; organizer rules HUMAN
ASSUMPTIONS:        Edge already on host â€” no tool install
CONTRACT CHANGES REQUESTED: none
NEXT STEP:          Human browser checklist + claims.md rules + video; T1 still human

## 2026-10 Completion pass 1 â€” demo & submission readiness (OpenCode)

ROLE / TASK:        Docs counts, demo script, submission checklist/disclosures, claims ledger, browser checklist
STATUS:             COMPLETE (no gate/schema/evidence changes)
FILES CHANGED:
  README.md, docs/LINUXONE_RUNBOOK.md   57â†’87 test count
  docs/STATUS.md                        completion-pass block
  docs/BROWSER_VERIFICATION_CHECKLIST.md NEW (checklist only â€” NOT a passed browser test)
  docs/submission/DEMO_SCRIPT.md        NEW â‰¤3 min
  docs/submission/SUBMISSION_CHECKLIST.md NEW
  docs/submission/DISCLOSURES.md        NEW honesty text
  evidence/claims.md                    host-verified claims + HUMAN REQUIRED rules fields
WHY EACH:           Task list for deadline pass 1
TESTS RUN + RESULTS:
  run_tests.py -> 87 passed 0 failed
  smoke_test.py -> all PASS incl HTTP; TX-00300 SIMULATED BLOCK_OR_HOLD forks=6
  demo analyze TX-00300 -> score 0.719, stress fails all 3 scenarios
  docker CLI -> None (BLOCKED)
  playwright/selenium/chromium -> absent (browser NOT VERIFIED)
  Phase2 bundle SHA prefixes unchanged; frozen weights/threshold unchanged
TESTS NOT RUN:      browser, docker build, s390x, locked test
KNOWN LIMITATIONS:  numpy backend only on this host; T1/T2/human rules still open
ASSUMPTIONS:        Auth for docs/demo packaging only; no policy change
CONTRACT CHANGES REQUESTED: none
NEXT STEP:          Human claims.md rules; browser dry-run; optional LinuxONE; then T1 decision

## 2026-10 Phase 3 â€” independent reproduction & robustness (OpenCode)

ROLE / TASK:        Phase 2 audit, unchanged reproduction, multi-seed robustness, adoption criteria
STATUS:             COMPLETE (AMD64/numpy; Phase 2 REPRODUCED; verdict BACKEND-CONDITIONAL)
FILES CHANGED:
  docs/PHASE3_ADOPTION_CRITERIA.md          NEW â€” A1..A10 predeclared BEFORE robustness
  scripts/phase3_reproduce_and_robustness.py NEW â€” R1..R6 driver
  tests/unit/test_phase3_ranking.py         NEW â€” 12 ranking/recalc/tie/bootstrap tests
  docs/PHASE3_REPRODUCTION_REPORT.md        NEW
  docs/PHASE3_ROBUSTNESS_REPORT.md          NEW
  docs/PHASE3_CHANGE_REPORT.md              NEW
  docs/STATUS.md, docs/DEBUG_LOG.md         updated
  evidence/results/analysis/phase3_20261013T204244Z_reproduction/ NEW (raw_predictions.csv etc.)
WHY EACH:           Mission Â§1â€“Â§7; independent verification before any adoption talk
TESTS RUN + RESULTS:
  phase3_reproduce_and_robustness.py -> exit 0; Phase 2 metrics reproduced 1e-9; sklearn BLOCKED
  pytest test_phase3_ranking + test_phase2_diagnostics -> 20 passed
  (full suite / smoke: see PHASE3_CHANGE_REPORT final verification rows)
TESTS NOT RUN:      sklearn re-run; s390x; locked test
KNOWN LIMITATIONS:  numpy-only; validation-only; jointly_dangerous still ~0.13 recall; seed invariance of A on numpy is structural
ASSUMPTIONS:        Predeclared criteria frozen before robustness; no production merge
CONTRACT CHANGES REQUESTED: none
NEXT STEP:          sklearn host re-run (A8); human A9/T1; LinuxONE runbook on target

## 2026-10 Phase 2 â€” research validation & gate diagnostics (OpenCode)

ROLE / TASK:        Gate diagnosis, interaction-aware hypothesis test, OSS reassessment, evidence integrity
STATUS:             COMPLETE (AMD64/numpy; hypothesis SUPPORTED_on_validation for that backend only)
FILES CHANGED:
  scripts/phase2_research_experiment.py   NEW â€” validation-only diagnosis + research ranking
  docs/GATE_DIAGNOSTIC_REPORT.md          NEW â€” root-cause + FN/category analysis
  docs/RESEARCH_EXPERIMENT_PLAN.md        NEW â€” pre-specified candidate + results
  docs/PHASE2_CHANGE_REPORT.md            NEW â€” change summary
  docs/OPEN_SOURCE_COMPONENT_ASSESSMENT.md Phase 2 addendum (no new runtime deps)
  docs/STATUS.md                          Open issue 1 annotated with Phase 2 VERIFIED findings
  tests/unit/test_phase2_diagnostics.py   NEW â€” 8 methodology tests
  evidence/results/analysis/phase2_*/     NEW experiment bundle (does not touch published validation/)
WHY EACH:           Deliverables 1-6 of Phase 2 mission; no frozen gate change
TESTS RUN + RESULTS:
  run_tests / pytest -> 75 passed, 0 failed
  smoke_test -> all PASS
  phase2_research_experiment.py -> exit 0; hypothesis_verdict=SUPPORTED_on_validation
  frozen constants + published evidence asserts -> OK
TESTS NOT RUN:      sklearn-backend Phase 2 re-run; s390x; locked test
KNOWN LIMITATIONS:  Interaction weights a priori (not calibration-fitted); numpy backend only
ASSUMPTIONS:        Validation-only policy selection is authorized research; production gate untouched
CONTRACT CHANGES REQUESTED: none
NEXT STEP:          Human T1 on M/D; re-run Phase 2 on sklearn/s390x; LinuxONE runbook on target

## 2026-10 LinuxONE validation tooling + evidence integrity session (OpenCode)

ROLE / TASK:        LinuxONE validation workflow, diagnostics, evidence integrity (Tasks 1-8)
STATUS:             COMPLETE (on AMD64 host; LinuxONE execution itself remains NOT VERIFIED)
FILES CHANGED:
  scripts/diagnose_env.py          NEW â€” offline env/arch/backend diagnostics
  scripts/validate_runtime.py      NEW â€” reproducible validation runner + evidence bundles
  scripts/trace_gate.py            NEW â€” read-only Impact Gate component trace
  docs/LINUXONE_RUNBOOK.md         NEW â€” target-platform procedure + evidence checklist
  docs/BACKEND_EVIDENCE.md         NEW â€” sklearn vs numpy evidence provenance
  docs/GATE_PERF_DIAGNOSTIC_PLAN.md NEW â€” T1 plan + TX-DEMO-0001 skip trace
  docs/STATUS.md                   UPDATED â€” VERIFIED/NOT VERIFIED/BLOCKED/KNOWN ISSUE labels
  docs/README.md                   UPDATED â€” verification table + diagnostics pointers
  AGENTS.md                        UPDATED â€” evidence rules, new commands
  backend/pipeline.py              runtime() adds config_sha256/dataset_sha256 inside model_versions dict (no schema change)
  backend/certificate/certificate.py â€” one runtime evidence line (no schema change)
  tests/unit/test_diagnostics_env.py NEW â€” 10 tests for diagnostics/reporting
WHY EACH:          Task 2/3 tooling; Task 4/5/6 documentation + truthful cert metadata; Task 7 status honesty; Task 8 coverage.
TESTS RUN + RESULTS:
  python scripts/run_tests.py      -> 67 passed, 0 failed
  python -m pytest -q              -> 67 passed, 1 warning (httpx/starlette deprecation)
  python scripts/smoke_test.py     -> all PASS incl. HTTP (not SKIP)
  python scripts/validate_runtime.py --include-optional -> overall PASS; live HTTP PASS;
    evidence: evidence/results/validation_runs/run_20261013T194724Z_AMD64_numpy/
  frozen constants + schemas assert -> UNCHANGED
  published evidence/results/validation/ -> INTACT (sklearn, 2026-10-13T02:28:31Z)
TESTS NOT RUN:      LinuxONE/s390x host run; Docker build; browser click-through
KNOWN LIMITATIONS:  Host is AMD64 + numpy backend; sklearn metrics not reproduced here.
                    Gate underperformance + demo skip remain KNOWN ISSUES (human T1/T2).
ASSUMPTIONS:        Pre-building rules claim still needs human source (claims.md).
CONTRACT CHANGES REQUESTED: none (model_versions keys and evidence lines only; schemas frozen)
NEXT STEP:          Execute docs/LINUXONE_RUNBOOK.md on real s390x; attach validation_runs bundle.

## 2026-10 pre-build session (Claude, cloud sandbox)

* ENVIRONMENT: `pip install fastapi pytest httpx` blocked (PyPI denied by the sandbox's egress policy). Did not work
  around it. Consequence: FastAPI layer + `pytest` itself unverified; added `scripts/run_tests.py` (pytest-style tests,
  no pytest needed) and kept all logic in framework-free `backend/pipeline.py`.
* BUG (mine): new mixed-type joint profile (wire -> ACH) judged "A alone survives" on B's service path, so A could fail
  on its own path. Fix: judge A on its own path in `build_jointly_dangerous`; found by
  `test_joint_pairs_keep_ground_truth_structure_and_60_second_cooccurrence`. Dataset regenerated.
* TEST BUG: certificate test expected a latency number in a `fraud_spike` failure case. Fixed the test.
* FINDING: gate under-performs the anomaly-only baseline on validation; demo transaction scored 0.503 < 0.60. Not fixed
  on purpose (frozen formula; human decision). See `docs/STATUS.md` and `docs/TASKS.md` T1/T2.
* CLEANUP: removed unused locals in `certificate._scenario_evidence`.

STATUS: PARTIAL. TESTS: 57 passed via `scripts/run_tests.py`. NOT RUN: pytest proper, HTTP routes, browser, Docker, s390x.
NEXT: TASKS T0.


## 2026-10-16 Interaction-aware gate wiring (human-authorized) - VERIFIED (OpenCode)

ROLE / TASK:        Activate interaction-aware ranking in the production gate per
                    user authorization ("anything for the win"). Wire
                    backend/gate/interaction_aware.py into ImpactGate.score_batch,
                    explain_signals, /explain explainer, what-if, certificate runtime.
STATUS:             INTERACTION_AWARE_ACTIVE_LOCAL_ALL_PASS - 141 passed, 0 failed
                    via scripts/run_tests.py (scikit-learn backend, 111.3s, 2026-10-16).
                    NOT YET re-run on LinuxONE (prior s390x runs are pre-activation).
STEPS EXECUTED:
  1. First wiring attempt computed window/load pressure from the INPUT BATCH -
     a batch of 1 degenerated to pressure=1.0, inflating every score by ~+0.40
     (demo 0.5824 -> 0.8824, all showcase txs selected). 8 tests failed.
     ROOT CAUSE: pressure must be dataset-context, not batch statistics.
  2. Rewrote interaction_aware.py to the Phase-2 research formula over
     extract_features columns (recent_count / recent_amount_ratio /
     recent_same_type -> W; max_background_load / path_max_background_load -> L),
     identical to scripts/phase2_research_experiment.py::build_interaction_features.
     Batch-size invariance now enforced by
     tests/unit/test_interaction_aware.py::test_score_is_batch_size_invariant.
  3. ImpactGate.score_batch: vectorized, uses score_feature_row(X, ...) when
     config.INTERACTION_AWARE_ENABLED; combine() retained as frozen reference.
  4. explain_signals + backend/explain/explainer.py + /explain endpoint: contributions
     are mode-aware (A/W/D/L when active, M/D/A/U frozen) and ALWAYS sum to the
     reported score; raw signals map {"M","D","A","U"} added so what-if stays stable.
  5. pipeline.runtime(): policy_formula now reports the active formula and
     ";mode=interaction_aware|frozen" so certificates self-describe.
  6. Showcase id set changed (slots are computed from live gate decisions):
     TX-DEMO-0001, TX-00154 (selected/fails), TX-01623 (selected/survives),
     TX-00001 (skipped/survives), TX-00108-B (missed failure).
     Tests de-hardcoded (static _SHOWCASE_IDS removed; hints are computed in
     pipeline.py:114 and remain honest).
SCORES (sklearn, 2026-10-16, interaction active):
  TX-DEMO-0001 0.516452 NO_SIMULATION (frozen was 0.582418; still below 0.60)
  TX-00154     0.661589 SIMULATED BLOCK_OR_HOLD ("fails a stress" slot)
  TX-01623     0.600031 SIMULATED REVIEW ("selected survives" slot; margin 3.1e-5
               over threshold - deterministic but tight; monitored)
  TX-00001     0.232720 NO_SIMULATION
  TX-00108-B   0.457158 NO_SIMULATION (counterexample/missed failure preserved)
TESTS:             141 passed, 0 failed (scripts/run_tests.py, AMD64/sklearn).
                   Previously failing 8 explained and fixed (see steps 1-6).
DEFECTS FIXED:     batch-degenerate pressure (critical, self-introduced);
                   explain/gate score divergence; frozen contributions vs active
                   score (explainer); policy_formula mislabeling; 3 stale test
                   assumptions (frozen-weight pins, index-based contribution reads).
DISCLOSURES / OPEN:
  D-1 config.py bytes changed by authorized activation (flag flip + INTERACTION
     keys): current SHA-256 f4b186a0ba2684f43153ceba7c4b535ff921e0fb48a7c29954b17e19e4d9d31c,
     which differs from the older frozen-list value 433cd998... (list predates activation).
     config.IMPACT_WEIGHTS / IMPACT_THRESHOLD / SCENARIOS / POLICY_VERSION / dataset
     SHA remain byte-identical; contract tests pin them (contract/test_schemas_and_interfaces.py:54).
  D-2 LinuxONE validation evidence (run_20261016T113630Z / run_20261016T132444Z) was
     produced by PRE-activation code. Target revalidation required before submission.
  D-3 Recall/budget tables in prior reports (PRE_TARGET_READINESS etc.) are frozen
     historical artifacts of frozen-gate scoring - still valid as recorded, not rerun.
GIT MUTATION:      NONE (working tree has no .git).
NEXT STEP:          docs/STATUS.md update; fresh AMD64 evidence run; tarball to
                    LinuxONE ~/blackbox; full s390x revalidation.

## 2026-10-16 Post-activation LinuxONE revalidation - VERIFIED (OpenCode)

ROLE / TASK:        Revalidate interaction-aware gate on the real LinuxONE
                    (s390x) target; supersede pre-activation target evidence.
STATUS:             LINUXONE_PASS_POST_ACTIVATION - overall_status=PASS,
                    runtime_label=linuxone, architecture=s390x,
                    model_backend=sklearn (first sklearn-mode target run;
                    prior target runs were numpy fallback).
EVIDENCE:           evidence/results/validation_runs/run_20261016T185139Z_s390x_sklearn/
                    (validation_report.json; pulled from guest ~/blackbox)
STEPS EXECUTED:
  1. tar.gz of working tree (0.94 MB) -> scp to guest -> extracted OVER ~/blackbox
     (project .venv preserved)
  2. scripts/run_tests.py -> 141 passed, 0 failed (26.9s, s390x)
  3. scripts/validate_runtime.py --include-optional -> overall PASS:
     env diagnostics (linuxone_verified=true), dataset SHA match
     546f57ce...d5c3, run_tests, pytest, smoke incl. HTTP, live_http_uvicorn
  4. Showcase scores on s390x/sklearn - IDENTICAL to AMD64/sklearn:
     TX-DEMO-0001 0.516452 NO_SIMULATION | TX-00154 0.661589 BLOCK (fails stress)
     TX-01623 0.600031 REVIEW (survives) | TX-00001 0.232720 skipped
     TX-00108-B 0.457158 skipped (missed failure)
CROSS-ARCH CLAIM:   interaction-aware gate scores reproducible AMD64 <-> s390x
                    (same sklearn 1.9.1, same dataset SHA, same seeds).
RESOLVES:           disclosure D-2 from the interaction-wiring entry.
REMAINING OPEN:     D-1 (config SHA disclosure) stands; browser click-through
                    still human-only; Docker build still BLOCKED on host.
GIT MUTATION:       NONE.

ROLE / TASK:        Rubric upgrades (human-authorized "start"): second AI
                    framework in the risk ensemble, IBM Granite LLM narrative,
                    containerized deployment path on LinuxONE.
STATUS:             LOCAL_ALL_PASS - 155/155 AMD64 (sklearn+xgboost); guest
                    s390x xgboost 3.4.1 source-built; Granite model
                    DOWNLOAD_OK into Jupyter container cache; s390x docker
                    build running (scipy/sklearn/xgboost compile).
EVIDENCE:           tests/unit/test_hybrid_risk.py (8 tests),
                    tests/unit/test_llm_explain.py (6 tests),
                    docs/STATUS.md hybrid+LLM activation block.
CHANGES (authorized):
  1. backend/gate/models.py  _XGBMembers + _HybridRisk; GateModels.hybrid_risk
     field; versions() reports both frameworks. resolve_hybrid() honours
     BLACKBOX_HYBRID_RISK=auto|on|off; "on" without xgboost is a hard error.
  2. backend/shared/config.py  UNCERTAINTY_HYBRID_MODEL, HYBRID_RISK_ENV,
     RISK_XGB_* (8 models x 64 trees, depth 4), LLM_* keys.
  3. backend/gate/calibration.py  fit_models(..., hybrid=None) pass-through.
  4. backend/intelligence/llm_explain.py  NEW: build_prompt + narrate with
     honest degradation (URL -> local transformers -> unavailable+reason).
  5. backend/main.py  /explain attaches llm_narrative (advisory; never
     changes the certificate). 6. frontend/static/app.js  renderLlmCard.
  7. scripts/llm_service.py  NEW: stdlib http.server Granite narrate service
     for the LinuxONE Jupyter container (torch+transformers preinstalled).
  8. requirements.txt  + xgboost>=3.0.  Dockerfile + INSTALL_BUILD_TOOLS
     (cmake/g++/gfortran/libopenblas/pkg-config) for s390x source builds;
     documented s390x recipe with BASE_IMAGE=s390x/python:3.11-bookworm.
SCORE IMPACT:       Gate scores byte-identical (interaction formula has no U
                    term; regression test pins it). U values change (hybrid
                    members) - disclosed via versions()["hybrid_risk"]=on and
                    risk_model string. Showcase ids unchanged.
DISCLOSURES:
  D-4 config.py SHA-256 evolved f4b186a0...d31c -> c6228f18...6cfd (hybrid+LLM
      keys) -> 7c38c455...e100 (LLM_TIMEOUT_S 20->120 after live s390x Granite
      measured ~48.7s/narrative; 20s caused honest TimeoutError degradation).
      Frozen weights/threshold/scenarios/POLICY_VERSION/dataset SHA unchanged
      (contract tests green).
  D-5 xgboost members may differ at low-order precision AMD64 vs s390x
      (hist tree builds); gate decisions unaffected (no U term). U shown in
      /explain is that machine's real value.
  D-6 LLM narrative is ADVISORY ONLY and unavailable unless BLACKBOX_LLM_URL
      or BLACKBOX_LLM_MODEL is configured; the API/frontend never invent text.
  D-7 Prior frozen-mode benchmark tables (recall@budget etc.) predate the
      hybrid; they remain historical artifacts (U did not drive those ranks
      directly but re-measurement under the hybrid is a possible follow-up).
TEST DISCIPLINE:    run_tests.py calls test functions with ZERO arguments -
                    new tests must not use pytest fixtures (monkeypatch broke
                    4 tests in full-suite mode; rewrote stdlib _env()).
TARGET STATUS:      guest suite + docker build on s390x IN PROGRESS at log
                    time; finalize in the next entry.
GIT MUTATION:       NONE.

ROLE / TASK:        Finalize rubric upgrades: container run on s390x, live
                    Granite narrate chain, evidence capture, doc alignment.
STATUS:             LINUXONE_PASS_FULL_STACK - all four rubric upgrades
                    VERIFIED on the real target.
EVIDENCE:
  evidence/capture/container_health_s390x.json      - app container /health
  evidence/capture/granite_service_health.json      - LLM service /health
  evidence/capture/explain_llm_chain_s390x.json     - /explain with live
                                                      Granite narrative
  evidence/results/validation_runs/run_20261016T203734Z_s390x_sklearn/
  evidence/results/validation_runs/run_20261016T203407Z_AMD64_sklearn/
RESULTS (s390x guest, 2026-10-17):
  1. docker build3 (python-multipart fix) DONE; image blackbox:latest.
  2. Container run: status ok, runtime=linuxone, architecture=s390x,
     model_backend=sklearn, HEALTHY (docker status).
  3. granite-svc (--network host, jupyter image, shared hf_cache):
     /health loaded=true for ibm-granite/granite-3.0-1b-a400m-instruct.
  4. Direct llm_explain.narrate -> available=true, ~48.2s CPU.
  5. App chain: uvicorn + BLACKBOX_LLM_URL -> POST /explain ->
     llm_narrative available=true, latency_ms=57209, text grounded on the
     real certificate (amount 2406.59, hybrid_risk on, score 0.516452,
     NO_SIMULATION); certificate score byte-unchanged (advisory isolation).
  6. Suites: AMD64 155/155 (post-timeout-change), s390x 155/155 +
     validate_runtime PASS (run_20261016T203734Z_s390x_sklearn).
DEFECT FOUND+FIXED:
  - LLM_TIMEOUT_S=20 starved CPU Granite (measured 48-57s) -> set 120.0.
    First app-chain run failed with honest TimeoutError degradation while
    the service kept generating (BrokenPipe on send) - that failure path is
    itself useful evidence the advisory isolation works.
  - setsid in the test helper broke $! PID capture -> orphaned uvicorn held
    port 8010 and skewed one rerun; helper rewritten (no setsid, pkill).
CONFIG SHA:         7c38c455...e100 (final).
GIT MUTATION:       NONE.

## 2026-10-17 Full audit + fix session â€” ALL PASS (OpenCode)

ROLE / TASK:        User-directed full-project audit ("fix everything").
                    Systematic audit (3 parallel explorers + ~25 live adversarial
                    API probes, every headline finding reproduced) followed by
                    fixes across gate, certificate, benchmark, datasets, API,
                    LLM chain, frontend, tests and docs.
STATUS:             159/159 pytest PASS on AMD64 (sklearn 1.9.1 + xgboost 3.4.1,
                    interaction-aware active) after all fixes; 155 pre-fix +
                    4 new reverse doc-contract tests. Frozen contracts intact.
EVIDENCE:           contract test tests/contract/test_docs_match_code.py (new);
                    full-suite output 2026-10-17; live API re-verification on
                    127.0.0.1:8000 after restart.
DEFECTS FOUND + FIXED (ledger ids continue F-010):
  F-010 P0 CRITICAL - NaN silent-safe. A non-finite value (e.g. NaN in
    local_dependency_load) flowed through the interaction-aware gate:
    np.clip(nan)=nan, and (nan >= 0.60)=False -> silently skipped simulation ->
    NO_SIMULATION / ALLOW_NORMAL_PATH (the forbidden false-safe). Infinity
    degraded correctly; NaN did not. FIXED in three layers: (1) schema
    boundary - EventContext.local_dependency_load values, ImpactSignals and
    ImpactScore.score now allow_inf_nan=False, recent_transactions capped
    (max_length=100), window_seconds gt=0; (2) interaction_aware._clip01 now
    raises GateError on non-finite (was bare np.clip), and
    interaction_aware_score routes all four inputs through it; (3)
    impact_gate.score_batch raises GateError if any final score is non-finite
    (defense-in-depth for both gate paths). GateError degrades to truthful
    REVIEW via the existing pipeline path. Verified: schema rejects NaN at the
    boundary; injected-past-schema NaN raises GateError at the gate.
  F-011 P1 - Certificate evidence cited the frozen formula (M/D/A/U + frozen
    weights) even when the score was produced by the interaction-aware policy
    (self-contradicting certificate). _gate_evidence now branches on the active
    policy, prints the real weights and names W/L as context features not
    stored on the frozen ImpactSignals schema. Score printed .3f->.4f to stop
    "score 0.600 < threshold 0.60" rounding contradictions. fragility_margin
    KeyError -> CertificateError.
  F-012 P1 - Challenge Lab benchmark hand-copied the FROZEN formula, so it
    measured a policy production does not run. map/evaluate now score through
    ImpactGate.score_batch (the production path). Report gained
    policy_mode/policy_formula/active weights, rows_truncated_by_limit, and a
    limitation that W/L are zero for uploads (CSV has no context window).
    test_dataset_studio now pins the ACTIVE policy (strengthened coupling).
  F-013 P1 - decide_action returned ALLOW (gate short-circuit) before checking
    measured stress failures; a certificate carrying a FAILED fork could
    recommend ALLOW_NORMAL_PATH. Failures are now checked first; NO_SIMULATION
    path (no forks) unchanged.
  F-014 P1 - docs/CONTRACTS.md documented 4 of 17 routes; main.py docstring
    had stale path params ({tx_id}/{id}). Both updated to the real 17 routes;
    NEW reverse contract test test_docs_match_code.py enforces route table
    (both directions), documented gate-policy values vs config, and
    live-doc POLICY_VERSION vs config.
  F-015 P1 - README claimed a "cryptographic-hash Decision Certificate";
    cert_id is a uuid4 identifier, no certificate body is hashed. Reworded:
    config file and dataset are SHA-256 content-hashed; ids are identifiers.
  F-016 P1 - README documented BLACKBOX_INTERACTION env var that did not
    exist. Implemented: interaction_aware.is_enabled() honors
    on|off|auto (fail-loud on invalid values, matching resolve_hybrid
    discipline); off reproduces the frozen gate exactly. config.py stale
    "Default OFF" comment replaced with the actual activation record.
  F-017 P1 - Dataset row-cap rejection was unreachable (parser stopped at
    40,000 < cap 50,000), so row_count silently under-reported. Parse cap is
    now MAX_ROWS+1: oversized files are rejected with a truthful 422 and
    row_count is exact. CSV/Parquet caps consistent.
  F-018 P1 - index.json rewritten non-atomically without a lock (torn reads,
    lost updates); corrupt index silently reset. Now: threading.Lock around
    all mutations, temp-file + os.replace atomic write, corrupt index logged
    loudly with an orphaned-payload warning.
  F-019 P2 - Dataset row cache was unbounded (repeated uploads -> RAM
    exhaustion). Now a bounded LRU (8 datasets), reload from disk on miss.
  F-020 P1 - Upload handler read the entire body into RAM before the 5 MiB
    check, on the event loop. Now: pure-ASGI Content-Length middleware
    rejects oversized /datasets/upload with 413 before the body is read
    (multipart overhead allowance), and ingest_bytes runs via
    run_in_threadpool so /health stays responsive.
  F-021 P2 - EvaluateRequest.max_rows=0/negative/>5000 silently fell to the
    default (client asked for 0 rows, got 5000). Now Field(gt=0,
    le=DATASET_EVAL_MAX_ROWS) -> clear 422.
  F-021b P2 - BlackboxError escaping non-analyze routes surfaced as raw 500s.
    Global exception handler now returns the structured
    {error_type, error_message, trace_id} envelope (InputError -> 422).
  F-022 P1 - LLM HTTP timeout was per-socket-operation: a trickling
    BLACKBOX_LLM_URL could hold the thread open indefinitely, and the
    response body was read unbounded. Added wall-clock deadline
    (worker + result(timeout) + shutdown(wait=False)), 64 KiB response cap,
    http/https scheme allow-list.
  F-023 P1 - scripts/llm_service.py bound 0.0.0.0 unauthenticated, --lazy
    never actually loaded on request, the shared model was unserialized
    (ThreadingHTTPServer x generate), request bodies were read unbounded, and
    /health returned 200 even when the model failed to load. Fixed: default
    bind 127.0.0.1 (--bind to override), _maybe_load_lazy under a lock,
    _generate_lock, 64 KiB body cap, /health -> 503 on load error.
  F-024 P2 - Unknown transaction ids got a synthesized quiet context with no
    disclosure (background load is not measured). Pipeline now inserts an
    honest evidence line when the context was defaulted.
  F-025 P1 - pipeline.analyze loaded context/runtime OUTSIDE the REVIEW-
    degrading try: corrupted context returned a raw 500 instead of an honest
    REVIEW certificate. Moved inside; InputError re-raised so Type A input
    errors still propagate to 422.
  F-026 P2 - RiskModel.member_probabilities crashed on single-class trees
    (proba[:,1] IndexError; bootstrap trees CAN be single-class). Now pads by
    tree.classes_ (never saw a failure -> P(fail)=0), mirroring sklearn.
  F-027 P1 - Frontend recomputed the gate decision (score >= hardcoded 0.60)
    instead of rendering the backend decision. Now renders
    impact_score.gate_decision; threshold/formula/policy-mode all sourced from
    backend (/health + /explain).
  F-028 P2 - /counterexample and DELETE /datasets were unreachable from the
    UI. Added: "Run independent counterexample measurement" button on
    gate-skipped results (renders missed-failure with per-scenario outcomes,
    gate decision unchanged) and per-dataset Delete button (confirm ->
    DELETE /datasets/{id} -> refresh).
  F-029 P2 - Sticky full-height mobile sidebar overlapped main content. Now a
    static compact header with a horizontal scrollable nav on <=900px.
  F-030 P3 - UI honesty defects: sidebar formula showed a bare "I" (fragile
    split); sidebar labeled the active policy "(Frozen) UNCHANGED" while the
    interaction-aware policy was active (now a backend-driven mode pill
    FROZEN/INTERACTION-AWARE); blank first timeline row (synthetic stageless
    entry removed - real diagnostics events carry stages).
  F-031 P2 - scripts/run_tests.py aborted on the first module that imports
    pytest and reported pytest.skip as FAIL. Now: import guards (ERROR, run
    continues), skip outcomes and truthy skipif markers counted as SKIP,
    argument-taking (fixture) functions skipped with a reason, summary line
    includes skipped/errors.
  F-032 P3 - misc: explain payload certificate_link pointed at a nonexistent
    /api/certificates route (removed); counterexample "kind" mislabeled
    benchmark-label semantics (now measured_stress_vs_gate_decision);
    simulation_executed now bool(forks_tested) (REVIEW with partial forks
    was misreported as not-executed); _EXPERIMENTS ring guarded by a lock
    with snapshot iteration; versions() reports the ACTUAL hybrid state
    (risk.hybrid, not the requested flag); failure_probability got its
    missing _fitted guard; health/datasets/experiments fetches now check
    r.ok and render errors instead of silently swallowing or hanging.
  F-033 P3 - docs drift: STATUS Open Issue 2 presented pre-activation demo
    scores as current (now mode-labeled: 0.516452 interaction / 0.580013
    frozen on this host, re-measured 2026-10-17); AGENTS.md route list now
    points at the CONTRACTS.md table; suite-count claims updated 155->159
    (AMD64 post-fix; s390x evidence runs remain 155/155 historical);
    DISCLOSURES gained #12.
  NOT CHANGED (deliberate): M11 numpy cross-arch byte-stability - the numpy
    fallback uses LAPACK (pinv/solve) whose last bits can differ across CPU
    architectures. Changing numerics risked pinned showcase values, and the
    byte-identical claim only ever covered the sklearn (tree-based) backend.
    Fixed as an honesty disclosure instead: DISCLOSURES.md #12 states
    byte-identical reproduction applies to the sklearn backend only.
SCORE IMPACT:       None. Interaction-mode demo re-measured 0.516452 (pinned
                    value, byte-identical); frozen reference re-measured
                    0.580013 (labelled mode-specific). Showcase outcome slots
                    unchanged. Frozen weights/threshold/scenarios/
                    POLICY_VERSION/dataset SHA untouched (contract tests green).
                    Challenge Lab report fields extended (policy_mode/
                    policy_formula); benchmark now measures the production
                    policy (intended correction, disclosed in report).
SCHEMA NOTE:        EventContext gained additive Field CONSTRAINTS only
                    (finite loads, max_length=100 on recent_transactions,
                    window_seconds gt=0) - no field added/removed/renamed;
                    frozen-names contract test green.
TEST DISCIPLINE:    All 4 new tests are zero-arg (no fixtures). Full suite
                    159/159. run_tests.py verified (19 PASS on filter run).
GIT MUTATION:       NONE (no .git; no commits).

## 2026-10-17 Addendum to the audit-fix session â€” ALL PASS (OpenCode)

ROLE / TASK:        Live re-verification of the audit-fix session against the
                    running server, plus closure of the remaining minors.
STATUS:             161/161 pytest PASS (159 + 2 new regression tests).
                    Live HTTP + browser re-verification on 127.0.0.1:8000.
DEFECTS FOUND + FIXED:
  F-010a P0 addendum - The C1 schema constraint exposed a second-order bug on
    the LIVE path that the unit tests missed: FastAPI's DEFAULT
    RequestValidationError handler json.dumps()s the pydantic error, which
    embeds the offending INPUT VALUE - so a NaN input crashed the handler
    itself ("Out of range float values are not JSON compliant") and the client
    saw a raw HTTP 500 instead of the required Type A 422. Fixed with a custom
    RequestValidationError handler that sanitizes non-finite floats to their
    string form before serializing ({detail, error_type, trace_id}). Verified
    live: NaN/Infinity context -> structured 422; regression test
    test_http_non_finite_context_is_structured_422_not_500 pins it (raw
    content, not json= - httpx's own encoder rejects NaN client-side).
  F-024a P3 addendum - regression test
    test_http_unknown_transaction_discloses_defaulted_context pins the
    context-defaulted evidence line (needs a REAL account id; use
    demo_transaction().account_id, not a private repo attribute).
  F-034 P3 - Challenge Lab silently evaluated the FIRST mapped dataset with no
    way to choose (and no echo of which one ran). Added an explicit dataset
    selector (#eval-ds, populated from the mapped-dataset cache, with a
    "map a dataset first" placeholder); the evaluation runs the selected id.
LIVE RE-VERIFICATION (browser + curl, after restart on the fixed code):
  - /health ok; demo score 0.516452 byte-identical (pinned).
  - Gate evidence now cites the ACTIVE formula (interaction-aware
    0.45/0.30/0.15/0.10, W/L named as context features).
  - NaN/Infinity context -> 422 structured + JSON-safe (was 500 before
    F-010a; was silent ALLOW before F-010).
  - Unknown tx id -> "Context defaulted..." evidence line present.
  - UI: sidebar shows "Impact Gate - INTERACTION-AWARE" + full formula +
    MVP PARAMETERS pill (was a bare "I" and a false "Frozen/UNCHANGED");
    threshold badge rendered from backend gate_decision (was recomputed
    client-side); counterexample button on gate-skipped results renders the
    MISSED FAILURE measurement (demo fails all three stress scenarios when
    forced); dataset Delete button removes via DELETE /datasets/{id} and
    refreshes the list; mobile sidebar renders as a static compact header.
  - evidence/browser_check/edge_profile/ (241 files, audited empty) removed
    as hygiene bloat; evidence/browser_check/ artifacts retained.
SCORE IMPACT:       None (frontend + error-path only).
TEST DISCIPLINE:    2 new tests zero-arg. Suite 161/161; run_tests.py and
                    DOM harness (real app.js) green.
GIT MUTATION:       NONE.

## 2026-10-17 Addendum â€” frontend dynamism + text spillage (OpenCode)

ROLE / TASK:        Frontend polish pass: make policy rendering dynamic on
                    first paint; fix text spillage reported with screenshots
                    (Trust & Provenance hashes, Open Datasets license/URLs).
STATUS:             Fixed + live-verified in browser; suite re-run green
                    (see end of entry).
DEFECTS FOUND + FIXED:
  F-035 P2 - Text spillage: long unbreakable tokens (64-char SHA-256 dataset
    fingerprint / config hash, long license strings, source URLs) blew out
    their table cells and spilled past card edges. The key/value tables used
    auto layout, so a single hash inflated the table beyond its container.
    Fixed in style.css: global `body { overflow-wrap: anywhere }` (inherits
    everywhere), new `.kv-table` fixed-track layout (label col 34%, value col
    wraps via overflow-wrap: anywhere), modernized `.foot` to overflow-wrap.
    app.js now tags the Trust & Provenance and Open Datasets tables with
    `kv-table`. Live-measured: scrollWidth == clientWidth on every kv table
    and open-dataset card (0 overflowing elements), screenshots confirm
    license text and URLs wrap inside their cards.
  F-036 P2 - The sidebar policy card was placeholder-text on first paint
    ("Impact Gate - run Explorer for formula", "v...", pill "MVP PARAMETERS")
    until the user ran an analysis; the values shown were HTML defaults, not
    backend state. Fixed: /health (pipeline.health()) now reports
    policy_version, policy_mode, policy_formula - sourced from config +
    gate.interaction_aware.is_enabled() + explain.active_formula() (the SAME
    source /explain uses, so no drift is possible). loadHealth() renders all
    sidebar fields (version/mode/pill/formula/threshold) from /health on page
    load; run-time updates still override with identical backend truth.
    Contract test test_health_and_transactions_fields_used_by_ui strengthened
    to pin the new fields, mode vocabulary, and formula/mode consistency.
    Docs updated: CONTRACTS.md /health row, DEMO_SCRIPT readiness check.
LIVE RE-VERIFICATION (browser, fresh reload):
  - First paint: v1.0.0 / Impact Gate - INTERACTION-AWARE /
    I = 0.45*A + 0.30*W + 0.15*D + 0.10*L / Threshold 0.60 / pill
    INTERACTION-AWARE - no analysis run required.
  - /health JSON carries policy_version=1.0.0, policy_mode=interaction_aware,
    policy_formula (display form) alongside existing fields.
  - Trust & Provenance: both SHA-256 values fully inside the card;
    table 703/703 px, card 735/735 px (scroll == client, no overflow).
  - Open Datasets: all 3 cards 344/344 px, tables 312/312 px, 0 elements
    past the viewport; license + URL text wraps within card borders.
  - Note: the browser served a stale cached app.js on first re-check;
    refresh the cache entry (fetch cache:"reload") + reload before judging
    static-asset changes.
SCORE IMPACT:       None (presentation + diagnostics endpoint only; frozen
                    contracts untouched - weights/threshold/scenarios/
                    POLICY_VERSION unchanged).
TEST DISCIPLINE:    No new test files; one existing zero-arg contract test
                    strengthened. Full suite re-run: see below.
GIT MUTATION:       NONE.
RESULT:             161/161 pytest PASS (205s, AMD64, sklearn).

## 2026-10-17 Addendum - futuristic UI polish, LinuxONE badge, footer removal

ROLE / TASK:        Visual overhaul of the dashboard (professional / clean /
                    futuristic), a prominent linuxone-s390x runtime indicator
                    for the SSH demo, and removal of the version footer.
STATUS:             Fixed + browser-verified; UI test battery 13/13 PASS;
                    full-suite result recorded at the end of this entry.
DEFECTS ADDRESSED (user-requested changes, F-037..F-039):
  F-037 P3 - UI polish: full style.css overhaul keeping EVERY selector/ID/
    class intact (behavioral contract with app.js + DOM harness unchanged).
    New design tokens (deep-space #060a12 base, layered aurora radial
    gradients, translucent hairline borders, cyan/violet accents), glass
    sticky header (backdrop blur), gradient active-nav with glow, hover/
    focus states (focus-visible rings, lift transitions), gradient BREAK
    button with hover elevation, refined pills/notices (left accent edge),
    dial ring glow + tabular numerals, table row-hover + uppercase header
    micro-labels, custom thin scrollbars, prefers-reduced-motion honored,
    theme-color meta added. .card given the same gradient as .panel to avoid
    a same-specificity background override.
  F-038 P3 - SSH/mainframe indicator: /health already reports runtime=
    "linuxone" + architecture="s390x" on the guest; the chip text was
    already truthful but visually anonymous. loadHealth now swaps #runtime
    to class "chip mainframe" when runtime==="linuxone": cyan badge with a
    pulsing status dot (keyframes pulse), title "GET /health - IBM
    LinuxONE (s390x) - live over SSH". Reverts to plain "chip" on the
    error path. Verified by previewing the exact class on the live page
    (screenshot), then reverted to the truthful local state.
  F-039 P3 - Removed the sidebar version footer: index.html side-foot
    element, app.js writer, and the .side-foot CSS rule all deleted (they
    were only referenced by each other; tests never asserted them). The
    page now contains ZERO "0.1.0-prebuild" text (verified via DOM query);
    version still truthfully available in /health + certificate
    model_versions for diagnostics.
LIVE RE-VERIFICATION (browser):
  - Cache-refreshed style.css/app.js/dashboard (fetch cache:"reload") then
    reloaded; confirmed cssNew/jsNew/no-footer/theme-color in served bytes.
  - DOM: side-foot absent, no version text anywhere, chip
    "runtime: local . AMD64 . models: sklearn" class "chip", policy card
    v1.0.0 / INTERACTION-AWARE / full formula.
  - Screenshots: new aurora layout, gradient nav, policy card glow,
    mainframe badge preview (linuxone . s390x) applied then reverted.
SCORE IMPACT:       None (presentation only; no backend change; frozen
                    contracts untouched).
TEST DISCIPLINE:    No new tests; existing suite must stay green (UI
                    battery: 13/13 - behavioral harness, UI-API contract,
                    HTTP API). Full suite: see RESULT below.
GIT MUTATION:       NONE.
RESULT:             161/161 pytest PASS (179s, AMD64, sklearn).

## 2026-10-17 Addendum - Decision Certificate .json download (F-040, F-041)

ROLE / TASK:        Make the issued Decision Certificate downloadable as
                    .json from the UI (user request).
STATUS:             Implemented + live-verified; UI battery 13/13 PASS;
                    full-suite result at the end of this entry.
DEFECTS ADDRESSED:
  F-040 P2 - No way to export a certificate. Added a client-side download
    (no backend change, no schema/route change):
    - downloadJson() helper: pretty-printed JSON.stringify(obj, null, 2) ->
      Blob(application/json) -> temporary <a download> click -> revoke.
    - Toolbar: "Download .json" button (#dl-cert) appears with View
      Certificate after a run; downloads the exact certificate object the
      API returned (payload.certificate || payload).
    - Certificates panel: every row gets a sibling "down-arrow .json"
      button (.cert-row flex layout, mirroring .ds-row) downloading that
      stored certificate.
    - Filename: BLACKBOX-<certificate_id>.json.
    Live-verified by intercepting URL.createObjectURL + anchor.click:
    blob type application/json, 2819 bytes, valid JSON round-trip,
    certificate_id/status/evidence/impact_score/runtime all present,
    filename BLACKBOX-CERT-6112366EF4AE.json (both toolbar and per-row
    paths checked).
  F-041 P2 - Pre-existing UI bug found during that verification: the
    "View Certificate" link was VISIBLE on fresh page load despite its
    HTML hidden attribute, because .cert-link sets display:grid (author
    CSS beats the UA [hidden] rule). Fixed with a global
    "[hidden] { display: none !important }" reset (the standard guard;
    .panel-group/.state hidden handling unaffected). Verified: fresh load
    -> computed display none for #view-cert and #dl-cert; after BREAK ->
    both reveal; panel show/hide still intact.
LIVE RE-VERIFICATION: cache-refreshed assets, fresh reload, BREAK, both
    download paths captured and parsed, screenshots of toolbar (download
    right-aligned under View Certificate) and hidden-state checks.
SCORE IMPACT:       None (frontend only; certificate bytes are the API's
                    own certificate object, re-pretty-printed only).
TEST DISCIPLINE:    No new tests (harness does not exercise Blob/URL;
    UI battery 13/13 green before the full run).
GIT MUTATION:       NONE.
RESULT:             161/161 pytest PASS (83s, AMD64, sklearn).

## 2026-10-17 Addendum - Open Datasets tab removed; Studio seeded (F-042, F-043)

ROLE / TASK:        Remove the "Open Datasets" tab from the UI and populate
                    Dataset Studio with usable open datasets (user request).
STATUS:             Done + browser-verified; UI battery 21/21 PASS;
                    full-suite result at the end of this entry.
DEFECTS ADDRESSED:
  F-042 P2 - Open Datasets tab removed from the UI (metadata-only catalog;
    user chose to drop it). Removed: index.html nav button + #panel-open
    section, app.js PANEL_TITLES/click-hook/loadOpenDatasets, CSS
    .card-grid/.open-card (tab-only rules), and "panel-open" from the
    behavioral harness sideItems list (intentional product change; harness
    matches the new UI). The backend GET /datasets/registry route and
    backend/datasets/registry.py were KEPT untouched — pinned by
    test_ui_api_contract.py, test_dataset_studio.py, sweep_api_contract.py
    and the frozen verification evidence script. Registry metadata for the
    three curated sources therefore still exists server-side.
  F-043 P2 - Dataset Studio was empty (metadata tab had no import path).
    Seeded three datasets via POST /datasets/upload with full provenance:
    1. UCI Default of Credit Card Clients (REAL open data, CC BY 4.0 per
       the UCI page) - downloaded from archive.ics.uci.edu during setup,
       converted .xls->CSV losslessly (all 30,000 rows, 2.9 MB, no
       sampling), uploaded with attribution "Yeh, I.-C. & Lien, C.-H., UCI
       ML Repository", source_url, registry_id=uci_default_credit_card,
       label_semantics=default, sha256 recorded by the store.
       NOTE: left UNMAPPED - the dataset has no timestamp or
       transaction_type columns, and store.set_mapping requires all five
       transaction fields with values that are real columns. Mapping it
       would require inventing columns (fabricated structure in
       certificates) - refused; the dataset remains a faithful ingest.
    2. Synthetic payment-fraud stream (GENERATED, seed 42) - 20,000 rows,
       PaySim-inspired structure (mule accounts: 10-14 small card_payment
       setup txns then one balance-clearing wire/internal_transfer spike;
       60 fraud rows, 0.30%), fully mapped (id/account_id/amount/
       timestamp/transaction_type/label=is_fraud, semantics=fraud).
       Attribution explicitly states SYNTHETIC - not the real PaySim data;
       license CC0 (our generated data); sha256 b7df...-> new file
       re-recorded after regeneration.
    3. Synthetic credit-risk application stream (GENERATED, seed 7) -
       12,240 rows (180 applicants x 68 rounds; defaulters spike their
       requested amount 3-6x above their own application history; 2,353
       defaults, 19.22%), fully mapped, semantics=default, labeled
       SYNTHETIC (not the real UCI/Kaggle credit data), CC0.
    WHY SYNTHETIC FOR 2/3: the two Kaggle sets (ULB creditcard fraud,
    PaySim) require authenticated download; PaySim is CC BY-NC-SA and
    287 MB (over the 5 MiB/50k-row upload caps); ULB's CSV has no
    account_id/transaction_type columns so it CANNOT satisfy the five-field
    mapping contract without fabricating structure. Uploading synthetic
    data clearly labeled synthetic keeps certificate provenance honest.
    HONEST MEASUREMENT: Challenge Lab evaluate runs on both synthetic sets
    completed with the frozen v1.0.0 policy (run EX-... recorded): gate
    selected 0 of 5,000 scored rows on each (score_max 0.534/0.552 <
    threshold 0.60). This is consistent with the product itself - the
    flagship demo transactions score 0.5164/0.5800, also below 0.60. The
    gate is conservative by design; the benchmark reports recall honestly
    (confusion_note included). Data was NOT tuned to force gate crossings
    (that would be result-fitting).
LIVE RE-VERIFICATION: cache-refreshed assets; sidebar now 5 items (no
    Open Datasets); #panel-open absent; all 3 datasets render in Studio
    with row/col counts and mapped/needs-mapping status; Challenge Lab
    dataset selector sees them; screenshots captured.
SCORE IMPACT:       None (UI + demo data only; frozen contracts untouched;
                    GET /datasets/registry unchanged and still tested).
TEST DISCIPLINE:    Harness sideItems updated to match the intentional
                    tab removal; UI battery 21/21 PASS (behavioral harness,
                    UI-API contract, HTTP API, dataset studio).
GIT MUTATION:       NONE.
RESULT:             161/161 pytest PASS (190s, AMD64, sklearn); first run had 1 expected fail in\ntest_frontend_contract (nav pinned the removed Open Datasets tab); contract test\nupdated to pin the removal instead, then full suite green.

---

## F-044 - Granite narrative live on AMD64 (llama.cpp path), prompt-format fix, pitch deck

CONTEXT:            "Granite pairing" rubric item (2+ AI frameworks / LLM
    pairing). The app-side chain already existed and was contract-tested
    (backend/intelligence/llm_explain.py -> /explain.llm_narrative -> UI card
    renderLlmCard), but the only local bring-up path was transformers+torch,
    which is not installed on this host. No fabrication was ever an option.

CHANGE A (runtime): scripts/llm_service.py gains an auto-detected llama.cpp
    backend: a --model value ending in .gguf loads via llama-cpp-python
    (CPU, greedy, no torch). The transformers path is unchanged and the
    /health payload now reports "backend" (additive).
CHANGE B (prompt):  Granite 4.2 GGUFs ship WITHOUT an embedded chat template
    (chat_template absent in metadata). The Granite-3.x wrap
    (<|system|>/<|user|>) made the model echo its own instructions, and raw
    completion degenerated into repetition loops. Fixed by using the literal
    ChatML form from ibm-granite/granite-4.2-3b chat_template.jinja with
    thinking disabled:
        <|im_start|>system <sys><|im_end|>
        <|im_start|>user <prompt><|im_end|>
        <|im_start|>assistant
        <think></think>
    stop = ["<|im_end|>", "<|im_start|>"]. Verified: grounded 3-5 sentence
    narratives that reach EOS.
CHANGE C (UI):      URL-mode narrate services no longer leak the endpoint URL
    into the card pill; it now reads "LLM local service". No element ids or
    classes changed.
CHANGE D (deps):    requirements-llm.txt (optional; llama-cpp-python + the
    CPU wheel index). Frozen requirements.txt untouched.

REPRO (AMD64, Windows, CPython 3.12.10, 4 vCPU / 7.7 GB):
    pip install -r requirements-llm.txt
    python scripts/llm_service.py --model <granite-4.2-3b-Q4_K_M.gguf>    # :38899
    BLACKBOX_LLM_URL=http://127.0.0.1:38899/narrate uvicorn backend.main:app
    POST /explain {"demo_mode": true}

RESULT:             llm_narrative.available=true; narrative grounded on the
    certificate facts only (score, formula, threshold, contributions, backend);
    CERTIFICATE SCORE UNCHANGED - 0.5164521517240461 with and without the
    service attached (one-way flow proven again); demo transaction still
    NO_SIMULATION. Latency measured 26.6 s - 80.2 s (CPU-bound, machine-load
    dependent; 192-token cap via LLM_SERVICE_MAX_TOKENS).
EVIDENCE:           evidence/capture/llm_narrative_card.png (UI card; pill
    "LLM local service"; footer "advisory only ... never changes scores or
    decisions").
HONESTY:            model = granite-4.2-3b Q4_K_M (Apache-2.0) via llama.cpp,
    local, no hosted API; the unavailable path is unchanged and template text
    is never presented as LLM output.
SUBMISSION ARTIFACTS (this session, not a defect): pitch deck + architecture
    diagram (scripts/build_pitch_deck.py -> docs/submission/
    BLACKBOX_Pitch_Deck.pdf [12 pages] and BLACKBOX_Architecture_Diagram.pdf);
    five form answers with a 1024-char guard (docs/submission/
    SUBMISSION_FORM_ANSWERS.md + scripts/check_submission_answers.py, max 1020).
TEST DISCIPLINE:    UI battery + frontend contract 31/31 PASS; FULL SUITE
                    161/161 PASS (211.5 s, AMD64, sklearn).
GIT MUTATION:       All change work above was uncommitted. Then, EXPLICITLY
                    AUTHORIZED by the user for the portal's public-code field,
                    the repository was initialized and one submission commit
                    created (250 files, 10.5 MB; .venv/__pycache__/secrets
                    excluded by the existing .gitignore). No other git history.
                    Push to a remote is pending a repository URL.
