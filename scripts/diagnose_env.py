"""Environment diagnostics for BLACKBOX (portable, offline, secret-free).

Reports host/process architecture, dependency availability, the model backend
BLACKBOX would actually select, dataset integrity and config identifiers.

Truth rules:
  * ``linuxone`` / ``s390x`` is reported only when the *running process*
    reports ``platform.machine() == "s390x"`` (or the sysconfig platform tag
    contains s390x). A config file or runbook that mentions s390x is NOT
    evidence of execution on s390x.
  * Host vs process: under user-mode emulation the process machine may differ
    from the host kernel machine; both are reported when they can be observed
    without elevated privileges.

Usage:
    python scripts/diagnose_env.py            # human-readable + JSON summary
    python scripts/diagnose_env.py --json     # machine-readable only

Import ``collect()`` from tests. No network access is required.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import struct
import sys
import sysconfig
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEPENDENCIES = (
    "fastapi",
    "uvicorn",
    "pydantic",
    "numpy",
    "sklearn",
    "pytest",
    "httpx",
)


def _process_pointer_bits() -> int:
    return struct.calcsize("P") * 8


def _host_kernel_machine() -> str | None:
    """Best-effort host kernel machine, distinct from the Python process.

    On Linux, ``uname -m`` is the kernel's machine. Under qemu-user the Python
    process may report the emulated target while the kernel reports the host.
    On non-Linux hosts this returns the same value as ``platform.machine()``.
    """
    if platform.system() == "Linux":
        try:
            import uname as uname_mod  # type: ignore[attr-defined]
        except ImportError:
            uname_mod = None
        # os.uname is POSIX-only and returns the kernel machine.
        try:
            return os.uname().machine  # type: ignore[attr-defined]
        except AttributeError:
            pass
    return platform.machine() or None


def _dependency_version(name: str) -> dict[str, Any]:
    try:
        mod = importlib.import_module(name)
    except ImportError:
        return {"installed": False, "version": None, "import_error": "ImportError"}
    except Exception as exc:  # noqa: BLE001 - report, never crash diagnostics
        return {"installed": True, "version": None, "import_error": type(exc).__name__}
    return {
        "installed": True,
        "version": getattr(mod, "__version__", None),
        "import_error": None,
    }


def _dataset_fingerprint() -> dict[str, Any]:
    dataset = ROOT / "backend" / "data" / "sample_dataset.json"
    manifest = ROOT / "backend" / "data" / "manifest.json"
    info: dict[str, Any] = {
        "dataset_path": str(dataset.relative_to(ROOT)) if dataset.exists() else None,
        "dataset_sha256": None,
        "manifest_sha256_field": None,
        "matches_manifest": None,
    }
    if dataset.exists():
        info["dataset_sha256"] = hashlib.sha256(dataset.read_bytes()).hexdigest()
    if manifest.exists():
        try:
            meta = json.loads(manifest.read_text(encoding="utf-8"))
            info["manifest_sha256_field"] = meta.get("sha256")
            if info["dataset_sha256"] and info["manifest_sha256_field"]:
                info["matches_manifest"] = info["dataset_sha256"] == info["manifest_sha256_field"]
        except (OSError, json.JSONDecodeError) as exc:
            info["manifest_error"] = type(exc).__name__
    return info


def _config_fingerprint() -> dict[str, Any]:
    config_path = ROOT / "backend" / "shared" / "config.py"
    sha = None
    if config_path.exists():
        sha = hashlib.sha256(config_path.read_bytes()).hexdigest()
    version = None
    try:
        from backend.shared import config

        version = config.VERSION
        threshold = config.IMPACT_THRESHOLD
        weights = dict(config.IMPACT_WEIGHTS)
    except Exception as exc:  # noqa: BLE001
        return {"config_version": None, "config_sha256": sha, "import_error": type(exc).__name__}
    return {
        "config_version": version,
        "config_sha256": sha,
        "impact_threshold": threshold,
        "impact_weights": weights,
    }


def _selected_backend() -> dict[str, Any]:
    try:
        from backend.gate.models import resolve_backend

        selected = resolve_backend()
    except Exception as exc:  # noqa: BLE001
        return {"selected": None, "error": type(exc).__name__, "message": str(exc)[:200]}
    return {
        "selected": selected,
        "env_var": os.environ.get("BLACKBOX_MODEL_BACKEND", "(unset)"),
        "note": (
            "numpy is the documented fallback when scikit-learn is unavailable; "
            "scores and rankings can differ between backends (see docs/BACKEND_EVIDENCE.md)."
        ),
    }


def collect() -> dict[str, Any]:
    """Collect a JSON-serializable environment report. Never raises."""
    process_machine = platform.machine() or None
    sysconfig_platform = sysconfig.get_platform()
    s390x_process = process_machine == "s390x" or "s390x" in (sysconfig_platform or "")
    deps = {name: _dependency_version(name) for name in DEPENDENCIES}
    git_rev = None
    try:
        from backend.shared import diagnostics

        git_rev = diagnostics.git_revision()
    except Exception:  # noqa: BLE001
        git_rev = None
    return {
        "report": "blackbox_environment_diagnostics",
        "truth_rule": (
            "runtime=linuxone is asserted only when the running Python process "
            f"reports machine s390x; observed process machine={process_machine!r}."
        ),
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "platform_string": platform.platform(),
            "host_kernel_machine": _host_kernel_machine(),
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
            "pointer_bits": _process_pointer_bits(),
            "sysconfig_platform": sysconfig_platform,
        },
        "architecture": {
            "process_machine": process_machine,
            "process_is_s390x": s390x_process,
            "runtime_label": "linuxone" if s390x_process else "local",
            "claim_linuxone_verified": s390x_process,
        },
        "dependencies": deps,
        "scikit_learn_importable": bool(deps.get("sklearn", {}).get("installed")),
        "model_backend": _selected_backend(),
        "config": _config_fingerprint(),
        "dataset": _dataset_fingerprint(),
        "git_revision": git_rev,
        "blackbox_root": str(ROOT),
    }


def _human_summary(report: dict[str, Any]) -> str:
    arch = report["architecture"]
    deps = report["dependencies"]
    backend = report["model_backend"]
    ds = report["dataset"]
    lines = [
        "BLACKBOX environment diagnostics",
        "================================",
        f"OS:                 {report['os']['system']} {report['os']['release']}",
        f"Python:             {report['python']['implementation']} {report['python']['version']}",
        f"Process machine:    {arch['process_machine']} ({arch['process_is_s390x'] and 's390x' or 'not s390x'})",
        f"Runtime label:      {arch['runtime_label']}"
        + ("   [LinuxONE process observed]" if arch["claim_linuxone_verified"] else "   [LinuxONE NOT verified on this process]"),
        f"Pointer width:      {report['python']['pointer_bits']}-bit",
        f"Sysconfig platform: {report['python']['sysconfig_platform']}",
        f"scikit-learn:       {'yes ' + str(deps['sklearn']['version']) if deps['sklearn']['installed'] else 'MISSING'}",
        f"numpy:              {deps['numpy']['version'] if deps['numpy']['installed'] else 'MISSING'}",
        f"fastapi:            {deps['fastapi']['version'] if deps['fastapi']['installed'] else 'MISSING'}",
        f"pytest:             {deps['pytest']['version'] if deps['pytest']['installed'] else 'MISSING'}",
        f"Selected backend:   {backend.get('selected')}",
        f"Config version:     {report['config'].get('config_version')}",
        f"Config sha256:      {report['config'].get('config_sha256')}",
        f"Dataset sha256:     {ds.get('dataset_sha256')}",
        f"Dataset=manifest:   {ds.get('matches_manifest')}",
        f"Git revision:       {report.get('git_revision') or '(not a git checkout / unset)'}",
        "",
        "Full JSON follows.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BLACKBOX environment diagnostics (offline)")
    parser.add_argument("--json", action="store_true", help="print only the JSON report")
    args = parser.parse_args(argv)
    report = collect()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_human_summary(report))
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
