# Local readiness evidence

- Host machine: **AMD64** (NOT LinuxONE unless s390x)
- Python: 3.12.10
- run_tests exit: **0**
- smoke_test exit: **0**
- HTTP: OK
- Frozen integrity: see integrity.json
- Demo: {
  "transaction_id": "TX-DEMO-0001",
  "status": "NO_SIMULATION",
  "action": "ALLOW_NORMAL_PATH",
  "score": 0.5824181914863561,
  "forks": 0,
  "backend": "sklearn"
}
- Simulated: {
  "transaction_id": "TX-00154",
  "status": "SIMULATED",
  "action": "BLOCK_OR_HOLD",
  "score": 0.6537432175146016,
  "forks": 6,
  "backend": "sklearn"
}

This bundle is **local host evidence only**. LinuxONE requires a separate run
on the authorized s390x guest (`docs/LINUXONE_RUNBOOK.md`).
