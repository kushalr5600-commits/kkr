"""Tests for environment diagnostics and validation reporting (new tooling).

These tests never claim LinuxONE: they assert that s390x labels appear only
when the running process actually reports s390x.
"""
from __future__ import annotations

import json
import os
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.diagnose_env import collect, _process_pointer_bits  # noqa: E402
from scripts.validate_runtime import ValidationReport, StepResult, write_evidence  # noqa: E402


def test_collect_returns_required_sections():
    report = collect()
    for key in (
        "report",
        "truth_rule",
        "os",
        "python",
        "architecture",
        "dependencies",
        "scikit_learn_importable",
        "model_backend",
        "config",
        "dataset",
        "git_revision",
    ):
        assert key in report, f"missing section {key}"
    assert report["report"] == "blackbox_environment_diagnostics"


def test_architecture_truth_rules_match_process_machine():
    import platform

    report = collect()
    arch = report["architecture"]
    machine = platform.machine() or None
    assert arch["process_machine"] == machine
    expected_s390x = machine == "s390x" or "s390x" in (sysconfig_platform())
    assert arch["process_is_s390x"] is expected_s390x
    assert arch["runtime_label"] == ("linuxone" if expected_s390x else "local")
    assert arch["claim_linuxone_verified"] is expected_s390x


def sysconfig_platform() -> str:
    import sysconfig

    return sysconfig.get_platform()


def test_does_not_claim_linuxone_from_config_mentions_alone():
    # On this (non-s390x) host the report must not assert linuxone even though
    # Dockerfile/runbooks mention s390x.
    import platform

    if (platform.machine() or "") == "s390x":
        return  # environment really is s390x; skip the negative claim check
    report = collect()
    assert report["architecture"]["claim_linuxone_verified"] is False
    assert report["architecture"]["runtime_label"] == "local"


def test_pointer_bits_matches_struct():
    assert _process_pointer_bits() == struct.calcsize("P") * 8


def test_dataset_fingerprint_reports_manifest_match():
    report = collect()
    ds = report["dataset"]
    assert ds["dataset_sha256"] is not None and len(ds["dataset_sha256"]) == 64
    assert ds["matches_manifest"] is True


def test_config_fingerprint_exposes_frozen_threshold():
    report = collect()
    cfg = report["config"]
    assert cfg["impact_threshold"] == 0.60
    assert cfg["impact_weights"] == {
        "magnitude": 0.30,
        "dependency": 0.30,
        "anomaly": 0.25,
        "uncertainty": 0.15,
    }
    assert cfg["config_sha256"] is not None


def test_model_backend_selection_is_reported():
    report = collect()
    backend = report["model_backend"]
    assert backend["selected"] in {"sklearn", "numpy"}
    # sklearn_importable flag must be consistent with selection under auto mode
    if os.environ.get("BLACKBOX_MODEL_BACKEND") is None and backend["env_var"] == "(unset)":
        if report["scikit_learn_importable"]:
            assert backend["selected"] == "sklearn"
        else:
            assert backend["selected"] == "numpy"


def test_report_is_json_serializable():
    json.dumps(collect())


def test_validation_report_evidence_bundle_write():
    import shutil
    import tempfile

    import scripts.validate_runtime as vr

    tmp = Path(tempfile.mkdtemp(prefix="bb_val_evidence_"))
    original_root = vr.EVIDENCE_ROOT
    try:
        vr.EVIDENCE_ROOT = tmp
        report = ValidationReport(
            started_at_utc="2026-10-14T00:00:00+00:00",
            finished_at_utc="2026-10-14T00:01:00+00:00",
            architecture_process="AMD64",
            runtime_label="local",
            python_version="3.12.10",
            git_revision=None,
            model_backend="numpy",
            dataset_sha256="0" * 64,
            dataset_matches_manifest=True,
            overall_status="PASS",
            steps=[
                StepResult(name="pytest_full_suite", required=True, status="PASS", exit_code=0),
                StepResult(name="live_http_uvicorn", required=False, status="NOT RUN", notes="skipped"),
            ],
        )
        out = write_evidence(report)
        assert (out / "validation_report.json").exists()
        payload = json.loads((out / "validation_report.json").read_text(encoding="utf-8"))
        assert payload["overall_status"] == "PASS"
        assert payload["runtime_label"] == "local"
        readme = (out / "README.md").read_text(encoding="utf-8")
        assert "LinuxONE" in readme
        assert "pytest_full_suite" in readme
    finally:
        vr.EVIDENCE_ROOT = original_root
        shutil.rmtree(tmp, ignore_errors=True)


def test_certificate_runtime_evidence_line_is_truthful():
    from backend.pipeline import BlackboxService
    from backend.certificate.certificate import _runtime_evidence

    svc = BlackboxService.build()
    runtime = svc.runtime()
    # Fingerprint keys live inside the existing model_versions dict (no schema change).
    assert "config_sha256" in runtime.model_versions
    assert "dataset_sha256" in runtime.model_versions
    assert runtime.model_versions["backend"] in {"sklearn", "numpy"}
    line = _runtime_evidence(runtime)
    assert "Runtime:" in line
    assert runtime.architecture in line
    assert "model backend" in line
    if (runtime.architecture or "") != "s390x":
        assert "s390x" not in line or "not" in line.lower()
