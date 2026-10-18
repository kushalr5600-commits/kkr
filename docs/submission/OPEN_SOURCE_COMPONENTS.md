# Open-source components — adopted inventory

**Date:** 2026-10-14  
**Policy:** Integrate only what reduces work or closes a reliability gap.  
Runtime vs test-only is strict. Frozen gate policy is unchanged.

Official license sources are the upstream project pages / PyPI metadata
linked below; re-check on the day of submission and note the access date in
`evidence/claims.md` if making a public claim.

---

## Adopted (this project already depends on them)

| Component | Version (host) | Purpose | Class | License | Official URL | s390x notes | Test evidence |
|---|---|---|---|---|---|---|---|
| FastAPI | 0.143.0 (clean venv) | HTTP API, OpenAPI, validation | **runtime** | MIT | https://github.com/fastapi/fastapi · https://pypi.org/project/fastapi/ | Pure Python + pydantic-core (Rust wheels; verify on guest) | `run_tests.py`, `smoke_test.py` HTTP, `tests/integration/test_http_api.py` |
| Uvicorn | 0.54.0 | ASGI server | **runtime** | BSD-3-Clause | https://github.com/encode/uvicorn · https://pypi.org/project/uvicorn/ | Pure Python + optional extras | live `uvicorn` on :8791 `/health` 200 (2026-10-14 clean venv) |
| Pydantic | 2.14.1 | Schema contract | **runtime** | MIT | https://github.com/pydantic/pydantic · https://pypi.org/project/pydantic/ | pydantic-core native; confirm wheel on s390x | contract tests |
| NumPy | 2.5.4 | Features, numpy models | **runtime** | BSD-3-Clause | https://github.com/numpy/numpy · https://pypi.org/project/numpy/ | Official s390x support historically; **verify on guest** | full suite numpy backend |
| scikit-learn | 1.9.1 | IsolationForest / RF (active backend) | **runtime** | BSD-3-Clause | https://scikit-learn.org · https://pypi.org/project/scikit-learn/ | May fail to build; fallback is numpy backend | published sklearn evidence is labeled separately |
| **httpx** | **0.28.1** | Starlette TestClient / HTTP integration | **test-only** | BSD-3-Clause | https://github.com/encode/httpx · https://pypi.org/project/httpx/ | Pure Python; install with test deps | `requirements-test.txt`; HTTP smoke PASS; `test_http_api.py` |
| pytest | (host) | Test runner | **test-only** | MIT | https://github.com/pytest-dev/pytest · https://pypi.org/project/pytest/ | Pure Python | full suite |

### New this sprint: explicit test dependency group

| File | Contents | Why |
|---|---|---|
| `requirements-test.txt` | `pytest>=8.0`, `httpx>=0.27` | Separates HTTP integration deps from production NumPy runtime |
| `requirements-dev.txt` | `-r requirements.txt` + `-r requirements-test.txt` | Single full-dev install for AMD64/CI |
| `requirements-numpy.txt` | fastapi, uvicorn, pydantic, numpy only | Lean production path without sklearn/test tools |

**httpx license:** BSD-3-Clause (upstream). Pure Python — low s390x risk.  
**Integration rationale:** Starlette/FastAPI TestClient requires httpx; without it
`smoke_test.py` used to SKIP HTTP. Full workflow now installs `requirements-test.txt`
and HTTP checks **PASS**. `BLACKBOX_REQUIRE_HTTP=1` turns missing HTTP stack into FAIL
for guest evidence runs.

### Optional observability (this sprint)

| File | Contents | Class | License | Notes |
|---|---|---|---|---|
| `requirements-observability.txt` | `opentelemetry-api`, `opentelemetry-sdk` | **optional** | Apache-2.0 | Behind `BLACKBOX_OTEL=1`; no-op without packages; no collector required |

`backend/shared/tracing.py` is a safe no-op when disabled or when packages are
absent. The core app **must** run with `BLACKBOX_OTEL` unset. OpenTelemetry was
**not** installed on the AMD64 host for this sprint; s390x wheels are
**UNVERIFIED** until Oct 16. Decision Certificates are **not** changed by OTel.

**Hypothesis:** not adopted (not installed; property-style tests use fixed cases).
Adding it would expand test-only surface without a demonstrated need.

### AI intelligence layer (this sprint)

| Component | Purpose | Class | License | Official URL | s390x notes | Test evidence |
|---|---|---|---|---|---|---|
| scikit-learn | IsolationForest (A) / Random Forest P(fail) std (U) — **active backend** since 2026-10-15 | **runtime** | BSD-3-Clause | https://scikit-learn.org | May fail to build; numpy fallback covers A/U | `tests/unit/test_ai_intelligence.py`; `docs/submission/SKLEARN_BACKEND_SWITCH_REPORT.md` |
| NumPy | Mahalanobis-like anomaly + bagged logistic risk + empirical CDF calibration — **fallback backend** | **runtime** | BSD-3-Clause | https://numpy.org | Official s390x support historically | same suite, numpy backend |
| SHAP / Evidently | **NOT adopted** | — | — | — | — | Explainer uses hand-engineered contributions + research what-if; no opaque model dump required |

The AI layer (`backend/intelligence/signals.py`) only **reads** gate model
outputs (`backend/gate/models.py`). It never mutates the frozen Impact Gate
formula or Decision Certificate. Research what-if is a pure function of the
current request + overrides; production state is untouched.

---

## Rejected / deferred (do not add)

| Candidate | Decision | Reason |
|---|---|---|
| NetworkX | **DEFER** | Custom BFS already sufficient; risk of changing D floats (`docs/OPEN_SOURCE_COMPONENT_ASSESSMENT.md`) |
| New frontend frameworks / CDNs | **REJECT** | Offline demo; current static HTML/JS is enough |
| Structured logging libs (structlog, etc.) | **REJECT for now** | Existing `diagnostics.py` is adequate; extra dep cost |
| Hypothesis | **DEFER** | Compatible test-only, but not required; keep suite lean |
| OTel in production requirements | **REJECT** | Optional only; core must work without it |
| Frictionless | **DEFER** | Not installed; Dataset Studio uses built-in CSV validation + Pydantic mapping |
| Evidently | **DEFER** | Not installed; Challenge Lab metrics computed in-repo |
| SHAP / AI Explainability 360 | **REJECT for gate** | Frozen ImpactGate uses direct mathematical explanation (`backend/explain/explainer.py`) |
| OpenML client | **OPTIONAL, not installed** | Registry metadata + local upload path works without it (`openml_package_installed: false`) |
| pandas (already present on host) | **optional for Parquet only** | CSV path is stdlib; Parquet import fails closed without pandas |

### Advanced prototype sprint (Dataset Studio)

| File | Contents | Class |
|---|---|---|
| *(none new required)* | Dataset Studio uses stdlib `csv` + existing numpy/pydantic; Parquet optional via host pandas | runtime unchanged |
| Frictionless / OpenML / Evidently | **not added** to requirements | optional / deferred |

---

## Verification status labels

| Item | Label |
|---|---|
| httpx as test-only dep + HTTP tests on AMD64 | **VERIFIED** (this host) |
| NumPy-only runtime without httpx/sklearn | **VERIFIED** (clean venv 2026-10-14) |
| OTel optional no-op path (package absent) | **VERIFIED** (unit tests; package not installed) |
| Native wheels on s390x (pydantic-core, numpy, otel) | **UNVERIFIED** until Oct 16 guest |
| LinuxONE execution | **NOT VERIFIED** |

**STOP.** No interaction ranking merge. No frozen policy change. No locked test.
