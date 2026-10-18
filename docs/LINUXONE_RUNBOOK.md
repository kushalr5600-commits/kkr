# LINUXONE RUNBOOK — BLACKBOX target-platform validation

**Status of LinuxONE execution: VERIFIED (2026-10-16/17).** Real s390x guest
runs exist: numpy 133/133, sklearn 141/141 (+ live HTTP), and the hybrid
155/155 suite + `validate_runtime.py --include-optional` PASS
(`evidence/results/validation_runs/run_20261016T203734Z_s390x_sklearn/`,
`runtime_label=linuxone`). This runbook remains the procedure for reproducing
those runs and producing fresh evidence. A run on AMD64/x86_64 (or any
non-s390x host) does **not** establish LinuxONE results. Do not paste AMD64
numbers into `evidence/results/validation_runs/` and call them LinuxONE.

Theme: IBM Z Datathon 2026 — Real-Time AI for Critical Decisions.

## 0. Truth rules

1. `runtime=linuxone` is reported only when the *running Python process*
   reports `platform.machine() == "s390x"` (`scripts/diagnose_env.py`,
   `GET /health`).
2. Never edit published validation evidence in
   `evidence/results/validation/` to match a new environment. New runs go to
   `evidence/results/validation_runs/run_<UTC>_<arch>_<backend>/`.
3. Required steps that cannot run are **BLOCKED** or **NOT RUN**, never PASS.
4. scikit-learn and the NumPy fallback produce different metrics
   (`docs/BACKEND_EVIDENCE.md`). Record which backend ran.
5. Frozen gate weights/threshold and the locked test split are not touched.

## 0b. Safe now vs SSH-only (Oct 16)

| Action | When |
|---|---|
| Re-read this runbook; ensure code is packaged | **Safe now** |
| `python scripts/run_tests.py` / `smoke_test.py` on AMD64 | **Safe now** (not LinuxONE evidence) |
| Create venv + `pip install -r requirements-numpy.txt` on AMD64 | **Safe now** (packaging check only) |
| `uname -m` on the Z guest; clone/copy repo; install on s390x | **SSH-only (authorized Oct 16)** |
| Claim `runtime=linuxone` / write `validation_runs/` with s390x metadata | **SSH-only** |
| Locked test / weight changes | **Never without human freeze** |

## 1. Prerequisites (on the LinuxONE guest / s390x machine)

```bash
uname -m                 # must print s390x — capture this line
cat /etc/os-release      # capture PRETTY_NAME
python3 --version         # 3.11+ recommended (Dockerfile targets 3.11)
python3 -m pip --version
git --version
```

Optional (Docker path):

```bash
docker version
```

If `uname -m` is not `s390x`, stop: you are not on the target.

## 2. Get the code

**Option A — Git clone (when a repository URL is available):**

```bash
git clone <repository-url> blackbox && cd blackbox
git rev-parse HEAD | tee /tmp/blackbox_git_rev.txt
```

**Option B — Tarball (when no `.git` directory is available):**

```bash
# On the source host, create the archive:
tar -czf blackbox_src.tar.gz --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.venv' --exclude='node_modules' -C /path/to/parent blackbox

# Transfer to the guest, then extract:
scp blackbox_src.tar.gz <user>@<host>:/tmp/
ssh <user>@<host> 'mkdir -p ~/blackbox && tar -xzf /tmp/blackbox_src.tar.gz -C ~'
cd ~/blackbox
```

Record the commit in the validation evidence (the runner stores
`git_revision` automatically when `.git` is present or
`BLACKBOX_GIT_REVISION` is set). When using the tarball path, `git_revision`
will be `null` — this is expected and honest.

## 3. Environment diagnostics (before install)

```bash
python3 scripts/diagnose_env.py | tee evidence/diagnose_env_preinstall.txt
```

Expected observations on a real target:

- `Process machine: s390x`
- `Runtime label: linuxone   [LinuxONE process observed]`
- `scikit-learn: MISSING` until installed (or present if preinstalled)
- `Selected backend:` will be `numpy` until sklearn imports, then `sklearn`

