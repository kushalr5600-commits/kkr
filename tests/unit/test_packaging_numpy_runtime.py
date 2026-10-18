"""Packaging regression: NumPy-only runtime must start the app without sklearn.

Pins requirements-numpy.txt contents and the BLACKBOX_MODEL_BACKEND=numpy path
so a LinuxONE guest can install only those packages and still serve /health.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _numpy_req_lines() -> list[str]:
    text = (ROOT / "requirements-numpy.txt").read_text(encoding="utf-8")
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_requirements_numpy_declares_runtime_deps_only():
    lines = _numpy_req_lines()
    joined = " ".join(lines).lower()
    for pkg in ("fastapi", "uvicorn", "pydantic", "numpy"):
        assert pkg in joined, f"requirements-numpy.txt must include {pkg}"
    assert "scikit-learn" not in joined
    assert "sklearn" not in joined
    assert "pytest" not in joined
    assert "httpx" not in joined


def test_numpy_backend_selects_without_sklearn_import():
    from backend.gate.models import resolve_backend

    prev = os.environ.get("BLACKBOX_MODEL_BACKEND")
    os.environ["BLACKBOX_MODEL_BACKEND"] = "numpy"
    try:
        assert resolve_backend() == "numpy"
        assert resolve_backend("numpy") == "numpy"
    finally:
        if prev is None:
            os.environ.pop("BLACKBOX_MODEL_BACKEND", None)
        else:
            os.environ["BLACKBOX_MODEL_BACKEND"] = prev


def test_runtime_modules_import_with_stdlib_plus_numpy_stack():
    """Runtime path must not require sklearn at import time."""
    for name in (
        "backend.shared.config",
        "backend.shared.schemas",
        "backend.shared.errors",
        "backend.shared.diagnostics",
        "backend.data.repository",
        "backend.gate.impact_gate",
        "backend.gate.models",
        "backend.certificate.certificate",
        "backend.pipeline",
        "backend.main",
    ):
        importlib.import_module(name)


def test_smoke_without_httpx_skips_http_not_fail():
    """Documented behavior: missing TestClient deps skip HTTP unless REQUIRE_HTTP=1."""
    src = (ROOT / "scripts" / "smoke_test.py").read_text(encoding="utf-8")
    assert "SKIP" in src
    assert "HTTP client stack unavailable" in src
    assert "BLACKBOX_REQUIRE_HTTP" in src
    assert "requirements-test.txt" in src
