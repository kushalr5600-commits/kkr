"""Dataset storage format, local dependency graph builder and DataRepository.

``DataRepository.load_context(transaction)`` returns the three things the rest
of the pipeline needs for one transaction:

    (Account, DependencyGraph, EventContext)

The graph is built deterministically from the account and the transaction
type. The event context is the stored recent-window/dependency-load snapshot
for dataset transactions, or a quiet default for unknown transaction ids.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.shared import config
from backend.shared.errors import InputError
from backend.shared.schemas import (
    Account,
    DependencyGraph,
    EventContext,
    GraphEdge,
    GraphNode,
    Transaction,
)

SAMPLE_DATASET_PATH = Path(__file__).with_name("sample_dataset.json")

Split = Literal["calibration", "validation", "test", "demo"]


class DatasetRecord(BaseModel):
    transaction: Transaction
    category: str
    split: Split
    context: EventContext
    joint_role: Literal["partner", "trigger"] | None = None
    joint_pair_id: str | None = None
    joint_profile: int | None = None  # which of the five JOINT_PROFILES built this pair


class DatasetMeta(BaseModel):
    seed: int
    size: int
    n_accounts: int
    version: str
    base_time: str
    generator: str = "backend.data.generator.DatasetGenerator.build_dataset"
    category_counts: dict[str, int] = Field(default_factory=dict)
    split_counts: dict[str, int] = Field(default_factory=dict)


class Dataset(BaseModel):
    meta: DatasetMeta
    accounts: list[Account]
    records: list[DatasetRecord]


# ---------------------------------------------------------------------------
# Local dependency graph
# ---------------------------------------------------------------------------
def build_graph(transaction: Transaction, account: Account) -> DependencyGraph:
    """Local dependency graph around one transaction.

    account -> transaction -> head services -> ... (per-type service flow),
    plus transaction -> counterparty accounts (``related_account_ids``).
    """
    profile = config.TRANSACTION_PROFILES.get(transaction.transaction_type)
    if profile is None:
        raise InputError(
            f"unsupported transaction_type {transaction.transaction_type!r}; "
            f"supported: {', '.join(config.TRANSACTION_TYPES)}"
        )

    flow = profile["flow"]
    services = [s for s in config.SERVICES if s in profile["footprint"]]
    targets = {target for _, target in flow}
    heads = [s for s in services if s not in targets]

    nodes = [
        GraphNode(id=account.id, node_type="account"),
        GraphNode(id=transaction.id, node_type="transaction"),
    ]
    nodes += [GraphNode(id=s, node_type=s) for s in services]  # type: ignore[arg-type]

    edges = [GraphEdge(source=account.id, target=transaction.id)]
    edges += [GraphEdge(source=transaction.id, target=h) for h in heads]
    edges += [GraphEdge(source=a, target=b) for a, b in flow]

    seen = {account.id}
    for rid in account.related_account_ids:
        if rid in seen:
            continue
        seen.add(rid)
        nodes.append(GraphNode(id=rid, node_type="account"))
        edges.append(GraphEdge(source=transaction.id, target=rid))

    return DependencyGraph(nodes=nodes, edges=edges)


def quiet_context() -> EventContext:
    """Default context for a transaction the repository has never seen."""
    load = round(config.BACKGROUND_LOAD_MIN + 0.4 * config.BACKGROUND_LOAD_SPAN, 4)
    return EventContext(
        recent_transactions=[],
        local_dependency_load={svc: load for svc in config.SERVICES},
        window_seconds=config.WINDOW_SECONDS,
    )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------
class DataRepository:
    _default: "DataRepository | None" = None

    def __init__(self, dataset: Dataset) -> None:
        self.dataset = dataset
        self._accounts = {a.id: a for a in dataset.accounts}
        self._records = {r.transaction.id: r for r in dataset.records}

    # -- construction --------------------------------------------------------
    @classmethod
    def from_json(cls, path: str | Path) -> "DataRepository":
        return cls(Dataset.model_validate_json(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def default(cls) -> "DataRepository":
        """The checked-in deterministic sample dataset (built on demand if absent)."""
        if cls._default is None:
            if SAMPLE_DATASET_PATH.exists():
                cls._default = cls.from_json(SAMPLE_DATASET_PATH)
            else:  # pragma: no cover - only when the sample file was deleted
                from backend.data.generator import DatasetGenerator

                cls._default = cls(DatasetGenerator.build_dataset())
        return cls._default

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(self.dataset.model_dump_json(), encoding="utf-8")

    # -- lookups -------------------------------------------------------------
    def account(self, account_id: str) -> Account:
        try:
            return self._accounts[account_id]
        except KeyError:
            raise InputError(f"unknown account_id {account_id!r}") from None

    def record(self, transaction_id: str) -> DatasetRecord | None:
        return self._records.get(transaction_id)

    def records_for_split(self, split: str) -> list[DatasetRecord]:
        return [r for r in self.dataset.records if r.split == split]

    def demo_transaction(self) -> Transaction:
        record = self._records.get(config.DEMO_TRANSACTION_ID)
        if record is None:
            raise InputError(f"demo transaction {config.DEMO_TRANSACTION_ID!r} is missing from the dataset")
        return record.transaction

    # -- public contract (Agent manual 1.7) -----------------------------------
    def load_context(self, transaction: Transaction) -> tuple[Account, DependencyGraph, EventContext]:
        account = self.account(transaction.account_id)
        graph = build_graph(transaction, account)
        record = self._records.get(transaction.id)
        context = record.context if record is not None else quiet_context()
        return account, graph, context.model_copy(deep=True)
