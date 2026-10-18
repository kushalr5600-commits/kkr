"""Dependency-free test runner for environments where pytest cannot be installed.

    python scripts/run_tests.py [substring-filter]

The tests are ordinary pytest-style functions, so ``python -m pytest`` is the
preferred way to run them. This runner imports every ``tests/**/test_*.py``,
calls every ``test_*`` function and prints PASS/FAIL/SKIP/ERROR per test.

It never aborts mid-run:
  * a module that fails to import (e.g. it hard-imports pytest) -> ERROR,
    the remaining modules still run;
  * ``pytest.skip`` / a truthy ``skipif`` marker -> SKIP, not FAIL;
  * a function requiring arguments (fixtures) -> SKIP with a reason, matching
    the zero-arg test discipline.
"""
from __future__ import annotations

import importlib
import inspect
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _skip_reason(module, fn):
    """Skip reason from pytest skip/skipif markers, or None to run the test.

    Works when pytest is importable; without pytest there are no markers to
    evaluate, so the test runs normally.
    """
    marks = list(getattr(fn, "pytestmark", [])) + list(getattr(module, "pytestmark", []))
    for mark in marks:
        if getattr(mark, "name", None) != "skipif":
            continue
        if mark.args and mark.args[0]:
            return mark.kwargs.get("reason", "skipif condition met")
    return None


def _is_pytest_skip(exc: BaseException) -> str | None:
    """If ``exc`` is a pytest ``skip`` outcome, return its reason."""
    if type(exc).__name__ == "Skipped":  # _pytest.outcomes.Skipped
        args = getattr(exc, "args", ())
        return str(args[0]) if args else "pytest.skip()"
    return None


def main() -> int:
    needle = sys.argv[1] if len(sys.argv) > 1 else ""
    modules = sorted(p for p in (ROOT / "tests").rglob("test_*.py"))
    passed = failed = skipped = errors = 0
    started = time.perf_counter()
    for path in modules:
        name = ".".join(path.relative_to(ROOT).with_suffix("").parts)
        try:
            module = importlib.import_module(name)
        except Exception:  # noqa: BLE001 - keep going: report and continue
            errors += 1
            print(f"ERROR {name} (import failed)")
            traceback.print_exc()
            continue
        for fn_name in sorted(n for n in dir(module) if n.startswith("test_")):
            full = f"{name}::{fn_name}"
            if needle and needle not in full:
                continue
            fn = getattr(module, fn_name)
            if not callable(fn):
                continue
            # Zero-arg discipline: fixture/parameterised tests are pytest-only.
            try:
                sig = inspect.signature(fn)
                if any(
                    p.default is inspect.Parameter.empty
                    and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
                    for p in sig.parameters.values()
                ):
                    skipped += 1
                    print(f"SKIP  {full}  (requires arguments/fixtures; run with pytest)")
                    continue
            except (TypeError, ValueError):
                pass  # builtins/callables without signatures: just try the call
            reason = _skip_reason(module, fn)
            if reason is not None:
                skipped += 1
                print(f"SKIP  {full}  ({reason})")
                continue
            t0 = time.perf_counter()
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                skip_reason = _is_pytest_skip(exc)
                if skip_reason is not None:
                    skipped += 1
                    print(f"SKIP  {full}  ({skip_reason})")
                else:
                    failed += 1
                    print(f"FAIL  {full}")
                    traceback.print_exc()
            else:
                passed += 1
                print(f"PASS  {full}  ({time.perf_counter() - t0:.2f}s)")
    print(
        f"\n{passed} passed, {failed} failed, {skipped} skipped, {errors} error(s) "
        f"in {time.perf_counter() - started:.1f}s"
    )
    return 1 if failed or errors else 0


if __name__ == "__main__":
    sys.exit(main())
