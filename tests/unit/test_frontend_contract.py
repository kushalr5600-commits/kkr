"""Regression tests: frontend/backend contract and demo honesty (completion sprint).

Plain functions so both pytest and ``scripts/run_tests.py`` can run them.
No browser is required: these checks pin the static assets and the API JSON
the dashboard renders.
"""
from __future__ import annotations

from pathlib import Path

from backend.shared import config

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "static"


def _app_js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def _index_html() -> str:
    return (FRONTEND / "index.html").read_text(encoding="utf-8")


def test_frontend_exists_and_is_presentation_only():
    js = _app_js()
    html = _index_html()
    assert "BREAK MY DECISION" in html
    assert "state-result" in html and "state-busy" in html and "state-error" in html
    # Must not compute gate policy in the browser
    assert "0.30" not in js  # frozen weights stay backend-only
    assert "should_simulate" not in js
    assert "fragility_margin" not in js


def test_frontend_brand_logo_and_slogan_assets():
    html = _index_html()
    css = (FRONTEND / "style.css").read_text(encoding="utf-8")
    logo = FRONTEND / "assets" / "logo.svg"
    wordmark = FRONTEND / "assets" / "wordmark.svg"
    assert logo.is_file() and logo.stat().st_size > 200
    assert wordmark.is_file()
    svg = logo.read_text(encoding="utf-8")
    assert "<svg" in svg and "BLACKBOX" in svg
    assert 'aria-label="BLACKBOX logo"' in svg
    assert 'src="/static/assets/logo.svg"' in html
    assert "Simulate today. Decide tomorrow." in html
    assert "SIMULATE TODAY. DECIDE TOMORROW." in wordmark.read_text(encoding="utf-8")
    assert ".brand-logo" in css and ".wm-box" in css
    # Presentation-only: no hardcoded gate policy sneaks in with branding
    assert "0.30" not in html


def test_what_if_button_bound_to_selected_transaction():
    """Regression: wi-btn must not close over an out-of-scope `tx` (strict-mode ReferenceError)."""
    js = _app_js()
    html = _index_html()
    assert 'id="wi-btn"' in html
    # Correct binding: one init-time listener using module-level `selected`
    assert 'runWhatIf(selected)' in js
    # The old broken call pattern (out-of-scope tx inside a handler) must not return.
    # Note: `function runWhatIf(tx) {` (the parameter) is fine; call sites are not.
    assert "runWhatIf(tx)" not in js.replace("function runWhatIf(tx)", "")
    assert ".onclick = function () { runWhatIf(" not in js
    # Wired regardless of analysis result, and disabled until a transaction exists
    assert '$("wi-btn").addEventListener("click"' in js
    assert '$("wi-btn").disabled = false' in js
    # File still parses as strict-mode-safe (no undeclared tx reference in handlers)
    assert '"use strict"' in js


def test_frontend_renders_certificate_fields_and_honest_no_simulation_notice():
    js = _app_js()
    for field in (
        "recommended_action",
        "status",
        "transaction_id",
        "trace_id",
        "certificate_id",
        "decision_description",
        "impact_score",
        "forks_tested",
        "fragility",
        "evidence",
        "runtime",
    ):
        assert field in js, f"dashboard must read certificate field {field!r}"
    assert "No deep simulation was performed" in js
    assert "NO_SIMULATION" in js
    assert "LIMITATION: " in js


def test_frontend_skips_incomplete_fork_pairs():
    js = _app_js()
    assert "incomplete" in js
    assert "!normal || !stress" in js


def test_frontend_action_and_status_classes_match_certificate_literals():
    css = (FRONTEND / "style.css").read_text(encoding="utf-8")
    for action in ("ALLOW_NORMAL_PATH", "BLOCK_OR_HOLD", "REVIEW"):
        assert f".action.{action}" in css, f"missing style for action {action}"
    for status in ("NO_SIMULATION", "SIMULATED", "REVIEW"):
        assert f".status.{status}" in css, f"missing style for status {status}"


def test_api_demo_no_simulation_is_honest_and_empty():
    from tests.fixtures import service

    cert = service().analyze(demo_mode=True)
    assert cert.transaction_id == config.DEMO_TRANSACTION_ID
    if cert.status == "NO_SIMULATION":
        assert cert.recommended_action == "ALLOW_NORMAL_PATH"
        assert cert.forks_tested == [] and cert.fragility == []
        assert any("No deep simulation was run" in line for line in cert.evidence)
    else:
        assert cert.status == "SIMULATED"
        assert len(cert.forks_tested) == 2 * len(config.SCENARIOS)
    assert any(line.startswith("LIMITATION: ") for line in cert.evidence)
    assert cert.impact_score.gate_decision is False
    assert cert.runtime.model_versions.get("backend") in {"numpy", "sklearn"}


def test_api_simulated_example_has_paired_forks_and_scenarios():
    from backend.shared.schemas import Transaction
    from tests.fixtures import service

    svc = service()
    found = False
    for item in svc.demo_transactions():
        cert = svc.analyze(Transaction.model_validate(item["transaction"]))
        if cert.status != "SIMULATED":
            continue
        found = True
        assert len(cert.forks_tested) == 2 * len(config.SCENARIOS)
        for scenario in config.SCENARIOS:
            names = {f.fork_name for f in cert.forks_tested if f.scenario == scenario}
            assert names == {"normal", "stress"}
        assert {f.scenario for f in cert.fragility} == set(config.SCENARIOS)
        break
    assert found, "expected at least one SIMULATED showcase transaction"


def test_frontend_navigation_and_design_tokens():
    """Advanced UI: nav destinations, honesty colors, no green-for-skipped-safety."""
    html = _index_html()
    js = _app_js()
    css = (FRONTEND / "style.css").read_text(encoding="utf-8")
    for label in (
        "Decision Explorer",
        "Dataset Studio",
        "Challenge Lab",
        "Experiments",
        "Certificates",
    ):
        assert label in html, f"missing nav destination {label!r}"
    # Open Datasets tab was removed by product decision (F-042): the metadata
    # catalog stays backend-only (GET /datasets/registry is still pinned
    # elsewhere); the UI must not resurrect the panel.
    assert "panel-open" not in html
    assert "Open Datasets" not in html
    # Design tokens: green success, amber warning, red missed failure
    for token in ("--ok", "--warn", "--bad", "sim-skipped", "bad-notice"):
        assert token in css or token in js, f"missing design token/use {token!r}"
    # Skipped simulation must not use green success language in the notice
    assert "not proven safety" in js
    assert "SKIPPED" in js
    # Score vs threshold visualization present
    assert "dial-score" in js and "Above threshold" in js
    # Trust / provenance fields rendered
    for field in ("policy_version", "dataset_sha256", "config_sha256", "Unknown"):
        assert field in js, f"missing trust field {field!r}"


def test_api_unknown_type_and_account_return_input_errors():
    from backend.shared.errors import InputError
    from tests.fixtures import expect_raises, repo, service

    base = repo().demo_transaction()
    bad_type = base.model_copy(update={"transaction_type": "crypto_swap"})
    bad_acct = base.model_copy(update={"account_id": "ACC-NOPE"})
    expect_raises(InputError, service().analyze, bad_type)
    expect_raises(InputError, service().analyze, bad_acct)
