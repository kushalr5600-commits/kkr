"""Reality Forks: turn a transaction's local state into a baseline fork.

``RealityForkGenerator.generate_baseline`` builds the *nominal* local state
(background load + the transaction + its recent-window neighbours) restricted
to the services downstream of the transaction. ``CrashTestEngine.attack``
then derives the "normal" and the "stress" outcomes from that one baseline.
The baseline object is an internal simulation object, not a public schema.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from backend.shared import config
from backend.shared.context_utils import recent_in_window, reachable_services
from backend.shared.errors import SimulationError
from backend.shared.schemas import DependencyGraph, EventContext, Transaction
from backend.simulation import physics


@dataclass(frozen=True)
class BaselineFork:
    """Nominal local state of one transaction (internal simulation object)."""

    transaction_id: str
    transaction_type: str
    amount: float
    path_services: tuple[str, ...]
    utilization: dict[str, float]          # nominal utilization per path service
    background: dict[str, float]           # background utilization per path service
    recent_count: int                      # recent-window neighbours included
    defaulted_services: tuple[str, ...] = field(default_factory=tuple)


class RealityForkGenerator:
    @staticmethod
    def generate_baseline(
        transaction: Transaction,
        graph: DependencyGraph,
        context: EventContext,
    ) -> BaselineFork:
        if not any(n.id == transaction.id and n.node_type == "transaction" for n in graph.nodes):
            raise SimulationError(
                f"transaction node {transaction.id!r} is missing from the dependency graph"
            )
        path = reachable_services(graph, transaction.id)
        if not path:
            raise SimulationError(
                f"transaction {transaction.id!r} has no downstream services in its local graph"
            )

        background: dict[str, float] = {}
        defaulted: list[str] = []
        for svc in path:
            if svc in context.local_dependency_load:
                value = float(context.local_dependency_load[svc])
                if not math.isfinite(value) or value < 0:
                    raise SimulationError(f"invalid background load for {svc!r}: {value!r}")
                background[svc] = value
            else:
                background[svc] = config.DEFAULT_BACKGROUND_LOAD
                defaulted.append(svc)

        recents = recent_in_window(transaction, context)
        transactions = [(transaction.transaction_type, transaction.amount)]
        transactions += [(r.transaction_type, r.amount) for r in recents]
        utilization = physics.nominal_utilization(path, background, transactions)

        return BaselineFork(
            transaction_id=transaction.id,
            transaction_type=transaction.transaction_type,
            amount=transaction.amount,
            path_services=tuple(path),
            utilization=utilization,
            background=background,
            recent_count=len(recents),
            defaulted_services=tuple(defaulted),
        )
