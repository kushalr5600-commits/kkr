"""Orchestration of the BLACKBOX pipeline (P4). Framework-free.

    validate -> load context -> Impact Gate -> (select?) -> baseline fork
             -> crash test x3 -> fragility search x3 -> Decision Certificate

``BlackboxService.analyze`` is the single entry point used by the FastAPI
route. It contains no gate, simulation or certificate logic of its own: it only
calls the frozen component interfaces and degrades to a truthful REVIEW
certificate when a valid request fails internally (error type B).
"""
from __future__ import annotations

import platform
import time
from dataclasses import dataclass

import numpy as np

from backend.certificate.certificate import CertificateGenerator
from backend.data.repository import DataRepository
from backend.gate.calibration import evaluate_split, fit_models
from backend.gate.impact_gate import ImpactGate
from backend.gate.interaction_aware import is_enabled
from backend.gate.models import GateModels
from backend.shared import config, diagnostics, tracing
from backend.shared.errors import BlackboxError, InputError
from backend.shared.schemas import (
    DecisionCertificate,
    EventContext,
    ForkResult,
    FragilityResult,
    ImpactScore,
    RuntimeMetadata,
    Transaction,
)
from backend.simulation.crash_test import CrashTestEngine
from backend.simulation.forks import RealityForkGenerator
from backend.simulation.fragility import FragilitySearch


@dataclass
class ShowcaseItem:
    transaction: Transaction
    hint: str


