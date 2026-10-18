#!/usr/bin/env python3
"""Export the versioned Decision Certificate JSON Schema from the live Pydantic model.

    python scripts/export_certificate_schema.py

Writes ``schemas/decision_certificate.v1.schema.json`` without inventing
certificate fields. Policy metadata (version, frozen formula, threshold) is
attached as document-level annotations derived from ``backend.shared.config`` —
it does not alter the Python schema contract.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.shared import config  # noqa: E402
from backend.shared.schemas import DecisionCertificate  # noqa: E402

OUT = ROOT / "schemas" / "decision_certificate.v1.schema.json"


def build_schema() -> dict:
    schema = DecisionCertificate.model_json_schema()
    schema["title"] = "BLACKBOX DecisionCertificate"
    schema["description"] = (
        "Decision Certificate issued by the Impact Gate preflight. "
        "status=NO_SIMULATION means deep simulation did not run "
        "(score below threshold); forks_tested is empty and must not be "
        "read as proof of safety under load. Limitations are evidence "
        "lines prefixed 'LIMITATION: '."
    )
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = (
        "https://blackbox.local/schemas/decision_certificate.v1.schema.json"
    )
    schema["x-blackbox-policy"] = {
        "policy_version": config.POLICY_VERSION,
        "app_version": config.VERSION,
        "formula": "I = 0.30*M + 0.30*D + 0.25*A + 0.15*U",
        "threshold": config.IMPACT_THRESHOLD,
        "weights": dict(config.IMPACT_WEIGHTS),
        "simulate_iff": "score >= threshold",
        "simulation_status_field": "status",
        "simulation_status_values": ["NO_SIMULATION", "SIMULATED", "REVIEW"],
        "limitations_location": "evidence[] where item startswith 'LIMITATION: '",
        "run_identifiers": ["certificate_id", "trace_id"],
        "score_components": "impact_score.{score,signals,gate_decision}",
        "scenario_outcomes": "forks_tested[] + fragility[]",
    }
    schema["x-blackbox-export"] = {
        "generator": "scripts/export_certificate_schema.py",
        "source_model": "backend.shared.schemas.DecisionCertificate",
        "note": "Generated from the live Pydantic model; no fields invented.",
    }
    return schema


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    schema = build_schema()
    OUT.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
