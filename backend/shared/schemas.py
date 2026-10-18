"""BLACKBOX shared schema contract (Agent manual v4, section 1.6).

Model names and field names are FROZEN. Pydantic ``Field`` constraints on
``Transaction`` implement the Type A input-validation rules (missing
transaction id, invalid amount, invalid timestamp must become an HTTP
validation error and never reach business logic). No field was added, removed
or renamed relative to the manual.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    amount: float = Field(gt=0, allow_inf_nan=False)
    timestamp: datetime
    transaction_type: str = Field(min_length=1)


class Account(BaseModel):
    id: str
    historical_avg_amount: float
    historical_std_amount: float
    related_account_ids: list[str] = Field(default_factory=list)


class EventContext(BaseModel):
    # Cap the window so a client-supplied context cannot amplify compute.
    recent_transactions: list[Transaction] = Field(default_factory=list, max_length=100)
    # Loads must be finite: a NaN/inf here flows into the gate and (previously)
    # could yield a silent "safe". Enforced at the boundary as defense-in-depth.
    local_dependency_load: dict[str, Annotated[float, Field(allow_inf_nan=False)]] = Field(
        default_factory=dict
    )
    window_seconds: int = Field(default=60, gt=0)


class GraphNode(BaseModel):
    id: str
    node_type: Literal[
        "account", "transaction", "fraud_engine", "ledger",
        "payment_gateway", "risk_model", "notification",
        "settlement", "reporting",
    ]


class GraphEdge(BaseModel):
    source: str
    target: str


class DependencyGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ImpactSignals(BaseModel):
    magnitude: float = Field(allow_inf_nan=False)
    dependency: float = Field(allow_inf_nan=False)
    anomaly: float = Field(allow_inf_nan=False)
    uncertainty: float = Field(allow_inf_nan=False)


class ImpactScore(BaseModel):
    transaction_id: str
    signals: ImpactSignals
    # A non-finite score must never be representable: it would serialize as the
    # bare ``NaN`` token and, downstream, ``nan >= threshold`` is False (silent skip).
    score: float = Field(allow_inf_nan=False)
    gate_decision: bool


class ForkResult(BaseModel):
    fork_name: Literal["normal", "stress"]
    scenario: str
    survived: bool
    metrics: dict[str, float]


class FragilityResult(BaseModel):
    scenario: str
    breaking_threshold: float
    unit: str
    resolution: float


class RuntimeMetadata(BaseModel):
    runtime: str
    architecture: str
    model_versions: dict[str, str] = Field(default_factory=dict)
    random_seed: int | None = None
    git_revision: str | None = None


class DecisionCertificate(BaseModel):
    certificate_id: str
    trace_id: str
    status: Literal["NO_SIMULATION", "SIMULATED", "REVIEW"]
    transaction_id: str
    decision_description: str
    impact_score: ImpactScore
    forks_tested: list[ForkResult]
    fragility: list[FragilityResult]
    recommended_action: Literal[
        "ALLOW_NORMAL_PATH", "REVIEW", "BLOCK_OR_HOLD"
    ]
    evidence: list[str]
    runtime: RuntimeMetadata
