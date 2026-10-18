# Completion pass 2 — submission rehearsal & evidence closure

**Date:** 2026-10-14  
**Host:** AMD64 Windows · CPython 3.12.10 · **backend: numpy**  
**Git:** unavailable  
**Scope:** docs, demo rehearsal, evidence closure only — **no gate / schema / dataset / locked-test changes**

---

## 1. Files changed and why

| File | Why |
|---|---|
| `docs/submission/DEMO_SCRIPT.md` | Operational reproducibility: prerequisites, readiness `curl`, exact URLs, expected TX-DEMO-0001 / TX-00300 outcomes, certificate location, shutdown, API vs browser labels |
| `docs/BROWSER_VERIFICATION_CHECKLIST.md` | Record real Edge headless partial evidence; keep interactive rows open |
| `docs/submission/SUBMISSION_CHECKLIST.md` | Pass 2 dates; browser/Docker/demo rows aligned with this rehearsal |
| `evidence/claims.md` | Organizer-rules: secondary team-manual note only; explicit HUMAN field list; **no** invented URL/date |
| `docs/submission/COMPLETION_PASS_2_REPORT.md` | This report |
| `docs/DEBUG_LOG.md` | Dated session entry |
| `evidence/browser_check/dashboard_dom.html`, `dashboard.png`, `edge_profile/` | Captured Edge artifacts (DOM + screenshot) |

**Unchanged (integrity):** ImpactGate weights/threshold/semantics, schemas, datasets, splits, `evidence/results/validation/`, Phase 2 bundles, production ranking.

---

## 2. Commands, exit codes, outcomes

| Command | Exit | Outcome |
|---|---|---|
| `python scripts/run_tests.py` | **0** | **87 passed, 0 failed** (22.4s) |
| `python scripts/smoke_test.py` | **0** | Pipeline + HTTP all PASS |
| In-process demo + TX-00300 analyze | 0 | See §4 |
| `uvicorn … --port 8765` + `Invoke-RestMethod` `/health` `/transactions` `/analyze` | HTTP OK | Both analyze paths OK |
| Edge headless `--dump-dom` `http://127.0.0.1:8765/dashboard` | 0 | DOM has `TX-DEMO-0001`, `BREAK MY DECISION`, `state-idle` |
| Edge headless `--screenshot=…dashboard.png` | file written | **47785 bytes** PNG (`evidence/browser_check/dashboard.png`) |
| `where docker` / `shutil.which('docker')` | none | **BLOCKED** |
| Playwright / Selenium import | false | not installed; **not** installed this pass |
| Frozen weights/threshold read | — | unchanged 0.30/0.30/0.25/0.15 · **0.60** |
| Phase 2 SHA-256 | — | see §5 |
| Locked test | **not run** | by design |

---

## 3. Test and smoke (host-specific, backend-specific)

- **run_tests:** 87/87 on **AMD64 / numpy**  
- **smoke:** all PASS including HTTP; simulated example line `TX-00300 BLOCK_OR_HOLD`

---

## 4. Demo verification (API-level VERIFIED)

| Transaction | Status | Action | Score | Forks | Backend |
|---|---|---|---|---|---|
| **TX-DEMO-0001** (`demo_mode=true`) | `NO_SIMULATION` | `ALLOW_NORMAL_PATH` | **0.413874** | **0** | numpy |
| **TX-00300** (showcase “fails a stress”) | `SIMULATED` | `BLOCK_OR_HOLD` | **0.718654** | **6** | numpy |

Stress forks on TX-00300: `3x_volume`, `fraud_spike`, `service_latency` all **failed** (`survived=false`).  
Evidence count: demo has gate-skip evidence; sim certificate **15** evidence lines.

Live HTTP (port 8765) reproduced the same status/action for both paths.

**Browser UI click-through:** **NOT VERIFIED** interactively (no automation framework).  
**Browser page load + JS list population:** **PARTIALLY VERIFIED** via Edge headless DOM (`TX-DEMO-0001` present after virtual-time budget).

---

## 5. Frozen integrity

| Check | Result |
|---|---|
| `IMPACT_WEIGHTS` | `{'magnitude': 0.3, 'dependency': 0.3, 'anomaly': 0.25, 'uncertainty': 0.15}` **unchanged** |
| `IMPACT_THRESHOLD` | **0.60** unchanged |
| Phase 2 `phase2_20261013T202326Z_numpy_validation/README.md` | SHA-256 `99dbe5102b4d350506d3ebe9505513d709c23dadbb554ae44a337fb1965f601a` |
| Phase 2 `results.json` | SHA-256 `3e26d1271e37fcf707a1b33aee26649b8c5dcef0677f5da42e18bfd52fd2ff52` |
| Published sklearn validation dir | not written this pass |
| Locked test | not run |

---

## 6. Browser and Docker status

| Capability | Label | Reason |
|---|---|---|
| Edge binary | **PRESENT** | `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` |
| Headless dashboard load | **PARTIALLY VERIFIED** | DOM + PNG under `evidence/browser_check/` |
| Interactive UI walkthrough | **NOT VERIFIED** | No Playwright/Selenium; cannot click without installing tools (not authorized) |
| Docker | **BLOCKED** | CLI not on PATH; no build attempted |
| LinuxONE | **NOT VERIFIED** | unchanged |
| sklearn | **BLOCKED** | not installed; numpy labeled throughout |

---

## 7. Organizer-rules evidence status

- Search of the project tree found **no** organizer URL, rules file, or dated primary source.  
- Only secondary text: `docs/manuals/BLACKBOX_Team_Manual_v4.md` §1 (team understanding of dates/requirements).  
- `evidence/claims.md` remains **HUMAN REQUIRED** with an explicit supply list (title, URL/path, dates, verbatim clauses).  
- **No** compliance claim was invented.

---

## 8. Submission package review

| Deliverable | State |
|---|---|
| Demo script | **PRESENT** (pass 2 operationalized) |
| Submission checklist | **PRESENT** |
| Disclosures | **PRESENT** |
| Claims ledger | **PRESENT**; human fields **open** |
| Design PDF | **PRESENT** (`docs/submission/BLACKBOX_Design_Document.pdf`) |
| Browser screenshots of certificates | **MISSING** (only idle dashboard headless PNG) |
| LinuxONE evidence | **MISSING** |
| Locked-test evidence | **MISSING** (intentional) |
| README test count | **87/87** consistent with this pass |

---

## 9. Labels summary

| Item | Label |
|---|---|
| Automated tests + smoke | **VERIFIED** (AMD64/numpy) |
| API demo both transactions | **VERIFIED** (AMD64/numpy) |
| Frozen constants + Phase 2 hashes | **VERIFIED** unchanged |
| Edge headless dashboard load | **PARTIALLY VERIFIED** |
| Interactive browser click-through | **NOT VERIFIED** |
| Docker build | **BLOCKED** |
| LinuxONE / sklearn / locked test | **NOT VERIFIED** / **BLOCKED** / **not run** |
| Organizer compliance | **HUMAN REQUIRED** |

---

## 10. Remaining human actions / external blockers

1. Organizer rules source + dates in `evidence/claims.md`  
2. Interactive browser checklist (B1–B16) + certificate screenshots  
3. Optional: Docker host build (when CLI available)  
4. LinuxONE s390x run (runbook)  
5. T1 gate decision (out of scope here)  
6. Video recording from `DEMO_SCRIPT.md`  
7. sklearn environment for cross-backend research (optional for demo)

---

**STOP.** No T1 work, no gate policy change, no locked test, no production ranking merge.
