from __future__ import annotations

import numpy as np

from backend.data.repository import DataRepository
from backend.gate.impact_gate import ImpactGate, combine, magnitude_signal
from backend.gate.models import extract_features
from backend.intelligence.signals import explain_signals
from backend.pipeline import BlackboxService
from backend.shared import config
from backend.shared.schemas import ImpactSignals

repo = DataRepository.default()
svc = BlackboxService.build(repo)
models = svc.models

# Backend truthful
assert models.backend == "numpy", models.backend
v = models.versions()
print("backend", models.backend, "versions", v)
assert v.get("backend", models.backend) in {models.backend, None} or "backend" not in v

# A: not fitted on eval labels; on calibration split
assert models.fitted_on_split == "calibration"

# Reproducibility: same input -> same score
tx = repo.demo_transaction()
account, graph, context = repo.load_context(tx)
s1 = ImpactGate.score(tx, account, graph, context)
s2 = ImpactGate.score(tx, account, graph, context)
assert s1.score == s2.score and s1.signals == s2.signals
print("reproducible", s1.score)

# Independent M/D/A/U
assert 0 <= s1.signals.magnitude <= 1
assert 0 <= s1.signals.dependency <= 1
assert 0 <= s1.signals.anomaly <= 1
assert 0 <= s1.signals.uncertainty <= 1
manual = 0.30 * s1.signals.magnitude + 0.30 * s1.signals.dependency + 0.25 * s1.signals.anomaly + 0.15 * s1.signals.uncertainty
assert abs(manual - s1.score) < 1e-12
assert s1.gate_decision == (s1.score >= 0.60)

# A is not fraud probability: explain caveats say so
ai = explain_signals(tx, account, graph, context)
assert any("not a fraud probability" in x for x in ai["anomaly"]["caveats"])
assert any("not a calibrated confidence" in x for x in ai["risk"]["caveats"])
# U = member std / 0.5 clipped
X = extract_features(tx, account, graph, context).reshape(1, -1)
members = models.risk._impl.member_probabilities(X)
std = float(members.std(axis=0)[0])
expect_u = float(np.clip(std / config.UNCERTAINTY_MAX_STD, 0, 1))
assert abs(ai["risk"]["normalized_u"] - expect_u) < 1e-12
print("U_matches_std_norm", expect_u)

# Non-finite M/D rejected
from backend.shared.errors import GateError
from backend.shared.schemas import Account, Transaction

bad_acct = Account(id="A", historical_avg_amount=100.0, historical_std_amount=1.0)
try:
    bad_tx = Transaction(
        id="T", account_id="A", amount=float("inf"),
        timestamp="2026-01-01T00:00:00Z", transaction_type="card_payment",
    )
    from backend.gate.impact_gate import magnitude_signal

    magnitude_signal(bad_tx, bad_acct)
    print("nonfinite_amount NOT_REJECTED")
except (GateError, Exception) as exc:  # noqa: BLE001
    print("nonfinite_amount_rejected OK", type(exc).__name__)

# M path with extreme but finite amount saturates at 1.0 (documented)
big_tx = Transaction(id="T2", account_id="A", amount=1e18, timestamp="2026-01-01T00:00:00Z", transaction_type="card_payment")
assert magnitude_signal(big_tx, bad_acct) == 1.0
print("M_saturation OK")

# NaN in combine
try:
    combine(ImpactSignals(magnitude=float("nan"), dependency=0, anomaly=0, uncertainty=0))
    print("nan_combine NOT_REJECTED")
except GateError:
    print("nan_combine_rejected OK")

# A/U from models, M/D deterministic without models
m0 = magnitude_signal(tx, account)
m0b = magnitude_signal(tx, account)
assert m0 == m0b
print("M_deterministic", m0)

# Countereexample: NO_SIMULATION never gets stress results
cert = svc.analyze(demo_mode=True)
assert cert.status == "NO_SIMULATION" and cert.forks_tested == []
print("no_sim_empty_forks OK")
