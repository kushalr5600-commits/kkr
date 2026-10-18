"""Shared test helpers. Plain Python so the suite runs under pytest or under
``python scripts/run_tests.py`` (used where pytest cannot be installed)."""
from __future__ import annotations

import functools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.data.generator import DatasetGenerator  # noqa: E402
from backend.data.repository import DataRepository  # noqa: E402
from backend.gate.calibration import fit_models  # noqa: E402
from backend.pipeline import BlackboxService  # noqa: E402


@functools.lru_cache(maxsize=1)
def repo() -> DataRepository:
    """The default-seed dataset, built in memory (identical to the checked-in file)."""
    return DataRepository(DatasetGenerator.build_dataset())


@functools.lru_cache(maxsize=1)
def models():
    return fit_models(repo())


@functools.lru_cache(maxsize=1)
def service() -> BlackboxService:
    return BlackboxService(repo(), models())


def expect_raises(exc_type, fn, *args, **kwargs):
    """Assert that ``fn`` raises ``exc_type`` and return the exception."""
    try:
        fn(*args, **kwargs)
    except exc_type as exc:
        return exc
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"expected {exc_type.__name__}, got {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"expected {exc_type.__name__} but nothing was raised")
