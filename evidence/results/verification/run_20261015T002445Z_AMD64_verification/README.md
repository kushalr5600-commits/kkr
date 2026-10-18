# Verification run 20261015T002445Z — AMD64

Comprehensive E2E verification evidence (BLACKBOX).

| File | Contents |
|---|---|
| `run_tests.txt` | Full authorized suite — **120 passed / 0 failed**, exit 0 |
| `smoke_test.txt` | HTTP-required smoke test — exit 0, all PASS |
| `live_http_checks.txt` | 19 live HTTP workflow checks vs uvicorn :8000 — **19/19 PASS** |
| `certificate_schema_checks.txt` | JSON Schema validation + score reconcile + health |
| `environment.json` | Python/arch/deps actually present |
| `integrity.json` | Phase 2 frozen hashes — **match** |
| `health.json` | `/health` snapshot (local/AMD64/numpy/otel=0) |

Locked test: NOT RUN. LinuxONE: NOT RUN (AMD64 host only).
Findings: F-001 (P2 what-if baseline graph) fixed — see `docs/submission/VERIFICATION_FINDINGS.md`.