## 4. Install dependencies

### 4a. Non-Docker path (preferred when Docker is unavailable)

**Ubuntu prerequisite:** Ensure `python3-venv` is installed before creating
the virtual environment:

```bash
sudo apt-get update -qq && sudo apt-get install -y python3.12-venv
```

If building NumPy from source is required (no s390x wheel available), also
install the compiler toolchain and Python development headers:

```bash
sudo apt-get install -y build-essential python3.12-dev
```

Then create the virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
# Option A — full stack (includes scikit-learn; may fail to build on s390x):
pip install -r requirements-dev.txt | tee /tmp/pip_install.log
```

If scikit-learn fails to build or PyPI blocks it, install the **documented NumPy-only runtime** (this is a complete server runtime: FastAPI + Uvicorn + Pydantic + NumPy):

```bash
pip install -r requirements-numpy.txt | tee /tmp/pip_install_numpy.log
export BLACKBOX_MODEL_BACKEND=numpy   # optional; auto when sklearn is absent
```

Optional (only if you want HTTP smoke checks and full integration tests in the same venv):

```bash
pip install -r requirements-test.txt | tee /tmp/pip_install_test.log   # pytest + httpx
export BLACKBOX_REQUIRE_HTTP=1   # smoke FAILs (not SKIPs) if HTTP stack missing
```

Then start without Docker:

```bash
# from repository root
python3 scripts/diagnose_env.py
uvicorn backend.main:app --host 0.0.0.0 --port 8000
# second terminal (same venv):
curl -s http://127.0.0.1:8000/health
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/dashboard   # expect 200
python3 scripts/smoke_test.py
```

Shutdown: `Ctrl+C` on uvicorn (or `kill <pid>`); confirm port free with
`ss -ltnp | grep :8000` (or equivalent).

Rollback: `deactivate; rm -rf .venv` (does not touch dataset or evidence).

`requirements-numpy.txt` is the **supported** non-Docker fallback. Do **not**
invent extra packages. Record which requirement file succeeded.

### 4b. If PyPI is blocked or scikit-learn fails to build

- Do **not** invent a workaround that hides the failure.
- The documented fallback is the NumPy model backend
  (`BLACKBOX_MODEL_BACKEND=numpy` or automatic when sklearn is absent).
- Record the pip error excerpt as BLOCKED evidence.

## 5. One-shot validation runner (preferred)

From the repository root, inside the venv:

```bash
python3 scripts/validate_runtime.py --include-optional | tee /tmp/validate_runtime.log
echo "exit_code=$?"
```

Add `--install` **only** if network install is allowed on the guest.

The runner:

| Step | Required? | Notes |
|---|---|---|
| environment_diagnostics | yes | process arch + selected backend |
| dataset_manifest_integrity | yes | SHA-256 vs `manifest.json` |
| run_tests_dependency_free | yes | `scripts/run_tests.py` |
| pytest_full_suite | yes | `python -m pytest -q` (full suite; count recorded in `docs/STATUS.md`) |
| smoke_test_pipeline_and_http | yes | `scripts/smoke_test.py` (HTTP must PASS, not SKIP, when httpx present) |
| live_http_uvicorn | optional | real uvicorn + `/health` + `/analyze` + 422 |
| pip_install_requirements_dev | optional (`--install`) | BLOCKED on failure |
| validation_experiment_rerun | never automatic | would overwrite published evidence |

Artifacts land in:

```text
evidence/results/validation_runs/run_<UTC>_<arch>_<backend>/
  validation_report.json   # full stdout/stderr tails, exit codes, timestamps
  README.md                # human summary table
```

**Acceptance for a LinuxONE claim:** `overall_status: PASS` **and**
`runtime_label: linuxone` **and** `process_machine: s390x` in that bundle.

## 6. Manual checks (equivalent, if not using the runner)

```bash
python3 scripts/run_tests.py
python3 -m pytest -q
python3 scripts/smoke_test.py
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
curl -s http://127.0.0.1:8000/health
# architecture must read s390x; model_backend must be sklearn or numpy truthfully
curl -s -X POST http://127.0.0.1:8000/analyze \
  -H 'content-type: application/json' -d '{"demo_mode":true}'
