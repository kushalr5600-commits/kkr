"""BLACKBOX frozen configuration.

Everything that the manuals call "frozen" lives here: gate weights/threshold,
signal normalization, scenario identifiers, failure thresholds, review margin,
model definitions and dataset parameters.

Rules (Agent manual v4, sections 1.8-1.11 and Part 8):
  * No agent changes a value here without a synchronized team decision.
  * Everything marked FROZEN-BEFORE-LOCKED-TEST must not change once the
    locked test evaluation has been run.
  * The weights and threshold are MVP parameters, not claimed optimal.
"""
from __future__ import annotations

VERSION = "0.1.0-prebuild"
PRODUCT_NAME = "BLACKBOX"
# Version of the frozen ImpactGate decision policy (weights + threshold +
# decision semantics). Bumped only with an explicit human team decision.
POLICY_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Impact Gate  (FROZEN)
#   I(T) = 0.30*M + 0.30*D + 0.25*A + 0.15*U      threshold = 0.60
# ---------------------------------------------------------------------------
IMPACT_WEIGHTS = {
    "magnitude": 0.30,
    "dependency": 0.30,
    "anomaly": 0.25,
    "uncertainty": 0.15,
}
IMPACT_THRESHOLD = 0.60
assert abs(sum(IMPACT_WEIGHTS.values()) - 1.0) < 1e-12, "gate weights must sum to 1"

# --- Signal normalization (FROZEN-BEFORE-LOCKED-TEST) ----------------------
# M: z = (amount - account_avg) / account_std ; M = clip(max(z, 0) / SAT, 0, 1)
MAGNITUDE_Z_SATURATION = 4.0
# D: criticality-weighted share of services reachable from the transaction
#    node, blended with the number of counterparty accounts reachable.
DEPENDENCY_SERVICE_WEIGHT = 0.8
DEPENDENCY_ACCOUNT_WEIGHT = 0.2
DEPENDENCY_ACCOUNT_SATURATION = 5  # counterparties at which the account part saturates
# A: IsolationForest (or numpy fallback) raw score -> empirical CDF fitted on
#    the CALIBRATION split only. Larger = more anomalous, range [0, 1].
ANOMALY_MODEL = "IsolationForest"
ANOMALY_FALLBACK_MODEL = "RobustMahalanobis"
ANOMALY_NORMALIZATION = "empirical_cdf_on_calibration_split"
# U: predictive disagreement of a bagged failure classifier.
#    Each ensemble member outputs P(fail); U = std across members / 0.5.
#    0.5 is the theoretical maximum std of values in [0, 1], so this
#    normalization needs no fitting and cannot leak test information.
UNCERTAINTY_MODEL = "RandomForestClassifier (std of per-tree P(fail))"
UNCERTAINTY_FALLBACK_MODEL = "BaggedLogisticRegression (std of member P(fail))"
UNCERTAINTY_NORMALIZATION = "std_across_members / 0.5, clipped to [0, 1]"
UNCERTAINTY_MAX_STD = 0.5

# --- Model hyper-parameters (FROZEN-BEFORE-LOCKED-TEST) --------------------
MODEL_SEED = 42
ANOMALY_N_ESTIMATORS = 100
RISK_N_ESTIMATORS = 100
RISK_MIN_SAMPLES_LEAF = 3
FALLBACK_N_BOOTSTRAPS = 25
FALLBACK_LOGREG_ITERATIONS = 25
FALLBACK_LOGREG_L2 = 1.0
MODEL_BACKEND_ENV = "BLACKBOX_MODEL_BACKEND"  # auto | sklearn | numpy

# Hybrid risk ensemble (two open-source frameworks, one uncertainty estimate):
# when the sklearn backend is active and xgboost imports, U is the std across
# the RandomForest trees PLUS XGBoost models fitted on bootstrap resamples.
# BLACKBOX_HYBRID_RISK = auto | on | off.  "auto" activates iff xgboost
# imports.  "on" without xgboost is a hard error (never silently degrade).
# The numpy backend never uses xgboost: its fallback stays dependency-free.
UNCERTAINTY_HYBRID_MODEL = "HybridTreeEnsemble (RF trees + XGBoost models)"
HYBRID_RISK_ENV = "BLACKBOX_HYBRID_RISK"  # auto | on | off
RISK_XGB_N_MODELS = 8
RISK_XGB_N_ESTIMATORS = 64
RISK_XGB_MAX_DEPTH = 4
RISK_XGB_SUBSAMPLE = 0.8
RISK_XGB_COLSAMPLE = 0.8

