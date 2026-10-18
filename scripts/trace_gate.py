"""Read-only gate diagnostic: explain Impact Gate signals for one transaction.

Prints M/D/A/U, weighted contributions, the frozen threshold comparison and the
simulation-selection decision for a given transaction id (default: the fixed
demo TX-DEMO-0001). Uses the currently selected model backend (sklearn or
numpy) and labels every output with that backend so results are never confused
across backends.

Does not modify models, weights, threshold, data or evidence files.

Usage (from repository root):
    python scripts/trace_gate.py
    python scripts/trace_gate.py --transaction-id TX-DEMO-0001
    python scripts/trace_gate.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def trace_transaction(transaction_id: str | None = None) -> dict[str, Any]:
    from backend.data.repository import DataRepository
    from backend.gate.calibration import fit_models
    from backend.gate.impact_gate import ImpactGate, combine, dependency_signal, magnitude_signal
    from backend.gate.models import FEATURE_NAMES, extract_features
    from backend.shared import config

    repo = DataRepository.default()
    models = fit_models(repo)
    ImpactGate.use_models(models)

    if transaction_id is None:
        transaction_id = config.DEMO_TRANSACTION_ID
    record = repo.record(transaction_id)
    if record is None:
        raise SystemExit(f"transaction {transaction_id!r} not found in the dataset")

    tx = record.transaction
    account, graph, context = repo.load_context(tx)
    impact = ImpactGate.score(tx, account, graph, context)
    s = impact.signals
    w = config.IMPACT_WEIGHTS
    contributions = {
        "magnitude": w["magnitude"] * s.magnitude,
        "dependency": w["dependency"] * s.dependency,
        "anomaly": w["anomaly"] * s.anomaly,
        "uncertainty": w["uncertainty"] * s.uncertainty,
    }
    features = extract_features(tx, account, graph, context)
    feature_map = dict(zip(FEATURE_NAMES, [float(x) for x in features]))
    payload: dict[str, Any] = {
        "model_backend": models.backend,
        "transaction_id": tx.id,
        "transaction_type": tx.transaction_type,
        "amount": tx.amount,
        "account_id": tx.account_id,
        "account_hist_avg": account.historical_avg_amount,
        "account_hist_std": account.historical_std_amount,
        "signals": {
            "magnitude_M": s.magnitude,
            "dependency_D": s.dependency,
            "anomaly_A": s.anomaly,
            "uncertainty_U": s.uncertainty,
        },
        "weighted_contributions": contributions,
        "score": impact.score,
        "threshold": config.IMPACT_THRESHOLD,
        "gate_decision": impact.gate_decision,
        "selected_for_simulation": impact.gate_decision,
        "decision_path": (
            f"score {impact.score:.6f} "
            f"{'>=' if impact.gate_decision else '<'} threshold {config.IMPACT_THRESHOLD:.2f} "
            f"-> {'SIMULATE' if impact.gate_decision else 'SKIP (NO_SIMULATION / ALLOW_NORMAL_PATH)'}"
        ),
        "dataset_category_label_not_used_by_gate": record.category,
        "feature_vector": feature_map,
        "notes": [
            "M and D are deterministic statistics/graph features; A and U are model outputs.",
            "Category and failure labels are never gate inputs; shown only for cross-checking.",
            "Scores differ between sklearn and numpy backends (see docs/BACKEND_EVIDENCE.md).",
        ],
    }
    # Cross-checks: standalone signal helpers must agree with the scored values.
    payload["cross_checks"] = {
        "magnitude_signal_helper": magnitude_signal(tx, account),
        "dependency_signal_helper": dependency_signal(tx, graph),
        "combine_of_scored_signals": combine(s),
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Impact Gate trace")
    parser.add_argument("--transaction-id", default=None, help="default: config.DEMO_TRANSACTION_ID")
    parser.add_argument("--json", action="store_true", help="print JSON only")
    args = parser.parse_args(argv)
    payload = trace_transaction(args.transaction_id)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(f"model_backend:     {payload['model_backend']}")
    print(f"transaction:       {payload['transaction_id']} ({payload['transaction_type']}, amount {payload['amount']})")
    print(f"account baseline:  avg={payload['account_hist_avg']:.2f} std={payload['account_hist_std']:.2f}")
    sig = payload["signals"]
    print(f"signals:           M={sig['magnitude_M']:.4f}  D={sig['dependency_D']:.4f}  "
          f"A={sig['anomaly_A']:.4f}  U={sig['uncertainty_U']:.4f}")
    con = payload["weighted_contributions"]
    print(f"contributions:     M={con['magnitude']:.4f}  D={con['dependency']:.4f}  "
          f"A={con['anomaly']:.4f}  U={con['uncertainty']:.4f}")
    print(f"score:             {payload['score']:.6f}")
    print(f"threshold:         {payload['threshold']}")
    print(f"gate_decision:     {payload['gate_decision']}")
    print(f"path:              {payload['decision_path']}")
    print(f"(label only) category: {payload['dataset_category_label_not_used_by_gate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
