"""Deterministic synthetic enterprise dataset.

Public API (Agent manual 1.7):

    DatasetGenerator.generate_accounts(n)                 -> list[Account]
    DatasetGenerator.generate_transactions(accounts, n)   -> list[Transaction]

plus ``build_dataset`` which assembles the full categorised, split dataset.

Determinism: everything is derived from ``numpy.random.default_rng`` seeds.
There is no wall-clock time, no global random state and no I/O here, so the
same seed always yields byte-identical JSON.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from backend.data import scenarios
from backend.data.repository import Dataset, DatasetMeta, DatasetRecord
from backend.shared import config
from backend.shared.schemas import Account, Transaction

SLOT_SECONDS = 300  # each dataset record lives in its own 5-minute slot


def _base_time() -> datetime:
    return datetime.fromisoformat(config.DATASET_BASE_TIME)


class DatasetGenerator:
    # ------------------------------------------------------------------ accounts
    @classmethod
    def generate_accounts(cls, n: int, seed: int | None = None) -> list[Account]:
        rng = np.random.default_rng(config.DATASET_SEED if seed is None else seed)
        ids = [f"ACC-{i + 1:04d}" for i in range(n)]
        accounts: list[Account] = []
        for i, acc_id in enumerate(ids):
            avg = float(np.clip(np.exp(rng.normal(np.log(700.0), 0.9)), 60.0, 6000.0))
            cv = float(rng.uniform(0.25, 0.6))
            n_rel = int(rng.choice([0, 1, 2, 3, 4, 5], p=[0.25, 0.25, 0.20, 0.15, 0.10, 0.05]))
            others = [x for j, x in enumerate(ids) if j != i]
            related: list[str] = []
            if n_rel and others:
                picks = rng.choice(len(others), size=min(n_rel, len(others)), replace=False)
                related = sorted(others[int(k)] for k in picks)
            accounts.append(
                Account(
                    id=acc_id,
                    historical_avg_amount=round(avg, 2),
                    historical_std_amount=round(avg * cv, 2),
                    related_account_ids=related,
                )
            )
        return accounts

    # -------------------------------------------------------------- transactions
    @classmethod
    def generate_transactions(
        cls, accounts: list[Account], n: int, seed: int | None = None
    ) -> list[Transaction]:
        """``n`` ordinary (normal-looking) transactions, one per time slot."""
        rng = np.random.default_rng((config.DATASET_SEED if seed is None else seed) + 1)
        base = _base_time()
        out: list[Transaction] = []
        for i in range(n):
            acct = accounts[int(rng.integers(len(accounts)))]
            ts = base + timedelta(seconds=i * SLOT_SECONDS)
            out.append(scenarios.normal_transaction(rng, acct, f"TX-N{i:05d}", ts))
        return out

    # ------------------------------------------------------------------- dataset
    @classmethod
    def category_unit_counts(cls, n_total: int) -> dict[str, int]:
        """Number of *units* per category (a jointly dangerous unit is a pair)."""
        counts: dict[str, int] = {}
        used = 0
        for category, share in config.CATEGORY_MIX.items():
            if category == "jointly_dangerous":
                pairs = max(1, round(n_total * share / 2))
                counts[category] = pairs
                used += 2 * pairs
            else:
                n = round(n_total * share)
                counts[category] = n
                used += n
        counts["normal"] = n_total - used
        return counts

    @classmethod
    def build_dataset(
        cls,
        seed: int | None = None,
        n_total: int | None = None,
        n_accounts: int | None = None,
    ) -> Dataset:
        seed = config.DATASET_SEED if seed is None else seed
        n_total = config.DATASET_SIZE if n_total is None else n_total
        n_accounts = config.DATASET_N_ACCOUNTS if n_accounts is None else n_accounts

        accounts = cls.generate_accounts(n_accounts, seed)
        rng = np.random.default_rng([seed, 17])
        base = _base_time()

        unit_counts = cls.category_unit_counts(n_total)
        units: list[str] = []
        for category in config.CATEGORIES:
            units += [category] * unit_counts[category]
        order = rng.permutation(len(units))

        # build every unit in a shuffled order so categories are not time-clustered
        built: dict[str, list[list[DatasetRecord]]] = {c: [] for c in config.CATEGORIES}
        for slot, unit_index in enumerate(order):
            category = units[int(unit_index)]
            t0 = base + timedelta(seconds=slot * SLOT_SECONDS)
            built[category].append(scenarios.BUILDERS[category](rng, accounts, slot, t0))

        # stratified, unit-level split assignment (a pair never straddles splits)
        records: list[DatasetRecord] = []
        for category in config.CATEGORIES:
            groups = built[category]
            perm = rng.permutation(len(groups))
            n_cal = round(len(groups) * config.SPLIT_FRACTIONS["calibration"])
            n_val = round(len(groups) * config.SPLIT_FRACTIONS["validation"])
            for rank, gi in enumerate(perm):
                split = "calibration" if rank < n_cal else "validation" if rank < n_cal + n_val else "test"
                for rec in groups[int(gi)]:
                    records.append(rec.model_copy(update={"split": split}))
        records.sort(key=lambda r: r.transaction.timestamp)

        records += cls.build_demo_records(accounts)

        meta = DatasetMeta(
            seed=seed,
            size=len(records),
            n_accounts=len(accounts),
            version=config.VERSION,
            base_time=config.DATASET_BASE_TIME,
            category_counts=_count(records, lambda r: r.category),
            split_counts=_count(records, lambda r: r.split),
        )
        return Dataset(meta=meta, accounts=accounts, records=records)

    # ---------------------------------------------------------------------- demo
    @classmethod
    def build_demo_records(cls, accounts: list[Account]) -> list[DatasetRecord]:
        """The fixed demo case: a jointly dangerous pair kept OUT of the
        calibration/validation/test splits (split == "demo") so showing it can
        never touch the locked evaluation."""
        rng = np.random.default_rng([config.DEMO_SEED, 99])
        t0 = _base_time() + timedelta(days=30)
        pair = scenarios.build_jointly_dangerous(
            rng, accounts, 0, t0,
            partner_id=f"{config.DEMO_TRANSACTION_ID}-A",
            trigger_id=config.DEMO_TRANSACTION_ID,
        )
        return [rec.model_copy(update={"split": "demo", "joint_pair_id": "PAIR-DEMO"}) for rec in pair]


def _count(records: list[DatasetRecord], key) -> dict[str, int]:
    out: dict[str, int] = {}
    for rec in records:
        k = key(rec)
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))
