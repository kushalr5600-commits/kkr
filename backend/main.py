"""FastAPI entrypoint (P4).  Start with:

    uvicorn backend.main:app --host 0.0.0.0 --port 8000

Routes:

    GET    /                            redirect to /dashboard
    GET    /health                      truthful runtime diagnostics
    GET    /dashboard                   the static frontend
    GET    /transactions                demo / showcase transactions
    POST   /analyze                     full preflight -> DecisionCertificate
    POST   /explain                     analyze + Explainable Decision Explorer payload
    POST   /research/what-if            research-only hypothetical re-score
    GET    /counterexample/{transaction_id}  showcase missed-failure w/ independent stress
    GET    /datasets                    list uploaded datasets
    POST   /datasets/upload             CSV/Parquet upload (multipart)
    GET    /datasets/registry           curated open-dataset registry (metadata only)
    GET    /datasets/{dataset_id}       metadata + preview rows
    POST   /datasets/{dataset_id}/map   column mapping
    DELETE /datasets/{dataset_id}       remove upload
    POST   /datasets/{dataset_id}/evaluate  Challenge Lab gate-selection benchmark
    GET    /experiments                 recent experiment reports (in-memory ring)
    GET    /experiments/{run_id}        one experiment report
"""
from __future__ import annotations

import math
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from backend.data.repository import DataRepository
from backend.datasets import registry as ds_registry
from backend.datasets.store import default_store
from backend.eval import benchmark as bench
from backend.explain import explainer
from backend.gate.models import extract_features
from backend.intelligence import llm_explain
from backend.intelligence import signals as intel
from backend.pipeline import BlackboxService
from backend.shared import config, diagnostics, tracing
from backend.shared.errors import BlackboxError, InputError
from backend.shared.schemas import DecisionCertificate, EventContext, Transaction

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend" / "static"

# In-memory experiment report ring (not a frozen artifact store).
_EXPERIMENTS: list[dict[str, Any]] = []
_EXPERIMENTS_MAX = 50
_EXPERIMENTS_LOCK = threading.Lock()


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction: Transaction | None = None
    context: EventContext | None = None
    demo_mode: bool = False


class MappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mapping: dict[str, str] = Field(min_length=1)
    label_semantics: str | None = None


class EvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Bounded: 0/negative would silently fall through to the default or slice
    # nonsensically; > DATASET_EVAL_MAX_ROWS bypasses the compute budget.
    max_rows: int | None = Field(default=None, gt=0, le=config.DATASET_EVAL_MAX_ROWS)
    run_stress_sample: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    diagnostics.configure_logging()
    try:
        app.state.service = BlackboxService.build()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "BLACKBOX failed to start: could not fit gate models. "
            f"({type(exc).__name__}: {exc}). "
            "Check dataset presence (backend/data/sample_dataset.json), "
            "Python 3.11+, and optional BLACKBOX_MODEL_BACKEND=numpy if scikit-learn "
            "is unavailable. See docs/LINUXONE_RUNBOOK.md."
        ) from exc
    yield


