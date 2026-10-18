"""Certificate JSON Schema export + policy annotations + optional OTel no-op."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.shared import config, tracing
from backend.shared.schemas import DecisionCertificate


def test_export_certificate_schema_matches_live_model():
    schema_path = ROOT / "schemas" / "decision_certificate.v1.schema.json"
    # Always regenerate from the live model so the file cannot drift.
    proc_ok = True
    import runpy

    try:
        runpy.run_path(str(ROOT / "scripts" / "export_certificate_schema.py"), run_name="__main__")
    except SystemExit as exc:
        proc_ok = exc.code in (0, None)
    assert proc_ok, "schema export script failed"
    assert schema_path.exists()

    data = json.loads(schema_path.read_text(encoding="utf-8"))
    live = DecisionCertificate.model_json_schema()
    assert set(data["properties"]) == set(live["properties"])
    assert data["properties"] == live["properties"]
    policy = data["x-blackbox-policy"]
    assert policy["policy_version"] == config.POLICY_VERSION
    assert policy["threshold"] == config.IMPACT_THRESHOLD
    assert policy["weights"] == dict(config.IMPACT_WEIGHTS)
    assert policy["formula"] == "I = 0.30*M + 0.30*D + 0.25*A + 0.15*U"
    assert data["$schema"].startswith("https://json-schema.org/")


def test_policy_version_stable_and_frozen_weights():
    assert config.POLICY_VERSION == "1.0.0"
    assert config.IMPACT_WEIGHTS == {
        "magnitude": 0.30,
        "dependency": 0.30,
        "anomaly": 0.25,
        "uncertainty": 0.15,
    }
    assert config.IMPACT_THRESHOLD == 0.60


def test_otel_disabled_is_noop_and_does_not_require_package():
    os.environ.pop("BLACKBOX_OTEL", None)
    assert tracing.otel_enabled() is False
    with tracing.span("unit_span", transaction_id="T-1", secret="must_not_set"):
        pass
    status = tracing.otel_status()
    assert status["enabled"] == "0"
    assert status["collector_required"] == "0"
    # Package may or may not be installed on the host; status is truthful either way.
    assert status["package_installed"] in {"0", "1"}


def test_otel_enabled_without_package_still_noop():
    os.environ["BLACKBOX_OTEL"] = "1"
    try:
        assert tracing.otel_enabled() is True
        if importlib.util.find_spec("opentelemetry") is None:
            with tracing.span("unit_span"):
                pass
        status = tracing.otel_status()
        assert status["enabled"] == "1"
        assert status["collector_required"] == "0"
    finally:
        os.environ.pop("BLACKBOX_OTEL", None)
