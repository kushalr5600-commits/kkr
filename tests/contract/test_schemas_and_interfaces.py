"""Contract tests: frozen names, enums, signatures and Type A input validation."""
from __future__ import annotations

import inspect
import typing

from tests.fixtures import expect_raises

from backend.certificate.certificate import CertificateGenerator
from backend.data.generator import DatasetGenerator
from backend.data.repository import DataRepository
from backend.gate.impact_gate import ImpactGate
from backend.shared import config, schemas
from backend.simulation.crash_test import CrashTestEngine
from backend.simulation.forks import RealityForkGenerator
from backend.simulation.fragility import FragilitySearch

EXPECTED_FIELDS = {
    "Transaction": {"id", "account_id", "amount", "timestamp", "transaction_type"},
    "Account": {"id", "historical_avg_amount", "historical_std_amount", "related_account_ids"},
    "EventContext": {"recent_transactions", "local_dependency_load", "window_seconds"},
    "GraphNode": {"id", "node_type"},
    "GraphEdge": {"source", "target"},
    "DependencyGraph": {"nodes", "edges"},
    "ImpactSignals": {"magnitude", "dependency", "anomaly", "uncertainty"},
    "ImpactScore": {"transaction_id", "signals", "score", "gate_decision"},
    "ForkResult": {"fork_name", "scenario", "survived", "metrics"},
    "FragilityResult": {"scenario", "breaking_threshold", "unit", "resolution"},
    "RuntimeMetadata": {"runtime", "architecture", "model_versions", "random_seed", "git_revision"},
    "DecisionCertificate": {
        "certificate_id", "trace_id", "status", "transaction_id", "decision_description",
        "impact_score", "forks_tested", "fragility", "recommended_action", "evidence", "runtime",
    },
}


def test_schema_model_names_and_fields_are_frozen():
    for name, fields in EXPECTED_FIELDS.items():
        model = getattr(schemas, name)
        assert set(model.model_fields) == fields, f"{name} fields drifted"


def test_node_type_vocabulary_matches_config():
    literal = typing.get_args(schemas.GraphNode.model_fields["node_type"].annotation)
    assert set(literal) == set(config.NODE_TYPES)
    assert len(literal) == 9


def test_scenario_identifiers_are_exact():
    assert config.SCENARIOS == ["3x_volume", "fraud_spike", "service_latency"]


def test_gate_formula_constants_are_frozen():
    assert config.IMPACT_WEIGHTS == {"magnitude": 0.30, "dependency": 0.30, "anomaly": 0.25, "uncertainty": 0.15}
    assert abs(sum(config.IMPACT_WEIGHTS.values()) - 1.0) < 1e-12
    assert config.IMPACT_THRESHOLD == 0.60


def test_certificate_enums():
    status = typing.get_args(schemas.DecisionCertificate.model_fields["status"].annotation)
    action = typing.get_args(schemas.DecisionCertificate.model_fields["recommended_action"].annotation)
    assert set(status) == {"NO_SIMULATION", "SIMULATED", "REVIEW"}
    assert set(action) == {"ALLOW_NORMAL_PATH", "REVIEW", "BLOCK_OR_HOLD"}
    fork = typing.get_args(schemas.ForkResult.model_fields["fork_name"].annotation)
    assert set(fork) == {"normal", "stress"}


def _params(fn) -> list[str]:
    return [p for p in inspect.signature(fn).parameters if p != "cls"]


def test_frozen_interface_names_and_parameters():
    assert _params(ImpactGate.score) == ["transaction", "account", "graph", "context"]
    assert _params(ImpactGate.should_simulate) == ["score"]
    assert _params(RealityForkGenerator.generate_baseline) == ["transaction", "graph", "context"]
    assert _params(CrashTestEngine.attack) == ["baseline_fork", "scenario"]
    assert _params(FragilitySearch.find_threshold) == ["baseline_fork", "scenario"]
    assert _params(CertificateGenerator.generate) == [
        "transaction", "impact_score", "fork_results", "fragility", "runtime",
    ]
    assert _params(DataRepository.load_context) == ["self", "transaction"]
    assert _params(DatasetGenerator.generate_accounts)[0] == "n"
    assert _params(DatasetGenerator.generate_transactions)[:2] == ["accounts", "n"]


def test_transaction_validation_rejects_bad_input():
    good = {"id": "T1", "account_id": "A1", "amount": 10.0, "timestamp": "2026-03-02T09:00:00Z",
            "transaction_type": "card_payment"}
    schemas.Transaction.model_validate(good)
    from pydantic import ValidationError

    for patch in (
        {"id": ""},
        {"amount": 0},
        {"amount": -5},
        {"amount": float("nan")},
        {"timestamp": "not-a-time"},
        {"transaction_type": ""},
    ):
        expect_raises(ValidationError, schemas.Transaction.model_validate, {**good, **patch})
    missing = dict(good)
    del missing["id"]
    expect_raises(ValidationError, schemas.Transaction.model_validate, missing)
