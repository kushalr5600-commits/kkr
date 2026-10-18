"""Deterministic builders for the eight required behaviour categories.

Every builder receives a seeded ``numpy`` generator and returns a list of
``DatasetRecord`` (one transaction plus the context it arrives in; the
jointly-dangerous builder returns a *pair*).

The jointly dangerous category is NOT left to chance (Agent manual P1):
``build_jointly_dangerous`` rejection-samples until

    transaction A alone                -> survives all three scenarios
    transaction B alone                -> survives all three scenarios
    A and B in the same local window   -> fails at least one scenario

using the same physics the simulator uses (``backend.simulation.physics``).
Whether a *gate* can see such a case is a separate question that the
experiment measures; the builders only guarantee the ground-truth structure.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

import numpy as np

from backend.data.repository import DatasetRecord, build_graph
from backend.shared import config
from backend.shared.context_utils import reachable_services
from backend.shared.errors import InputError
from backend.shared.schemas import Account, EventContext, Transaction
from backend.simulation import physics

Builder = Callable[[np.random.Generator, list[Account], int, datetime], list[DatasetRecord]]

NORMAL_TYPE_WEIGHTS = {
    "card_payment": 0.36,
    "internal_transfer": 0.20,
    "refund": 0.10,
    "ach_batch": 0.12,
    "wire_transfer": 0.22,
}
# Ordinary background traffic in a normal window is mostly light transactions;
# heavy transfers bunching up is what the dangerous categories model.
NORMAL_RECENT_TYPE_WEIGHTS = {
    "card_payment": 0.45,
    "internal_transfer": 0.30,
    "refund": 0.15,
    "ach_batch": 0.05,
    "wire_transfer": 0.05,
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _pick_account(rng: np.random.Generator, accounts: list[Account]) -> Account:
    return accounts[int(rng.integers(len(accounts)))]


def _pick_type(rng: np.random.Generator, weights: dict[str, float]) -> str:
    names = list(weights)
    probs = np.array([weights[n] for n in names], dtype=float)
    return str(names[int(rng.choice(len(names), p=probs / probs.sum()))])


def normal_amount(rng: np.random.Generator, account: Account) -> float:
    """Amount drawn around the account's own baseline."""
    cv = account.historical_std_amount / account.historical_avg_amount
    value = account.historical_avg_amount * float(np.exp(rng.normal(-0.5 * cv * cv, cv)))
    return round(max(5.0, value), 2)


def multiple_amount(rng: np.random.Generator, account: Account, low: float, high: float) -> float:
    return round(max(5.0, account.historical_avg_amount * float(rng.uniform(low, high))), 2)


def background(rng: np.random.Generator, low: float | None = None, span: float | None = None) -> dict[str, float]:
    lo = config.BACKGROUND_LOAD_MIN if low is None else low
    sp = config.BACKGROUND_LOAD_SPAN if span is None else span
    return {svc: round(lo + sp * float(rng.beta(2, 3)), 4) for svc in config.SERVICES}


def make_transaction(tx_id: str, account: Account, amount: float, ts: datetime, ttype: str) -> Transaction:
    return Transaction(
        id=tx_id, account_id=account.id, amount=amount, timestamp=ts, transaction_type=ttype
    )


def normal_transaction(rng: np.random.Generator, account: Account, tx_id: str, ts: datetime, ttype: str | None = None) -> Transaction:
    """One ordinary transaction (shared by ``generate_transactions``)."""
    return make_transaction(
        tx_id, account, normal_amount(rng, account), ts,
        ttype or _pick_type(rng, NORMAL_TYPE_WEIGHTS),
    )


def _recents(
    rng: np.random.Generator,
    accounts: list[Account],
    tx_id: str,
    t0: datetime,
    n: int,
    *,
    type_weights: dict[str, float] | None = None,
    fixed_type: str | None = None,
    pool: list[Account] | None = None,
    amount_range: tuple[float, float] | None = None,
) -> list[Transaction]:
    out: list[Transaction] = []
    for k in range(n):
        acct = _pick_account(rng, pool or accounts)
        ttype = fixed_type or _pick_type(rng, type_weights or NORMAL_TYPE_WEIGHTS)
        amount = multiple_amount(rng, acct, *amount_range) if amount_range else normal_amount(rng, acct)
        ts = t0 - timedelta(seconds=round(float(rng.uniform(2, 55)), 1))
        out.append(make_transaction(f"{tx_id}-R{k + 1}", acct, amount, ts, ttype))
    return out


