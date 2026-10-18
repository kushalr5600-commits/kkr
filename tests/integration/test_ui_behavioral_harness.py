"""Behavioral regression: run the real frontend/static/app.js inside a minimal
DOM stub (scripts/behavioral_dom_harness.js) and exercise the user flows:
load -> analyze -> what-if click -> navigation. Catches strict-mode
ReferenceError / dead-handler bugs like the wi-btn closure class.
Skipped when node is not installed."""
from __future__ import annotations

import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
HARNESS = ROOT / "scripts" / "behavioral_dom_harness.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_behavioral_dom_harness_all_flows():
    proc = subprocess.run(
        ["node", str(HARNESS)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, f"harness failed:\n{out}"
    assert "ALL_FLOWS_OK" in out, out


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_app_js_syntax_check():
    proc = subprocess.run(
        ["node", "--check", str(ROOT / "frontend" / "static" / "app.js")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
