"""Feature extraction and the two learned models behind the Impact Gate.

  A  anomaly model   IsolationForest (scikit-learn)  or  RobustMahalanobis (numpy)
  U  risk model      RandomForest failure classifier, optionally HYBRIDIZED with
                     XGBoost models (two open-source frameworks, one std), or
                     bagged logistic regression (numpy)

Both are fitted on the CALIBRATION split only.

  * A is normalized to [0, 1] with the empirical CDF of the calibration raw
    scores (larger = more anomalous).
  * U is the std, across ensemble members, of the predicted P(failure),
    divided by 0.5 (the largest possible std of values in [0, 1]) and clipped.
    That normalization needs no fitting, so it cannot leak test information.
    With the hybrid risk ensemble the members are the sklearn trees PLUS the
    XGBoost bootstrap models, so U literally measures cross-framework
    disagreement.

The numpy backend exists because scikit-learn may not install on s390x
(Agent manual, PART 6/7: "activate the approved simpler statistical fallback
and document it"). ``BLACKBOX_MODEL_BACKEND`` = auto | sklearn | numpy.
``BLACKBOX_HYBRID_RISK`` = auto | on | off controls the XGBoost members
(auto = activate iff xgboost imports; the numpy backend never uses xgboost).
``GateModels.versions()`` always reports which backend actually ran.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np

from backend.shared import config
from backend.shared.context_utils import recent_in_window, reachable_services
from backend.shared.errors import GateError, ModelError
from backend.shared.schemas import Account, DependencyGraph, EventContext, Transaction

FEATURE_NAMES: tuple[str, ...] = (
    "amount_zscore",
    "amount_ratio",
    "recent_count",
    "recent_amount_ratio",
    "recent_same_type",
    "max_background_load",
    "mean_background_load",
    "reach_service_count",
    "reach_criticality_share",
    "path_max_background_load",
) + tuple(f"type_{t}" for t in config.TRANSACTION_TYPES)

_TOTAL_CRITICALITY = sum(config.CRITICALITY.values())


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------
def criticality_share(path_services: list[str]) -> float:
    return sum(config.CRITICALITY[s] for s in path_services) / _TOTAL_CRITICALITY


def extract_features(
    transaction: Transaction,
    account: Account,
    graph: DependencyGraph,
    context: EventContext,
) -> np.ndarray:
    """Cheap, non-simulating features of one transaction and its local state."""
    avg = max(float(account.historical_avg_amount), 1e-6)
    std = max(float(account.historical_std_amount), 1e-6)
    z = float(np.clip((transaction.amount - avg) / std, -5.0, 20.0))
    ratio = float(np.clip(transaction.amount / avg, 0.0, 50.0))

    recents = recent_in_window(transaction, context)
    recent_count = float(min(len(recents), 10))
    recent_ratio = float(np.clip(sum(r.amount for r in recents) / avg, 0.0, 100.0))
    same_type = float(sum(1 for r in recents if r.transaction_type == transaction.transaction_type))

    loads = [float(v) for v in context.local_dependency_load.values()]
    max_bg = max(loads) if loads else config.DEFAULT_BACKGROUND_LOAD
    mean_bg = float(np.mean(loads)) if loads else config.DEFAULT_BACKGROUND_LOAD

    if not any(n.id == transaction.id and n.node_type == "transaction" for n in graph.nodes):
        raise GateError(f"transaction node {transaction.id!r} is missing from the dependency graph")
    path = reachable_services(graph, transaction.id)
    path_max_bg = max(
        (float(context.local_dependency_load.get(s, config.DEFAULT_BACKGROUND_LOAD)) for s in path),
        default=0.0,
    )

    one_hot = [1.0 if transaction.transaction_type == t else 0.0 for t in config.TRANSACTION_TYPES]
    values = [
        z, ratio, recent_count, recent_ratio, same_type,
        max_bg, mean_bg, float(len(path)), criticality_share(path), path_max_bg,
    ] + one_hot
    return np.asarray(values, dtype=np.float64)


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------
def resolve_backend(requested: str | None = None) -> str:
    """Return the backend that will actually be used ("sklearn" or "numpy")."""
    choice = (requested or os.environ.get(config.MODEL_BACKEND_ENV, "auto")).strip().lower()
    if choice not in {"auto", "sklearn", "numpy"}:
        raise ModelError(f"{config.MODEL_BACKEND_ENV} must be auto, sklearn or numpy, got {choice!r}")
    if choice == "numpy":
        return "numpy"
    try:
        import sklearn  # noqa: F401
    except Exception as exc:  # noqa: BLE001 - any import failure means "not available"
        if choice == "sklearn":
            raise ModelError(
                f"scikit-learn was requested but cannot be imported: {exc}",
                recovery_action="set BLACKBOX_MODEL_BACKEND=numpy to use the documented fallback",
            ) from exc
        return "numpy"
    return "sklearn"


def resolve_hybrid(requested: str | None = None) -> bool:
    """Whether XGBoost members join the sklearn risk ensemble (never the numpy backend)."""
    choice = (requested or os.environ.get(config.HYBRID_RISK_ENV, "auto")).strip().lower()
    if choice not in {"auto", "on", "off"}:
        raise ModelError(
            f"{config.HYBRID_RISK_ENV} must be auto, on or off, got {choice!r}"
        )
    if choice == "off":
        return False
    try:
        import xgboost  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        if choice == "on":
            raise ModelError(
                f"xgboost was requested ({config.HYBRID_RISK_ENV}=on) but cannot be imported: {exc}",
                recovery_action="pip install xgboost, or set BLACKBOX_HYBRID_RISK=auto/off",
            ) from exc
        return False
    return True


def _ecdf(sorted_reference: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Fraction of calibration scores <= value, in [0, 1]."""
    return np.searchsorted(sorted_reference, values, side="right") / float(len(sorted_reference))


