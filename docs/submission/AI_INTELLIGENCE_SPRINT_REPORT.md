# AI Intelligence Layer Implementation Sprint Report

**Date:** 2026-10-14  
**Status:** COMPLETE — local AMD64 **118 passed / 0 failed**; LinuxONE/s390x **NOT VERIFIED**  
**Frozen gate policy:** unchanged (`0.30M+0.30D+0.25A+0.15U`, threshold `0.60`, `POLICY_VERSION = "1.0.0"`).  
**Locked test:** never run.  
**Interaction ranking hit count in `backend/`:** 0 (unchanged).

---

## 1. Mission scope

| # | Mission item | Delivered |
|---|---|---|
| 1 | Inspect models | `backend/gate/models.py` + new `backend/intelligence/signals.py` |
| 2 | Expose real anomaly/risk outputs | `/explain` now returns `ai_signals` (raw A, calibrated A, ensemble U, model versions, caveats) |
| 3 | Signal-to-decision trace | `technical_detail` + `plain_language` + contribution table matching certificate score |
| 4 | AI & Risk Signals panel | Decision Explorer sidebar card (backend badge, provenance M/D/A/U, post-decision evidence, unknowns) |
| 5 | Challenge Lab false-negative research | `false_negative_analysis` on every `/datasets/{id}/evaluate` report |
| 6 | What-if workspace | `POST /research/what-if` + collapsible UI; research-only; rejects unsupported keys |
| 7 | Tests | 5 new unit/HTTP tests in `tests/unit/test_ai_intelligence.py` |
| 8 | Docs | This report + `OPEN_SOURCE_COMPONENTS.md` AI section + `DEBUG_LOG.md` |

---

## 2. Files changed / created

| Path | Change |
|---|---|
| `backend/intelligence/__init__.py` | package |
| `backend/intelligence/signals.py` | `explain_signals`, `what_if` (amount / transaction_type / historical avg+std only) |
| `backend/main.py` | `/explain` → `ai_signals`; `POST /research/what-if`; import |
| `backend/eval/benchmark.py` | `_false_negative_analysis` (FN-001 threshold gap, FN-002 score compare) |
| `frontend/static/index.html` | What-If Research Workspace (`RESEARCH ONLY` pill) |
| `frontend/static/app.js` | `renderAiPanel`, `runWhatIf` |
| `frontend/static/style.css` | `.whatif`, `.ai-panel` |
| `tests/unit/test_ai_intelligence.py` | 5 tests (real outputs, consistency, what-if isolation, HTTP, FN analysis) |
| `docs/submission/OPEN_SOURCE_COMPONENTS.md` | AI layer inventory (sklearn optional / numpy fallback; SHAP/Evidently **not** adopted) |
| `docs/DEBUG_LOG.md` | this sprint entry |

---

## 3. Architecture (read-only for the gate)

```
Transaction + account/graph/context
        │
        ▼
backend/gate/models.py  (AnomalyModel, RiskModel) ── fitted on calibration split only
        │
        ├──► ImpactGate (frozen) ──► DecisionCertificate (unchanged)
        │
        └──► backend/intelligence/signals.py
                    ├── explain_signals  →  /explain.ai_signals  →  AI & Risk panel
                    └── what_if          →  /research/what-if    →  What-If UI
```

- Anomaly: IsolationForest (sklearn) or Mahalanobis-distance (numpy); empirical CDF on calibration scores → A ∈ [0,1].  
- Uncertainty: bagged logistic / RF member probabilities → mean P(fail) + member std → U ∈ [0,1] via frozen `UNCERTAINTY_NORMALIZATION`.  
- **Anomaly score ≠ fraud probability.** Caveats say so explicitly.  
- **U is not calibrated confidence.** Caveats say so.  
- **NO_SIMULATION ≠ safe.** UI shows amber “Simulation skipped / stress outcome unknown.”

---

## 4. What-if research workspace

Allowed overrides only: `amount`, `transaction_type`, `historical_avg_amount`, `historical_std_amount`.  
Unsupported keys → `InputError` → HTTP 422 with `error_message`.  
Response always includes `research_only: true`, original vs hypothetical gates, score/A/U deltas, and a plain-language research note.  
The original transaction object is never mutated (test asserts amount unchanged).

---

## 5. Challenge Lab false-negative research

Every evaluate report now contains:

```json
"false_negative_analysis": {
  "available": true,
  "research_only": true,
  "finding_count": 0,
  "note": "No false negatives …",
  "never_changes_production_gate": true
}
```

When labeled positives were skipped by the gate:

- **FN-001** — max missed score vs threshold (descriptive).  
- **FN-002** — mean missed score vs mean selected-positive score (descriptive).  
- `finding_type: "descriptive"`, `validated: false`.  
- Sample-size limitation string when FN count < 5.  
- `dataset_sha256` always echoed for reproducibility.  
- **Never** feeds back into scoring.

---

## 6. Test evidence

| Suite | Result |
|---|---|
| Full local suite | **118 passed / 0 failed** (~47 s, numpy backend) |
| `tests/unit/test_ai_intelligence.py` | 5/5 PASS |
| Frozen phase-2 `results.json` hash | unchanged |
| Locked test | **NOT RUN** (policy) |

New tests cover:

1. Real anomaly + risk outputs, contribution sum == certificate score, provenance.  
2. Showroom TX-00300: `ai_signals.gate.score == cert.impact_score.score`.  
3. What-if isolation + InputError rejections.  
4. HTTP `/explain` has `ai_signals`; demo `simulation_executed=false`; `/research/what-if` 200/422.  
5. Challenge Lab FN analysis structure + research-only flags.

---

## 7. Honest limitations

| Item | Status |
|---|---|
| sklearn on host | **not installed** → numpy backend exercised |
| IsolationForest/RF sklearn path | code present; **not measured** this sprint |
| U calibration | ensemble disagreement only; **not** a probability |
| A semantics | anomaly ≠ fraud |
| What-if | research-only; **does not** re-run simulation forks |
| FN patterns | descriptive; **not** experimentally validated |
| LinuxONE / s390x | **NOT VERIFIED** (authorized window Oct 16) |
| Interactive video of AI panel | **NOT CAPTURED** |
| Locked test | **NOT RUN** |

---

## 8. Verdict / markers

```
AI_INTELLIGENCE_SPRINT: COMPLETE
LOCAL_AMD64: 118/118 PASS
LINUXONE_S390X: NOT VERIFIED
FROZEN_GATE: UNCHANGED
LOCKED_TEST: NOT RUN
RESEARCH_WHAT_IF: ISOLATED
FALSE_NEGATIVE_PATTERNS: DESCRIPTIVE_ONLY
```

**Overall project status:** LOCAL PROJECT COMPLETE — READY FOR TARGET VALIDATION  
Human-required items (media, organizer rules, certificate screenshots, T1 gate decision) remain open in `HUMAN_HANDOFF.md`.
