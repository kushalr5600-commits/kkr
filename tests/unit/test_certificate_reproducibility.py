"""Decision Certificate reproducibility (read-only audit outcome).

Established by the 2026-10-15 audit:
  * The RAW certificate is intentionally NOT byte-reproducible: it carries a random
    ``certificate_id`` (uuid4), a per-request ``trace_id``, and a wall-clock
    ``"Pipeline time ... ms."`` evidence line.
  * A CANONICAL PROJECTION — the certificate with those three volatile items
    removed — IS byte-identical across repeats and across a fresh model re-fit
    on the same host/backend/versions/config/dataset.

This is a determinism (integrity) property, NOT a digital signature: no signing
key or verification process is present or claimed.

The projection deliberately does not hard-code any hash value, so it is portable
across hosts/backends; it only asserts stability *within a run*.
"""
from __future__ import annotations

import hashlib
import json
import re

from backend.pipeline import BlackboxService
from backend.shared.schemas import Transaction

VOLATILE_EVIDENCE = re.compile(r"^Pipeline time .* ms\.$")
VOLATILE_KEYS = ("certificate_id", "trace_id")

# Showcase ids are derived from the live showcase (they follow the gate's
# scoring mode); only the outcome coverage (>= 5 slots) is pinned.
_service_cache: BlackboxService | None = None


def _service() -> BlackboxService:
    global _service_cache
    if _service_cache is None:
        _service_cache = BlackboxService.build()
    return _service_cache


def _transactions(svc: BlackboxService):
    return [
        (it["transaction"]["id"], Transaction.model_validate(it["transaction"]))
        for it in svc.demo_transactions()
    ]


def canonical_certificate(cert: dict) -> dict:
    """The reproducible projection: drop volatile identity + wall-clock latency."""
    c = json.loads(json.dumps(cert))
    for key in VOLATILE_KEYS:
        c.pop(key, None)
    c["evidence"] = [e for e in c.get("evidence", []) if not VOLATILE_EVIDENCE.match(e)]
    return c


def cert_digest(cert: dict) -> str:
    blob = json.dumps(canonical_certificate(cert), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def core_decision(cert: dict) -> dict:
    """Smallest judge-visible decision surface that must never drift."""
    return {
        "status": cert["status"],
        "transaction_id": cert["transaction_id"],
        "decision_description": cert["decision_description"],
        "impact_score": cert["impact_score"],
        "forks_tested": cert["forks_tested"],
        "fragility": cert["fragility"],
        "recommended_action": cert["recommended_action"],
    }


def test_canonical_projection_is_stable_across_repeats():
    svc = _service()
    txs = _transactions(svc)
    assert len(txs) >= 5, "showcase must expose all five outcomes"
    for tx_id, tx in txs:
        first = svc.analyze(transaction=tx).model_dump(mode="json")
        second = svc.analyze(transaction=tx).model_dump(mode="json")
        assert cert_digest(first) == cert_digest(second), f"{tx_id}: canonical digest drifted on repeat"
        # The decision surface itself is identical too.
        assert core_decision(first) == core_decision(second), f"{tx_id}: core decision drifted on repeat"


def test_raw_certificate_is_intentionally_volatile():
    svc = _service()
    _, tx = _transactions(svc)[0]
    first = svc.analyze(transaction=tx).model_dump(mode="json")
    second = svc.analyze(transaction=tx).model_dump(mode="json")
    # Identity/trace are per-issue, so the RAW bytes must NOT match (proves the
    # canonical projection is doing real work, and that we never claim raw replay).
    assert first["certificate_id"] != second["certificate_id"]
    assert first["trace_id"] != second["trace_id"]
    raw = lambda c: hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()
    assert raw(first) != raw(second)
    # A certificate must not smuggle in an unspecified timestamp field.
    assert "timestamp" not in first and "created_at" not in first


def test_canonical_projection_is_stable_across_fresh_model_fit():
    svc_a = _service()
    svc_b = BlackboxService.build()  # independent model re-fit
    assert svc_b.models.backend == svc_a.models.backend
    for tx_id, tx in _transactions(svc_a):
        a = svc_a.analyze(transaction=tx).model_dump(mode="json")
        b = svc_b.analyze(transaction=tx).model_dump(mode="json")
        assert cert_digest(a) == cert_digest(b), f"{tx_id}: canonical digest differs after fresh model fit"
        assert core_decision(a) == core_decision(b), f"{tx_id}: core decision differs after fresh model fit"
