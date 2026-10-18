"""Fixed-budget failure-recall experiment (Team manual section 11).

    python scripts/run_experiment.py                         # validation split (development)
    python scripts/run_experiment.py --split test --confirm-frozen

The locked ``test`` split is refused unless ``--confirm-frozen`` is passed: only
run it once the weights, normalization, scenario thresholds and models are
frozen. Never tune against its output.

Artifacts are written to evidence/results/<split>/:
    results.json  results.csv  config_snapshot.json  model_metadata.json  README-results.md
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from backend.data.repository import DataRepository  # noqa: E402
from backend.gate.calibration import budget_curve, evaluate_split, fit_models, threshold_operating_point  # noqa: E402
from backend.shared import config  # noqa: E402


def _config_snapshot() -> dict:
    keep = {}
    for name in dir(config):
        if name.startswith("_") or not name.isupper():
            continue
        value = getattr(config, name)
        if isinstance(value, (int, float, str, bool, list, tuple, dict)):
            keep[name] = value
    return keep


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="validation", choices=["validation", "test"])
    parser.add_argument("--confirm-frozen", action="store_true",
                        help="required for --split test: confirms the configuration is frozen")
    parser.add_argument("--backend", default=None, help="auto | sklearn | numpy")
    args = parser.parse_args()
    if args.split == "test" and not args.confirm_frozen:
        sys.exit("refusing to evaluate the locked test split without --confirm-frozen")

    repo = DataRepository.default()
    models = fit_models(repo, backend=args.backend)
    ev = evaluate_split(repo, models, args.split)
    rows = budget_curve(ev)
    operating = threshold_operating_point(ev)

    out = ROOT / "evidence" / "results" / args.split
    out.mkdir(parents=True, exist_ok=True)

    categories = sorted(set(ev.categories))
    with open(out / "results.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["policy", "simulation_budget", "simulation_count", "simulation_fraction", "failures_found",
             "total_failures", "failure_recall", "false_negative_rate", "simulation_avoidance",
             "total_simulation_runtime_ms", "mean_simulation_runtime_ms"]
            + [f"recall_{c}" for c in categories]
        )
        for r in rows + [operating]:
            writer.writerow(
                [r["policy"], f"{r['simulation_budget']:.4f}", f"{r['simulation_count']:.1f}",
                 f"{r['simulation_fraction']:.4f}", f"{r['failures_found']:.2f}", r["total_failures"],
                 f"{r['failure_recall']:.4f}", f"{r['false_negative_rate']:.4f}",
                 f"{r['simulation_avoidance']:.4f}", f"{r['total_simulation_runtime_ms']:.2f}",
                 f"{r['mean_simulation_runtime_ms']:.4f}"]
                + ["" if r["category_recall"].get(c) is None else f"{r['category_recall'][c]:.4f}" for c in categories]
            )

    meta = {
        "split": args.split,
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_transactions": ev.n,
        "n_true_failures": ev.n_failures,
        "dataset_seed": repo.dataset.meta.seed,
        "dataset_split_counts": repo.dataset.meta.split_counts,
        "score_threshold": config.IMPACT_THRESHOLD,
        "gate_weights": config.IMPACT_WEIGHTS,
        "gate_runtime_ms_per_transaction": ev.gate_ms_per_tx,
        "mean_simulation_runtime_ms_per_transaction": float(ev.sim_ms.mean()),
        "python": platform.python_version(),
        "architecture": platform.machine(),
        "models": models.versions(),
        "model_fit": {"split": models.fitted_on_split, "samples": models.n_fit_samples,
                      "failures": models.n_fit_failures},
    }
    (out / "model_metadata.json").write_text(json.dumps(meta, indent=1, default=str), encoding="utf-8")
    (out / "config_snapshot.json").write_text(json.dumps(_config_snapshot(), indent=1, default=str), encoding="utf-8")
    (out / "results.json").write_text(
        json.dumps({"meta": meta, "budget_curve": rows, "threshold_operating_point": operating}, indent=1, default=str),
        encoding="utf-8",
    )

    lines = [
        f"# Experiment results - split `{args.split}`",
        "",
        f"{ev.n} transactions, {ev.n_failures} true failures (ground truth = full stress simulation).",
        "Ranking experiment: each policy ranks the split and the top budget fraction is simulated.",
        "",
        "| budget | " + " | ".join(config.EXPERIMENT_POLICIES) + " |",
        "|---|" + "---|" * len(config.EXPERIMENT_POLICIES),
    ]
    for budget in config.EXPERIMENT_BUDGETS:
        cells = []
        for pol in config.EXPERIMENT_POLICIES:
            r = next(x for x in rows if x["policy"] == pol and x["simulation_budget"] == budget)
            cells.append(f"{r['failure_recall']:.3f}")
        lines.append(f"| {budget:.1%} | " + " | ".join(cells) + " |")
    lines += [
        "",
        f"Production rule (simulate iff score >= {config.IMPACT_THRESHOLD:.2f}): simulates "
        f"{operating['simulation_fraction']:.1%} of transactions, failure recall "
        f"{operating['failure_recall']:.3f}, precision "
        f"{'n/a' if operating['precision'] is None else format(operating['precision'], '.3f')}.",
        "",
        "Numbers are for the synthetic dataset only; weights and threshold are declared MVP parameters.",
    ]
    (out / "README-results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    print(f"\nartifacts written to {out}")


if __name__ == "__main__":
    main()
