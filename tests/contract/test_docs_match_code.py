"""Reverse contract checks: the documents must match the code.

The forward direction (code constants vs frozen expectations) lives in
``test_schemas_and_interfaces.py``. These tests hold the DOCUMENTS to the same
contract so claims cannot drift silently:

  * every API route registered on the FastAPI app is listed in
    ``docs/CONTRACTS.md``, and every route listed there is registered;
  * the gate-policy values printed in ``docs/CONTRACTS.md`` equal
    ``backend/shared/config.py`` (threshold, weights, POLICY_VERSION,
    scenarios, interaction-aware weights);
  * live top-level docs that state a ``POLICY_VERSION`` state the real one.

Zero-argument tests (no pytest fixtures), per project test discipline.
"""
from __future__ import annotations

import re
from pathlib import Path

from backend.shared import config

ROOT = Path(__file__).resolve().parents[2]

# FastAPI's auto-generated endpoints are not part of the documented API surface.
_AUTO_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/static")


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _app_routes() -> set[str]:
    from backend.main import app

    routes: set[str] = set()
    for r in app.routes:
        path = getattr(r, "path", "")
        methods = getattr(r, "methods", None)
        if not path or path.startswith(_AUTO_PREFIXES):
            continue
        for m in sorted(methods or ["GET"]):
            routes.add(f"{m} {path}")
    return routes


def _documented_routes() -> set[str]:
    doc = _read("docs/CONTRACTS.md")
    # Markdown table rows: | METHOD | `path` | purpose |   (path may be just "/")
    return {
        f"{m.upper()} {p}"
        for m, p in re.findall(r"^\|\s*([A-Z]+)\s*\|\s*`(/[^`]*)`", doc, re.M)
    }


def test_every_app_route_is_documented_in_contracts_md():
    missing = sorted(_app_routes() - _documented_routes())
    assert not missing, f"routes missing from docs/CONTRACTS.md: {missing}"


def test_contracts_md_documents_no_unknown_routes():
    unknown = sorted(_documented_routes() - _app_routes())
    assert not unknown, f"docs/CONTRACTS.md lists routes that do not exist: {unknown}"


def test_contracts_md_gate_policy_matches_config():
    doc = _read("docs/CONTRACTS.md")

    # Frozen reference policy line: formula and threshold on one line.
    frozen = re.search(
        r"I\(T\)\s*=\s*([0-9.]+)\*M\s*\+\s*([0-9.]+)\*D\s*\+\s*([0-9.]+)\*A\s*\+\s*([0-9.]+)\*U"
        r".*?threshold\s*=\s*([0-9.]+)",
        doc,
    )
    assert frozen, "docs/CONTRACTS.md is missing the frozen policy formula line"
    m, d, a, u, thr = (float(x) for x in frozen.groups())
    assert (m, d, a, u) == (
        config.IMPACT_WEIGHTS["magnitude"],
        config.IMPACT_WEIGHTS["dependency"],
        config.IMPACT_WEIGHTS["anomaly"],
        config.IMPACT_WEIGHTS["uncertainty"],
    ), "documented frozen weights drifted from config.IMPACT_WEIGHTS"
    assert thr == config.IMPACT_THRESHOLD, "documented threshold drifted from config.IMPACT_THRESHOLD"

    # Interaction-aware policy line (production ranking).
    inter = re.search(
        r"I\(T\)\s*=\s*([0-9.]+)\*A\s*\+\s*([0-9.]+)\*W\s*\+\s*([0-9.]+)\*D\s*\+\s*([0-9.]+)\*L",
        doc,
    )
    assert inter, "docs/CONTRACTS.md is missing the interaction-aware policy formula line"
    a2, w, d2, l = (float(x) for x in inter.groups())
    assert (a2, w, d2, l) == (
        config.INTERACTION_AWARE_WEIGHTS["anomaly"],
        config.INTERACTION_AWARE_WEIGHTS["window_pressure"],
        config.INTERACTION_AWARE_WEIGHTS["dependency"],
        config.INTERACTION_AWARE_WEIGHTS["load_pressure"],
    ), "documented interaction weights drifted from config.INTERACTION_AWARE_WEIGHTS"

    # POLICY_VERSION and scenario identifiers.
    pv = re.search(r"POLICY_VERSION\s*=\s*([0-9.]+)", doc)
    assert pv, "docs/CONTRACTS.md is missing POLICY_VERSION"
    assert pv.group(1) == config.POLICY_VERSION, "documented POLICY_VERSION drifted from config"
    sc = re.search(r"SCENARIOS\s*=\s*([a-z0-9_,\s]+)", doc)
    assert sc, "docs/CONTRACTS.md is missing SCENARIOS"
    assert [s.strip() for s in sc.group(1).split(",")] == list(config.SCENARIOS), (
        "documented SCENARIOS drifted from config.SCENARIOS"
    )


def test_live_docs_policy_version_matches_config():
    for rel in ("HANDOFF.md", "README.md", "docs/STATUS.md"):
        text = _read(rel)
        for stated in re.findall(r"POLICY_VERSION\s*[:=]?\s*[`\"']?(\d+\.\d+(?:\.\d+)?)", text):
            assert stated == config.POLICY_VERSION, (
                f"{rel} states POLICY_VERSION {stated}, config says {config.POLICY_VERSION}"
            )
