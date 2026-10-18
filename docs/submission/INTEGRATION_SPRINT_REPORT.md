# Mature Open-Source Integration Sprint — report

**Date:** 2026-10-14  
**Host:** AMD64 · CPython 3.12.10 · model backend **numpy**  
**Overall label:** **LOCAL PROJECT COMPLETE — READY FOR TARGET VALIDATION**  
**LinuxONE / s390x:** **NOT VERIFIED** (authorized guest only; Oct 16)

---

## Status labels

| Label | Value |
|---|---|
| Local AMD64 validation | **PASSED** (104/104) |
| Frozen ImpactGate / Phase 2 | **UNCHANGED** |
| Interaction ranking in production | **ABSENT** (0 hits) |
| Locked test | **NOT RUN** |
| LinuxONE target validation | **NOT VERIFIED** |
| Submission media + organizer rules | **PARTIAL / HUMAN** |
| Overall | **LOCAL PROJECT COMPLETE — READY FOR TARGET VALIDATION** |

---

## What was integrated (and why)

| Component / change | Problem solved | Production? |
|---|---|---|
| Versioned Decision Certificate JSON Schema (`schemas/decision_certificate.v1.schema.json` + `scripts/export_certificate_schema.py`) | Reviewer had no machine-readable certificate contract; policy metadata was implicit | Schema is documentation of the **existing** Pydantic model — no field added/removed |
| `config.POLICY_VERSION = "1.0.0"` + `runtime.model_versions["policy_version"]` / `["policy_formula"]` | Certificates could not be tied to the frozen policy identity | Runtime **dict** fill only (RuntimeMetadata schema frozen) |
| Strict `AnalyzeRequest` (`extra="forbid"`) | Silent ignore of unknown top-level keys weakened the API contract | Yes — still 422 via Pydantic |
| Optional OTel hooks (`backend/shared/tracing.py`, `requirements-observability.txt`, `BLACKBOX_OTEL=1`) | Observability without requiring collector or changing certificates | **Optional**; no-op when disabled/absent |
| Certificate consistency + schema + OTel no-op tests | Regression risk when tightening contracts | test-only |
| HTTP smoke: `policy_version`, unknown-key 422, `otel_enabled` on `/health` | Smoke did not exercise the new contracts | yes |
| Runbook §6b: VS Code Remote-SSH + schema export + test deps | Authorized Oct 16 session path was incomplete | docs |
| OSS inventory update (OTel optional; Hypothesis deferred) | License/class inventory lagged | docs |

**Explicitly not integrated:** NetworkX, new frontend, new ML framework, Hypothesis (deferred — not needed), OTel as a production requirement.

---

## Files changed

| Path | Change |
|---|---|
| `backend/shared/config.py` | `POLICY_VERSION` |
| `backend/pipeline.py` | policy versions in runtime; optional `tracing.span` around stages |
| `backend/main.py` | strict `AnalyzeRequest`; `/health` otel fields; span on `/analyze` |
| `backend/shared/tracing.py` | **NEW** optional no-op OTel helpers |
| `requirements-observability.txt` | **NEW** optional otel packages (Apache-2.0) |
| `scripts/export_certificate_schema.py` | **NEW** schema exporter |
| `schemas/decision_certificate.v1.schema.json` | **NEW** generated schema |
| `tests/unit/test_certificate_schema_export.py` | **NEW** 4 tests |
| `tests/integration/test_http_api.py` | stricter API + certificate consistency |
| `scripts/smoke_test.py` | otel health field, policy_version, unknown-key 422 |
| `docs/LINUXONE_RUNBOOK.md` | §6b VS Code Remote-SSH + Oct 16 commands |
| `docs/submission/OPEN_SOURCE_COMPONENTS.md` | OTel optional, Hypothesis deferred |
| `docs/submission/INTEGRATION_SPRINT_REPORT.md` | this report |
| `docs/submission/LINUXONE_EXECUTION_READINESS.md` | labels + schema step |
| `docs/submission/FINAL_PACKAGE_CHECKLIST.md` | new deliverable rows |
| `docs/DEBUG_LOG.md` | append-only sprint entry |

---

## Commands executed (primary env)

```text
python scripts/export_certificate_schema.py     -> wrote schemas/decision_certificate.v1.schema.json
python scripts/run_tests.py                     -> 104 passed, 0 failed
python scripts/smoke_test.py                    -> all PASS including HTTP + policy_version + unknown-key 422
python -c integrity check                       -> weights/threshold/Phase2 hashes unchanged
```

| Check | Result |
|---|---|
| Tests | **104 passed, 0 failed** (was 100; +4 schema/OTel) |
| Smoke HTTP | **PASS** |
| Demo TX-DEMO-0001 | **NO_SIMULATION** / ALLOW_NORMAL_PATH / forks **0** (still) |
| Simulated TX-00300 | **SIMULATED** / 6 forks / BLOCK_OR_HOLD (still) |
| Frozen weights | `0.30/0.30/0.25/0.15` threshold **0.60** |
| Phase 2 `results.json` SHA | `3e26d127…` prefix unchanged |
| Interaction ranking in `backend/` | **0** |

---

## Acceptance criteria

| Criterion | Result |
|---|---|
| Full demo workflow without hidden steps | **PASS** (dashboard/API documented) |
| Schema-valid decisions incl. `NO_SIMULATION` | **PASS** (JSON Schema + HTTP consistency tests) |
| Existing tests not weakened | **PASS** (100 → 104; prior assertions kept) |
| Core app without optional observability | **PASS** (OTel absent; suite green) |
| Dependency/license changes documented | **PASS** (`OPEN_SOURCE_COMPONENTS.md`) |
| Local vs LinuxONE reported separately | **PASS** (this report labels AMD64 only) |
| Files / commands / tests / limits listed | **PASS** (this section) |

---

## Known limitations / unverified

1. **LinuxONE / s390x** — not executed; wheels for pydantic-core/numpy/otel **UNVERIFIED**.  
2. **Organizer rules, demo video, certificate screenshots** — HUMAN.  
3. **Gate performance (T1)** — open; interaction ranking stays research-only.  
4. **sklearn** — not installed on this host; backend **numpy**.  
5. **OpenTelemetry packages** — not installed here; path verified as no-op only.  
6. **Hypothesis** — deferred (test-only, compatible, not required).  
7. **Interactive browser video** — still not automated.

---

## STOP

Scope ends at local integration readiness. Do **not** claim `LINUXONE VERIFIED`
until `uname -m` is `s390x` and the runbook procedure has actually run.
Do not run the locked test. Do not change frozen gate policy.
