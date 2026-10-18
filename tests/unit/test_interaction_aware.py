import numpy as np

from backend.gate.interaction_aware import (
    build_load_pressure,
    build_window_pressure,
    interaction_aware_score,
    is_enabled,
    score_feature_row,
)
from backend.gate.models import FEATURE_NAMES
from backend.shared import config


def _features(rows: list[dict]) -> np.ndarray:
    """Build a feature matrix from sparse {name: value} rows."""
    X = np.zeros((len(rows), len(FEATURE_NAMES)))
    for i, row in enumerate(rows):
        for name, value in row.items():
            X[i, FEATURE_NAMES.index(name)] = value
    return X


def test_interaction_aware_enabled():
    assert is_enabled()
    assert config.INTERACTION_AWARE_ENABLED is True


def test_interaction_aware_score_formula():
    a = np.array([0.5, 0.8, 0.2])
    d = np.array([0.3, 0.9, 0.1])
    wp = np.array([0.6, 0.2, 0.7])
    lp = np.array([0.4, 0.5, 0.3])
    score = interaction_aware_score(a, d, wp, lp)
    w = config.INTERACTION_AWARE_WEIGHTS
    expected = (
        w["anomaly"] * a
        + w["window_pressure"] * wp
        + w["dependency"] * d
        + w["load_pressure"] * lp
    )
    np.testing.assert_allclose(score, expected)


def test_interaction_aware_score_clipped():
    a = np.array([1.0, 0.0])
    d = np.array([1.0, 0.0])
    wp = np.array([1.0, 0.0])
    lp = np.array([1.0, 0.0])
    score = interaction_aware_score(a, d, wp, lp)
    assert score[0] == 1.0
    assert score[1] == 0.0


def test_build_window_pressure_research_formula():
    X = _features([{"recent_count": 10, "recent_amount_ratio": 50.0, "recent_same_type": 10}])
    (wp,) = build_window_pressure(X, FEATURE_NAMES)
    # 0.45*(10/10) + 0.35*clip(50/50) + 0.20*(10/10) = 1.00
    np.testing.assert_allclose(wp, 1.0)
    X0 = _features([{"recent_count": 0, "recent_amount_ratio": 0.0, "recent_same_type": 0}])
    assert build_window_pressure(X0, FEATURE_NAMES)[0] == 0.0


def test_build_load_pressure_research_formula():
    X = _features([{"max_background_load": 1.0, "path_max_background_load": 0.0}])
    (lp,) = build_load_pressure(X, FEATURE_NAMES)
    np.testing.assert_allclose(lp, 0.5)  # 0.5*1 + 0.5*0
    Xmax = _features([{"max_background_load": 3.0, "path_max_background_load": 2.0}])
    assert build_load_pressure(Xmax, FEATURE_NAMES)[0] == 1.0  # clipped


def test_pressure_empty_matrix():
    X = np.zeros((0, len(FEATURE_NAMES)))
    assert len(build_window_pressure(X, FEATURE_NAMES)) == 0
    assert len(build_load_pressure(X, FEATURE_NAMES)) == 0
    assert len(score_feature_row(X, np.array([]), np.array([]), FEATURE_NAMES)) == 0


def test_score_is_batch_size_invariant():
    """Regression: a single-tx batch must score identically to that row inside
    a large batch (batch-composition pressure was the original wiring bug)."""
    rng = np.random.default_rng(7)
    n = 64
    X = np.zeros((n, len(FEATURE_NAMES)))
    for name in ("recent_count", "recent_amount_ratio", "recent_same_type"):
        X[:, FEATURE_NAMES.index(name)] = rng.integers(0, 10, n)
    for name in ("max_background_load", "path_max_background_load"):
        X[:, FEATURE_NAMES.index(name)] = rng.random(n) * 3
    a = rng.random(n)
    d = rng.random(n)

    batch_scores = score_feature_row(X, a, d, FEATURE_NAMES)
    for i in (0, 17, 63):
        single = score_feature_row(X[i : i + 1], a[i : i + 1], d[i : i + 1], FEATURE_NAMES)
        np.testing.assert_allclose(single[0], batch_scores[i], rtol=0, atol=1e-12)


def test_score_feature_row_matches_manual_formula():
    X = _features([{"recent_count": 5, "recent_amount_ratio": 25.0, "recent_same_type": 5,
                    "max_background_load": 0.4, "path_max_background_load": 0.8}])
    a, d = np.array([0.7]), np.array([0.6])
    wp = 0.45 * 0.5 + 0.35 * 0.5 + 0.20 * 0.5
    lp = 0.5 * 0.4 + 0.5 * 0.8
    expected = 0.45 * 0.7 + 0.30 * wp + 0.15 * 0.6 + 0.10 * lp
    np.testing.assert_allclose(score_feature_row(X, a, d, FEATURE_NAMES)[0], expected)
