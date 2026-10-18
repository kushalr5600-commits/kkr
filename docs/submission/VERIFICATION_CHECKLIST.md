# Verification Checklist — BLACKBOX E2E Verification Sprint (2026-10-15)

Legend: **PASS** · **FAIL** · **N/R** (not run — reason given) · **LIMITED** (partial).

## Environment & baseline
- [x] PASS — Working dir + source identity recorded (no `.git`; tree `blackbox_work/blackbox`)
- [x] PASS — Runtime inspected (`CPython 3.12.10 AMD64`; not inferred from docs)
- [x] PASS — Active Python env + deps enumerated (sklearn/otel absent, recorded)
- [x] PASS — Baseline test result recorded: **119/119** before edits
- [x] PASS — Phase 2 frozen hashes verified: `3e26d127…` / `99dbe510…` **match**
- [x] PASS — Entry points & routes identified (`backend/main.py`; smoke/static tests)

## Frozen gate (§3)
- [x] PASS — Weights 0.30/0.30/0.25/0.15 (sum=1 asserted)
- [x] PASS — Score = frozen weighted sum (≤1e-12 error, 50-vector test)
- [x] PASS — Threshold boundary: 0.60 yes / 0.5999999 no / 0.6000001 yes
- [x] PASS — Certificate score == API score; contributions reconcile (1.1e-16)
- [x] PASS — Frontend does not recompute gate (`0.30` not in app.js)
- [x] PASS — NaN/Inf/out-of-range rejected (422 / GateError / pydantic)
- [x] PASS — M, D deterministic; A, U from active model

## AI/ML signals (§4)
- [x] PASS — A real output + empirical-CDF on calibration split only
- [x] PASS — A not presented as fraud probability (caveats asserted)
- [x] PASS — U = member std / 0.5 clipped (live match 1e-12)
- [x] PASS — U not described as calibrated confidence (caveats asserted)
- [x] PASS — Backend identity truthful (`numpy` in /health, versions, ai_signals)
- [N/R] sklearn backend — package absent (no parity claim)
- [x] PASS — Invalid features rejected (ValidationError / GateError)

## Simulation & fragility (§5)
- [x] PASS — Simulation only when gate-selected or documented research path
- [x] PASS — 3 frozen scenarios; 6 forks + 3 fragility on selected TX-00300
- [x] PASS — Skipped sim never gets fabricated stress results (empty arrays)
- [x] PASS — Successful sim ≠ universal safety (evidence limitations present)
- [x] PASS — Research paths cannot mutate production config/certs

## Explain & certificates (§6)
- [x] PASS — /explain values == /analyze decision (delta 0.0)
- [x] PASS — Plain/technical language agree; AI provenance correct
- [x] PASS — Policy version + threshold truthful in responses
- [x] PASS — Certificates validate against `decision_certificate.v1.schema.json`
- [x] PASS — Simulation evidence only when measured
- [x] PASS — Malformed input → controlled 422 (no traceback)

## Dataset Studio (§7)
- [x] PASS — CSV workflow end-to-end live (upload→map→evaluate)
- [x] PASS — Parquet path exercised by existing tests (deps present)
- [x] PASS — Size limit 422; row cap; unsupported suffix 422
- [x] PASS — Filename traversal sanitized (`_safe_stem`); id traversal 404
- [x] PASS — No code execution from uploads; JSON-safe preview only
- [x] PASS — Fingerprint sha256 preserved across evaluate
- [x] PASS — Unmappable rows excluded + counted

## Challenge Lab reference (§8)
- [x] PASS — External labels ≠ stress outcomes (separate fields/notes)
- [x] PASS — Confusion matrix = selection vs external label
- [x] PASS — FN = skipped ∩ label-positive (reference vector: 3/13)
- [x] PASS — Precision `null` when zero selected (not 0.0)
- [x] PASS — Recall 0.0 correct for 0-selected / 3-positive matrix
- [x] PASS — Live run reproduced same *logic shape* with its own run ID
- [x] PASS — Small-sample warning visible
- [x] PASS — Stress sample separate; labels not overwritten
- [x] PASS — FN analysis cannot change gate (research_only flags)
- [x] PASS — New runs mint new IDs; historical evidence untouched

## What-If & Experiments (§9)
- [x] PASS — Only documented overrides accepted; unknown key 422
- [x] PASS — NaN/Infinity rejected 422
- [x] PASS — Original object never mutated
- [x] PASS — research_only + disclaimer present
- [x] PASS — Deterministic on repeat
- [x] PASS — /experiments unique run IDs, measured vs hypothetical distinguished
- [x] **FAIL→FIXED (F-001)** — original baseline graph corruption on type override (P2)

## Frontend & API (§10)
- [x] PASS — Dashboard 200; logo asset 200; node syntax check
- [x] PASS — 9 frontend contract tests (honesty strings, nav, brand)
- [x] PASS — No hardcoded demo scores as live results
- [x] PASS — Green/amber/red semantics (sim-skip is amber)
- [x] LIMITED — Visual browser click-through **not performed** (no browser tool)
- [x] PASS — Live API suite 19/19 (same endpoints the UI calls)

## Security & ops (§11)
- [x] PASS — Strict request schemas (extra=forbid)
- [x] PASS — Upload limits + safe temp paths + cleanup
- [x] PASS — Secrets scan clean (2 contextvar false positives)
- [x] PASS — No dev-absolute paths in code
- [x] PASS — OTel disabled no-op (`otel_enabled=0`)
- [x] PASS — Health truthful; startup failure message actionable
- [x] PASS — No external network calls in core decision path

## Test suite (§12)
- [x] PASS — `run_tests.py` → **120 passed / 0 failed**, exit 0
- [x] PASS — `smoke_test.py` (HTTP required) → exit 0
- [x] PASS — New regression test added for F-001 (suite grew, none weakened)
- [N/R] Locked test — **forbidden**

## IBM Z / LinuxONE (§13)
- [x] PASS — Architecture determined at runtime: **AMD64**
- [N/R] s390x checks — not on target; commands prepared in report §13
- [x] PASS — No s390x compatibility claimed

## Outputs (§15)
- [x] PASS — Evidence dir `evidence/results/verification/run_20261015T002445Z_AMD64_verification/`
- [x] PASS — `COMPREHENSIVE_VERIFICATION_REPORT.md`
- [x] PASS — `VERIFICATION_FINDINGS.md`
- [x] PASS — `VERIFICATION_CHECKLIST.md`
- [x] PASS — Historical reports/evidence preserved

## Final status (§16)
- AMD64: **PASS_WITH_LIMITATIONS** (browser visual, sklearn path, OTel-enabled path unverified)
- LinuxONE: **BLOCKED** (not on target)
