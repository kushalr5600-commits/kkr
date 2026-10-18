"""Reproducible runtime validation for BLACKBOX (including LinuxONE targets).

Runs the existing tests and smoke checks without weakening them, captures full
command output with exit codes, timestamps, environment metadata and git
revision, and writes a timestamped evidence bundle under
``evidence/results/validation_runs/``.

Steps that cannot run are reported as BLOCKED or NOT RUN — never as PASS.
The process exits nonzero if any required step fails.

Usage (from the repository root):
    python scripts/validate_runtime.py                  # required steps only
    python scripts/validate_runtime.py --include-optional
    python scripts/validate_runtime.py --json-summary

This script does not install packages by default (the build environment may
block PyPI). Use ``--install`` only where network install is allowed; a failed
install is recorded as BLOCKED, not hidden.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EVIDENCE_ROOT = ROOT / "evidence" / "results" / "validation_runs"


@dataclass
class StepResult:
    name: str
    required: bool
    status: str  # PASS | FAIL | BLOCKED | NOT RUN
    exit_code: int | None = None
    duration_s: float = 0.0
    command: str = ""
    stdout_tail: str = ""
    stderr_tail: str = ""
    notes: str = ""


@dataclass
class ValidationReport:
    started_at_utc: str
    finished_at_utc: str = ""
    architecture_process: str = ""
    runtime_label: str = ""
    python_version: str = ""
    git_revision: str | None = None
    model_backend: str | None = None
    dataset_sha256: str | None = None
    dataset_matches_manifest: bool | None = None
    overall_status: str = "UNKNOWN"
    steps: list[StepResult] = field(default_factory=list)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _run(cmd: list[str], timeout: int, cwd: Path = ROOT) -> tuple[int, str, str, float]:
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONHASHSEED": "0"},
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr, time.perf_counter() - start
    except FileNotFoundError as exc:
        return 127, "", f"FileNotFoundError: {exc}", time.perf_counter() - start
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or b"") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = (exc.stderr or b"") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        return 124, out, err + "\nTIMEOUT", time.perf_counter() - start


def _tail(text: str, limit: int = 4000) -> str:
    return text if len(text) <= limit else text[-limit:]


def _step_from_run(
    name: str,
    required: bool,
    cmd: list[str],
    timeout: int,
    pass_probe=None,
) -> StepResult:
    code, out, err, dur = _run(cmd, timeout=timeout)
    status = "PASS" if code == 0 else "FAIL"
    notes = ""
    if pass_probe is not None and status == "PASS":
        ok, notes = pass_probe(out, err)
        if not ok:
            status = "FAIL"
    if code == 127:
        status = "BLOCKED"
        notes = notes or "command not found"
    return StepResult(
        name=name,
        required=required,
        status=status,
        exit_code=code,
        duration_s=round(dur, 3),
        command=" ".join(cmd),
        stdout_tail=_tail(out),
        stderr_tail=_tail(err),
        notes=notes,
    )


def _check_dataset(report: ValidationReport) -> StepResult:
    dataset = ROOT / "backend" / "data" / "sample_dataset.json"
    manifest = ROOT / "backend" / "data" / "manifest.json"
    if not dataset.exists() or not manifest.exists():
        report.dataset_matches_manifest = None
        return StepResult(
            name="dataset_manifest_integrity",
            required=True,
            status="FAIL",
            notes="dataset or manifest file missing",
        )
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    meta = json.loads(manifest.read_text(encoding="utf-8"))
    expected = meta.get("sha256")
    report.dataset_sha256 = digest
    report.dataset_matches_manifest = digest == expected
    return StepResult(
        name="dataset_manifest_integrity",
        required=True,
        status="PASS" if report.dataset_matches_manifest else "FAIL",
        exit_code=0 if report.dataset_matches_manifest else 1,
        notes=f"sha256={digest}; manifest={expected}",
        command="inline: hashlib.sha256(sample_dataset.json) vs manifest.sha256",
    )


def _check_env_and_backend(report: ValidationReport) -> StepResult:
    cmd = [sys.executable, str(ROOT / "scripts" / "diagnose_env.py"), "--json"]
    code, out, err, dur = _run(cmd, timeout=60)
    if code != 0:
        return StepResult(
            name="environment_diagnostics",
            required=True,
            status="FAIL",
            exit_code=code,
            duration_s=round(dur, 3),
            command=" ".join(cmd),
            stdout_tail=_tail(out),
            stderr_tail=_tail(err),
        )
    try:
        diag = json.loads(out)
    except json.JSONDecodeError:
        return StepResult(
            name="environment_diagnostics",
            required=True,
            status="FAIL",
            exit_code=1,
            command=" ".join(cmd),
            stdout_tail=_tail(out),
            stderr_tail=_tail(err),
            notes="diagnostics did not emit valid JSON",
        )
    arch = diag.get("architecture", {})
    report.architecture_process = arch.get("process_machine") or ""
    report.runtime_label = arch.get("runtime_label") or ""
    report.model_backend = diag.get("model_backend", {}).get("selected")
    report.git_revision = diag.get("git_revision")
    ds = diag.get("dataset", {})
    report.dataset_matches_manifest = ds.get("matches_manifest")
    if report.dataset_sha256 is None:
        report.dataset_sha256 = ds.get("dataset_sha256")
    return StepResult(
        name="environment_diagnostics",
        required=True,
        status="PASS",
        exit_code=0,
        duration_s=round(dur, 3),
        command=" ".join(cmd),
        stdout_tail=_tail(out),
        notes=(
            f"process_machine={report.architecture_process}; runtime_label={report.runtime_label}; "
            f"backend={report.model_backend}; linuxone_verified={arch.get('claim_linuxone_verified')}"
        ),
    )


def _probe_run_tests(out: str, err: str) -> tuple[bool, str]:
    text = out + "\n"
    if "failed" in text.lower() and "0 failed" not in text.lower() and "passed" not in text.lower():
        return False, "run_tests reported failures"
    if "0 failed" in text or "57 passed" in text or "passed," in text:
        # require no FAIL lines
        if "\nFAIL " in text or text.startswith("FAIL "):
            return False, "FAIL lines present"
        return True, "no FAIL lines"
    if "PASS " in text and "FAIL " not in text:
        return True, "PASS lines only"
    return False, "could not parse run_tests output"


def _probe_pytest(out: str, err: str) -> tuple[bool, str]:
    text = out + err
    if "passed" in text and "failed" not in text.replace("0 failed", ""):
        return True, "pytest reported passed without failed"
    if "failed" in text and "0 failed" not in text:
        return False, "pytest reported failures"
    return False, "could not parse pytest output"


def _probe_smoke(out: str, err: str) -> tuple[bool, str]:
    text = out
    if "smoke test complete" not in text:
        return False, "smoke test did not finish"
    if "\nFAIL " in text or text.startswith("FAIL "):
        return False, "smoke FAIL lines present"
    if "SKIP  HTTP routes" in text:
        return False, "HTTP routes were SKIPped (FastAPI unavailable) — not a pass"
    if "PASS  GET /health" in text and "PASS  POST /analyze" in text:
        return True, "all smoke checks PASS including HTTP"
    return False, "smoke output incomplete"


def _optional_http_live(report: ValidationReport) -> StepResult:
    """Optional: boot uvicorn briefly and hit real HTTP. Requires uvicorn+fastapi."""
    try:
        import uvicorn  # noqa: F401
        import fastapi  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return StepResult(
            name="live_http_uvicorn",
            required=False,
            status="BLOCKED",
            notes=f"uvicorn/fastapi not importable: {type(exc).__name__}",
        )
    port = 8765
    env = {**os.environ, "PYTHONHASHSEED": "0"}
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        # Poll until the app is actually ready: startup fits models on the
        # calibration split (can take >10s); a fixed 6s sleep raced it.
        import urllib.error
        import urllib.request

        deadline = time.time() + 90.0
        ready = False
        while time.time() < deadline and server.poll() is None:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as resp:
                    if resp.status == 200:
                        ready = True
                        break
            except (urllib.error.URLError, OSError):
                time.sleep(1.0)
        if not ready:
            server.terminate()
            out, err = server.communicate(timeout=10)
            return StepResult(
                name="live_http_uvicorn",
                required=False,
                status="FAIL",
                exit_code=server.returncode,
                command=f"uvicorn :{port} + urllib /health /analyze demo + empty-body 422",
                stdout_tail=_tail(out or ""),
                stderr_tail=_tail(err or ""),
                notes="uvicorn did not become healthy within 90s",
            )
        code, out, err, dur = _run(
            [
                sys.executable,
                "-c",
                (
                    "import json,urllib.request,urllib.error;\n"
                    f"base='http://127.0.0.1:{port}'\n"
                    "h=json.load(urllib.request.urlopen(base+'/health', timeout=5));\n"
                    "assert h.get('status')=='ok', h;\n"
                    "req=urllib.request.Request(base+'/analyze', data=b'{\"demo_mode\":true}',"
                    " headers={'content-type':'application/json'}, method='POST');\n"
                    "a=json.load(urllib.request.urlopen(req, timeout=60));\n"
                    "assert a.get('transaction_id'), a;\n"
                    "assert a.get('status') in ('NO_SIMULATION','SIMULATED','REVIEW'), a;\n"
                    "try:\n"
                    "    urllib.request.urlopen(urllib.request.Request(base+'/analyze',"
                    " data=b'{}', headers={'content-type':'application/json'}, method='POST'), timeout=10)\n"
                    "    raise SystemExit('empty body must 422')\n"
                    "except urllib.error.HTTPError as e:\n"
                    "    assert e.code==422, e.code\n"
                    "print('LIVE_HTTP_OK', h.get('architecture'), a.get('status'), a.get('recommended_action'))\n"
                ),
            ],
            timeout=120,
        )
        ok = code == 0 and "LIVE_HTTP_OK" in out
        return StepResult(
            name="live_http_uvicorn",
            required=False,
            status="PASS" if ok else "FAIL",
            exit_code=code,
            duration_s=round(dur, 3),
            command=f"uvicorn :{port} + urllib /health /analyze demo + empty-body 422",
            stdout_tail=_tail(out),
            stderr_tail=_tail(err),
            notes="real HTTP against a live uvicorn process",
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


def run_validation(include_optional: bool = False, install: bool = False) -> ValidationReport:
    report = ValidationReport(started_at_utc=_utc_now())

    if install:
        install_result = _step_from_run(
            "pip_install_requirements_dev",
            required=False,
            cmd=[sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"],
            timeout=600,
        )
        if install_result.status == "FAIL":
            install_result.status = "BLOCKED"
            install_result.notes = (
                install_result.notes
                or "pip install failed (often egress policy); not worked around — see AGENTS.md"
            )
        report.steps.append(install_result)
    else:
        report.steps.append(
            StepResult(
                name="pip_install_requirements_dev",
                required=False,
                status="NOT RUN",
                notes="skipped (no --install flag); use on target only if install is permitted",
            )
        )

    report.steps.append(_check_env_and_backend(report))
    report.steps.append(_check_dataset(report))

    report.steps.append(
        _step_from_run(
            "run_tests_dependency_free",
            required=True,
            cmd=[sys.executable, str(ROOT / "scripts" / "run_tests.py")],
            timeout=600,
            pass_probe=_probe_run_tests,
        )
    )
    report.steps.append(
        _step_from_run(
            "pytest_full_suite",
            required=True,
            cmd=[sys.executable, "-m", "pytest", "-q"],
            timeout=600,
            pass_probe=_probe_pytest,
        )
    )
    report.steps.append(
        _step_from_run(
            "smoke_test_pipeline_and_http",
            required=True,
            cmd=[sys.executable, str(ROOT / "scripts" / "smoke_test.py")],
            timeout=300,
            pass_probe=_probe_smoke,
        )
    )

    if include_optional:
        report.steps.append(_optional_http_live(report))
    else:
        report.steps.append(
            StepResult(
                name="live_http_uvicorn",
                required=False,
                status="NOT RUN",
                notes="pass --include-optional to boot uvicorn and hit real HTTP",
            )
        )

    # Optional: validation-split experiment re-run (development only; never test).
    report.steps.append(
        StepResult(
            name="validation_experiment_rerun",
            required=False,
            status="NOT RUN",
            notes=(
                "deliberately not run by default: re-running overwrites evidence/results/validation. "
                "See docs/BACKEND_EVIDENCE.md; use scripts/run_experiment.py manually when needed."
            ),
        )
    )

    required = [s for s in report.steps if s.required]
    if any(s.status == "FAIL" for s in required):
        report.overall_status = "FAIL"
    elif all(s.status == "PASS" for s in required):
        report.overall_status = "PASS"
    else:
        report.overall_status = "INCOMPLETE"
    report.finished_at_utc = _utc_now()
    return report


def write_evidence(report: ValidationReport) -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    machine = report.architecture_process or "unknown"
    backend = report.model_backend or "unknown"
    out_dir = EVIDENCE_ROOT / f"run_{stamp}_{machine}_{backend}"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = asdict(report)
    (out_dir / "validation_report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    lines = [
        "# BLACKBOX runtime validation run",
        "",
        f"- started_at_utc: {report.started_at_utc}",
        f"- finished_at_utc: {report.finished_at_utc}",
        f"- process architecture: {report.architecture_process}",
        f"- runtime label: {report.runtime_label}"
        + (" (process is s390x)" if report.runtime_label == "linuxone" else " (LinuxONE NOT verified here)"),
        f"- python: {report.python_version}",
        f"- git_revision: {report.git_revision or '(unavailable)'}",
        f"- model_backend: {report.model_backend}",
        f"- dataset_sha256: {report.dataset_sha256}",
        f"- dataset_matches_manifest: {report.dataset_matches_manifest}",
        f"- overall_status: **{report.overall_status}**",
        "",
        "| step | required | status | exit | duration_s | notes |",
        "|---|---|---|---|---|---|",
    ]
    for s in report.steps:
        lines.append(
            f"| {s.name} | {'yes' if s.required else 'no'} | **{s.status}** | "
            f"{s.exit_code if s.exit_code is not None else '-'} | {s.duration_s} | {s.notes} |"
        )
    lines += [
        "",
        "AMD64 (or any non-s390x) results do NOT establish LinuxONE results.",
        "Full command stdout/stderr tails are in validation_report.json.",
    ]
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BLACKBOX reproducible runtime validation")
    parser.add_argument("--include-optional", action="store_true", help="also run optional live-HTTP check")
    parser.add_argument("--install", action="store_true", help="attempt pip install -r requirements-dev.txt first")
    parser.add_argument("--json-summary", action="store_true", help="print machine-readable summary only")
    args = parser.parse_args(argv)

    report = run_validation(include_optional=args.include_optional, install=args.install)
    report.python_version = platform.python_version()
    out_dir = write_evidence(report)

    if args.json_summary:
        print(
            json.dumps(
                {
                    "overall_status": report.overall_status,
                    "runtime_label": report.runtime_label,
                    "architecture": report.architecture_process,
                    "model_backend": report.model_backend,
                    "evidence_dir": str(out_dir),
                    "steps": [{"name": s.name, "status": s.status} for s in report.steps],
                },
                indent=2,
            )
        )
    else:
        print(f"overall_status: {report.overall_status}")
        print(f"runtime_label:  {report.runtime_label} (process {report.architecture_process})")
        print(f"model_backend:  {report.model_backend}")
        print(f"evidence:       {out_dir}")
        for s in report.steps:
            print(f"  [{s.status:8s}] {s.name}  {s.notes}")
        if report.runtime_label != "linuxone":
            print(
                "\nNOTE: this host is not s390x. LinuxONE execution remains NOT VERIFIED "
                "until this runner completes with runtime_label=linuxone on the target."
            )
    return 0 if report.overall_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
