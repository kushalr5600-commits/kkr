"""Generate the deterministic sample dataset and its manifest.

    python scripts/build_dataset.py

Writes backend/data/sample_dataset.json and backend/data/manifest.json. The same
seed always produces byte-identical files; the manifest records the SHA-256 so
a changed dataset is detectable.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.data.generator import DatasetGenerator  # noqa: E402
from backend.data.repository import SAMPLE_DATASET_PATH, DataRepository  # noqa: E402
from backend.shared import config  # noqa: E402


def main() -> None:
    dataset = DatasetGenerator.build_dataset()
    repo = DataRepository(dataset)
    repo.save_json(SAMPLE_DATASET_PATH)

    digest = hashlib.sha256(SAMPLE_DATASET_PATH.read_bytes()).hexdigest()
    splits: dict[str, list[str]] = {}
    for rec in dataset.records:
        splits.setdefault(rec.split, []).append(rec.transaction.id)
    joint = [r for r in dataset.records if r.category == "jointly_dangerous"]
    manifest = {
        "seed": dataset.meta.seed,
        "version": dataset.meta.version,
        "size": dataset.meta.size,
        "n_accounts": dataset.meta.n_accounts,
        "sha256": digest,
        "category_counts": dataset.meta.category_counts,
        "split_counts": dataset.meta.split_counts,
        "joint_pairs": len({r.joint_pair_id for r in joint if r.joint_pair_id}),
        "demo_transaction_id": config.DEMO_TRANSACTION_ID,
        "split_ids": splits,
        "note": "Split membership only. No category or failure label is exposed to the gate.",
    }
    path = SAMPLE_DATASET_PATH.with_name("manifest.json")
    path.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
    print(f"wrote {SAMPLE_DATASET_PATH} ({SAMPLE_DATASET_PATH.stat().st_size / 1e6:.1f} MB) sha256={digest[:16]}...")
    print(f"wrote {path}")
    print("splits:", dataset.meta.split_counts)
    print("categories:", dataset.meta.category_counts)


if __name__ == "__main__":
    main()