def _context(recents: list[Transaction], load: dict[str, float]) -> EventContext:
    return EventContext(
        recent_transactions=recents,
        local_dependency_load=load,
        window_seconds=config.WINDOW_SECONDS,
    )


def _record(tx: Transaction, category: str, context: EventContext, **extra) -> DatasetRecord:
    return DatasetRecord(transaction=tx, category=category, split="calibration", context=context, **extra)


def _tx_id(slot: int) -> str:
    return f"TX-{slot:05d}"


def _footprint_services(ttype: str) -> list[str]:
    return [s for s in config.SERVICES if s in config.TRANSACTION_PROFILES[ttype]["footprint"]]


def _index_accounts(accounts: list[Account]) -> dict[str, Account]:
    return {a.id: a for a in accounts}


# ---------------------------------------------------------------------------
# 1. normal
# ---------------------------------------------------------------------------
def build_normal(rng, accounts, slot, t0):
    tx_id = _tx_id(slot)
    acct = _pick_account(rng, accounts)
    tx = normal_transaction(rng, acct, tx_id, t0)
    n_recent = int(rng.choice([0, 1, 2], p=[0.55, 0.33, 0.12]))
    recents = _recents(rng, accounts, tx_id, t0, n_recent, type_weights=NORMAL_RECENT_TYPE_WEIGHTS)
    return [_record(tx, "normal", _context(recents, background(rng)))]


# ---------------------------------------------------------------------------
# 2. unusual but harmless: large-ish amounts on light services, busier window
# ---------------------------------------------------------------------------
def build_unusual_but_harmless(rng, accounts, slot, t0):
    tx_id = _tx_id(slot)
    acct = _pick_account(rng, accounts)
    ttype = _pick_type(rng, {"card_payment": 0.4, "refund": 0.3, "internal_transfer": 0.3})
    tx = make_transaction(tx_id, acct, multiple_amount(rng, acct, 2.0, 3.5), t0, ttype)
    n_recent = int(rng.choice([1, 2, 3], p=[0.5, 0.35, 0.15]))
    light = {"card_payment": 0.4, "refund": 0.3, "internal_transfer": 0.3}
    recents = _recents(rng, accounts, tx_id, t0, n_recent, type_weights=light)
    return [_record(tx, "unusual_but_harmless", _context(recents, background(rng, 0.04, 0.07)))]


# ---------------------------------------------------------------------------
# 3. obvious single-signal danger: ONE signal is extreme
# ---------------------------------------------------------------------------
def build_obvious_single_signal_danger(rng, accounts, slot, t0):
    tx_id = _tx_id(slot)
    acct = _pick_account(rng, accounts)
    if rng.random() < 0.5:
        # extreme amount on a heavy service flow
        ttype = _pick_type(rng, {"wire_transfer": 0.6, "ach_batch": 0.4})
        tx = make_transaction(tx_id, acct, multiple_amount(rng, acct, 8.0, 20.0), t0, ttype)
        load = background(rng, 0.07, 0.06)
    else:
        # extreme background load on one downstream service
        ttype = _pick_type(rng, {"wire_transfer": 0.4, "ach_batch": 0.3, "card_payment": 0.3})
        tx = normal_transaction(rng, acct, tx_id, t0, ttype)
        load = background(rng)
        victim = _footprint_services(ttype)[int(rng.integers(len(_footprint_services(ttype))))]
        load[victim] = round(float(rng.uniform(0.55, 0.9)), 4)
    return [_record(tx, "obvious_single_signal_danger", _context([], load))]


