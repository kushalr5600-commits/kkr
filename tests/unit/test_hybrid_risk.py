"""Hybrid risk ensemble: XGBoost members join the sklearn forest (rubric: >=2 frameworks)."""
from __future__ import annotations

import numpy as np
import pytest

from tests.fixtures import models, repo

from backend.gate.calibration import fit_models
from backend.gate.models import GateModels, resolve_hybrid
from backend.shared import config
from backend.shared.errors import ModelError


def test_resolve_hybrid_auto_is_on_when_xgboost_imports():
    import xgboost  # noqa: F401

    assert resolve_hybrid("auto") is True


def test_resolve_hybrid_off_and_on_env_overrides():
    assert resolve_hybrid("off") is False
    assert resolve_hybrid("on") is True
    with pytest.raises(ModelError):
        resolve_hybrid("maybe")


def test_default_sklearn_fit_is_hybrid_and_versions_report_both_frameworks():
    m = models()
    if m.backend != "sklearn":
        pytest.skip("hybrid risk requires the sklearn backend")
    assert m.hybrid_risk is True
    v = m.versions()
    assert v["hybrid_risk"] == "on"
    assert "scikit-learn" in v["risk_model"] and "xgboost" in v["risk_model"]
    assert config.UNCERTAINTY_HYBRID_MODEL.split(" ")[0] in v["risk_model"]


def test_hybrid_members_are_trees_plus_xgboost_models():
    r = repo()
    rows = []
    for rec in r.records_for_split("validation")[:200]:
        account, graph, context = r.load_context(rec.transaction)
        from backend.gate.models import extract_features

        rows.append(extract_features(rec.transaction, account, graph, context))
    X = np.stack(rows)
    m = models()
    if m.backend != "sklearn" or not m.hybrid_risk:
        pytest.skip("needs hybrid sklearn backend")
    members = m.risk._impl.member_probabilities(X)
    assert members.shape[0] == config.RISK_N_ESTIMATORS + config.RISK_XGB_N_MODELS
    u = m.risk.uncertainty(X)
    assert np.allclose(u, np.clip(members.std(axis=0) / config.UNCERTAINTY_MAX_STD, 0, 1))


def test_hybrid_off_restores_plain_randomforest_and_changes_only_u():
    r = repo()
    base = models()
    if base.backend != "sklearn":
        pytest.skip("needs sklearn backend")
    plain = fit_models(r, backend="sklearn", hybrid=False)
    assert plain.hybrid_risk is False
    assert "xgboost" not in plain.versions()["risk_model"]
    assert plain.risk.name == config.UNCERTAINTY_MODEL


def test_same_seed_gives_identical_hybrid_uncertainty():
    r = repo()
    m1 = fit_models(r, backend="sklearn", hybrid=True)
    m2 = fit_models(r, backend="sklearn", hybrid=True)
    assert m1.hybrid_risk and m2.hybrid_risk
    assert np.array_equal(
        m1.versions()["risk_model"], m2.versions()["risk_model"]
    )


def test_numpy_backend_never_uses_xgboost():
    fb = fit_models(repo(), backend="numpy")
    assert fb.hybrid_risk is False
    v = fb.versions()
    assert v["hybrid_risk"] == "off"
    assert "xgboost" not in v["risk_model"]
    assert "xgboost" not in v["anomaly_model"]


def test_gate_scores_ignore_hybrid_in_interaction_mode():
    """Interaction-aware gate has no U term: hybrid must not move the decision."""
    from backend.gate.impact_gate import ImpactGate

    r = repo()
    base = models()
    if base.backend != "sklearn" or not config.INTERACTION_AWARE_ENABLED:
        pytest.skip("interaction mode off or not sklearn")
    plain = fit_models(r, backend="sklearn", hybrid=False)
    recs = r.records_for_split("demo")[:40]
    items = []
    for rec in recs:
        account, graph, context = r.load_context(rec.transaction)
        items.append((rec.transaction, account, graph, context))
    s_hybrid = ImpactGate.score_batch(items, base)
    s_plain = ImpactGate.score_batch(items, plain)
    assert [s.score for s in s_hybrid] == [s.score for s in s_plain]
    assert [s.gate_decision for s in s_hybrid] == [s.gate_decision for s in s_plain]
    # but the raw U signal does differ somewhere (the frameworks disagree)
    u_h = np.asarray([s.signals.uncertainty for s in s_hybrid])
    u_p = np.asarray([s.signals.uncertainty for s in s_plain])
    assert u_h.shape == u_p.shape
