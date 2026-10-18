"""Optional OpenTelemetry-compatible span hooks (safe no-op by default).

Disabled unless ``BLACKBOX_OTEL=1``. When disabled — or when the optional
``opentelemetry`` packages are not installed — every helper is a cheap
context manager that does nothing. The core application never requires a
collector, exporter, or network destination.

Sensitive payloads (full Transaction bodies, amounts, account ids) are
never attached as span attributes. Only stage names, status codes, and the
existing ``trace_id`` are recorded.
"""
from __future__ import annotations

import contextlib
import os
from typing import Iterator

from backend.shared import config

_OTEL_ENV = "BLACKBOX_OTEL"


def otel_enabled() -> bool:
    return os.environ.get(_OTEL_ENV, "").strip().lower() in {"1", "true", "yes"}


def _try_tracer():
    """Return an OpenTelemetry tracer or None. Never raises."""
    if not otel_enabled():
        return None
    try:
        from opentelemetry import trace

        return trace.get_tracer("blackbox")
    except Exception:  # noqa: BLE001 - optional dependency missing/broken
        return None


@contextlib.contextmanager
def span(name: str, **attrs: str) -> Iterator[None]:
    """Record a lightweight span. Attributes must be non-sensitive strings."""
    tracer = _try_tracer()
    if tracer is None:
        yield
        return
    with tracer.start_as_current_span(name) as s:
        for key, value in attrs.items():
            if key in {"transaction_id", "trace_id", "stage", "status"}:
                s.set_attribute(key, str(value))
        yield


def otel_status() -> dict[str, str]:
    """Truthful status for /health-style diagnostics (not a schema field)."""
    installed = False
    try:
        import opentelemetry  # noqa: F401

        installed = True
    except Exception:  # noqa: BLE001
        installed = False
    return {
        "enabled": "1" if otel_enabled() else "0",
        "package_installed": "1" if installed else "0",
        "collector_required": "0",
    }