# ---------------------------------------------------------------------------
# 4. high value / low blast radius
# ---------------------------------------------------------------------------
def build_high_value_low_blast_radius(rng, accounts, slot, t0):
    tx_id = _tx_id(slot)
    acct = _pick_account(rng, accounts)
    tx = make_transaction(tx_id, acct, multiple_amount(rng, acct, 4.0, 8.0), t0, "internal_transfer")
    n_recent = int(rng.choice([0, 1], p=[0.7, 0.3]))
    recents = _recents(rng, accounts, tx_id, t0, n_recent, fixed_type="internal_transfer")
    return [_record(tx, "high_value_low_blast_radius", _context(recents, background(rng)))]


# ---------------------------------------------------------------------------
# 5. low value / high blast radius
# ---------------------------------------------------------------------------
def build_low_value_high_blast_radius(rng, accounts, slot, t0):
    tx_id = _tx_id(slot)
    acct = _pick_account(rng, accounts)
    ttype = _pick_type(rng, {"wire_transfer": 0.6, "ach_batch": 0.4})
    tx = make_transaction(tx_id, acct, multiple_amount(rng, acct, 0.1, 0.6), t0, ttype)
    load = background(rng)
    for svc in ("ledger", "settlement"):
        load[svc] = round(float(rng.uniform(0.24, 0.40)), 4)
    return [_record(tx, "low_value_high_blast_radius", _context([], load))]


# ---------------------------------------------------------------------------
# 6. correlated anomalies: a burst of similar elevated transactions
# ---------------------------------------------------------------------------
def build_correlated_anomalies(rng, accounts, slot, t0):
    tx_id = _tx_id(slot)
    by_id = _index_accounts(accounts)
    acct = _pick_account(rng, accounts)
    ttype = _pick_type(rng, {"wire_transfer": 0.4, "ach_batch": 0.2, "card_payment": 0.4})
    tx = make_transaction(tx_id, acct, multiple_amount(rng, acct, 1.3, 2.5), t0, ttype)
    pool = [acct] + [by_id[r] for r in acct.related_account_ids if r in by_id]
    n_recent = int(rng.integers(3, 6))
    recents = _recents(rng, accounts, tx_id, t0, n_recent, fixed_type=ttype, pool=pool, amount_range=(1.3, 2.5))
    return [_record(tx, "correlated_anomalies", _context(recents, background(rng)))]


# ---------------------------------------------------------------------------
# 7. dependency-chain failures: a chain of moderately loaded services
# ---------------------------------------------------------------------------
def build_dependency_chain_failures(rng, accounts, slot, t0):
    tx_id = _tx_id(slot)
    acct = _pick_account(rng, accounts)
    ttype = _pick_type(rng, {"wire_transfer": 0.5, "ach_batch": 0.25, "card_payment": 0.25})
    tx = make_transaction(tx_id, acct, multiple_amount(rng, acct, 0.7, 1.3), t0, ttype)
    services = _footprint_services(ttype)
    length = int(min(len(services), rng.integers(2, 5)))
    start = int(rng.integers(0, len(services) - length + 1))
    load = background(rng)
    for svc in services[start:start + length]:
        load[svc] = round(float(rng.uniform(0.24, 0.34)), 4)
    n_recent = int(rng.choice([0, 1], p=[0.6, 0.4]))
    recents = _recents(rng, accounts, tx_id, t0, n_recent)
    return [_record(tx, "dependency_chain_failures", _context(recents, load))]


# ---------------------------------------------------------------------------
# 8. jointly dangerous co-occurrence (deliberately constructed pairs)
# ---------------------------------------------------------------------------
def _fails_any_scenario(path: list[str], load: dict[str, float], txs: list[tuple[str, float]]) -> bool:
    util = physics.nominal_utilization(path, load, txs)
    for scenario in config.SCENARIOS:
        survived, _ = physics.evaluate(scenario, util, config.SCENARIO_DEFAULT_INTENSITY[scenario])
        if not survived:
            return True
    return False


