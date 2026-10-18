"""Tracing, stage logging and runtime metadata (Agent manual v4, section 1.12).

Every request gets a ``trace_id``. Every pipeline stage logs
``trace_id, transaction_id, stage, status, elapsed_ms`` and, on failure,
``error_type, error_message, owner, recovery_action``. Nothing else is logged:
no payloads, no credentials.

``RuntimeMetadata`` is built from what is actually observed at runtime
(``platform.machine()``, interpreter version, git revision). It never claims
LinuxONE unless the process really runs on ``s390x``.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import platform
import subprocess
import time
import uuid
from collections import deque
from contextvars import ContextVar
from pathlib import Path
from typing import Iterator

from backend.shared import config
from backend.shared.errors import BlackboxError
from backend.shared.schemas import RuntimeMetadata

logger = logging.getLogger("blackbox.diag")

_trace_id: ContextVar[str | None] = ContextVar("blackbox_trace_id", default=None)

# Recent stage events, newest last. Used by tests and for local debugging.
RECENT_EVENTS: deque[dict] = deque(maxlen=2000)

STAGES = (
    "request_received",
    "context_loaded",
    "gate_scored",
    "simulation_started",
    "scenario_completed",
    "fragility_completed",
    "certificate_generated",
    "response_sent",
)


def new_trace_id() -> str:
    return "TR-" + uuid.uuid4().hex[:12]


def set_trace_id(trace_id: str | None) -> None:
    _trace_id.set(trace_id)


def get_trace_id(create: bool = True) -> str | None:
    """Return the current trace id, creating one when none is active."""
    current = _trace_id.get()
    if current is None and create:
        current = new_trace_id()
        _trace_id.set(current)
    return current


@contextlib.contextmanager
def trace_scope(trace_id: str | None = None) -> Iterator[str]:
    """Activate a trace id for the duration of one request."""
    tid = trace_id or new_trace_id()
    token = _trace_id.set(tid)
    try:
        yield tid
    finally:
        _trace_id.reset(token)


def _emit(event: dict) -> None:
    RECENT_EVENTS.append(event)
    logger.info(json.dumps(event, sort_keys=True))


@contextlib.contextmanager
def stage(name: str, transaction_id: str | None) -> Iterator[None]:
    """Log one pipeline stage with its elapsed time and outcome."""
    start = time.perf_counter()
    base = {
        "trace_id": get_trace_id(),
        "transaction_id": transaction_id,
        "stage": name,
    }
    try:
        yield
    except Exception as exc:  # noqa: BLE001 - logged then re-raised
        event = dict(base)
        event["status"] = "error"
        event["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 3)
        if isinstance(exc, BlackboxError):
            event.update(exc.as_dict())
        else:
            event.update(
                {
                    "error_code": None,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "owner": "unknown",
                    "recovery_action": "reproduce with the demo transaction; inspect first failing stage",
                }
            )
        _emit(event)
        raise
    else:
        event = dict(base)
        event["status"] = "ok"
        event["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 3)
        _emit(event)


def log_event(name: str, transaction_id: str | None, status: str = "ok", elapsed_ms: float = 0.0) -> None:
    """Log a stage that has no natural duration (e.g. scenario_completed)."""
    _emit(
        {
            "trace_id": get_trace_id(),
            "transaction_id": transaction_id,
            "stage": name,
            "status": status,
            "elapsed_ms": round(elapsed_ms, 3),
        }
    )


def configure_logging(level: int = logging.INFO) -> None:
    """Emit stage events as JSON lines on stderr (idempotent)."""
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


# ---------------------------------------------------------------------------
# Runtime metadata
# ---------------------------------------------------------------------------
_git_revision_cache: tuple[bool, str | None] = (False, None)


def git_revision() -> str | None:
    """Short git revision, from $BLACKBOX_GIT_REVISION or ``git`` if available."""
    global _git_revision_cache
    done, value = _git_revision_cache
    if done:
        return value
    value = os.environ.get("BLACKBOX_GIT_REVISION") or None
    if value is None:
        root = Path(__file__).resolve().parents[2]
        try:
            out = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=root, capture_output=True, text=True, timeout=2, check=False,
            )
            if out.returncode == 0 and out.stdout.strip():
                value = out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            value = None
    _git_revision_cache = (True, value)
    return value


def runtime_description() -> str:
    return f"{platform.python_implementation()} {platform.python_version()} on {platform.system()}"


def runtime_metadata(
    model_versions: dict[str, str] | None = None,
    random_seed: int | None = None,
) -> RuntimeMetadata:
    """Truthful runtime metadata for certificates and /health."""
    return RuntimeMetadata(
        runtime=runtime_description(),
        architecture=platform.machine() or "unknown",
        model_versions=dict(model_versions or {}),
        random_seed=random_seed if random_seed is not None else config.DEMO_SEED,
        git_revision=git_revision(),
    )