app = FastAPI(title="BLACKBOX", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


class _UploadSizeLimitMiddleware:
    """Reject oversized ``/datasets/upload`` requests by ``Content-Length``
    BEFORE the body is read into memory. Defense-in-depth against a single
    request exhausting RAM (the store also enforces the cap after parsing)."""

    def __init__(self, app_obj):
        self.app = app_obj

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path") == "/datasets/upload":
            headers = {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in scope.get("headers", [])
            }
            raw = headers.get("content-length")
            if raw is not None:
                try:
                    size = int(raw)
                except ValueError:
                    size = -1
                # Allow multipart framing overhead beyond the raw byte cap.
                limit = config.DATASET_MAX_BYTES + 1024 * 1024
                if size > limit:
                    resp = JSONResponse(
                        status_code=413,
                        content={
                            "error_type": "InputError",
                            "error_message": f"upload exceeds max size ({size} > {limit} bytes)",
                            "recovery_action": "upload a smaller sample or subset the dataset offline",
                        },
                    )
                    await resp(scope, receive, send)
                    return
        await self.app(scope, receive, send)


app.add_middleware(_UploadSizeLimitMiddleware)


def _json_safe(obj):
    """Replace non-finite floats with their string form so error payloads are
    JSON-compliant (``json.dumps`` refuses bare ``NaN``/``Infinity``)."""
    if isinstance(obj, float) and not math.isfinite(obj):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


@app.exception_handler(RequestValidationError)
async def _request_validation_handler(request, exc: RequestValidationError):
    """Type A input errors -> 422 with a JSON-safe envelope.

    The default handler serializes the raw pydantic errors, which embed the
    offending INPUT VALUE; a NaN/Infinity input therefore crashed the handler
    itself ("Out of range float values are not JSON compliant") and turned a
    required 422 into a raw 500.
    """
    return JSONResponse(
        status_code=422,
        content={
            "detail": _json_safe(exc.errors()),
            "error_type": "ValidationError",
            "trace_id": diagnostics.get_trace_id() or diagnostics.new_trace_id(),
        },
    )


@app.exception_handler(BlackboxError)
def _blackbox_error_handler(request, exc: BlackboxError):
    """Structured error envelope for any BlackboxError escaping a route.

    Only /analyze and /explain previously honored the {error_type, error_message,
    trace_id} contract; other routes surfaced raw 500s. InputError stays a 422;
    every other BlackboxError is a structured 500.
    """
    status = 422 if isinstance(exc, InputError) else 500
    return JSONResponse(
        status_code=status,
        content={**exc.as_dict(), "trace_id": diagnostics.get_trace_id() or diagnostics.new_trace_id()},
    )


def _service() -> BlackboxService:
    return app.state.service


def _analyze_or_http(request: AnalyzeRequest) -> DecisionCertificate:
    trace_id = diagnostics.new_trace_id()
    try:
        with tracing.span("http_analyze", trace_id=trace_id):
            return _service().analyze(
                transaction=request.transaction,
                context=request.context,
                demo_mode=request.demo_mode,
                trace_id=trace_id,
            )
    except InputError as exc:
        raise HTTPException(status_code=422, detail={**exc.as_dict(), "trace_id": trace_id})
    except BlackboxError as exc:
        return JSONResponse(status_code=500, content={**exc.as_dict(), "trace_id": trace_id})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=500,
            content={"error_type": type(exc).__name__, "error_message": str(exc), "trace_id": trace_id},
        )


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/dashboard")


@app.get("/health")
def health() -> dict[str, str]:
    payload = _service().health()
    otel = tracing.otel_status()
    payload["otel_enabled"] = otel["enabled"]
    payload["otel_package"] = otel["package_installed"]
    payload["dataset_studio"] = "enabled"
    payload["openml_client"] = "1" if ds_registry.OPENML_AVAILABLE else "0"
    return payload


