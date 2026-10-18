# BLACKBOX demo script (≤ 3 minutes)

**Host (2026-10-15):** AMD64 Windows · CPython 3.12.10 · backend **sklearn** (scikit-learn 1.9.1)  
**Backend note:** Certificate `model_versions.backend` reads `sklearn` here (scikit-learn 1.9.1 installed). The NumPy fallback is available on hosts without scikit-learn. Evidence dated before 2026-10-15 is NumPy-labeled — do not mix labels (see `docs/submission/SKLEARN_BACKEND_SWITCH_REPORT.md`).

## Prerequisites (from a clean checkout)

| Item | Value |
|---|---|
| Python | 3.11+ (verified 3.12.10) |
| Install | `python -m venv .venv` then activate; `pip install -r requirements.txt` (or `requirements-dev.txt` for tests) |
| Working directory | **repository root** (where `backend/` and `frontend/` live) |
| Port | free `8000` (demo uses `8000`; pass-2 rehearsal used `8765` to avoid clashes) |

```bash
# from repo root
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Readiness check (required before the timer)

1. Log shows Uvicorn running **and** startup finished (models fit for a few seconds: messages about fitting / application start).
2. In a second terminal:

```bash
curl -s http://127.0.0.1:8000/health
```

Expected JSON fields: `"status": "ok"`, `"runtime": "local"` (or `"linuxone"` only on s390x), `"model_backend": "numpy"` or `"sklearn"`, `"gate_threshold": "0.60"`, plus the policy fields the sidebar renders on first paint: `"policy_version": "1.0.0"`, `"policy_mode": "interaction_aware"` (or `"frozen"`), `"policy_formula": "I = …"`.

3. Optional API precheck (does not replace the UI demo):

```bash
curl -s -X POST http://127.0.0.1:8000/analyze -H "content-type: application/json" -d "{\"demo_mode\":true}"
# expect "status": "NO_SIMULATION", "transaction_id": "TX-DEMO-0001"
```

4. **Optional — LLM narrative beat (LinuxONE showcase env only):** the IBM
   Granite service must already be up (it is a second container on the guest:
   `docker run -d --network host --name granite-svc -v /home/linux1/shared:/home/ibm-user/shared
   -e HF_HOME=/home/ibm-user/shared/hf_cache <jupyter-image> python .../llm_service.py`,
   model cached; `/health` on `:38899`). Start the app with
   `BLACKBOX_LLM_URL=http://127.0.0.1:38899/narrate`. Verify:
   `curl -s -X POST http://127.0.0.1:8000/explain -H "content-type: application/json"
   -d "{\"demo_mode\":true}"` → `llm_narrative.available: true`. If any of this
   is not up, skip to the honest unavailable card — never fake the narrative.

### Open the dashboard

Browser URL: **`http://127.0.0.1:8000/dashboard`**  
(Also `http://127.0.0.1:8000/` → redirect to `/dashboard`.)

---

## Timeline (target ≤ 180 s)

### 0:00–0:20 — Hook + honesty
- Brand line: *“Don't predict the future. Test it first.”*
- **Runtime chip** (top-right): e.g. `runtime: local · AMD64 · models: sklearn`.
- One sentence: *“A cheap Impact Gate decides which transactions are worth expensive counterfactual simulation. Everything on this page is computed by the backend.”*

### 0:20–0:50 — Normal / no-simulation path
1. Left list: first item **TX-DEMO-0001** (hint: fixed demo / jointly dangerous pair) is auto-selected.
2. Click **BREAK MY DECISION**.
3. Expected certificate (verified via API **2026-10-16**, interaction-aware
   sklearn on AMD64 **and** s390x — identical scores; UI renders the same JSON):
   - **Status:** `NO_SIMULATION`
   - **Action:** `ALLOW_NORMAL_PATH`
   - **Score:** **0.516** on this sklearn host (threshold marker 0.60;
     interaction-aware mode `I = 0.45*A + 0.30*W + 0.15*D + 0.10*L`;
     frozen mode was 0.582 sklearn / 0.414 numpy)
   - **No** Normal-vs-stress table (empty `forks_tested`)
4. Call out: *“Empty fork table means no simulation was run — not ‘safe under load’.”*
5. Optional: mention the known gate blind spot (disclosures §7).