# LLM narrative (advisory ONLY; never changes scores or decisions).
# Showcase: scripts/llm_service.py runs IBM Granite behind BLACKBOX_LLM_URL.
LLM_NARRATIVE_ENABLED = True
LLM_URL_ENV = "BLACKBOX_LLM_URL"      # POST {"prompt"} -> {"text"}
LLM_MODEL_ENV = "BLACKBOX_LLM_MODEL"  # local transformers model id/path
LLM_TIMEOUT_S = 120.0  # CPU Granite on s390x measures ~50s/narrative; 20s starved it
LLM_MAX_NEW_TOKENS = 128

# Interaction-aware ranking (research candidate, NOT the frozen gate).
# When enabled, uses window/load pressure features to improve failure recall.
# ACTIVATED 2026-10-16 by explicit human decision (documented in docs/STATUS.md
# and DISCLOSURES.md section 2); it is now the production ranking policy.
# The frozen reference formula (IMPACT_WEIGHTS) is unchanged and still used for
# the frozen-mode ablation. BLACKBOX_INTERACTION = on | off | auto overrides
# this default at runtime (off reproduces the frozen gate exactly).
INTERACTION_AWARE_ENV = "BLACKBOX_INTERACTION"  # on | off | auto (auto = default below)
INTERACTION_AWARE_ENABLED = True
INTERACTION_AWARE_WEIGHTS = {"anomaly": 0.45, "window_pressure": 0.30, "dependency": 0.15, "load_pressure": 0.10}

# ---------------------------------------------------------------------------
# Graph / enterprise world
# ---------------------------------------------------------------------------
SERVICES = (
    "payment_gateway",
    "fraud_engine",
    "risk_model",
    "ledger",
    "settlement",
    "notification",
    "reporting",
)
# Frozen node-type vocabulary (must equal the Literal in schemas.GraphNode).
NODE_TYPES = ("account", "transaction") + SERVICES

TRANSACTION_TYPES = (
    "card_payment",
    "wire_transfer",
    "ach_batch",
    "refund",
    "internal_transfer",
)

# Business criticality of each service (used by D).
CRITICALITY = {
    "payment_gateway": 2.0,
    "fraud_engine": 2.0,
    "risk_model": 2.0,
    "ledger": 3.0,
    "settlement": 3.0,
    "notification": 1.0,
    "reporting": 1.0,
}

# Capacity of each service in abstract load units.
CAPACITY = {
    "payment_gateway": 10.0,
    "fraud_engine": 8.0,
    "risk_model": 6.0,
    "ledger": 12.0,
    "settlement": 10.0,
    "notification": 15.0,
    "reporting": 20.0,
}

# Per-transaction-type load footprint (units at amount factor 1.0) and the
# service flow the transaction traverses (edges are source -> target).
TRANSACTION_PROFILES = {
    "card_payment": {
        "footprint": {
            "payment_gateway": 0.8, "fraud_engine": 0.7, "risk_model": 0.4,
            "ledger": 0.6, "notification": 0.3,
        },
        "flow": [
            ("payment_gateway", "fraud_engine"),
            ("fraud_engine", "risk_model"),
            ("risk_model", "ledger"),
            ("ledger", "notification"),
        ],
    },
    "wire_transfer": {
        "footprint": {
            "payment_gateway": 0.5, "fraud_engine": 0.9, "risk_model": 0.9,
            "ledger": 0.9, "settlement": 1.2, "reporting": 0.4,
            "notification": 0.3,
        },
        "flow": [
            ("payment_gateway", "fraud_engine"),
            ("fraud_engine", "risk_model"),
            ("risk_model", "ledger"),
            ("ledger", "settlement"),
            ("settlement", "reporting"),
            ("settlement", "notification"),
        ],
    },
    "ach_batch": {
        "footprint": {
            "payment_gateway": 0.5, "ledger": 1.0, "settlement": 1.3,
            "reporting": 0.6,
        },
        "flow": [
            ("payment_gateway", "ledger"),
            ("ledger", "settlement"),
            ("settlement", "reporting"),
        ],
    },
    "refund": {
        "footprint": {
            "fraud_engine": 0.4, "risk_model": 0.3, "ledger": 0.7,
            "notification": 0.3,
        },
        "flow": [
            ("fraud_engine", "risk_model"),
            ("risk_model", "ledger"),
            ("ledger", "notification"),
        ],
    },
    "internal_transfer": {
        "footprint": {"ledger": 0.6, "reporting": 0.3, "notification": 0.2},
        "flow": [("ledger", "reporting"), ("ledger", "notification")],
    },
}

# Amount -> load factor:  factor = BASE + SLOPE * min(amount / REF, CAP)
AMOUNT_LOAD_REF = 2000.0
AMOUNT_LOAD_BASE = 0.7
AMOUNT_LOAD_SLOPE = 0.3
AMOUNT_LOAD_CAP = 5.0