@app.get("/dashboard", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/transactions")
def transactions() -> list[dict]:
    return _service().demo_transactions()


@app.post("/analyze", response_model=DecisionCertificate)
def analyze(request: AnalyzeRequest):
    result = _analyze_or_http(request)
    if isinstance(result, JSONResponse):
        return result
    return result


@app.post("/explain")
def explain(request: AnalyzeRequest):
    cert = _analyze_or_http(request)
    if isinstance(cert, JSONResponse):
        return cert
    tx = request.transaction
    if tx is None and request.demo_mode:
        tx = DataRepository.default().demo_transaction()
    account, graph, context = DataRepository.default().load_context(tx)
    features = extract_features(tx, account, graph, context).reshape(1, -1)
    payload = explainer.explain_certificate(cert, transaction=tx, features=features)
    payload["certificate"] = cert.model_dump(mode="json")
    # AI intelligence layer: real model outputs (same context as above).
    try:
        ai = intel.explain_signals(tx, account, graph, context)
        # True whenever simulation produced fork results (including a mid-run
        # REVIEW with partial forks), not only the clean SIMULATED status.
        ai["gate"]["simulation_executed"] = bool(cert.forks_tested)
        ai["simulation_status"] = cert.status
        if cert.forks_tested:
            ai["measured_stress_failures"] = sum(
                1 for f in cert.forks_tested if f.fork_name == "stress" and not f.survived
            )
        else:
            ai["measured_stress_failures"] = None
        payload["ai_signals"] = ai
    except Exception as exc:  # noqa: BLE001 - AI panel must not break the certificate path
        payload["ai_signals"] = {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
            "unknowns": ["AI signal detail unavailable for this request"],
        }
    # LLM narrative (advisory): pairs the certificate facts with Granite/LLM
    # reasoning when configured; honest "unavailable" otherwise.
    try:
        summary = {
            "transaction_id": cert.transaction_id,
            "amount": tx.amount,
            "transaction_type": tx.transaction_type,
            "impact_score": round(float(cert.impact_score.score), 6),
            "gate_decision": bool(cert.impact_score.gate_decision),
            "status": cert.status,
            "policy_formula": cert.runtime.model_versions.get("policy_formula"),
            "backend": cert.runtime.model_versions.get("backend"),
            "hybrid_risk": cert.runtime.model_versions.get("hybrid_risk"),
            "risk_model": cert.runtime.model_versions.get("risk_model"),
            "contributions": payload.get("contributions"),
        }
        payload["llm_narrative"] = llm_explain.narrate(summary)
    except Exception as exc:  # noqa: BLE001 - narrative must never break the certificate path
        payload["llm_narrative"] = {
            "available": False,
            "text": None,
            "reason": f"{type(exc).__name__}: {exc}",
            "advisory_only": True,
        }
    return payload


class WhatIfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction: Transaction | None = None
    demo_mode: bool = False
    overrides: dict[str, Any] = Field(min_length=1)


@app.post("/research/what-if")
def research_what_if(request: WhatIfRequest):
    """Research-only hypothetical re-score. Never mutates production state."""
    try:
        if request.transaction is not None:
            tx = request.transaction
        elif request.demo_mode:
            tx = DataRepository.default().demo_transaction()
        else:
            raise InputError("transaction or demo_mode is required")
        account, graph, context = DataRepository.default().load_context(tx)
        return intel.what_if(tx, account, graph, context, request.overrides)
    except InputError as exc:
        raise HTTPException(status_code=422, detail=exc.as_dict())


@app.get("/counterexample/{transaction_id}")
def counterexample(transaction_id: str) -> dict[str, Any]:
    """Independently establish stress outcome for a showcase transaction.

    Runs the full pipeline (including simulation when the gate selects) OR,
    for gate-skipped showcase ids, forces a labeled stress measurement via the
    crash-test engine without changing the gate decision.
    """
    service = _service()
    showcase = {item["transaction"]["id"]: item for item in service.demo_transactions()}
    if transaction_id not in showcase:
        raise HTTPException(
            status_code=404,
            detail={"error_message": f"unknown showcase transaction {transaction_id!r}"},
        )
    tx = Transaction.model_validate(showcase[transaction_id]["transaction"])
    cert = service.analyze(transaction=tx)
    # Force independent stress measurement even when the gate skipped.
    if cert.status == "NO_SIMULATION":
        from backend.data.repository import DataRepository

        repo = DataRepository.default()
        account, graph, context = repo.load_context(tx)
        from backend.simulation.crash_test import CrashTestEngine
        from backend.simulation.forks import RealityForkGenerator

        baseline = RealityForkGenerator.generate_baseline(tx, graph, context)
        forced_forks = []
        for scenario in config.SCENARIOS:
            n, s = CrashTestEngine.attack(baseline, scenario)
            forced_forks.extend([n, s])
        # Attach measured stress results without rewriting the gate decision.
        cert.forks_tested = forced_forks
        from backend.certificate.certificate import decide_action, _pair_by_scenario

        paired = _pair_by_scenario(forced_forks)
        # Only the reason is used here; the gate's recommended_action is kept
        # unchanged so the view still reflects the (missed) gate decision.
        _action, reason = decide_action(cert.impact_score, paired, cert.fragility)
        cert.evidence.append(
            f"Counterexample measurement: stress suite run independently of gate selection ({reason})."
        )
        # Mark that stress was measured for the counterexample view:
        cert.evidence.insert(
            0,
            "COUNTEREXAMPLE: stress outcomes below were measured independently of the gate decision.",
        )
    view = explainer.counterexample_from_certificate(cert)
    view["certificate"] = cert.model_dump(mode="json")
    view["showcase_hint"] = showcase[transaction_id]["hint"]
    return view


@app.get("/datasets")
def datasets_list() -> list[dict]:
    return default_store.list()


@app.post("/datasets/upload")
async def datasets_upload(
    file: UploadFile = File(...),
    display_name: str = Form(""),
    attribution: str = Form(""),
    license_name: str = Form(""),
    source_url: str = Form(""),
    registry_id: str = Form(""),
    label_semantics: str = Form(""),
) -> dict[str, Any]:
    filename = Path(file.filename or "upload.csv").name
    data = await file.read()
    try:
        # CPU-bound (decode/parse/sha256/write): run in a worker thread so the
        # event loop (and /health) stay responsive during a large upload.
        meta = await run_in_threadpool(
            default_store.ingest_bytes,
            filename=filename,
            data=data,
            display_name=display_name or None,
            attribution=attribution,
            license_name=license_name,
            source_url=source_url,
            registry_id=registry_id or None,
            label_semantics=label_semantics or None,
        )
    except InputError as exc:
        raise HTTPException(status_code=422, detail=exc.as_dict())
    return meta.to_dict()


@app.get("/datasets/registry")
def datasets_registry() -> dict[str, Any]:
    return {
        "entries": ds_registry.list_registry(),
        "openml": ds_registry.openml_import_status(),
        "policy": "Metadata only — no dataset bytes are redistributed by BLACKBOX.",
    }


@app.get("/datasets/{dataset_id}")
def datasets_get(dataset_id: str, preview_rows: int = 20) -> dict[str, Any]:
    try:
        meta = default_store.get(dataset_id)
    except InputError as exc:
        raise HTTPException(status_code=404, detail=exc.as_dict())
    rows = default_store.rows(dataset_id, limit=max(0, min(preview_rows, config.DATASET_MAX_PREVIEW_ROWS)))
    payload = meta.to_dict()
    payload["preview_rows"] = rows
    return payload


@app.post("/datasets/{dataset_id}/map")
def datasets_map(dataset_id: str, request: MappingRequest) -> dict[str, Any]:
    try:
        meta = default_store.set_mapping(dataset_id, request.mapping, request.label_semantics)
    except InputError as exc:
        raise HTTPException(status_code=422, detail=exc.as_dict())
    return meta.to_dict()


@app.delete("/datasets/{dataset_id}")
def datasets_delete(dataset_id: str) -> dict[str, str]:
    try:
        default_store.remove(dataset_id)
    except InputError as exc:
        raise HTTPException(status_code=404, detail=exc.as_dict())
    return {"status": "removed", "dataset_id": dataset_id}


@app.post("/datasets/{dataset_id}/evaluate")
def datasets_evaluate(dataset_id: str, request: EvaluateRequest) -> dict[str, Any]:
    try:
        report = bench.run_gate_benchmark(
            default_store,
            dataset_id,
            models=None,
            max_rows=request.max_rows,
        )
        if request.run_stress_sample:
            rows = bench.map_rows(default_store, dataset_id, limit=config.DATASET_STRESS_SAMPLE_MAX)
            report["stress_sample"] = bench.maybe_run_stress_sample(
                rows, max_rows=config.DATASET_STRESS_SAMPLE_MAX
            )
    except InputError as exc:
        raise HTTPException(status_code=422, detail=exc.as_dict())
    with _EXPERIMENTS_LOCK:
        _EXPERIMENTS.append(report)
        if len(_EXPERIMENTS) > _EXPERIMENTS_MAX:
            _EXPERIMENTS.pop(0)
    return report


@app.get("/experiments")
def experiments_list() -> list[dict[str, Any]]:
    with _EXPERIMENTS_LOCK:
        snapshot = list(_EXPERIMENTS)
    return [
        {
            "run_id": r["run_id"],
            "dataset_id": r["dataset_id"],
            "timestamp": r["timestamp"],
            "rows_scored": r["rows_scored"],
            "simulation_rate": r["simulation_rate"],
            "label_semantics": r.get("label_semantics"),
            "metrics": r.get("metrics", {}),
        }
        for r in reversed(snapshot)
    ]


@app.get("/experiments/{run_id}")
def experiments_get(run_id: str) -> dict[str, Any]:
    with _EXPERIMENTS_LOCK:
        snapshot = list(_EXPERIMENTS)
    for r in snapshot:
        if r.get("run_id") == run_id:
            return r
    raise HTTPException(status_code=404, detail={"error_message": f"unknown run_id {run_id!r}"})