### 0:50–1:40 — Simulation path
1. Left list: select the item whose hint is **“Gate selects it; fails a stress test”** → showcase id **TX-00154** (ids are backend/mode-dependent — trust the hint from `GET /transactions`).
2. Click **BREAK MY DECISION**.
3. Expected (API-verified **2026-10-16**, interaction-aware sklearn):
   - **Status:** `SIMULATED`
   - **Action:** `BLOCK_OR_HOLD`
   - **Score:** **0.662**
   - **Six** fork rows: normal+stress for `3x_volume`, `fraud_spike`, `service_latency` — stress forks fail on this sklearn host (count may vary by backend; label what you see)
   - **15** evidence lines (including limitations)
   - Fragility column populated
4. Point at one normal-vs-stress number, M/D/A/U(+W/L) bars, footer `model_versions` (`policy_formula` shows the active formula + `mode=`).

### 1:40–2:20 — Certificate anatomy
- transaction_id, trace_id, certificate_id, evidence, limitations, runtime fingerprints.
- Footer `model_versions`: point out **`hybrid_risk: on`** and
  `risk_model: HybridTreeEnsemble (RF trees + XGBoost models)
  [scikit-learn-1.9.1 + xgboost-3.4.1]` — two AI frameworks in one
  uncertainty estimate. Gate scores are unchanged (the active interaction
  formula has no U term; a regression test pins that).
- Scroll to the **LLM Narrative (advisory)** card. If the Granite service is
  up (`scripts/llm_service.py` + `BLACKBOX_LLM_URL`, optional readiness
  step), read the 2–3 sentence narrative (~10 s) and stress "advisory only;
  scores never depend on it". If it is not configured, show the honest
  "Narrative unavailable" card instead — that honesty IS the demo. Never
  fake the narrative.

### 2:20–2:45 — Budget honesty (voice-over)
- Simulate iff score ≥ 0.60 under the **active** gate. Since 2026-10-16 the
  gate is **interaction-aware** (`I = 0.45*A + 0.30*W + 0.15*D + 0.10*L`;
  W/L = dataset-context pressure features, human-authorized activation) —
  the certificate `policy_formula` and `/explain` contributions show the
  active formula. The frozen formula is retained in code as a reference.

### 2:45–3:00 — Close
- LinuxONE reports `runtime: linuxone` only on s390x — **VERIFIED** (141/141
  pre-LLM + **155/155** hybrid/LLM tree + `validate_runtime.py` PASS,
  2026-10-17; identical showcase scores to AMD64). The local demo host itself
  is AMD64 unless you are recording on the guest.

---

## Where the certificate appears

| Path | What you see |
|---|---|
| Browser | Main panel after busy spinner; remains until you pick another tx and break again |
| API | `POST /analyze` JSON body (`DecisionCertificate`) |
| Logs | stderr diagnostics lines `request_received` … `response_sent` with `trace_id` |

There is **no** certificate file written to disk by default (demo is in-memory API + UI).

---

## Clean shutdown

| How | Steps |
|---|---|
| Foreground uvicorn | `Ctrl+C` in the server terminal (once); confirm process exits |
| Background job (PowerShell) | `Stop-Job <job>; Remove-Job <job>` or kill the PID listening on the port |
| Verify port free | `netstat -ano | findstr :8000` → no LISTENING row |

---

## API vs browser verification (as of pass 3)

| Check | Label |
|---|---|
| `/health`, `/transactions`, `/analyze` for both txs | **VERIFIED** on this host (HTTP + in-process, sklearn, interaction-aware) and on LinuxONE s390x (2026-10-16) |
| Edge headless loads `/dashboard`; DOM contains `TX-DEMO-0001` after JS | **PARTIALLY VERIFIED** (`evidence/browser_check/`) |
| Click BREAK, certificate panel, error state, themes, phone width | **NOT VERIFIED** (human checklist only) |

Do not describe the headless load as a full UI pass. Full click-through: `docs/BROWSER_VERIFICATION_CHECKLIST.md`.

---

## What must be captured manually (not present in the repo)

No demo video or certificate screenshots exist in the tree as of pass 3. A human must capture:

| Capture | When |
|---|---|
| Screen recording ≤ 3 min | Full timeline in this script |
| Screenshot: TX-DEMO-0001 certificate (NO_SIMULATION) | After first BREAK |
| Screenshot: “fails a stress test” showcase certificate (SIMULATED, 6 forks) | After second BREAK (id TX-00154 under 2026-10-16 sklearn) |
| Optional: `/health` JSON in a second tab | During runtime chip explanation |

Do not upload or claim these files until they are actually recorded.
