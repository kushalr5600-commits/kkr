# Architecture (as implemented)

Six product components; everything else (FastAPI, validation, logging, UI, Docker) is plumbing.

```
frontend/static (HTML/CSS/JS)  --HTTP/JSON-->  backend/main.py (FastAPI)
                                                    |
                                            backend/pipeline.py  BlackboxService.analyze
        trace_scope -> context_loaded -> gate_scored -> [simulation_started -> scenario_completed x3
        -> fragility_completed] -> certificate_generated -> response_sent
```

| # | Component | Code | Notes |
|---|---|---|---|
| 1 | Impact Gate | `backend/gate/impact_gate.py`, `models.py`, `calibration.py` | M, D deterministic; A, U learned; ECDF normalization for A fitted on the calibration split |
| 2 | Local State Graph | `backend/data/repository.py::build_graph`, `shared/context_utils.py` | account -> transaction -> per-type service flow (+ counterparties) |
| 3 | Reality Forks | `backend/simulation/forks.py` | `BaselineFork` = nominal utilization of the services on the path |
| 4 | Crash Test Engine | `backend/simulation/crash_test.py`, `physics.py` | `attack` -> `[normal, stress]`, never stresses twice |
| 5 | Fragility Search | `backend/simulation/fragility.py` | grid-bisection on intensity 1.0..10.0, resolution 0.05, monotonicity verifiable |
| 6 | Decision Certificate | `backend/certificate/certificate.py` | evidence from real metrics; `LIMITATION:`-prefixed lines; REVIEW degradation |

Simulation physics (`physics.py`): per-service utilization = background load (from the event context) + load
of the transaction and its recent-window neighbours / service capacity. `3x_volume` and `fraud_spike` fail when any
path service exceeds utilization 1.0; `service_latency` fails when end-to-end latency exceeds the budget. All three
predicates are monotone in intensity (tested), which is what makes bisection valid.

Data: `DatasetGenerator.build_dataset` (seed in `config.py`) builds 8 behaviour categories; jointly dangerous pairs
use five explicit profiles and are verified so that A alone and B alone survive while A+B within 60 s fails.
Splits are stratified by unit (pairs never straddle splits): calibration 50%, validation 20%, locked test 30%, plus a
2-transaction `demo` pair outside all three.

Diagnostics: every request has a `TR-...` trace id; each stage logs `trace_id, transaction_id, stage, status,
elapsed_ms` (JSON lines on `blackbox.diag`), errors add code/type/message/owner/recovery.