# Background utilization assumed for a path service that the context does not
# report. Surfaced in ForkResult metrics + certificate evidence when used.
DEFAULT_BACKGROUND_LOAD = 0.15

WINDOW_SECONDS = 60

# Normal-state background utilization range (data generator)
BACKGROUND_LOAD_MIN = 0.04
BACKGROUND_LOAD_SPAN = 0.09

# ---------------------------------------------------------------------------
# Simulation  (FROZEN-BEFORE-LOCKED-TEST)
# ---------------------------------------------------------------------------
SCENARIOS = [
    "3x_volume",
    "fraud_spike",
    "service_latency",
]

# Stress intensity applied by CrashTestEngine.attack for each scenario.
SCENARIO_DEFAULT_INTENSITY = {
    "3x_volume": 3.0,
    "fraud_spike": 3.0,
    "service_latency": 3.0,
}

# Failure predicates
UTILIZATION_FAILURE_LIMIT = 1.0      # 3x_volume, fraud_spike: any path service > limit
LATENCY_BUDGET_MS = 1100.0           # service_latency: end-to-end path latency > budget
BASE_LATENCY_MS = {
    "payment_gateway": 40.0,
    "fraud_engine": 60.0,
    "risk_model": 80.0,
    "ledger": 50.0,
    "settlement": 120.0,
    "notification": 30.0,
    "reporting": 90.0,
}
# Latency of a service grows with its utilization: lat = base * (1 + util)
LATENCY_UTILIZATION_COEFF = 1.0
LATENCY_AFFECTED_SERVICES = ("payment_gateway", "ledger", "settlement")

FRAUD_AFFECTED_SERVICES = ("fraud_engine", "risk_model")
FRAUD_CASCADE_SERVICES = ("ledger", "notification", "settlement")
FRAUD_CASCADE_COEFF = 0.5            # downstream load factor = 1 + coeff*(m-1)

# Fragility search: grid search on intensity, bounded and resolution-honest.
MIN_INTENSITY = 1.0
MAX_INTENSITY = 10.0
FRAGILITY_RESOLUTION = 0.05
FRAGILITY_UNIT = "x_intensity"
# When the decision never fails inside the bound, breaking_threshold is a
# LOWER bound (it survives through MAX_INTENSITY) and the unit says so.
FRAGILITY_UNIT_LOWER_BOUND = "x_intensity_lower_bound"

# ---------------------------------------------------------------------------
# Certificate policy  (FROZEN-BEFORE-LOCKED-TEST)
# ---------------------------------------------------------------------------
# no failure + (breaking_threshold / tested_intensity - 1) < REVIEW_MARGIN -> REVIEW
REVIEW_MARGIN = 0.25

# ---------------------------------------------------------------------------
# Dataset / experiment
# ---------------------------------------------------------------------------
DATASET_SEED = 42
DATASET_SIZE = 5000
DATASET_N_ACCOUNTS = 150
SPLIT_FRACTIONS = {"calibration": 0.50, "validation": 0.20, "test": 0.30}
DATASET_BASE_TIME = "2026-03-02T09:00:00+00:00"

# Share of the dataset by category. Remainder is "normal".
CATEGORY_MIX = {
    "unusual_but_harmless": 0.12,
    "obvious_single_signal_danger": 0.02,
    "high_value_low_blast_radius": 0.05,
    "low_value_high_blast_radius": 0.02,
    "correlated_anomalies": 0.02,
    "dependency_chain_failures": 0.02,
    "jointly_dangerous": 0.03,   # counts both halves of each pair
}
CATEGORIES = ("normal",) + tuple(CATEGORY_MIX)

EXPERIMENT_BUDGETS = (0.005, 0.01, 0.02, 0.05, 0.10, 1.00)
EXPERIMENT_POLICIES = ("random", "amount_only", "anomaly_only", "BLACKBOX")
EXPERIMENT_RANDOM_DRAWS = 200

# ---------------------------------------------------------------------------
# Deterministic demo  (Agent manual 1.14)
# ---------------------------------------------------------------------------
DEMO_TRANSACTION_ID = "TX-DEMO-0001"
DEMO_SEED = 42
DEMO_SCENARIO = "3x_volume"   # headline scenario highlighted in the UI

# ---------------------------------------------------------------------------
# Dataset Studio / Challenge Lab limits (runtime config, not gate policy)
# ---------------------------------------------------------------------------
DATASET_MAX_BYTES = 5 * 1024 * 1024          # 5 MiB per upload
DATASET_MAX_ROWS = 50_000
DATASET_MAX_PREVIEW_ROWS = 200
DATASET_EVAL_MAX_ROWS = 5_000
DATASET_STRESS_SAMPLE_MAX = 25
