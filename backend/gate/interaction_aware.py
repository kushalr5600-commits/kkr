"""Interaction-aware ranking (research candidate from Phase 2/3).

When enabled via config.INTERACTION_AWARE_ENABLED, replaces the frozen
combine() score in the production gate with:

    score = 0.45*A + 0.30*window_pressure + 0.15*D + 0.10*load_pressure

Window/load pressure are deterministic functions of dataset-context features
already produced by extract_features (recent_count, recent_amount_ratio,
recent_same_type, max_background_load, path_max_background_load) — identical
to scripts/phase2_research_experiment.py::build_interaction_features. They do
NOT depend on batch composition, so a batch of 1 scores the same as a batch
of 1000. No failure labels, no test split, no frozen weight change.
"""
from __future__ import annotations

import os
from collections.abc import Sequence

import numpy as np

from backend.shared import config
from backend.shared.errors import GateError

# Columns of extract_features() used for context pressure.
WINDOW_FEATURES = ("recent_count", "recent_amount_ratio", "recent_same_type")
LOAD_FEATURES = ("max_background_load", "path_max_background_load")


def _clip01(x: np.ndarray) -> np.ndarray:
    """Clip to [0, 1], rejecting non-finite values.

    ``np.clip(nan, 0, 1)`` returns ``nan`` and ``nan >= threshold`` is ``False``,
    which would silently skip simulation and issue a false ALLOW. A non-finite
    signal means we could not compute a score, so we raise (the pipeline degrades
    to a truthful REVIEW) instead of letting it masquerade as "safe".
    """
    arr = np.asarray(x, dtype=float)
    if not np.all(np.isfinite(arr)):
        raise GateError(
            "non-finite value in interaction-aware gate signal; refusing to issue a gate decision"
        )
    return np.clip(arr, 0.0, 1.0)


def build_window_pressure(X: np.ndarray, feature_names: Sequence[str]) -> np.ndarray:
    """Co-occurrence pressure from dataset-context features (research formula)."""
    if X.size == 0:
        return np.zeros(0, dtype=float)
    idx = {name: i for i, name in enumerate(feature_names)}
    recent_count = X[:, idx["recent_count"]]
    recent_ratio = X[:, idx["recent_amount_ratio"]]
    recent_same = X[:, idx["recent_same_type"]]
    pressure = (
        0.45 * (recent_count / 10.0)
        + 0.35 * _clip01(recent_ratio / 50.0)
        + 0.20 * (recent_same / 10.0)
    )
    return _clip01(pressure)


def build_load_pressure(X: np.ndarray, feature_names: Sequence[str]) -> np.ndarray:
    """Rolling/background load pressure from dataset-context features."""
    if X.size == 0:
        return np.zeros(0, dtype=float)
    idx = {name: i for i, name in enumerate(feature_names)}
    max_bg = X[:, idx["max_background_load"]]
    path_max_bg = X[:, idx["path_max_background_load"]]
    return _clip01(0.5 * _clip01(max_bg) + 0.5 * _clip01(path_max_bg))


def interaction_aware_score(
    anomaly: np.ndarray,
    dependency: np.ndarray,
    window_pressure: np.ndarray,
    load_pressure: np.ndarray,
) -> np.ndarray:
    """Compute interaction-aware ranking score."""
    w = config.INTERACTION_AWARE_WEIGHTS
    score = (
        w["anomaly"] * _clip01(anomaly)
        + w["window_pressure"] * _clip01(window_pressure)
        + w["dependency"] * _clip01(dependency)
        + w["load_pressure"] * _clip01(load_pressure)
    )
    return _clip01(score)


def score_feature_row(
    X: np.ndarray,
    anomaly: np.ndarray,
    dependency: np.ndarray,
    feature_names: Sequence[str],
) -> np.ndarray:
    """One call: pressure from features + weighted score. Batch-size invariant."""
    if X.size == 0:
        return np.zeros(0, dtype=float)
    wp = build_window_pressure(X, feature_names)
    lp = build_load_pressure(X, feature_names)
    return interaction_aware_score(anomaly, dependency, wp, lp)


def is_enabled() -> bool:
    """Whether the interaction-aware ranking policy is active.

    ``BLACKBOX_INTERACTION`` overrides the config default at runtime: ``on``/
    ``off`` force the value, ``auto`` (or unset) uses ``INTERACTION_AWARE_ENABLED``.
    Any other value is a hard error — never a silent fallback (matches the
    ``resolve_hybrid`` fail-loud discipline). ``off`` reproduces the frozen gate.
    """
    raw = os.environ.get(config.INTERACTION_AWARE_ENV, "").strip().lower()
    if raw in ("", "auto"):
        return config.INTERACTION_AWARE_ENABLED
    if raw in ("on", "true", "1", "yes"):
        return True
    if raw in ("off", "false", "0", "no"):
        return False
    raise ValueError(
        f"invalid {config.INTERACTION_AWARE_ENV}={raw!r}; expected on|off|auto"
    )
