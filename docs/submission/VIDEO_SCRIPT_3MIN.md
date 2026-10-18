# BLACKBOX - 3-minute demo video script (shot list + narration)

**Target: <= 180 s.** Record on the machine you actually demo on and **say which
host it is** (this script assumes an **AMD64 laptop**; the s390x evidence is a
separate labelled bundle). 720p/1080p, upload to YouTube/Vimeo.

Everything you say here is backed by `docs/submission/DISCLOSURES.md`. Do not
skip the honesty lines - they are a scoring strength, not a weakness.

---

## Before you hit record (5 minutes of prep)

```powershell
cd blackbox

# terminal 1 - IBM Granite narrate service, local (CPU, no torch)
$env:LLM_SERVICE_MAX_TOKENS = "192"
.\.venv\Scripts\python.exe scripts\llm_service.py `
    --model "$env:TEMP\bbx_models\granite-4.2-3b-Q4_K_M.gguf"      # :38899
# wait until:  curl -s http://127.0.0.1:38899/health   ->  "loaded": true

# terminal 2 - the app, pointed at the service
$env:BLACKBOX_LLM_URL = "http://127.0.0.1:38899/narrate"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Readiness (must all be true before recording):

- [ ] `/health` shows `status ok`, `gate_threshold 0.60`, `policy_version 1.0.0`.
- [ ] Browser open at `http://127.0.0.1:8000/dashboard`, sidebar shows 5 tabs.
- [ ] **Warm the model**: do one throwaway `BREAK MY DECISION` click and let the
      narrative finish, so the first cold generation is not in the video.
- [ ] Window at 1080p or larger; hide the taskbar; close chat apps.
- [ ] If the Granite service is NOT up, do not fake it - record the honest
      "Narrative unavailable: ..." card instead and say why.

---

## 0:00 - 0:15 | Problem + hook

**On screen:** the dashboard, runtime chip visible top-right.

> "Critical decisions - a payment authorization, a fraud block - are made in
> milliseconds. But the tools that would actually *test* a decision are far too
> expensive to run on every case. So teams route by hand-tuned rules, and the
> evidence behind a decision is missing.
> BLACKBOX closes that gap: **don't predict the future - test it first.**"

## 0:15 - 0:45 | The normal path (and what it does NOT mean)

**Action:** click **BREAK MY DECISION** (TX-DEMO-0001 is pre-selected).

**On screen:** Decision Certificate appears - `NO_SIMULATION`,
`ALLOW_NORMAL_PATH`, score **0.516**, threshold marker **0.60**.

> "The Impact Gate scored this in milliseconds: 0.516, below the 0.60 threshold,
> so no simulation ran. Look at the fork table - it is **empty**. That means no
> stress test was executed - *not* 'safe under load'. That distinction is the
> whole product."

## 0:45 - 1:20 | The decision that needs evidence

**Action:** in the left list, pick the transaction whose hint reads
**"Gate selects it; fails a stress test"** (showcase id TX-00154 - trust the hint
from `GET /transactions`, ids are backend-dependent). Click **BREAK MY DECISION**.

**On screen:** the certificate with forks tested: `3x_volume`, `fraud_spike`,
`service_latency`, normal vs stress outcomes, and the fragility margin.

> "Here the gate selected it, so it *was* tested - three stress scenarios on a
> local state graph, plus a fragility search for the **distance to failure**.
> The certificate records the score, every contribution - which always sums to
> the score - the scenarios, the limitations, and the policy and model versions."

## 1:20 - 2:05 | IBM Granite, on-platform (the pairing)

**Action:** on the same result, scroll to the **LLM NARRATIVE (ADVISORY)** card.
If it is empty because you just triggered a fresh run, show the warmed one.

> "Structured models decide; **IBM Granite explains**. This narrative is
> generated **locally** - Granite 4.2 3B through llama.cpp, on CPU, no data
> leaving the machine.
> The flow is one-way: the certificate goes in, text comes out. **The LLM never
> touches a score or a decision** - the certificate stays authoritative."

**If you need a jump cut** (CPU generation takes roughly 30-80 s), cut here and
put a caption on screen: *"local CPU inference, ~1 min - cut for time"*. Say it
out loud too; the latency is a disclosed trade-off of keeping inference
on-platform, not a hidden failure.

## 2:05 - 2:35 | It runs on IBM Z / LinuxONE

**On screen:** the s390x `/health` JSON and the container check from
`evidence/capture/` (or the LINUXONE_VALIDATION_REPORT page).

> "This is not an x86 story with a Z sticker. The full test suite, smoke tests
> and live HTTP run on a real LinuxONE guest - s390x, Ubuntu 24.04. **`/health`
> reports `runtime: linuxone`**, and the showcase gate scores are
> **byte-identical** between AMD64 and s390x. NumPy, scipy, scikit-learn and
> XGBoost compile from source on the guest, and the Docker image builds and runs
> natively on s390x."

## 2:35 - 3:00 | Honesty + value + close

**On screen:** the contributions panel and the footer `model_versions`.

> "Two things we will not hide: the gate currently **under-performs a simple
> anomaly baseline** on validation recall, and the weights and the 0.60
> threshold are **declared MVP parameters**, not claimed optimal. The data is
> synthetic and our locked test split is deliberately unused.
> What you get is a pattern that generalises: **score cheaply, simulate rarely,
> record everything** - so expensive AI compute lands where it changes a
> decision, and every commitment carries evidence a regulator can inspect."

---

## Do-not-say list

- Do not call the demo host "LinuxONE". Say AMD64; s390x is separate evidence.
- Do not claim the gate is better than the baselines.
- Do not claim production readiness or real customer data.
- Do not present the narrative as anything other than advisory.
