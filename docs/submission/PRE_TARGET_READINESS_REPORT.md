# Pre-Target Readiness Report

**Date:** 2026-10-15 · **Host:** AMD64 Windows (dry-run only — no LinuxONE access)
**Scope:** LinuxONE runbook dry-run + gate tradeoff evidence verification
**Constraints respected:** no gate/threshold/scenario/schema changes · no frozen evidence rewritten ·
no locked test split · no installs/network · no s390x claims · no new runtime dependencies

---

## 1. LinuxONE runbook dry-run

**Runbook:** `docs/LINUXONE_RUNBOOK.md` (256 lines)
**Label:** `AMD64_RUNBOOK_DRY_RUN` — no step below was executed on s390x.

### Steps reviewed

| Step | Description | Dry-run result |
|---|---|---|
| 0 | Truth rules (s390x-only claims, evidence paths) | PASS — rules correct and unambiguous |
| 0b | Safe-now vs SSH-only table | PASS — correctly separates AMD64-safe from SSH-only actions |
| 1 | Prerequisites (`uname -m`, `python3 --version`, `pip`, `git`) | PASS — `uname -m` must print `s390x`; stop condition explicit |
| 2 | Get code (`git clone`, record commit) | PASS — `git rev-parse HEAD` captured; runner stores `git_revision` |
| 3 | `scripts/diagnose_env.py` pre-install | PASS — script present; expected observations (`Process machine: s390x`, `Runtime label: linuxone`) match `diagnostics.py` behavior |
| 4a | Install deps: `requirements-dev.txt` (full) → fallback `requirements-numpy.txt` | PASS — both files present; fallback documented; `BLACKBOX_MODEL_BACKEND=numpy` noted |
| 4b | PyPI-blocked fallback | PASS — instructs to record BLOCKED, not hide failure |
| 5 | `scripts/validate_runtime.py --include-optional` | PASS — script present with `--include-optional` and `--install` flags; step table matches actual script behavior |
| 6 | Manual checks (run_tests, pytest, smoke, uvicorn, curl) | PASS with one correction (see below) |
| 6b | Oct 16 first commands (copy-paste order) | PASS — all commands valid; `requirements-numpy.txt` + `requirements-test.txt` + `BLACKBOX_MODEL_BACKEND=numpy` is the documented target path |
| 7 | `scripts/trace_gate.py` demo-gate trace | PASS — script present; backend comparison instruction correct |
| 8 | What must NOT be done | PASS — correctly prohibits locked-test runs, weight/threshold changes, x86-as-Z claims |
| 9 | Evidence checklist | PASS — all items map to actual scripts/endpoints |
| 10 | Failure handling | PASS — references `AGENTS.md` §7, `DEBUG_LOG.md`, `CONTRACT_CHANGE_REQUEST.md` |

### Concrete correction made

| Location | Issue | Fix |
|---|---|---|
| Step 6, line 177 | Comment hardcoded `TX-00300` (numpy-only showcase id). Under scikit-learn the showcase id is `TX-00154`. | Replaced with backend-neutral instruction: trust the hint "Gate selects it; fails a stress test" from `GET /transactions`, not a hardcoded id. |

### Target-dependent checks (PENDING_ON_AUTHORIZED_S390X_TARGET)

All of the following require the actual s390x guest and are **not** replaced by AMD64 approximations:

| Check | Why it needs the target |
|---|---|
| `uname -m` = `s390x` | Only the real guest can prove architecture |
| `diagnose_env.py` → `Runtime label: linuxone` | Requires `platform.machine() == "s390x"` |
| `/health` → `architecture: s390x` | Process must actually run on s390x |
| `pip install -r requirements-*.txt` on s390x | s390x wheel availability unverified |
| scikit-learn import on s390x | Build from source may be needed; unverified |
| Full test suite on s390x | Must run on target to produce LinuxONE evidence |
| `validate_runtime.py` with linuxone metadata | Evidence bundle must show `runtime_label: linuxone` |
| Git commit hash | Requires `.git` on the cloned target repo |

### Environment / tooling verified (AMD64, read-only)

| Tool | Present |
|---|---|
| `scripts/diagnose_env.py` | YES |
| `scripts/validate_runtime.py` (`--include-optional`, `--install`) | YES |
| `scripts/run_tests.py` | YES |
| `scripts/smoke_test.py` | YES |
| `scripts/export_certificate_schema.py` | YES |
| `scripts/trace_gate.py` | YES |
| `requirements-dev.txt` / `requirements-numpy.txt` / `requirements-test.txt` / `requirements-observability.txt` | YES |
| `backend.main:app` + `/health`, `/dashboard`, `/analyze`, `/transactions` | YES |
| `schemas/decision_certificate.v1.schema.json` | YES (generated) |
| `git` (repository) | NO — no `.git` in working tree |
| `matplotlib` (for chart) | NO — chart not possible; Markdown/CSV table produced instead |

---

## 2. Gate tradeoff evidence

### Source artifact

| Field | Value |
|---|---|
| Path | `evidence/results/analysis/phase2_20261013T202326Z_numpy_validation/results.json` |
| Split | validation |
| Transactions | 1,000 |
| True failures | 102 |
| Backend | NumPy (model_backend = "numpy") |
| Architecture | AMD64 |
| Frozen | YES — SHA-256 `3e26d127…2ff52` (re-verified) |
| `linuxone_verified` | false |

