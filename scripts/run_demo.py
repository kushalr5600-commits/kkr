"""Print the deterministic demo certificate as JSON.

    python scripts/run_demo.py [TRANSACTION_ID]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.pipeline import BlackboxService  # noqa: E402


def main() -> None:
    service = BlackboxService.build()
    if len(sys.argv) > 1:
        record = service.repo.record(sys.argv[1])
        if record is None:
            sys.exit(f"unknown transaction id {sys.argv[1]!r}")
        certificate = service.analyze(record.transaction)
    else:
        certificate = service.analyze(demo_mode=True)
    print(certificate.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