class BlackboxService:
    def __init__(self, repo: DataRepository, models: GateModels) -> None:
        self.repo = repo
        self.models = models
        ImpactGate.use_models(models)
        self._showcase: list[ShowcaseItem] | None = None

    # ------------------------------------------------------------ construction
    @classmethod
    def build(cls, repo: DataRepository | None = None, backend: str | None = None) -> "BlackboxService":
        repo = repo or DataRepository.default()
        return cls(repo, fit_models(repo, backend=backend))

    # ---------------------------------------------------------------- metadata
    def runtime(self) -> RuntimeMetadata:
        """Truthful runtime metadata. Fills existing RuntimeMetadata fields only
        (no schema change): model_versions carries backend, library versions,
        config fingerprint and dataset fingerprint so a certificate can be tied
        back to the code/configuration that produced it."""
        import hashlib
        from pathlib import Path

        versions = dict(self.models.versions())
        versions["python"] = platform.python_version()
        versions["numpy"] = np.__version__
        versions["blackbox"] = config.VERSION
        # Policy identity for certificates / JSON Schema (existing dict only).
        versions["policy_version"] = config.POLICY_VERSION
        if is_enabled():
            versions["policy_formula"] = (
                f"I=0.45*A+0.30*W+0.15*D+0.10*L;threshold={config.IMPACT_THRESHOLD:.2f};mode=interaction_aware"
            )
        else:
            versions["policy_formula"] = (
                f"I=0.30*M+0.30*D+0.25*A+0.15*U;threshold={config.IMPACT_THRESHOLD:.2f};mode=frozen"
            )
        backend_dir = Path(__file__).resolve().parent
        config_path = backend_dir / "shared" / "config.py"
        if config_path.exists():
            versions["config_sha256"] = hashlib.sha256(config_path.read_bytes()).hexdigest()
        manifest_path = backend_dir / "data" / "manifest.json"
        if manifest_path.exists():
            try:
                import json as _json

                meta = _json.loads(manifest_path.read_text(encoding="utf-8"))
                if meta.get("sha256"):
                    versions["dataset_sha256"] = str(meta["sha256"])
            except (OSError, ValueError):
                pass
        return diagnostics.runtime_metadata(model_versions=versions, random_seed=config.DEMO_SEED)

    def health(self) -> dict[str, str]:
        arch = platform.machine() or "unknown"
        # Display formula + mode from the SAME source as /explain, so the UI can
        # render the active policy on first paint (no analysis required).
        from backend.explain.explainer import active_formula

        return {
            "status": "ok",
            # Truthful: "linuxone" only when the process really runs on s390x.
            "runtime": "linuxone" if arch == "s390x" else "local",
            "architecture": arch,
            "version": config.VERSION,
            "model_backend": self.models.backend,
            "gate_threshold": f"{config.IMPACT_THRESHOLD:.2f}",
            "policy_version": config.POLICY_VERSION,
            "policy_mode": "interaction_aware" if is_enabled() else "frozen",
            "policy_formula": active_formula(),
            "python": platform.python_version(),
        }

    # -------------------------------------------------------------- demo lists
    def demo_transactions(self) -> list[dict]:
        """The fixed demo transaction plus validation-split examples that show
        every gate outcome (including a missed failure). Computed once."""
        if self._showcase is None:
            items = [ShowcaseItem(self.repo.demo_transaction(), "Fixed demo transaction (jointly dangerous pair, 2nd half)")]
            ev = evaluate_split(self.repo, self.models, "validation")
            wanted = [
                ("selected_fails", "Gate selects it; fails a stress test", lambda g, f: g and f),
                ("selected_survives", "Gate selects it; survives stress", lambda g, f: g and not f),
                ("skipped_survives", "Gate skips it; would survive stress", lambda g, f: (not g) and not f),
                ("skipped_fails", "Gate skips it; would FAIL stress (missed failure)", lambda g, f: (not g) and f),
            ]
            by_id = {r.transaction.id: r for r in self.repo.records_for_split("validation")}
            for _key, hint, pred in wanted:
                for i, tx_id in enumerate(ev.transaction_ids):
                    if pred(bool(ev.gate_decision[i]), bool(ev.failed[i])):
                        items.append(ShowcaseItem(by_id[tx_id].transaction, hint))
                        break
            self._showcase = items
        return [
            {"transaction": item.transaction.model_dump(mode="json"), "hint": item.hint}
            for item in self._showcase
        ]

    # ----------------------------------------------------------------- analyze
    def _resolve_transaction(self, transaction: Transaction | None, demo_mode: bool) -> Transaction:
        if transaction is not None:
            return transaction
        if demo_mode:
            return self.repo.demo_transaction()
        raise InputError("a transaction is required unless demo_mode is true")

    def analyze(
        self,
        transaction: Transaction | None = None,
        context: EventContext | None = None,
        demo_mode: bool = False,
        trace_id: str | None = None,
    ) -> DecisionCertificate:
        with diagnostics.trace_scope(trace_id):
            tx = self._resolve_transaction(transaction, demo_mode)
            diagnostics.log_event("request_received", tx.id)

            # Capture whether the caller supplied a context (vs. the repo defaulting).
            supplied_context = context is not None

            impact: ImpactScore | None = None
            forks: list[ForkResult] = []
            fragility: list[FragilityResult] = []
            t_start = time.perf_counter()
            try:
                # Type A errors (InputError) from context loading must still propagate
                # to the HTTP layer as a 422; every other internal failure degrades to
                # a truthful REVIEW certificate (error type B).
                with tracing.span("context_loaded", transaction_id=tx.id), diagnostics.stage(
                    "context_loaded", tx.id
                ):
                    account, graph, repo_context = self.repo.load_context(tx)
                    context = context if supplied_context else repo_context

                runtime = self.runtime()

                with tracing.span("gate_scored", transaction_id=tx.id), diagnostics.stage(
                    "gate_scored", tx.id
                ):
                    impact = ImpactGate.score(tx, account, graph, context)

                if ImpactGate.should_simulate(impact):
                    diagnostics.log_event("simulation_started", tx.id)
                    with tracing.span("simulation", transaction_id=tx.id):
                        baseline = RealityForkGenerator.generate_baseline(tx, graph, context)
                        for scenario in config.SCENARIOS:
                            t0 = time.perf_counter()
                            forks.extend(CrashTestEngine.attack(baseline, scenario))
                            diagnostics.log_event(
                                "scenario_completed", tx.id, elapsed_ms=(time.perf_counter() - t0) * 1000
                            )
                        with diagnostics.stage("fragility_completed", tx.id):
                            fragility = [FragilitySearch.find_threshold(baseline, s) for s in config.SCENARIOS]

                with tracing.span("certificate_generated", transaction_id=tx.id), diagnostics.stage(
                    "certificate_generated", tx.id
                ):
                    certificate = CertificateGenerator.generate(tx, impact, forks, fragility, runtime)
            except InputError:
                raise  # Type A: propagate to HTTP layer as a validation error.
            except Exception as exc:  # noqa: BLE001 - type B: degrade, never claim safety
                reason = f"{type(exc).__name__}: {exc}"
                if isinstance(exc, BlackboxError):
                    reason = f"{exc.code.value} {type(exc).__name__}: {exc.message}"
                certificate = CertificateGenerator.generate_review(
                    tx, impact, reason, runtime, partial_forks=forks, partial_fragility=fragility
                )

            # Truthful disclosure: an unknown transaction id gets a synthesized quiet
            # context (background load), never a measured one. Say so in the evidence.
            if not supplied_context and self.repo.record(tx.id) is None:
                certificate.evidence.insert(
                    1,
                    "Context defaulted: this transaction id is not in the dataset, so the background "
                    "load is a synthesized quiet default, not a measured snapshot.",
                )

            elapsed = (time.perf_counter() - t_start) * 1000.0
            certificate.evidence.insert(1, f"Pipeline time (gate, simulation, certificate): {elapsed:.1f} ms.")
            diagnostics.log_event("response_sent", tx.id, elapsed_ms=elapsed)
            return certificate