### Verified operating-point metrics (threshold = 0.60)

| Metric | Source value | User-stated value | Match |
|---|---:|---:|:---:|
| Simulation fraction | 0.114 | 0.114 | ✓ |
| Failure recall | 0.216 | 0.216 | ✓ |
| Precision | 0.193 | 0.193 | ✓ |
| Not selected for simulation | 0.886 | 88.6% | ✓ |

### Verified recall-at-budget table

| Budget | Random | Amount-only | Anomaly-only | Frozen gate | Interaction-aware (research) |
|---:|---:|---:|---:|---:|
| 1% | 0.010 | 0.020 | 0.059 | 0.039 | 0.098 |
| 5% | 0.049 | 0.020 | 0.324 | 0.137 | 0.412 |
| 10% | 0.102 | 0.039 | 0.529 | 0.196 | 0.627 |

All values match the user-stated leads. No discrepancies found.

**Additional budgets from source (not in user's table):** 0.5% and 2.0% also present in `budget_curve`.

### Derived evidence files created

| File | Contents |
|---|---|
| `evidence/results/pre_target_readiness/gate_tradeoff_recall_vs_budget.csv` | CSV table (3 budgets × 5 policies) |
| `evidence/results/pre_target_readiness/gate_tradeoff_recall_vs_budget.md` | Markdown table + operating point + observations |

No chart (matplotlib unavailable, no network to install). Markdown/CSV table is the deliverable.

---

## 3. Honest statements

- **Production policy was NOT changed.** Weights, threshold, scenarios, `POLICY_VERSION`, schemas,
  and decision semantics are untouched.
- **No claim of LinuxONE validation.** The runbook dry-run is `AMD64_RUNBOOK_DRY_RUN`. Target-dependent
  checks are `PENDING_ON_AUTHORIZED_S390X_TARGET`.
- **No statistical significance or real-world financial performance is claimed.** The benchmark is
  synthetic data (1,000 transactions, 102 failures) on a validation split.
- **The interaction-aware ranking is research-only.** It is not wired into production, not
  independently replicated, and not production-approved.
- **The frozen gate trails anomaly-only at every reported budget.** This is a measured fact from
  the frozen NumPy validation evidence. The production policy decision (T1) remains with the human owner.
- **NumPy historical evidence vs current scikit-learn runtime are clearly separated.** The tradeoff
  table is labeled NumPy/frozen. The current AMD64 runtime uses scikit-learn and produces different
  scores/rankings (see `docs/submission/SKLEARN_BACKEND_SWITCH_REPORT.md`).

---

## 4. Files created or edited

| File | Action |
|---|---|
| `docs/submission/PRE_TARGET_READINESS_REPORT.md` | NEW — this report |
| `evidence/results/pre_target_readiness/gate_tradeoff_recall_vs_budget.csv` | NEW — derived CSV |
| `evidence/results/pre_target_readiness/gate_tradeoff_recall_vs_budget.md` | NEW — derived Markdown |
| `docs/LINUXONE_RUNBOOK.md` | EDITED — one minimal fix (TX-00300 → backend-neutral hint) |

No frozen evidence was overwritten. No new runtime dependencies. No feature work.

---

## 5. Next operator action for LinuxONE validation

1. **Oct 16 (authorized window):** Open VS Code Remote-SSH to the LinuxONE guest.
2. **Verify target:** `uname -m` must print `s390x`. If not, stop.
3. **First commands (copy-paste order):** Follow `docs/LINUXONE_RUNBOOK.md` §6b exactly:
   ```bash
   uname -m | tee /tmp/bb_uname.txt
   cat /etc/os-release | tee /tmp/bb_osrelease.txt
   python3 --version | tee /tmp/bb_python.txt
   python3 -m pip --version | tee /tmp/bb_pip.txt
   cd <repo>
   python3 scripts/diagnose_env.py | tee /tmp/bb_diagnose_pre.txt
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements-numpy.txt | tee /tmp/bb_pip_numpy.log
   pip install -r requirements-test.txt | tee /tmp/bb_pip_test.log
   export BLACKBOX_MODEL_BACKEND=numpy
   export BLACKBOX_REQUIRE_HTTP=1
   python3 scripts/run_tests.py | tee /tmp/bb_run_tests.log
   python3 scripts/smoke_test.py | tee /tmp/bb_smoke.log
   python3 scripts/export_certificate_schema.py | tee /tmp/bb_export_schema.log
   uvicorn backend.main:app --host 127.0.0.1 --port 8000 | tee /tmp/bb_uvicorn.log &
   curl -s http://127.0.0.1:8000/health | tee /tmp/bb_health.json
   ```
4. **If scikit-learn is needed:** `pip install -r requirements-dev.txt` (may fail on s390x — record as BLOCKED).
5. **Capture evidence:** Copy `/tmp/bb_*` artifacts into
   `evidence/results/validation_runs/run_<UTC>_s390x_<backend>/` only when `uname -m` printed `s390x`.
6. **Acceptance:** `overall_status: PASS` AND `runtime_label: linuxone` AND `process_machine: s390x`
   in the validation bundle.