# expect TX-DEMO-0001, status NO_SIMULATION, forks_tested == []
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8000/analyze \
  -H 'content-type: application/json' -d '{}'   # expect 422
# optional second demo: pick TX-00300 from GET /transactions and POST it
curl -s http://127.0.0.1:8000/transactions | python3 -c "import sys,json; t=json.load(sys.stdin); print([x['transaction']['id'] for x in t])"
# optional second demo: pick the showcase whose hint is "Gate selects it; fails a stress
# test" from GET /transactions and POST it. NOTE: the id is backend-dependent
# (numpy -> TX-00300, scikit-learn -> TX-00154); trust the hint, not a hardcoded id.
```

## 6b. October 16 first commands (copy-paste order)

Preferred transport: **VS Code Remote-SSH** to the authorized LinuxONE guest
(never connect early). Open a VS Code terminal on the remote host, then:

```bash
uname -m | tee /tmp/bb_uname.txt
cat /etc/os-release | tee /tmp/bb_osrelease.txt
python3 --version | tee /tmp/bb_python.txt
python3 -m pip --version | tee /tmp/bb_pip.txt
# ... obtain repository, then:
cd blackbox
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
# optional observability (never required for core app):
#   pip install -r requirements-observability.txt && export BLACKBOX_OTEL=1
```

VS Code Remote-SSH notes:
- Do **not** enable port forwarding until the guest checks pass.
- After `/health` returns `architecture: s390x`, optionally forward port 8000
  to preview the dashboard in the local browser (still the same s390x process).
- Copy `/tmp/bb_*` artifacts back into
  `evidence/results/validation_runs/run_<UTC>_<arch>_<backend>/` only when
  `uname -m` printed `s390x`.

Stop if `uname` is not `s390x`. Never paste these AMD64 results into LinuxONE evidence folders.

## 7. Demo-gate trace on the target (read-only)

```bash
python3 scripts/trace_gate.py | tee /tmp/trace_gate_demo.txt
```

Record `model_backend`, the four signals and the score. Compare only against
a run with the **same** backend (`docs/BACKEND_EVIDENCE.md`).

## 8. What must NOT be done

- Do not run `scripts/run_experiment.py --split test` unless a human has
  frozen the configuration and passes `--confirm-frozen` (once).
- Do not change `IMPACT_WEIGHTS`, `IMPACT_THRESHOLD`, scenario ids, or
  schemas to make demo/selection outcomes look better.
- Do not describe an x86_64 container as LinuxONE.
- Do not delete or weaken a failing test; fix the cause or report BLOCKED.

## 9. Evidence checklist for the submission

- [ ] `uname -m` = s390x (captured)
- [ ] `/etc/os-release` captured
- [ ] `scripts/diagnose_env.py` shows `Runtime label: linuxone`
- [ ] `scripts/validate_runtime.py` overall PASS with linuxone metadata
- [ ] `/health` JSON with `architecture: s390x`
- [ ] One real `POST /analyze` response (demo_mode or explicit transaction)
- [ ] Model backend recorded (sklearn or numpy) + package versions
- [ ] Git commit hash
- [ ] Dataset SHA-256 matches `manifest.json`
- [ ] Dashboard screenshot (optional but recommended)
- [ ] Statement of which steps, if any, were BLOCKED

## 10. If validation fails on LinuxONE

Follow `AGENTS.md` §7: reproduce with the smallest command, classify
(contract / logic / model-data / wiring / environment / s390x / frontend),
fix only inside the owning module, re-run unit → contract → integration,
append to `docs/DEBUG_LOG.md`. Contract conflicts go to
`docs/CONTRACT_CHANGE_REQUEST.md` — do not silently change frozen items.
