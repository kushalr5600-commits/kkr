"""Small pure helpers shared by P1/P2/P3 so the three agents agree on what the
"local window" and the "local dependency path" mean.

These implement no decision logic. They only answer two structural questions:
  * which recent transactions belong to this transaction's window?
  * which nodes are reachable downstream of the transaction node?
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from backend.shared.config import SERVICES
from backend.shared.schemas import DependencyGraph, EventContext, Transaction


def as_utc(ts: datetime) -> datetime:
    """Treat naive timestamps as UTC so naive/aware values compare safely."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def recent_in_window(transaction: Transaction, context: EventContext) -> list[Transaction]:
    """Recent transactions that precede ``transaction`` by at most
    ``context.window_seconds`` (the transaction itself is excluded)."""
    t0 = as_utc(transaction.timestamp)
    window = context.window_seconds
    selected = []
    for other in context.recent_transactions:
        if other.id == transaction.id:
            continue
        delta = (t0 - as_utc(other.timestamp)).total_seconds()
        if 0 <= delta <= window:
            selected.append(other)
    return selected


def reachable_nodes(graph: DependencyGraph, source_id: str) -> list[str]:
    """Node ids reachable from ``source_id`` following edges source -> target
    (the source itself is excluded). Deterministic breadth-first order."""
    adjacency: dict[str, list[str]] = {}
    for edge in graph.edges:
        adjacency.setdefault(edge.source, []).append(edge.target)
    seen = {source_id}
    order: list[str] = []
    queue = deque([source_id])
    while queue:
        current = queue.popleft()
        for nxt in adjacency.get(current, []):
            if nxt not in seen:
                seen.add(nxt)
                order.append(nxt)
                queue.append(nxt)
    return order


def reachable_services(graph: DependencyGraph, source_id: str) -> list[str]:
    """Service node ids reachable from ``source_id`` in canonical SERVICES order."""
    types = {node.id: node.node_type for node in graph.nodes}
    reach = {n for n in reachable_nodes(graph, source_id) if types.get(n) in SERVICES}
    return [s for s in SERVICES if s in reach]


def reachable_accounts(graph: DependencyGraph, source_id: str) -> list[str]:
    """Account node ids reachable downstream of ``source_id``."""
    types = {node.id: node.node_type for node in graph.nodes}
    return [n for n in reachable_nodes(graph, source_id) if types.get(n) == "account"]
