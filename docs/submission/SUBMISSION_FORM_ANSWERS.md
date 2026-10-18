# IBM Z Datathon 2026 — submission form answers (copy/paste)

Track selected: **Real-Time AI for Critical Decisions**
Limits: 1024 characters per text field. Counts below are verified by
`scripts/check_submission_answers.py`.

---

## 1. What is the Problem you are trying to solve?

Critical decisions — a payment authorization, a fraud block, a credit approval — must be made in milliseconds at immense volume. Yet the tools that genuinely TEST such a decision (counterfactual stress simulation, multi-scenario crash tests) are too expensive to run on every case. Operations teams therefore choose which cases deserve scarce scrutiny using hand-tuned rules or a raw risk score. The result: dangerous cases get skipped, safe cases burn simulation capacity, and afterwards nobody can produce the evidence behind a decision.

BLACKBOX (theme: Real-Time AI for Critical Decisions) closes the gap between a cheap prediction and an accountable decision. We do not try to predict the future; we test it first — spending expensive simulation only where it changes the decision, then issuing a verifiable evidence record at commit time.

This hurts payments, fraud and lending operations reviewers on IBM Z, and the risk and compliance teams who must defend those decisions.

---

## 2. How are you planning to solve the problem? (Brief Overview)

BLACKBOX is an open-source Python system (FastAPI, NumPy, scikit-learn, XGBoost) with a static HTML/JS dashboard, 161 automated tests and a container image.

1. IMPACT GATE — a fast deterministic score I = 0.45*A + 0.30*W + 0.15*D + 0.10*L (A = IsolationForest anomaly, W/L = window and load pressure, D = dependency-graph exposure). Only cases with I >= 0.60 proceed.
2. REALITY FORK + CRASH TEST — selected cases are simulated across three scenarios (3x_volume, fraud_spike, service_latency) on a local state graph; a fragility search measures distance to failure instead of predicting a label.
3. DECISION CERTIFICATE — immutable JSON: score, per-term contributions that always sum to the score, forks tested, scenario outcomes, limitations, policy and model versions.
4. IBM GRANITE NARRATIVE — an on-platform LLM writes an advisory plain-English explanation; it never changes a score or decision.

Honest scope: synthetic data, research prototype, declared MVP parameters — not production authorization.

---

## 3. How does your solution leverage IBM Z / LinuxONE technologies?

BLACKBOX is built to run where the decisions happen — on IBM Z / LinuxONE — not on a separate x86 cluster.

- Verified on real s390x: the full 161-test suite, smoke tests and live HTTP run on a LinuxONE guest (Ubuntu 24.04.5, s390x). /health reports runtime:linuxone, architecture:s390x, and showcase gate scores are byte-identical to AMD64 — cross-architecture reproducibility.
- Native s390x stack: NumPy, scipy, scikit-learn and XGBoost compile from source on the guest; the app truthfully reports its active model backend (numpy or sklearn).
- Containerised on-platform: the Docker image builds and runs natively on s390x from the s390x Python base image.
- IBM Granite on-platform: the Granite LLM narrative runs locally on the guest, so no transaction data leaves the environment.

Why it matters: scoring, simulation and explanation all stay inside the trusted platform — low latency, and Z's security, throughput and resilience extend to AI-driven decisions.

---

## 4. What value does your solution deliver, and who will benefit from it?

Value
- Efficient scrutiny: expensive simulation runs only on gate-selected cases, so compute goes where it matters.
- Accountability: every decision carries a Decision Certificate — score, contributing terms, scenarios tested, known limitations, versions — an audit trail a regulator can inspect.
- Transparency: contributions sum to the score, paired with an advisory Granite narrative; no opaque model dump is needed.
- Honest AI: known blind spots and MVP parameters are published, not hidden.

Who benefits
- Payments, fraud and lending reviewers on IBM Z: faster, more consistent preflight before irreversible settlement.
- Risk, compliance and audit teams: verifiable evidence, not after-the-fact rationalisation.
- Platform owners: real-time inference stays inside the trusted environment under peak load.
- End customers and businesses: decisions that hold up when load spikes.

The Impact Gate and certificate pattern generalises to any high-volume "score cheaply, simulate rarely, record everything" workflow.

---

## 5. Link to all open-source resources used

All components are open source; no proprietary runtime is required.

- Python 3.12, FastAPI (MIT), Uvicorn (BSD-3), Pydantic (MIT), Starlette (BSD-3)
- NumPy (BSD-3), scikit-learn (BSD-3), XGBoost (Apache-2.0)
- IBM Granite 4.2 3B model (Apache-2.0) + llama-cpp-python runtime (MIT)
- OpenTelemetry API/SDK (Apache-2.0, optional)
- pytest (MIT), httpx (BSD-3) — test-only

Repos: https://github.com/fastapi/fastapi · https://github.com/encode/uvicorn · https://github.com/pydantic/pydantic · https://numpy.org · https://scikit-learn.org · https://github.com/dmlc/xgboost · https://huggingface.co/ibm-granite/granite-4.2-3b · https://github.com/abetlen/llama-cpp-python · https://opentelemetry.io · https://github.com/pytest-dev/pytest · https://github.com/encode/httpx

Dataset: synthetic transaction data generated in-repo (seed 42); no third-party personal data.
