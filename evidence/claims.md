# Evidence ledger

Record every externally verifiable claim before it appears in the README, video or slides.

```
CLAIM:
SOURCE:
DATE VERIFIED:
WHAT THE SOURCE ACTUALLY SUPPORTS:
WHAT WE ARE NOT CLAIMING:
```

## Rules / compliance (HUMAN MUST COMPLETE)

```
CLAIM: Pre-building BLACKBOX before the hacking period is permitted by the organizers.
SOURCE: <HUMAN REQUIRED — organizer message / rules URL / email, with the exact wording>
DATE VERIFIED: <HUMAN REQUIRED>
WHAT THE SOURCE ACTUALLY SUPPORTS: <HUMAN REQUIRED — only what the document actually says>
WHAT WE ARE NOT CLAIMING: that the code was written during the event, unless the source says that explicitly.
```

**Current status (2026-10-14 completion pass 2):** Still **unverified** against an organizer primary source.

**In-repo secondary material only (not a substitute for the organizer document):**
- `docs/manuals/BLACKBOX_Team_Manual_v4.md` §1 states the team’s understanding that the event is October 17–18, 2026, requires work during the official hacking period, and requires a demo video + codebase + LinuxONE demonstration.
- This is **team-authored documentation**, not an organizer URL, email, or published rules file. No organizer URL, document path, or access date was found in the project tree.

**HUMAN must supply exactly:**
1. Title of the current official rules (PDF/DOCX/web page)
2. Stable URL or attachment path
3. Date accessed / published
4. Verbatim sentences on: hacking-period requirements, pre-building, AI-assisted coding (if any), video length, submission contents, LinuxONE demonstration requirements
5. Whether the PDF and DOCX copies match

Until then, **do not** claim organizer compliance in the form, video, or README.

## Platform claims (evidence-backed from this repository / host)

```
CLAIM: LinuxONE architecture is s390x.
SOURCE: IBM LinuxONE / s390x architecture documentation (external); in-repo runbook docs/LINUXONE_RUNBOOK.md
DATE VERIFIED: 2026-10-14 (runbook text only — NOT a native execution log)
WHAT THE SOURCE ACTUALLY SUPPORTS: the target architecture name and that /health should report linuxone only when platform.machine()==s390x (backend/pipeline.py health()).
WHAT WE ARE NOT CLAIMING: that BLACKBOX has been executed on LinuxONE.
```

```
CLAIM: Python container images exist for linux/s390x (e.g. official python images).
SOURCE: Docker Hub / Python official images multi-arch manifests (external — human should re-open and date)
DATE VERIFIED: <HUMAN REQUIRED for any public claim>
WHAT THE SOURCE ACTUALLY SUPPORTS: image tags advertise s390x — only if the human confirms the manifest page.
WHAT WE ARE NOT CLAIMING: that our Dockerfile built successfully on s390x.
```

```
CLAIM: scikit-learn / NumPy install on the team's LinuxONE VM.
SOURCE: <HUMAN REQUIRED — actual install log on the VM>
DATE VERIFIED: <HUMAN REQUIRED>
WHAT THE SOURCE ACTUALLY SUPPORTS: <only the log>
WHAT WE ARE NOT CLAIMING: LinuxONE runs today (audit host is AMD64, sklearn missing).
```

```
CLAIM: Event format (24 hours), submission requirements, <= 3 minute video.
SOURCE: <HUMAN REQUIRED — organizer page URL + date>
DATE VERIFIED: <HUMAN REQUIRED>
```

## Software / environment claims (this host, 2026-10-14)

```
CLAIM: Automated suite is 87/87 on AMD64 CPython 3.12.10.
SOURCE: python scripts/run_tests.py → "87 passed, 0 failed"; python scripts/smoke_test.py all PASS
DATE VERIFIED: 2026-10-14
WHAT THE SOURCE ACTUALLY SUPPORTS: implementation consistency on this host with backend=numpy.
WHAT WE ARE NOT CLAIMING: LinuxONE, sklearn parity, or gate optimality.
```

```
CLAIM: Published sklearn validation evidence exists and was not overwritten.
SOURCE: evidence/results/validation/model_metadata.json (backend sklearn, 2026-10-13)
DATE VERIFIED: 2026-10-14 (file hash / content read)
WHAT THE SOURCE ACTUALLY SUPPORTS: prior validation run provenance.
WHAT WE ARE NOT CLAIMING: that the current host reproduced sklearn numbers.
```

```
CLAIM: Interaction-aware ranking beats anomaly-only on validation (numpy) and was independently reproduced.
SOURCE: docs/PHASE3_REPRODUCTION_REPORT.md; evidence/results/analysis/phase3_*/
DATE VERIFIED: 2026-10-13/14 (Phase 3 session)
WHAT THE SOURCE ACTUALLY SUPPORTS: validation-only research metrics at stated budgets.
WHAT WE ARE NOT CLAIMING: production authorization, locked-test results, or sklearn/s390x generalization.
```

```
CLAIM: Docker image builds and runs.
SOURCE: N/A — BLOCKED (no Docker CLI on completion-pass host)
DATE VERIFIED: 2026-10-14 (which docker → None)
```

```
CLAIM: Browser dashboard click-through passed.
SOURCE: N/A — NOT VERIFIED (no browser/automation on completion-pass host)
DATE VERIFIED: 2026-10-14
WHAT WE ARE NOT CLAIMING: any successful manual or automated UI session on this host.
```
