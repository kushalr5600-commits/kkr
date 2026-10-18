# Manual evidence-capture checklist (browser + video)

**Status:** **OPEN — HUMAN REQUIRED** (2026-10-14).  
**Do not mark complete from headless Edge, API/HTTP checks, or any automated session.**  
A screenshot of the **idle dashboard alone does not prove both workflows.**

Related: `DEMO_SCRIPT.md` (timeline), `BROWSER_VERIFICATION_CHECKLIST.md` (B1–B16 UI rows), `HUMAN_HANDOFF.md` (rules).

---

## 1. Start the application (documented repository instructions)

- [ ] From repository root, use `docs/submission/DEMO_SCRIPT.md` prerequisites (venv, `pip install -r requirements.txt`, `uvicorn backend.main:app --host 127.0.0.1 --port 8000`).
- [ ] Confirm readiness: `/health` returns `"status":"ok"`; note `model_backend` (`numpy` or `sklearn`).
- [ ] Record: backend ____________, port ____________, date ____________.

## 2. Open `/dashboard` in a **real interactive browser**

- [ ] Navigate to `http://127.0.0.1:8000/dashboard` (not headless-only).
- [ ] Record browser and version: ____________ (e.g. Edge 1xx).

## 3. Capture TX-DEMO-0001 (normal path)

- [ ] Select **TX-DEMO-0001** in the transaction list.
- [ ] Press **BREAK MY DECISION**.
- [ ] Capture the displayed result: **NO_SIMULATION** / **ALLOW_NORMAL_PATH**.
- [ ] Save screenshot: `evidence/capture/TX-DEMO-0001_certificate.png` (create folder if needed).

## 4. Capture the simulated path (fails-a-stress showcase)

- [ ] Select the item whose hint is **“Gate selects it; fails a stress test”** (2026-10-16 sklearn: **TX-00154**; trust the hint, ids are backend/mode-dependent).
- [ ] Press **BREAK MY DECISION**.
- [ ] Capture: **SIMULATED** result, **certificate / evidence panel**, and **all three scenario outcomes** (e.g. 3x_volume, fraud_spike, service_latency).
- [ ] Save screenshot: `evidence/capture/showcase_fails_stress_certificate.png`.
- [ ] Confirm the three stress outcomes are visible in the capture (not just the headline action).

## 5. Legibility and quality checks

- [ ] No visible uncaught JS errors or broken layout on primary controls.
- [ ] Scores, status, action, and scenario rows are legible at normal video bitrate.
- [ ] Optional: run B1–B16 in `docs/BROWSER_VERIFICATION_CHECKLIST.md` and attach results.

## 6. Record demo (≤ 3 minutes)

- [ ] Record screen following `DEMO_SCRIPT.md` timeline (hook, both transactions, limitations, close).
- [ ] Stay within **≤ 180 seconds** (or the limit stated by official rules once supplied).
- [ ] Do **not** narrate organizer compliance until `HUMAN_HANDOFF.md` is filled from an official source.

## 7. Save genuine artifacts

| Artifact | Path (suggested) | Exists? |
|---|---|---|
| TX-DEMO-0001 screenshot | `evidence/capture/TX-DEMO-0001_certificate.png` | [ ] |
| Fails-a-stress showcase screenshot (3 scenarios) | `evidence/capture/showcase_fails_stress_certificate.png` | [ ] |
| LLM Narrative card screenshot (Granite text OR honest unavailable) | `evidence/capture/llm_narrative_card.png` | [x] |
| Footer `model_versions` showing `hybrid_risk: on` | `evidence/capture/hybrid_risk_footer.png` | [ ] |
| Container `/health` JSON on s390x (optional but strong) | `evidence/capture/container_health_s390x.json` | [ ] |
| Demo video | `evidence/capture/blackbox_demo.mp4` (or official portal path) | [ ] |
| Session metadata | `evidence/capture/SESSION_NOTES.md` (browser, backend, date, deviations) | [ ] |

- [ ] Files are real captures from this session — **no mockups, no invented metrics, no reuse of headless idle PNG as proof of both workflows**.
- [ ] Update `docs/submission/FINAL_PACKAGE_CHECKLIST.md` media rows with actual paths.

## 8. Session metadata

| Field | Value |
|---|---|
| Date / timezone | |
| Browser + version | |
| Backend (`numpy` / `sklearn`) | |
| OS | |
| Deviations from DEMO_SCRIPT | |
| Reviewer name | |

---

**Result:** Until every checked row above is performed by a human and files exist at the listed paths, interactive browser verification and demo media remain **NOT VERIFIED / ABSENT** in completion reports.
