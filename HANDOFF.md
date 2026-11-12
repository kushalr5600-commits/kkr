# HANDOFF.md â€” session-start context for opencode on the laptop (2026-10-17)

**Read this file FIRST**, then `docs/STATUS.md`, then the last entries of
`docs/DEBUG_LOG.md`. `AGENTS.md` sections 2â€“3 are **stale** (still say "67 tests" /
"LinuxONE unverified") â€” trust STATUS.md, DEBUG_LOG, and this file. A pointer banner
now sits at the top of AGENTS.md.

## 1. Where you are

BLACKBOX â€” enterprise decision-preflight engine for the **IBM Z Datathon 2026**.
Submission tree as of **2026-10-17**: code + tests + docs + evidence are complete and
verified. This folder is the whole project (17.1 MB / 968 entries zipped 1.8 MB).
There is **no .git** here (`GIT_MUTATION: NONE` throughout) â€” do not init/commit
unless the user explicitly asks.

## 2. Verified state (do not re-verify unless asked; evidence already captured)

| Claim | Evidence |
|---|---|
| 161/161 tests pass on AMD64 (2026-10-17, post-audit fix session: 155 frozen-pinned + 4 reverse doc-contract + 2 C1/disclosure regression tests); the 155-subset passed on s390x LinuxONE | `evidence/results/validation_runs/run_20261016T203407Z_AMD64_sklearn/`, `run_20261016T203734Z_s390x_sklearn/` + local suite |
| `validate_runtime.py --include-optional` PASS, `runtime_label=linuxone` | same runs; `docs/submission/LINUXONE_VALIDATION_REPORT.md` |
| Hybrid risk ensemble active (sklearn RF trees + 8 XGBoost models), xgboost 3.4.1 | `backend/gate/models.py`, `tests/unit/test_hybrid_risk.py` |
| IBM Granite LLM narrative live on target (~57 s, advisory-only, score untouched) | `evidence/capture/explain_llm_chain_s390x.json`, `granite_service_health.json` |
| Docker image built+healthy **on the guest** (s390x) | `evidence/capture/container_health_s390x.json` |
| Active gate formula (interaction-aware, no U term) + frozen weights/threshold | `docs/STATUS.md` activation block; contract tests pin them |
| Config SHA final `7c38c455â€¦e100` (disclosed chain in DISCLOSURES Â§2) | `docs/submission/DISCLOSURES.md` |

Showcase scores (AMD64 â†” s390x identical): TX-DEMO-0001 0.516452 NO_SIMULATION;
TX-00154 0.661589 BLOCK; TX-01623 0.600031 REVIEW; TX-00001 0.232720; TX-00108-B 0.457158.
Showcase ids are dynamic â€” trust `GET /transactions` hints.

## 3. First commands on this laptop

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt          # sklearn 1.9.1 + xgboost 3.4.1 wheels
python -m pytest -q                      # expect: 155 passed
uvicorn backend.main:app --port 8000     # dashboard at http://127.0.0.1:8000/dashboard
```

`scripts/run_tests.py` calls tests with **zero arguments** â€” new tests must not use
pytest fixtures (stdlib helpers only). No matplotlib on this codebase â€” don't add it.

## 4. Remaining work (mostly human-only)

1. **Demo video â‰¤ 3 min** (user records on/near the LinuxONE target) â€” `docs/submission/DEMO_SCRIPT.md`.
2. Browser click-through of `/dashboard` (interactive UI never screen-captured in CI).
3. Organizer compliance check (human; `docs/submission/DISCLOSURES.md` Â§10/Â§D).
4. After the event: **rotate the `blackbox.pem` SSH key** (it was copied around during setup).

Optional agent assists if the user asks: help script the video, polish pitch docs,
package a submission bundle, re-verify on a new machine.

## 5. LinuxONE guest (only if remote work is needed)

- `<redacted-linuxone-guest>`, key `blackbox.pem` (**key intentionally NOT in this zip** â€”
  user must supply/rotate; never commit keys). Code lived at `~/blackbox` (final-synced).
- Guest extras not in this zip (rebuildable): `.venv`, Granite model cache
  `~/shared/hf_cache` (~1 GB), running containers (`blackbox`, `granite-svc`, `notebook`).
  Restart procedures: `docs/LINUXONE_RUNBOOK.md` (marked VERIFIED) +
  `docs/DEBUG_LOG.md` 2026-10-17b entry.
- Transfer notes: PowerShell has no `&&`; ssh heredocs with `$(...)` break â€” scp
  scripts instead; background tasks need `setsid nohup â€¦ &` (and beware `$!` capture).

## 6. Hard rules (audit safety â€” see AGENTS.md evidence rules)

- Never overwrite `evidence/results/validation/` or regenerate the dataset
  (manifest SHA pinned: `546f57ceâ€¦d5c3`).
- Never fake the LLM/demo: honest degradation only (`llm_narrative.available:false` is a feature).
- Frozen contracts: `POLICY_VERSION=1.0.0`, threshold 0.60, weights
  `{0.30,0.30,0.25,0.15}`, scenarios `[3x_volume, fraud_spike, service_latency]`.
- Claims discipline: `docs/submission/DISCLOSURES.md` governs what may be said in the pitch.

## 7. Key files map

`backend/` gate+models+LLM Â· `frontend/` plain-HTML dashboard Â· `tests/` 161 tests Â·
`docs/STATUS.md` activation + completion log Â· `docs/DEBUG_LOG.md` defect ledger Â·
`docs/submission/` DEMO_SCRIPT, DISCLOSURES, CHECKLISTS, LINUXONE report Â·
`evidence/` validation runs + live captures Â· `Dockerfile` s390x-ready Â·
`docs/BLACKBOX_LLM_Demo.ipynb` Granite notebook.