# Five distinct, individually plausible profiles (Agent manual v4, P1). Each is
# (type of A, type of B, amount-multiple range of A, amount-multiple range of B),
# amounts as multiples of the account's own historical average.
JOINT_PROFILES: tuple[tuple[str, str, tuple[float, float], tuple[float, float]], ...] = (
    ("wire_transfer", "wire_transfer", (0.9, 1.3), (0.9, 1.3)),   # 0 modest wire pair
    ("wire_transfer", "wire_transfer", (1.4, 1.8), (1.4, 1.8)),   # 1 larger wire pair
    ("ach_batch", "ach_batch", (0.9, 1.3), (0.9, 1.3)),           # 2 modest ACH pair
    ("ach_batch", "ach_batch", (1.4, 1.8), (1.4, 1.8)),           # 3 larger ACH pair
    ("wire_transfer", "ach_batch", (0.9, 1.5), (0.9, 1.5)),       # 4 mixed wire -> ACH pair
)


def build_jointly_dangerous(
    rng,
    accounts,
    slot,
    t0,
    *,
    partner_id: str | None = None,
    trigger_id: str | None = None,
    profile: int | None = None,
    min_avg: float = 1500.0,
    max_attempts: int = 5000,
) -> list[DatasetRecord]:
    """Return ``[partner A, trigger B]`` built from one of the five profiles.

    ``profile`` defaults to ``slot % 5`` so every profile is represented.
    A arrives first with an empty recent window; B arrives with A in its
    recent window (8-45 s earlier, inside the 60 s window). Each is
    individually survivable under every scenario, but A + B in the same local
    window fails at least one scenario.
    """
    index = (slot if profile is None else profile) % len(JOINT_PROFILES)
    type_a, type_b, range_a, range_b = JOINT_PROFILES[index]

    by_id = _index_accounts(accounts)
    pool = [a for a in accounts if min_avg <= a.historical_avg_amount <= 6000.0] or accounts
    base = _tx_id(slot)
    a_id = partner_id or f"{base}-A"
    b_id = trigger_id or f"{base}-B"
    pair_id = f"PAIR-{slot:05d}"

    for _ in range(max_attempts):
        acct_b = pool[int(rng.integers(len(pool)))]
        related = [by_id[r] for r in acct_b.related_account_ids if r in by_id and r != acct_b.id]
        acct_a = acct_b if (not related or rng.random() < 0.5) else related[int(rng.integers(len(related)))]
        amount_a = multiple_amount(rng, acct_a, *range_a)
        amount_b = multiple_amount(rng, acct_b, *range_b)
        load = background(rng, 0.06, 0.08)

        tx_a = make_transaction(a_id, acct_a, amount_a, t0 - timedelta(seconds=round(float(rng.uniform(8, 45)), 1)), type_a)
        tx_b = make_transaction(b_id, acct_b, amount_b, t0, type_b)

        path = reachable_services(build_graph(tx_b, acct_b), tx_b.id)
        path_a = reachable_services(build_graph(tx_a, acct_a), tx_a.id)   # A is judged on ITS OWN path
        a_only = _fails_any_scenario(path_a, load, [(type_a, amount_a)])
        b_only = _fails_any_scenario(path, load, [(type_b, amount_b)])
        together = _fails_any_scenario(path, load, [(type_b, amount_b), (type_a, amount_a)])
        if not a_only and not b_only and together:
            return [
                _record(tx_a, "jointly_dangerous", _context([], dict(load)),
                        joint_role="partner", joint_pair_id=pair_id, joint_profile=index),
                _record(tx_b, "jointly_dangerous", _context([tx_a], dict(load)),
                        joint_role="trigger", joint_pair_id=pair_id, joint_profile=index),
            ]
    raise InputError(  # pragma: no cover - parameters guarantee success long before this
        f"could not construct jointly dangerous profile {index} for slot {slot} in {max_attempts} attempts"
    )


BUILDERS: dict[str, Builder] = {
    "normal": build_normal,
    "unusual_but_harmless": build_unusual_but_harmless,
    "obvious_single_signal_danger": build_obvious_single_signal_danger,
    "high_value_low_blast_radius": build_high_value_low_blast_radius,
    "low_value_high_blast_radius": build_low_value_high_blast_radius,
    "correlated_anomalies": build_correlated_anomalies,
    "dependency_chain_failures": build_dependency_chain_failures,
    "jointly_dangerous": build_jointly_dangerous,
}
