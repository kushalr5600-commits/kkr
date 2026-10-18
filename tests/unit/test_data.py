"""P1 tests: deterministic generation, linkage, five joint profiles, 60 s behaviour."""
from __future__ import annotations

from tests.fixtures import expect_raises, repo

from backend.data.generator import DatasetGenerator
from backend.data.repository import build_graph
from backend.shared import config
from backend.shared.context_utils import as_utc, recent_in_window
from backend.shared.errors import InputError
from backend.shared.schemas import Transaction
from backend.simulation.crash_test import CrashTestEngine
from backend.simulation.forks import RealityForkGenerator


def _fails(transaction, graph, context) -> bool:
    baseline = RealityForkGenerator.generate_baseline(transaction, graph, context)
    return any(not CrashTestEngine.attack(baseline, s)[1].survived for s in config.SCENARIOS)


def test_generation_is_deterministic_under_a_fixed_seed():
    a = DatasetGenerator.build_dataset(seed=7, n_total=400, n_accounts=40)
    b = DatasetGenerator.build_dataset(seed=7, n_total=400, n_accounts=40)
    c = DatasetGenerator.build_dataset(seed=8, n_total=400, n_accounts=40)
    assert a.model_dump_json() == b.model_dump_json()
    assert a.model_dump_json() != c.model_dump_json()


def test_ids_are_unique_and_all_categories_present():
    ds = repo().dataset
    ids = [r.transaction.id for r in ds.records]
    assert len(ids) == len(set(ids))
    assert set(config.CATEGORIES) <= {r.category for r in ds.records}


def test_account_and_context_linkage():
    r = repo()
    for rec in r.dataset.records:
        account, graph, context = r.load_context(rec.transaction)
        assert account.id == rec.transaction.account_id
        node_ids = {n.id for n in graph.nodes}
        assert all(e.source in node_ids and e.target in node_ids for e in graph.edges)
        assert set(context.local_dependency_load) <= set(config.SERVICES)
        assert all(v >= 0 for v in context.local_dependency_load.values())
        for other in context.recent_transactions:
            delta = (as_utc(rec.transaction.timestamp) - as_utc(other.timestamp)).total_seconds()
            assert 0 <= delta <= context.window_seconds


def test_graph_uses_only_frozen_node_types():
    r = repo()
    for rec in r.dataset.records[:300]:
        account = r.account(rec.transaction.account_id)
        graph = build_graph(rec.transaction, account)
        assert {n.node_type for n in graph.nodes} <= set(config.NODE_TYPES)


def test_unknown_account_and_unsupported_type_are_input_errors():
    r = repo()
    base = r.dataset.records[0].transaction
    expect_raises(InputError, r.load_context, base.model_copy(update={"account_id": "ACC-NOPE"}))
    expect_raises(InputError, r.load_context, base.model_copy(update={"transaction_type": "crypto_swap"}))


def test_exactly_five_joint_profiles_are_present():
    triggers = [x for x in repo().dataset.records if x.category == "jointly_dangerous" and x.joint_role == "trigger"]
    assert {t.joint_profile for t in triggers} == {0, 1, 2, 3, 4}


def test_joint_pairs_keep_ground_truth_structure_and_60_second_cooccurrence():
    r = repo()
    records = {x.transaction.id: x for x in r.dataset.records}
    pairs: dict[str, dict[str, object]] = {}
    for rec in r.dataset.records:
        if rec.category == "jointly_dangerous":
            pairs.setdefault(rec.joint_pair_id, {})[rec.joint_role] = rec
    assert len(pairs) >= 10
    for pair_id, roles in pairs.items():
        partner, trigger = roles["partner"], roles["trigger"]
        assert partner.split == trigger.split, f"{pair_id} straddles splits"
        gap = (as_utc(trigger.transaction.timestamp) - as_utc(partner.transaction.timestamp)).total_seconds()
        assert 0 < gap <= config.WINDOW_SECONDS
        assert partner.transaction.id in {t.id for t in trigger.context.recent_transactions}

        acct_t, graph_t, ctx_t = r.load_context(trigger.transaction)
        assert _fails(trigger.transaction, graph_t, ctx_t), f"{pair_id}: A+B should fail"
        alone = ctx_t.model_copy(update={"recent_transactions": []})
        assert not _fails(trigger.transaction, graph_t, alone), f"{pair_id}: B alone should survive"
        _acct_p, graph_p, ctx_p = r.load_context(partner.transaction)
        assert not _fails(partner.transaction, graph_p, ctx_p), f"{pair_id}: A alone should survive"
        assert records[trigger.transaction.id].joint_profile == partner.joint_profile


def test_joint_cases_are_not_extreme_by_amount_alone():
    r = repo()
    for rec in r.dataset.records:
        if rec.category != "jointly_dangerous":
            continue
        account = r.account(rec.transaction.account_id)
        z = (rec.transaction.amount - account.historical_avg_amount) / account.historical_std_amount
        assert z < 4.0, f"{rec.transaction.id} has z={z:.1f}; not 'individually ordinary'"


def test_demo_pair_is_outside_the_evaluation_splits():
    demo = [x for x in repo().dataset.records if x.split == "demo"]
    assert {x.transaction.id for x in demo} >= {config.DEMO_TRANSACTION_ID}
    assert isinstance(repo().demo_transaction(), Transaction)
