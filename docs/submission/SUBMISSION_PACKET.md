# Submission packet - IBM Z Datathon 2026

**Deadline:** 18/10/2026 22:00 IST &nbsp;·&nbsp; **Track:** Real-Time AI for Critical Decisions

This page maps each portal field to the finished artifact and lists what only a
human can do. Everything below was produced/verified in this session.

---

## A. Paste-ready text (1024-character fields)

Source of truth: `docs/submission/SUBMISSION_FORM_ANSWERS.md`
Verified lengths (`python scripts/check_submission_answers.py`): **1020/1024 max**.

| Portal field | Source section |
|---|---|
| What is the Problem you are trying to solve? | §1 |
| How are you planning to solve the problem? (Brief Overview) | §2 |
| How does your solution leverage IBM Z / LinuxONE technologies? | §3 |
| What value does your solution deliver, and who will benefit from it? | §4 |
| Link to all open-source resources used | §5 |

## B. Upload / link

| Portal field | Artifact |
|---|---|
| Upload your pitch deck in PDF format | `docs/submission/BLACKBOX_Pitch_Deck.pdf` (12 pages, ~18 KB, well under 5 MB) |
| Any other document (flowchart / architecture) | `docs/submission/BLACKBOX_Architecture_Diagram.pdf` (1 page) |
| Github Link / public Zip | **NEEDED** - see blockers |
| Video Submission Link (max 3 min) | **NEEDED** - record with `docs/submission/DEMO_SCRIPT.md` |

Rebuild the deck any time with: `python scripts/build_pitch_deck.py`

## C. Blockers only a human can clear

- [x] **Repository prepared locally.** The tree was initialized and one
      submission commit created (250 files, 10.5 MB) after your explicit
      go-ahead. Still needed: a remote URL + push auth (GitHub PAT or
      `gh auth login` / credential manager). Then:
      `git remote add origin <URL>` and `git push -u origin main`.
- [ ] **Public repository / zip URL.** Choose one: (a) create a GitHub repo and
      push the prepared commit, (b) upload a zip to a public host
      (Drive/Dropbox with "anyone with the link"), or (c) paste an existing URL.
      The portal requires `https://` and public accessibility.
- [ ] **Demo video** (<= 3 min, 720p/1080p) recorded and uploaded to YouTube or
      Vimeo, link opening without a sign-in request.
- [ ] **Deck upload** (or a public link if the upload is rejected).

## D. Local demo for the recording (Granite live)

```powershell
cd blackbox

# 1) IBM Granite narrate service (CPU, local; no data leaves the machine)
$env:LLM_SERVICE_MAX_TOKENS = "192"
.\.venv\Scripts\python.exe scripts\llm_service.py `
    --model "$env:TEMP\bbx_models\granite-4.2-3b-Q4_K_M.gguf"      # :38899

# 2) the app, pointed at the service
$env:BLACKBOX_LLM_URL = "http://127.0.0.1:38899/narrate"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 3) open http://127.0.0.1:8000/dashboard  -> BREAK MY DECISION
```

Expected: `NO_SIMULATION` certificate, score **0.516** (threshold 0.60), and the
**LLM Narrative (advisory)** card with a Granite-written explanation. CPU
generation is measured at **~30-80 s** depending on machine load - narrate over
it in the video ("on-platform inference costs latency, and that trade is
deliberate").

Honesty note for the video: the demo host is **AMD64**; say so. Never present an
x86 run as LinuxONE (the s390x evidence is a separate, labelled bundle).

## E. Honesty checklist (required by `docs/submission/DISCLOSURES.md`)

- [ ] Say the gate currently under-performs a simple anomaly baseline on
      validation recall.
- [ ] Say the weights and the 0.60 threshold are declared MVP parameters.
- [ ] Say the data is synthetic and the locked test split is unused.
- [ ] Say the LLM narrative is advisory only and never changes a decision.
- [ ] Label the recording host (AMD64 vs LinuxONE).
