# Browser verification checklist (manual)

**Status:** **PARTIALLY VERIFIED** (pass 2, 2026-10-14) — Edge headless page load only; **not** a full interactive pass.

## Pass 2 automated-adjacent evidence (real Edge, no installs)

| Check | Result | Artifact |
|---|---|---|
| Edge present | `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` | host |
| `GET /dashboard` while uvicorn on `127.0.0.1:8765` | HTTP OK | — |
| Headless `--dump-dom` after virtual time | DOM contains `tx-list`, **`TX-DEMO-0001`**, `BREAK MY DECISION`, `state-idle` | `evidence/browser_check/dashboard_dom.html` |
| Headless `--screenshot` | **25719 / 47785 byte** PNG written | `evidence/browser_check/dashboard.png` |
| Live `POST /analyze` demo + TX-00300 | `NO_SIMULATION` / `SIMULATED BLOCK_OR_HOLD` forks=6 | session log |

**Still NOT VERIFIED:** clicking BREAK in a browser, certificate panel render, error state after server stop, dark/light, phone width, keyboard nav. No Playwright/Selenium (not installed; not authorized to install).

Use this checklist on a real desktop session. Only mark rows pass after **you** perform them.

For video, certificate screenshots, and session metadata paths, also use `docs/submission/EVIDENCE_CAPTURE_CHECKLIST.md` (submission unblock pass).

## Preconditions

- [ ] `uvicorn backend.main:app --host 127.0.0.1 --port 8000` running  
- [ ] `curl http://127.0.0.1:8000/health` returns `"status":"ok"`  
- [ ] Open `http://127.0.0.1:8000/dashboard`

## Functional walk-through

| # | Step | Expected | Pass? |
|---|---|---|---|
| B1 | Page load | Title BLACKBOX; runtime chip leaves “checking…” for e.g. `runtime: local · … · models: numpy` | [ ] |
| B2 | Transaction list | ≥2 items; first is TX-DEMO-0001 with hint about jointly dangerous pair; auto-selected | [ ] |
| B3 | BREAK MY DECISION enabled | Button enabled after selection | [ ] |
| B4 | Press BREAK MY DECISION | Busy state: spinner + “Stress-testing TX-…”) | [ ] |
| B5 | Certificate (demo) | Action ALLOW_NORMAL_PATH; status NO_SIMULATION; score gauge &lt; 0.60 marker (~0.41 numpy); **no** Normal-vs-stress table | [ ] |
| B6 | Stale-result guard | Select another tx and break again: previous certificate cleared before new busy state | [ ] |
| B7 | Simulating example | Choose hint “Gate selects it; fails a stress test” (backend-dependent id; 2026-10-16: TX-00154 under interaction-aware sklearn) → expect SIMULATED + BLOCK_OR_HOLD; 6 fork rows; all three stress FAILED on this host | [ ] |
| B8 | Signal bars | M, D, A, U all in [0,1] with numeric labels | [ ] |
| B9 | Evidence + limitations | Evidence bullets; Limitations section present | [ ] |
| B10 | Footer metadata | runtime, architecture, seed, models JSON visible | [ ] |
| B11 | Error path | Stop the server, press BREAK MY DECISION → error state with message; trace_id shown or “n/a” | [ ] |
| B12 | Retry/back | Error “Back” returns to idle; list still usable when server returns | [ ] |

## Presentation

| # | Step | Expected | Pass? |
|---|---|---|---|
| B13 | Phone width (~375px) | No horizontal clipping of primary controls; list scrollable | [ ] |
| B14 | Dark theme (if OS dark) | Text and gauge readable | [ ] |
| B15 | Light theme | Text and gauge readable | [ ] |
| B16 | Keyboard | Tab to list buttons and BREAK; Enter/Space activates | [ ] |

## Result

| Outcome | Mark |
|---|---|
| All rows pass | Browser click-through **VERIFIED** — update README + STATUS and attach your screenshots |
| Any row fails | File a UI bug (fixes allowed only if they do **not** change decision logic/schemas) |
| Partial only (headless load) | **Current state** — keep interactive rows **NOT VERIFIED** |
