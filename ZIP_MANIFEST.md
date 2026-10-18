# ZIP manifest — BLACKBOX updated review archive

| Field | Value |
|---|---|
| Snapshot name | `blackbox-updated-review` (BLACKBOX 0.1.0-prebuild + LinuxONE tooling + evidence integrity docs + OSS assessment) |
| Archive creation timestamp (UTC) | 2026-10-13T20:01:55Z (build host clock; see `ZIP_BUILD_REPORT.md` for packaging steps) |
| Python used to prepare archive | CPython 3.12.10 |
| Host architecture of packager | AMD64 (Windows 10) — **not** s390x |
| Source directory is a Git repository? | **No** (handoff tree has no `.git`) |
| Git commit | **Unavailable** (no git metadata in the tree; certificates will show `git unavailable` unless `BLACKBOX_GIT_REVISION` is set) |
| Theme | IBM Z Datathon 2026 — Real-Time AI for Critical Decisions |
| LinuxONE/s390x status | **NOT VERIFIED** — packaging this ZIP does **not** constitute LinuxONE validation |

## Included top-level entries (under `blackbox/`)

| Path | Role |
|---|---|
| `backend/` | Application source: `shared/` schemas+config+diagnostics, `data/` generator+repository+dataset, `gate/` Impact Gate+models, `simulation/` forks+crash tests+fragility, `certificate/` Decision Certificate, `pipeline.py`, `main.py` (FastAPI) |
| `frontend/` | Static dashboard (`index.html`, `app.js`, `style.css`) — renders backend responses only |
| `tests/` | `contract/`, `unit/`, `integration/`, `fixtures.py` (67 tests) |
| `scripts/` | `run_tests.py`, `smoke_test.py`, `diagnose_env.py`, `validate_runtime.py`, `trace_gate.py`, `run_experiment.py`, `run_demo.py`, `build_dataset.py` |
| `docs/` | `STATUS.md`, `TASKS.md`, `DEBUG_LOG.md`, `CONTRACTS.md`, `ARCHITECTURE.md`, `LINUXONE_RUNBOOK.md`, `BACKEND_EVIDENCE.md`, `GATE_PERF_DIAGNOSTIC_PLAN.md`, `OPEN_SOURCE_COMPONENT_ASSESSMENT.md`, manuals, submission PDF |
| `evidence/` | `claims.md`, published `results/validation/` (sklearn, 2026-10-13), labeled `results/validation_rerun_2026-10-14_amd64_numpy/`, `results/validation_runs/run_20261013T194724Z_AMD64_numpy/` |
| `README.md`, `AGENTS.md` | Human + AI-agent entry points |
| `requirements.txt`, `requirements-dev.txt`, `pytest.ini` | Dependencies and pytest config |
| `Dockerfile`, `.dockerignore`, `.gitignore` | Deployment / ignore rules |
| `backend/data/sample_dataset.json` | Deterministic synthetic dataset (~2.8 MB) |
| `backend/data/manifest.json` | Split membership + dataset SHA-256 |
| `ZIP_MANIFEST.md` | This file |

## Excluded categories

| Category | Reason |
|---|---|
| `.venv/`, `venv/` | Virtual environments |
| `__pycache__/`, `*.pyc`, `.pytest_cache/` | Bytecode / test caches |
| `.mypy_cache/`, `.ruff_cache/`, `*.egg-info/` | Tool caches (none expected; excluded defensively) |
| `.env`, `*.pem`, `*.key`, `id_rsa*`, `credentials*` | Secrets / private material (none found in scan; excluded defensively) |
| `*.log` outside `evidence/` | Local logs not required to reproduce |
| OS junk (`.DS_Store`, `Thumbs.db`) | Machine-specific |
| Virtualenv-embedded site-packages | Not part of the project |

Nothing under `evidence/` was excluded for size. The published validation
bundle and both labeled re-run directories are retained in full.

## Integrity hashes (packaging time)

| Artifact | SHA-256 |
|---|---|
| `backend/data/sample_dataset.json` | `546f57ce91292214e813e7fd7f7004c32188da54e8a952894076a0e5a8d2d5c3` |
| `manifest.json` → `sha256` field | `546f57ce91292214e813e7fd7f7004c32188da54e8a952894076a0e5a8d2d5c3` (**match**) |
| `backend/shared/config.py` | `83b2a8f3669a48a81795ea4a7e29197a4d879d90500e4f54103b09a2df432a91` |
| Original handoff ZIP (untouched) | `624916696EE3E2F08B6200C61FC3056DE3CD723859616308E9B1DB436B50631E` |
| Final review ZIP | see sidecar `blackbox-updated-review.zip.sha256` (**not** embedded in this archive) |

