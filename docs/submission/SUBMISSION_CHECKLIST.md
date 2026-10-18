# Submission checklist (IBM Z Datathon 2026)

**Updated:** 2026-10-14 (completion pass 2)  
**Verdict:** **NOT READY TO SUBMIT** until P0 items are closed or explicitly waived in writing.

Legend: **[DONE]** · **[OPEN]** · **[HUMAN]** · **[BLOCKED]**

## A. Code and demo (product)

| Item | State | Notes |
|---|---|---|
| Pipeline + gate + 3 scenarios + certificate | **[DONE]** | 155/155 tests (AMD64 + s390x, 2026-10-17); smoke PASS |
| FastAPI `/health` `/analyze` `/dashboard` `/transactions` | **[DONE]** | HTTP smoke PASS |
| Dashboard UI (static) | **[DONE]** code | Headless Edge load **PARTIALLY VERIFIED**; interactive click-through **[OPEN]** |
| Demo script ≤ 3 min | **[DONE]** | `docs/submission/DEMO_SCRIPT.md` (operational details pass 2) |
| Honest skipped-sim demo (TX-DEMO-0001) | **[DONE]** intentional | API-verified NO_SIMULATION score 0.516 (interaction-aware sklearn, 2026-10-16; AMD64 + s390x identical) |
| Full simulation demo path (selected failing tx) | **[DONE]** | API-verified “fails a stress” showcase (TX-00154) SIMULATED BLOCK_OR_HOLD score 0.662 forks=6 |
| Second AI framework in the product | **[DONE]** | Hybrid risk ensemble: RF trees + XGBoost bootstrap models (`hybrid_risk: on`); 155/155 tests AMD64 + s390x |
| LLM narrative (IBM Granite, advisory) | **[DONE]** code + model cached on target | `/explain.llm_narrative`; `scripts/llm_service.py`; honest unavailable state; DISCLOSURES §11 |
| Containerized deployment on s390x | **[DONE]** image built on target | s390x `blackbox:latest` via `INSTALL_BUILD_TOOLS=1`; container re-run after python-multipart fix |

## B. Honesty disclosures (must ship with any public claim)

| Disclosure | State |
|---|---|
| Gate underperforms anomaly-only on validation (frozen-era numbers) | **[DONE]** `DISCLOSURES.md` §1 + DEBUG_LOG D-7 |
| Interaction ranking research-only, not production | **[DONE]** §2 |
| sklearn cross-backend BLOCKED on current host | **[DONE]** §3 |
| LinuxONE VERIFIED (+ 155/155 post-LLM suite) | **[DONE]** §4 |
| Docker not claimed | **[DONE]** §5 |
| Locked test unused | **[DONE]** §6 |
| Demo TX-DEMO-0001 gate skip blind spot | **[DONE]** §7 |
| Synthetic / prototype policy | **[DONE]** §8 |

## C. Platform

| Item | State | Evidence / next step |
|---|---|---|
| AMD64 Python run | **[DONE]** | tests + smoke 2026-10-14 |
| LinuxONE / s390x native run | **[DONE]** | `run_20261016T185139Z_s390x_sklearn/` + 155/155 on guest; `docs/LINUXONE_RUNBOOK.md` |
| Docker image build on s390x target | **[DONE]** | `blackbox:latest` 2.04GB on guest Docker 29.8.0 (`INSTALL_BUILD_TOOLS=1`); AMD64 host CLI still absent |
| Browser manual click-through | **[OPEN]** | Headless Edge DOM+screenshot done; interactive rows still open |

## D. Research freeze / evaluation

| Item | State |
|---|---|
| Published validation evidence preserved | **[DONE]** |
| Phase 2/3 validation research | **[DONE]** (numpy; Phase 3 reproduced) |
| T1 human gate/D/M decision | **[HUMAN]** |
| T2 demo-story redesign (if T1 changes gate) | **[OPEN]** after T1 |
| Locked test `--confirm-frozen` once | **[OPEN]** only after freeze authorization |
| Interaction ranking production merge | **[HUMAN]** — **do not** without A9 |

## E. Submission package

| Item | State |
|---|---|
| README run instructions | **[DONE]** (counts corrected to 87) |
| Design PDF | **[DONE]** (pre-code; re-check statements if T1 changes D) |
| Demo script | **[DONE]** `DEMO_SCRIPT.md` |
| Disclosures | **[DONE]** `DISCLOSURES.md` |
| Evidence ledger sources/dates | **[HUMAN]** `evidence/claims.md` |
| Organizer rules / pre-build compliance | **[HUMAN]** `evidence/claims.md` §Rules + `docs/submission/HUMAN_HANDOFF.md` |
| Evidence capture (browser + media) | **[HUMAN]** `docs/submission/EVIDENCE_CAPTURE_CHECKLIST.md` (open) |
| Final package inventory | **[DONE]** as inventory `docs/submission/FINAL_PACKAGE_CHECKLIST.md` (media still open) |
| ≤ 3 minute video recording | **[HUMAN]** follow DEMO_SCRIPT |
| ≤ 3 min live demo dry-run + screenshots | **[OPEN]** |
| Dashboard screenshots (dark + light) | **[OPEN]** |
| Contact / team identity fields on portal | **[HUMAN]** |

## F. Explicit non-claims (repeat on the form if fields are free-text)

- Do **not** mark “runs on IBM LinuxONE” without s390x evidence.  
- Do **not** mark “Docker verified” without a successful build record.  
- Do **not** report locked-test metrics.  
- Do **not** present interaction-aware ranking as the shipped gate.

## Minimum path to “credible submission” if time collapses

1. **[HUMAN]** Answer claims.md rules block (or remove any pre-build claim).  
2. Record the ≤ 3 min demo from `DEMO_SCRIPT.md` on the AMD64 host (numpy backend, labeled).  
3. Paste `DISCLOSURES.md` into the submission notes.  
4. Ship with LinuxONE / Docker / locked-test = **not verified / not run**.  
5. Optional if 30+ min remains: browser checklist + screenshots; x86 `docker build` only if Docker appears.

**STOP:** Do not change gate weights, promote research ranking, or run the locked split under this checklist alone.