class _SklearnAnomaly:
    name = config.ANOMALY_MODEL

    def __init__(self, seed: int) -> None:
        from sklearn.ensemble import IsolationForest

        self.model = IsolationForest(
            n_estimators=config.ANOMALY_N_ESTIMATORS, random_state=seed, contamination="auto"
        )

    def fit(self, X: np.ndarray) -> None:
        self.model.fit(X)

    def raw(self, X: np.ndarray) -> np.ndarray:
        return -self.model.score_samples(X)


class _NumpyAnomaly:
    """Robust Mahalanobis distance from the calibration distribution."""

    name = config.ANOMALY_FALLBACK_MODEL

    def __init__(self, seed: int) -> None:  # noqa: ARG002 - deterministic, no randomness
        self.mean = np.zeros(0)
        self.scale = np.ones(0)
        self.precision = np.zeros((0, 0))

    def fit(self, X: np.ndarray) -> None:
        self.mean = X.mean(axis=0)
        self.scale = X.std(axis=0)
        self.scale[self.scale < 1e-9] = 1.0
        Z = (X - self.mean) / self.scale
        cov = np.cov(Z, rowvar=False) + 1e-3 * np.eye(Z.shape[1])
        self.precision = np.linalg.pinv(cov)

    def raw(self, X: np.ndarray) -> np.ndarray:
        Z = (X - self.mean) / self.scale
        return np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", Z, self.precision, Z), 0.0))


class AnomalyModel:
    """Anomaly score A in [0, 1]; larger means more anomalous."""

    def __init__(self, backend: str, seed: int) -> None:
        self.backend = backend
        impl = _SklearnAnomaly if backend == "sklearn" else _NumpyAnomaly
        self._impl = impl(seed)
        self._reference = np.zeros(0)

    @property
    def name(self) -> str:
        return self._impl.name

    def fit(self, X: np.ndarray) -> "AnomalyModel":
        self._impl.fit(X)
        self._reference = np.sort(self._impl.raw(X))
        return self

    def raw(self, X: np.ndarray) -> np.ndarray:
        return self._impl.raw(X)

    def score(self, X: np.ndarray) -> np.ndarray:
        if self._reference.size == 0:
            raise ModelError("anomaly model has not been fitted")
        return np.clip(_ecdf(self._reference, self._impl.raw(X)), 0.0, 1.0)


class _SklearnRisk:
    name = config.UNCERTAINTY_MODEL

    def __init__(self, seed: int) -> None:
        from sklearn.ensemble import RandomForestClassifier

        self.model = RandomForestClassifier(
            n_estimators=config.RISK_N_ESTIMATORS,
            min_samples_leaf=config.RISK_MIN_SAMPLES_LEAF,
            random_state=seed,
            n_jobs=1,
        )

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        self.model.fit(X, y)

    def member_probabilities(self, X: np.ndarray) -> np.ndarray:
        forest = self.model
        if forest.n_classes_ == 1:  # degenerate labels: every member is certain
            p = 1.0 if int(forest.classes_[0]) == 1 else 0.0
            return np.full((len(forest.estimators_), X.shape[0]), p)
        X32 = np.asarray(X, dtype=np.float32)
        rows = []
        for tree in forest.estimators_:
            proba = tree.predict_proba(X32)
            classes = list(tree.classes_)
            if 1 in classes:
                # A tree whose bootstrap saw both classes, or only class 1.
                rows.append(proba[:, classes.index(1)])
            else:
                # Single-class tree that never saw a failure: it predicts P(fail)=0.
                rows.append(np.zeros(X.shape[0]))
        return np.stack(rows)


