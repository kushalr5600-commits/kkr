# Final package checklist (submission inventory)

**Date:** 2026-10-14 (submission unblock pass)  
**Working tree:** completion-pass checkout (git revision unavailable)  
**Legend:** VERIFIED = present and content-checked · PRESENT = file exists · ABSENT = not in tree · HUMAN REQUIRED · BLOCKED · NOT VERIFIED · UNKNOWN RULE (requirement not confirmed against official source)

**Required vs recommended:** Until official rules are reviewed (`HUMAN_HANDOFF.md`), rows marked **UNKNOWN RULE** are treated as **recommended evidence** or **team-policy required**, not as confirmed organizer mandates.

---

## Deliverables table

| Deliverable | Current file / path | Status | Human action needed |
|---|---|---|---|
| Design document | `docs/submission/BLACKBOX_Design_Document.pdf` | PRESENT | Confirm format matches official rules when known |
| Demo script | `docs/submission/DEMO_SCRIPT.md` | PRESENT (operationalized) | Follow for live/video run |
| Disclosures | `docs/submission/DISCLOSURES.md` | PRESENT | Add official-rules citations when available |
| Completion pass 2 report | `docs/submission/COMPLETION_PASS_2_REPORT.md` | PRESENT | none for packaging |
| Completion pass 3 report | `docs/submission/COMPLETION_PASS_3_REPORT.md` | PRESENT | none for packaging |
| Submission unblock report | `docs/submission/SUBMISSION_UNBLOCK_REPORT.md` | PRESENT | none for packaging |
| Final completion sprint report | `docs/submission/FINAL_COMPLETION_SPRINT_REPORT.md` | PRESENT | none for packaging |
| Integration sprint report | `docs/submission/INTEGRATION_SPRINT_REPORT.md` | PRESENT | none for packaging |
| Prototype sprint report | `docs/submission/PROTOTYPE_SPRINT_REPORT.md` | PRESENT | none for packaging |
| Decision Certificate JSON Schema | `schemas/decision_certificate.v1.schema.json` | PRESENT | re-export on guest after install |
| Optional observability group | `requirements-observability.txt` | PRESENT (not installed) | install only if OTel demos needed |
| Open-source components inventory | `docs/submission/OPEN_SOURCE_COMPONENTS.md` | PRESENT | re-check licenses on submit day |
| Local readiness evidence | `evidence/results/local_readiness/run_20261014T040122Z_AMD64_local/` | PRESENT | re-run on LinuxONE guest |
| Human rules handoff | `docs/submission/HUMAN_HANDOFF.md` | PRESENT (OPEN) | **Fill official source + verbatim clauses** |
| Evidence capture checklist | `docs/submission/EVIDENCE_CAPTURE_CHECKLIST.md` | PRESENT (OPEN) | **Complete captures; do not self-close** |
| Official organizer rules source | *not in tree* | **HUMAN REQUIRED** / **UNKNOWN RULE** | Supply URL/doc → `HUMAN_HANDOFF.md` + `evidence/claims.md` |
| Claims ledger | `evidence/claims.md` | PRESENT; rules section **HUMAN REQUIRED** | Complete human fields only from official source |
| Submission checklist (team) | `docs/submission/SUBMISSION_CHECKLIST.md` | PRESENT | Reconcile after rules + media |
| TX-DEMO-0001 certificate screenshot | *expected* `evidence/capture/TX-DEMO-0001_certificate.png` | **ABSENT** | Capture in interactive browser |
| TX-00300 certificate + 3 stress scenarios screenshot | *expected* `evidence/capture/TX-00300_certificate.png` | **ABSENT** | Capture in interactive browser |
| Demo video (≤ 3 min or official limit) | *expected* `evidence/capture/blackbox_demo.mp4` (or portal path) | **ABSENT** / **UNKNOWN RULE** (length) | Record genuine demo; confirm limit via official rules |
| Headless dashboard idle PNG (supporting only) | `evidence/browser_check/dashboard.png` | PRESENT | **Do not use as proof of both workflows** |
| Final compliance review | — | **NOT DONE** / **HUMAN REQUIRED** | After rules + media + optional LinuxONE/Docker |
| Automated suite evidence | host: `run_tests.py` 87/87 (2026-10-14) | **VERIFIED** (this host, numpy) | Re-run on target env if rules require |
| Smoke test | `scripts/smoke_test.py` | **VERIFIED** (this host) | Re-run on target env if rules require |
| LinuxONE / s390x run | `docs/LINUXONE_RUNBOOK.md` only | **NOT VERIFIED** | Execute on s390x if required by rules |
| Docker image | — | **BLOCKED** (no CLI) | Build where Docker exists if required |
| Locked test | `scripts/run_experiment.py --split test --confirm-frozen` | **NOT RUN** (by policy) | Run only under frozen `--confirm-frozen` policy when authorized |
| Interaction ranking in production | `backend/` | **VERIFIED absent** | none |
| T1 gate performance decision | `docs/STATUS.md` / TASKS | **OPEN** (human decision) | Team decision; out of packaging scope |

---

## Notes

- No extra deliverables were invented beyond files already referenced by prior completion passes and the unblock mission.
- **Required-by-official-rules** status for video length, LinuxONE, Docker, and form fields remains **UNKNOWN RULE** until `HUMAN_HANDOFF.md` is completed from a primary source.
- Automated agents must leave ABSENT / HUMAN REQUIRED / OPEN rows unchecked.

**STOP** after packaging inventory — do not mark human rows complete.
