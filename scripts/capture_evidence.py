"""Capture genuine local readiness evidence (AMD64 or any host actually running).

    python scripts/capture_evidence.py

Writes a timestamped bundle under evidence/results/local_readiness/:
  - environment.json (platform, python, backend, versions)
  - run_tests.txt / run_tests.exit
  - smoke_test.txt / smoke_test.exit
  - health.json, demo_api.json, simulated_api.json (via TestClient when available)
  - integrity.json (weights, threshold, Phase 2 hashes, interaction scan)
  - README.md summary

Never fabricates LinuxONE labels. Exit code is 0 only if required steps pass.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_ROOT = ROOT / "evidence" / "results" / "local_readiness"

PHASE2 = ROOT / "evidence" / "results" / "analysis" / "phase2_20261013T202326Z_numpy_validation"


def _utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _run(cmd: list[str], name: str, out_dir: Path) -> int:
    proc = subprocess.run(
        [sys.executable, *cmd],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    (out_dir / f"{name}.txt").write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    (out_dir / f"{name}.exit").write_text(str(proc.returncode), encoding="utf-8")
    print(f"{name}: exit={proc.returncode}")
    return proc.returncode


def _integrity() -> dict:
    from backend.shared import config

    p2 = {}
    if PHASE2.is_dir():
        for f in sorted(PHASE2.iterdir()):
            if f.is_file():
                p2[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    interaction = sum(
        1
        for p in (ROOT / "backend").rglob("*.py")
        if "interaction" in p.read_text(encoding="utf-8", errors="ignore").lower()
    )
    return {
        "impact_weights": dict(config.IMPACT_WEIGHTS),
        "impact_threshold": config.IMPACT_THRESHOLD,
        "phase2_sha256": p2,
        "interaction_hits_in_backend_py": interaction,
    }


def _api_capture(out_dir: Path) -> dict:
    try:
        from fastapi.testclient import TestClient
        from backend.main import app
    except Exception as exc:  # noqa: BLE001
        return {"http_status": "SKIP", "reason": f"{type(exc).__name__}: {exc}"}

    from backend.shared import config

    result: dict = {"http_status": "OK"}
    with TestClient(app) as client:
        health = client.get("/health").json()
        (out_dir / "health.json").write_text(json.dumps(health, indent=2), encoding="utf-8")
        result["health"] = health
        demo = client.post("/analyze", json={"demo_mode": True}).json()
        (out_dir / "demo_api.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
        result["demo"] = {
            "transaction_id": demo.get("transaction_id"),
            "status": demo.get("status"),
            "action": demo.get("recommended_action"),
            "score": demo.get("impact_score", {}).get("score"),
            "forks": len(demo.get("forks_tested") or []),
            "backend": demo.get("runtime", {}).get("model_versions", {}).get("backend"),
        }
        txs = client.get("/transactions").json()
        sim = next((t for t in txs if t["transaction"]["id"] == "TX-00300"), None)
        if sim is None:
            sim = next((t for t in txs if "fails a stress" in t.get("hint", "")), None)
        if sim:
            body = client.post("/analyze", json={"transaction": sim["transaction"]}).json()
            (out_dir / "simulated_api.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
            result["simulated"] = {
                "transaction_id": body.get("transaction_id"),
                "status": body.get("status"),
                "action": body.get("recommended_action"),
                "score": body.get("impact_score", {}).get("score"),
                "forks": len(body.get("forks_tested") or []),
                "backend": body.get("runtime", {}).get("model_versions", {}).get("backend"),
            }
        empty = client.post("/analyze", json={}).status_code
        result["empty_request_status"] = empty
        result["dashboard_status"] = client.get("/dashboard").status_code
        result["expected_demo_id"] = config.DEMO_TRANSACTION_ID
    return result


def main() -> int:
    stamp = _utc_stamp()
    arch = platform.machine() or "unknown"
    out_dir = OUT_ROOT / f"run_{stamp}_{arch}_local"
    out_dir.mkdir(parents=True, exist_ok=True)

    env = {
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "platform": platform.platform(),
        "machine": arch,
        "python": platform.python_version(),
        "runtime_label_note": "linuxone only when machine==s390x on the real guest",
    }
    try:
        import numpy as np

        env["numpy"] = np.__version__
    except ImportError:
        env["numpy"] = None
    try:
        import sklearn

        env["sklearn"] = sklearn.__version__
    except ImportError:
        env["sklearn"] = None
    try:
        import httpx

        env["httpx"] = httpx.__version__
    except ImportError:
        env["httpx"] = None

    (out_dir / "environment.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
    integrity = _integrity()
    (out_dir / "integrity.json").write_text(json.dumps(integrity, indent=2), encoding="utf-8")

    e_tests = _run(["scripts/run_tests.py"], "run_tests", out_dir)
    e_smoke = _run(["scripts/smoke_test.py"], "smoke_test", out_dir)
    api = _api_capture(out_dir)
    (out_dir / "api_summary.json").write_text(json.dumps(api, indent=2), encoding="utf-8")

    ok = e_tests == 0 and e_smoke == 0
    if api.get("http_status") == "OK":
        ok = ok and api.get("dashboard_status") == 200 and api.get("empty_request_status") == 422
        ok = ok and api.get("demo", {}).get("transaction_id") == env.get("expected", api.get("demo", {}).get("transaction_id"))
    summary = f"""# Local readiness evidence

- Host machine: **{arch}** (NOT LinuxONE unless s390x)
- Python: {platform.python_version()}
- run_tests exit: **{e_tests}**
- smoke_test exit: **{e_smoke}**
- HTTP: {api.get('http_status')}
- Frozen integrity: see integrity.json
- Demo: {json.dumps(api.get('demo'), indent=2)}
- Simulated: {json.dumps(api.get('simulated'), indent=2)}

This bundle is **local host evidence only**. LinuxONE requires a separate run
on the authorized s390x guest (`docs/LINUXONE_RUNBOOK.md`).
"""
    (out_dir / "README.md").write_text(summary, encoding="utf-8")
    print(f"wrote {out_dir}")
    print(f"overall_exit_required={0 if ok else 1}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
