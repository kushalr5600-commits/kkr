"""P3 tests: [0,1] normalization, exact equation, 0.60 boundary, model behaviour, leakage guard."""
from __future__ import annotations

import numpy as np

from tests.fixtures import expect_raises, models, repo

from backend.gate.calibration import evaluate_split, fit_models
from backend.gate.impact_gate import ImpactGate, combine, magnitude_signal
from backend.gate.models import GateModels, extract_features
from backend.shared import config
from backend.shared.errors import DataLeakError
from backend.shared.schemas import Account, ImpactScore, ImpactSignals, Transaction


def _signals(m, d, a, u) -> ImpactSignals:
    return ImpactSignals(magnitude=m, dependency=d, anomaly=a, uncertainty=u)


def _score(value: float) -> ImpactScore:
    return ImpactScore(transaction_id="T", signals=_signals(0, 0, 0, 0), score=value, gate_decision=value >= 0.6)


def test_all_signals_and_scores_are_normalized_to_unit_interval():
    ev = evaluate_split(repo(), models(), "validation")
    assert ev.n > 500
    for name, values in ev.signals.items():
        assert values.min() >= 0.0 and values.max() <= 1.0, name
    assert ev.score.min() >= 0.0 and ev.score.max() <= 1.0


def test_exact_weighted_equation():
    assert combine(_signals(1, 0, 0, 0)) == 0.30
    assert combine(_signals(0, 1, 0, 0)) == 0.30
    assert combine(_signals(0, 0, 1, 0)) == 0.25
    assert combine(_signals(0, 0, 0, 1)) == 0.15
    assert abs(combine(_signals(1, 1, 1, 1)) - 1.0) < 1e-12
    rng = np.random.default_rng(1)
    for m, d, a, u in rng.random((50, 4)):
        expected = 0.30 * m + 0.30 * d + 0.25 * a + 0.15 * u
        assert abs(combine(_signals(m, d, a, u)) - expected) < 1e-12


def test_threshold_routing_boundary_is_0_60_inclusive():
    assert ImpactGate.should_simulate(_score(0.60)) is True
    assert ImpactGate.should_simulate(_score(0.6000001)) is True
    assert ImpactGate.should_simulate(_score(0.5999999)) is False
    # the decision stored on a real score agrees with should_simulate
    ev = evaluate_split(repo(), models(), "validation")
    assert bool(ev.gate_decision[0]) == (ev.score[0] >= 0.60)


def test_magnitude_is_monotone_and_zero_below_baseline():
    acct = Account(id="A", historical_avg_amount=100.0, historical_std_amount=20.0)

    def m(amount):
        tx = Transaction(id="T", account_id="A", amount=amount, timestamp="2026-03-02T09:00:00Z", transaction_type="card_payment")
        return magnitude_signal(tx, acct)

    assert m(50) == 0.0 and m(100) == 0.0
    assert 0.0 < m(110) < m(140) <= m(1_000_000) == 1.0


def test_anomaly_signal_is_higher_for_failures_than_for_ordinary_transactions():
    ev = evaluate_split(repo(), models(), "validation")
    a = ev.signals["anomaly"]
    assert a[ev.failed].mean() > a[~ev.failed].mean() + 0.1


def test_uncertainty_is_a_real_ensemble_disagreement_and_reproducible():
    r = repo()
    rows = []
    for rec in r.records_for_split("validation")[:200]:
        account, graph, context = r.load_context(rec.transaction)
        rows.append(extract_features(rec.transaction, account, graph, context))
    X = np.stack(rows)
    m = models()
    members = m.risk._impl.member_probabilities(X)
    assert members.shape[0] >= 5                         # an ensemble, not one probability
    u = m.risk.uncertainty(X)
    assert np.allclose(u, np.clip(members.std(axis=0) / config.UNCERTAINTY_MAX_STD, 0, 1))
    assert u.max() > u.min()                             # not a constant
    assert np.array_equal(u, m.risk.uncertainty(X))      # reproducible for the same inputs


def test_same_input_and_seed_give_the_same_score():
    first = evaluate_split(repo(), models(), "validation")
    refit = fit_models(repo())
    second = evaluate_split(repo(), refit, "validation")
    assert np.array_equal(first.score, second.score)


def test_fitting_on_any_split_but_calibration_is_refused():
    X = np.zeros((10, len(models().feature_names)))
    y = np.zeros(10)
    for split in ("validation", "test", "demo"):
        exc = expect_raises(DataLeakError, GateModels.fit, X, y, split=split)
        assert exc.code.value == "E012"


def test_numpy_fallback_backend_produces_valid_scores():
    fallback = fit_models(repo(), backend="numpy")
    assert fallback.backend == "numpy"
    ev = evaluate_split(repo(), fallback, "validation")
    assert ev.score.min() >= 0.0 and ev.score.max() <= 1.0
    assert "numpy" in fallback.versions()["anomaly_model"]


def test_models_were_fitted_on_the_calibration_split_only():
    m = models()
    assert m.fitted_on_split == "calibration"
    assert m.n_fit_samples == len(repo().records_for_split("calibration"))