## Frozen configuration snapshot (must not drift)

| Constant | Value |
|---|---|
| `IMPACT_WEIGHTS` | magnitude 0.30, dependency 0.30, anomaly 0.25, uncertainty 0.15 |
| `IMPACT_THRESHOLD` | 0.60 |
| `SCENARIOS` | `3x_volume`, `fraud_spike`, `service_latency` (exactly three) |
| Fork names | `normal` / `stress` |
| Certificate actions | `ALLOW_NORMAL_PATH`, `REVIEW`, `BLOCK_OR_HOLD` |
| Certificate statuses | `NO_SIMULATION`, `SIMULATED`, `REVIEW` |
| Model seed / dataset seed | 42 / 42 |
| Split fractions | calibration 50%, validation 20%, test 30% (locked test requires `--confirm-frozen`) |

## Verification status carried in this snapshot

| Item | Label |
|---|---|
| `python scripts/run_tests.py` → 67 passed, 0 failed (AMD64, CPython 3.12.10) | **VERIFIED** |
| `python -m pytest -q` → 67 passed (1 env deprecation warning) | **VERIFIED** |
| `python scripts/smoke_test.py` → all PASS including HTTP routes | **VERIFIED** |
| `scripts/validate_runtime.py --include-optional` → overall PASS, `runtime_label=local` | **VERIFIED (AMD64 only)** |
| Dataset SHA-256 matches manifest | **VERIFIED** |
| Published validation evidence (sklearn backend) intact | **VERIFIED** |
| Gate underperforms anomaly-only on validation | **KNOWN ISSUE** (preserved; see `docs/STATUS.md`, `docs/GATE_PERF_DIAGNOSTIC_PLAN.md`) |
| `TX-DEMO-0001` skipped by gate (score 0.503 sklearn / 0.414 numpy < 0.60) | **KNOWN ISSUE** |
| LinuxONE / s390x execution | **NOT VERIFIED** |
| Docker image build | **NOT VERIFIED** on the packager host |
| Interactive browser click-through | **NOT VERIFIED** |
| Organizer pre-build permission | **NOT VERIFIED** (`evidence/claims.md` still needs a human source) |

AMD64 test or validation output in this archive must **not** be represented
as LinuxONE results.

## Exact commands (from the extracted `blackbox/` root)

### Tests (any host with Python 3.11+)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python scripts/run_tests.py          # 67 tests, no pytest required
python -m pytest -q                  # same suite under pytest
python scripts/smoke_test.py         # pipeline + FastAPI HTTP routes
```

### Diagnostics and gate trace

```bash
python scripts/diagnose_env.py
python scripts/trace_gate.py --transaction-id TX-DEMO-0001
```

### LinuxONE validation workflow (run on the real s390x target)

```bash
uname -m                            # must print s390x
python3 scripts/diagnose_env.py | tee /tmp/diag.txt
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python3 scripts/validate_runtime.py --include-optional --install
echo "exit_code=$?"
```

Acceptance for a LinuxONE claim: the validation bundle under
`evidence/results/validation_runs/` must show `runtime_label: linuxone`,
`architecture_process: s390x`, and `overall_status: PASS`.
Full procedure: `docs/LINUXONE_RUNBOOK.md`.

### Application (optional)

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
# http://127.0.0.1:8000/dashboard
```

### Locked test experiment (human-gated — do not run casually)

```bash
# only after configuration freeze decision:
python scripts/run_experiment.py --split test --confirm-frozen
```

Default development experiment (validation split only; overwrites
`evidence/results/validation/` if run — prefer a copy first):

```bash
python scripts/run_experiment.py --split validation
```

## Note on evidence directories

| Directory | Meaning |
|---|---|
| `evidence/results/validation/` | **Published** development experiment (sklearn backend, 2026-10-13). Do not overwrite. |
| `evidence/results/validation_rerun_2026-10-14_amd64_numpy/` | Labeled NumPy-fallback re-run for backend comparison only |
| `evidence/results/validation_runs/run_20261013T194724Z_AMD64_numpy/` | First `validate_runtime.py` bundle (AMD64, not LinuxONE) |

## Packaging integrity statement

Creating or extracting this ZIP does not establish LinuxONE validation,
organizer approval, Docker portability, or browser certification. Those
remain as labeled above until executed on the appropriate environment and
recorded under `evidence/`.
