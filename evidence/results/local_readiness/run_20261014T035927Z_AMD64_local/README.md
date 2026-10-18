# Local readiness evidence

- Host machine: **AMD64** (NOT LinuxONE unless s390x)
- Python: 3.12.10
- run_tests exit: **1**
- smoke_test exit: **0**
- HTTP: OK
- Frozen integrity: see integrity.json
- Demo: {
  "transaction_id": "TX-DEMO-0001",
  "status": "NO_SIMULATION",
  "action": "ALLOW_NORMAL_PATH",
  "score": 0.41387409174663015,
  "forks": 0,
  "backend": "numpy"
}
- Simulated: {
  "transaction_id": "TX-00300",
  "status": "SIMULATED",
  "action": "BLOCK_OR_HOLD",
  "score": 0.7186539195457872,
  "forks": 6,
  "backend": "numpy"
}

This bundle is **local host evidence only**. LinuxONE requires a separate run
on the authorized s390x guest (`docs/LINUXONE_RUNBOOK.md`).