class _XGBMembers:
    """XGBoost bootstrap members: each fitted model contributes one P(fail)."""

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.models: list[tuple[str, object]] = []

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        from xgboost import XGBClassifier

        y = y.astype(int)
        self.models = []
        if y.min() == y.max():  # single class: nothing to boost
            return
        rng = np.random.default_rng(self.seed)
        X32 = np.asarray(X, dtype=np.float32)
        for i in range(config.RISK_XGB_N_MODELS):
            idx = rng.integers(0, len(X32), size=len(X32))
            yb = y[idx]
            if yb.min() == yb.max():
                self.models.append(("const", float(yb[0])))
                continue
            model = XGBClassifier(
                n_estimators=config.RISK_XGB_N_ESTIMATORS,
                max_depth=config.RISK_XGB_MAX_DEPTH,
                subsample=config.RISK_XGB_SUBSAMPLE,
                colsample_bytree=config.RISK_XGB_COLSAMPLE,
                random_state=self.seed + i + 1,
                n_jobs=1,
                tree_method="hist",
                eval_metric="logloss",
                verbosity=0,
            )
            model.fit(X32[idx], yb)
            self.models.append(("xgb", model))

    def member_probabilities(self, X: np.ndarray) -> np.ndarray:
        if not self.models:
            return np.zeros((0, X.shape[0]))
        X32 = np.asarray(X, dtype=np.float32)
        rows = []
        for kind, model in self.models:
            if kind == "const":
                rows.append(np.full(X.shape[0], float(model)))
            else:
                proba = model.predict_proba(X32)
                rows.append(proba[:, 1] if proba.shape[1] == 2 else proba[:, 0])
        return np.stack(rows)


class _HybridRisk(_SklearnRisk):
    """scikit-learn RandomForest trees + XGBoost bootstrap models, one std."""

    name = config.UNCERTAINTY_HYBRID_MODEL

    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        self.xgb = _XGBMembers(seed)

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        super().fit(X, y)
        self.xgb.fit(X, y)

    def member_probabilities(self, X: np.ndarray) -> np.ndarray:
        rf = super().member_probabilities(X)
        xg = self.xgb.member_probabilities(X)
        return np.vstack([rf, xg]) if xg.size else rf


def _fit_logreg(X: np.ndarray, y: np.ndarray, l2: float, iterations: int) -> np.ndarray:
    """L2-regularised logistic regression by Newton / IRLS (numpy only)."""
    n, d = X.shape
    A = np.hstack([np.ones((n, 1)), X])
    w = np.zeros(d + 1)
    reg = l2 * np.eye(d + 1)
    reg[0, 0] = 0.0
    for _ in range(iterations):
        p = 1.0 / (1.0 + np.exp(-np.clip(A @ w, -30.0, 30.0)))
        weights = np.clip(p * (1.0 - p), 1e-6, None)
        grad = A.T @ (p - y) + reg @ w
        hess = (A.T * weights) @ A + reg + 1e-8 * np.eye(d + 1)
        step = np.linalg.solve(hess, grad)
        w -= step
        if float(np.max(np.abs(step))) < 1e-6:
            break
    return w


class _NumpyRisk:
    """Bagged logistic regression; disagreement is std across bootstrap members."""

    name = config.UNCERTAINTY_FALLBACK_MODEL

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.mean = np.zeros(0)
        self.scale = np.ones(0)
        self.members: list[np.ndarray | float] = []

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        rng = np.random.default_rng(self.seed)
        self.mean = X.mean(axis=0)
        self.scale = X.std(axis=0)
        self.scale[self.scale < 1e-9] = 1.0
        Z = (X - self.mean) / self.scale
        self.members = []
        for _ in range(config.FALLBACK_N_BOOTSTRAPS):
            idx = rng.integers(0, len(Z), size=len(Z))
            yb = y[idx]
            if yb.min() == yb.max():
                self.members.append(float(yb[0]))
            else:
                self.members.append(_fit_logreg(Z[idx], yb, config.FALLBACK_LOGREG_L2, config.FALLBACK_LOGREG_ITERATIONS))

    def member_probabilities(self, X: np.ndarray) -> np.ndarray:
        Z = (X - self.mean) / self.scale
        A = np.hstack([np.ones((Z.shape[0], 1)), Z])
        rows = []
        for member in self.members:
            if isinstance(member, float):
                rows.append(np.full(Z.shape[0], member))
            else:
                rows.append(1.0 / (1.0 + np.exp(-np.clip(A @ member, -30.0, 30.0))))
        return np.stack(rows)


class RiskModel:
    """Failure classifier whose ensemble disagreement defines U in [0, 1]."""

    def __init__(self, backend: str, seed: int, *, hybrid: bool = False) -> None:
        self.backend = backend
        self.hybrid = hybrid and backend == "sklearn"
        if backend == "numpy":
            self._impl: _NumpyRisk | _SklearnRisk = _NumpyRisk(seed)
        elif self.hybrid:
            self._impl = _HybridRisk(seed)
        else:
            self._impl = _SklearnRisk(seed)
        self._fitted = False

    @property
    def name(self) -> str:
        return self._impl.name

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RiskModel":
        self._impl.fit(X, y.astype(int) if self.backend == "sklearn" else y.astype(float))
        self._fitted = True
        return self

    def failure_probability(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise ModelError("risk model has not been fitted")
        return self._impl.member_probabilities(X).mean(axis=0)

    def disagreement(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise ModelError("risk model has not been fitted")
        return self._impl.member_probabilities(X).std(axis=0)

    def uncertainty(self, X: np.ndarray) -> np.ndarray:
        return np.clip(self.disagreement(X) / config.UNCERTAINTY_MAX_STD, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Bundle
# ---------------------------------------------------------------------------
@dataclass
class GateModels:
    """Fitted A and U models plus the provenance of how they were fitted."""

    anomaly: AnomalyModel
    risk: RiskModel
    backend: str
    seed: int
    fitted_on_split: str
    n_fit_samples: int
    n_fit_failures: int
    hybrid_risk: bool = False
    feature_names: tuple[str, ...] = field(default=FEATURE_NAMES)

    @classmethod
    def fit(
        cls,
        X: np.ndarray,
        y: np.ndarray,
        *,
        split: str,
        backend: str | None = None,
        seed: int = config.MODEL_SEED,
        hybrid: bool | None = None,
    ) -> "GateModels":
        if split != "calibration":
            from backend.shared.errors import DataLeakError

            raise DataLeakError(f"gate models may only be fitted on the calibration split, got {split!r}")
        resolved = resolve_backend(backend)
        hybrid_on = bool(hybrid) if hybrid is not None else (resolve_hybrid() if resolved == "sklearn" else False)
        try:
            anomaly = AnomalyModel(resolved, seed).fit(X)
            risk = RiskModel(resolved, seed, hybrid=hybrid_on).fit(X, y)
        except ModelError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ModelError(f"model fitting failed on backend {resolved!r}: {exc}") from exc
        return cls(
            anomaly=anomaly, risk=risk, backend=resolved, seed=seed, fitted_on_split=split,
            n_fit_samples=int(X.shape[0]), n_fit_failures=int(np.sum(y)),
            # Report the ACTUAL hybrid state of the fitted model, not the requested
            # flag: RiskModel coerces hybrid off for the numpy backend.
            hybrid_risk=risk.hybrid,
        )

    def anomaly_scores(self, X: np.ndarray) -> np.ndarray:
        try:
            return self.anomaly.score(X)
        except ModelError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ModelError(f"anomaly inference failed: {exc}") from exc

    def uncertainty_scores(self, X: np.ndarray) -> np.ndarray:
        try:
            return self.risk.uncertainty(X)
        except ModelError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ModelError(f"uncertainty inference failed: {exc}") from exc

    def versions(self) -> dict[str, str]:
        lib = "numpy-" + np.__version__
        if self.backend == "sklearn":
            import sklearn

            lib = "scikit-learn-" + sklearn.__version__
            if self.hybrid_risk:
                import xgboost

                lib = f"{lib} + xgboost-{xgboost.__version__}"
        return {
            "backend": self.backend,
            "hybrid_risk": "on" if self.hybrid_risk else "off",
            "anomaly_model": f"{self.anomaly.name} [{lib}]",
            "risk_model": f"{self.risk.name} [{lib}]",
            "anomaly_normalization": config.ANOMALY_NORMALIZATION,
            "uncertainty_normalization": config.UNCERTAINTY_NORMALIZATION,
            "fitted_on_split": self.fitted_on_split,
        }
