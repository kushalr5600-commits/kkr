"""Build the BLACKBOX pitch deck PDF (IBM Z Datathon 2026 submission).

Pure reportlab (no matplotlib). Produces a 16:9, vector-only deck aimed at the
submission form's "pitch deck (PDF, <= 5 MB)" field, plus a standalone
architecture-diagram page for the "solution flowchart / architecture" field.

    python scripts/build_pitch_deck.py
    -> docs/submission/BLACKBOX_Pitch_Deck.pdf
    -> docs/submission/BLACKBOX_Architecture_Diagram.pdf
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)

OUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "submission"
PAGE = (13.333 * inch, 7.5 * inch)  # 16:9
MARGIN = 0.55 * inch

NAVY = HexColor("#0b1220")
DEEP = HexColor("#111c33")
ACCENT = HexColor("#22d3ee")
INK = HexColor("#0f172a")
BODY = HexColor("#1e293b")
MUTED = HexColor("#64748b")
CARD = HexColor("#f1f5f9")
LINE = HexColor("#cbd5e1")
OK = HexColor("#059669")

DECK_TITLE = "BLACKBOX - IBM Z Datathon 2026"


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title", fontName="Helvetica-Bold", fontSize=34, leading=38, textColor=INK
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName="Helvetica", fontSize=15, leading=20, textColor=ACCENT
        ),
        "h": ParagraphStyle(
            "h", fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=INK,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=13.5, leading=19, textColor=BODY,
        ),
        "bullet": ParagraphStyle(
            "bullet", fontName="Helvetica", fontSize=12.5, leading=18, textColor=BODY,
            leftIndent=14, bulletIndent=2, spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "small", fontName="Helvetica", fontSize=10.5, leading=15, textColor=MUTED,
        ),
        "mono": ParagraphStyle(
            "mono", fontName="Courier-Bold", fontSize=12.5, leading=17, textColor=DEEP,
        ),
    }


class Slide:
    """Collects the flowables for one slide and its heading."""

    def __init__(self, doc_flow: list, styles: dict, title: str, kicker: str = "") -> None:
        doc_flow.append(_Header(title, kicker, styles))
        doc_flow.append(Spacer(1, 16))
        self.flow = doc_flow
        self.s = styles

    def bullets(self, items: list[str]) -> None:
        for it in items:
            self.flow.append(Paragraph(it, self.s["bullet"], bulletText="\u2022"))

    def para(self, text: str, style: str = "body") -> None:
        self.flow.append(Paragraph(text, self.s[style]))

    def gap(self, pt: float = 8) -> None:
        self.flow.append(Spacer(1, pt))

    def end(self) -> None:
        self.flow.append(PageBreak())


class _Header(Flowable):
    def __init__(self, title: str, kicker: str, styles: dict) -> None:
        super().__init__()
        self.title = title
        self.kicker = kicker
        self.styles = styles
        self.width = PAGE[0] - 2 * MARGIN
        self.height = 52

    def wrap(self, aw: float, ah: float) -> tuple[float, float]:
        return self.width, self.height

    def draw(self) -> None:
        c = self.canv
        c.setFillColor(NAVY)
        c.rect(-MARGIN, 8, PAGE[0], 3, stroke=0, fill=1)
        c.setFillColor(ACCENT)
        c.rect(-MARGIN, 8, 120, 3, stroke=0, fill=1)
        if self.kicker:
            c.setFillColor(MUTED)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(0, 36, self.kicker.upper())
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 23)
        c.drawString(0, 12, self.title)


class Diagram(Flowable):
    """Vector architecture diagram (also exported as its own PDF)."""

    def __init__(self, width: float, height: float = 400, scale: float = 1.0) -> None:
        super().__init__()
        self.width = width
        self.height = height
        self.scale = scale

    def wrap(self, aw: float, ah: float) -> tuple[float, float]:
        return self.width, self.height

    def _box(
        self, c, x, y, w, h, title, lines, fill=CARD, edge=LINE, tcol=INK
    ) -> None:
        c.setFillColor(fill)
        c.setStrokeColor(edge)
        c.setLineWidth(1)
        c.roundRect(x, y, w, h, 6, stroke=1, fill=1)
        c.setFillColor(tcol)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawCentredString(x + w / 2, y + h - 15, title)
        c.setFont("Helvetica", 9)
        for i, ln in enumerate(lines):
            c.drawCentredString(x + w / 2, y + h - 28 - i * 11, ln)

    def _arrow(self, c, x1, y1, x2, y2, label="") -> None:
        c.setStrokeColor(MUTED)
        c.setLineWidth(1.2)
        c.line(x1, y1, x2, y2)
        # arrow head
        import math

        ang = math.atan2(y2 - y1, x2 - x1)
        for d in (2.6, -2.6):
            c.line(
                x2, y2,
                x2 - 9 * math.cos(ang - d * 0.18),
                y2 - 9 * math.sin(ang - d * 0.18),
            )
        if label:
            c.setFillColor(MUTED)
            c.setFont("Helvetica-Oblique", 8.5)
            c.drawCentredString((x1 + x2) / 2, (y1 + y2) / 2 + 4, label)

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        c.scale(self.scale, self.scale)
        W = self.width
        # Row 1: entry + gate
        self._box(c, 0, 320, 200, 62, "POST /analyze",
                  ["validate + load context", "synthetic sandbox"])
        self._box(c, 250, 320, 300, 62, "IMPACT GATE (ms)",
                  ["I = 0.45A + 0.30W + 0.15D + 0.10L",
                   "IsolationForest A - window/load W,L - graph D"],
                  fill=HexColor("#e0f2fe"), edge=ACCENT)
        self._arrow(c, 200, 351, 250, 351)

        # Row 2: branch
        self._box(c, 250, 205, 145, 62, "I < 0.60",
                  ["NO_SIMULATION", "ALLOW_NORMAL_PATH", "certificate issued"],
                  fill=HexColor("#dcfce7"), edge=OK)
        self._box(c, 430, 205, 300, 62, "I >= 0.60  ->  REALITY FORK",
                  ["baseline state graph", "fork: counterfactual branch"],
                  fill=HexColor("#fef9c3"), edge=HexColor("#eab308"))
        self._arrow(c, 400, 340, 400, 267, "score")
        self._arrow(c, 400, 267, 480, 267, "selected")

        # Row 3: crash test + fragility
        self._box(c, 430, 105, 300, 62, "CRASH TEST x 3",
                  ["3x_volume - fraud_spike - service_latency",
                   "normal + stress per scenario"])
        self._arrow(c, 580, 205, 580, 167)

        # Row 4: certificate
        self._box(c, 250, 10, 480, 62, "DECISION CERTIFICATE",
                  ["score - contributions (sum to score) - forks - outcomes",
                   "limitations - policy + model versions - REVIEW on failure"],
                  fill=HexColor("#e2e8f0"), edge=INK)
        self._arrow(c, 580, 105, 580, 72, "evidence")

        # Advisory LLM (right side)
        self._box(c, 770, 205, 110, 62, "IBM GRANITE",
                  ["advisory", "narrative only"],
                  fill=HexColor("#ede9fe"), edge=HexColor("#8b5cf6"))
        self._arrow(c, 730, 236, 770, 236, "explain")
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Oblique", 8.5)
        c.drawString(770, 196, "never changes scores/decisions")
        c.restoreState()


def _cover(flow: list, styles: dict) -> None:
    s = styles
    flow.append(Spacer(1, 40))
    flow.append(Paragraph("BLACKBOX", ParagraphStyle(
        "cover", fontName="Helvetica-Bold", fontSize=64, leading=66, textColor=INK)))
    flow.append(Spacer(1, 6))
    flow.append(Paragraph("Don't predict the future. Test it first.", s["subtitle"]))
    flow.append(Spacer(1, 20))
    flow.append(Paragraph(
        "A real-time <b>decision preflight engine</b>: a cheap, explainable Impact Gate "
        "decides which transactions deserve expensive counterfactual simulation, the "
        "selected cases are stress-tested, and every decision is committed with a "
        "verifiable <b>Decision Certificate</b>.", s["body"]))
    flow.append(Spacer(1, 22))
    flow.append(Paragraph(
        "<b>IBM Z Datathon 2026</b> &nbsp;|&nbsp; Track: <b>Real-Time AI for Critical "
        "Decisions</b><br/>Verified on IBM LinuxONE (s390x) &nbsp;|&nbsp; IBM Granite "
        "narrative on-platform &nbsp;|&nbsp; 100% open source", s["small"]))
    flow.append(Spacer(1, 14))
    flow.append(Paragraph(
        "Synthetic data - research prototype - the recommended action is a demo policy, "
        "not production authorization.", s["small"]))
    flow.append(PageBreak())


def build(path: Path, *, only_diagram: bool) -> None:
    styles = _styles()
    doc = BaseDocTemplate(
        str(path), pagesize=PAGE,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=0.7 * inch, bottomMargin=0.5 * inch,
        title=DECK_TITLE, author="BLACKBOX team",
    )

    def on_page(canv, _doc) -> None:
        canv.saveState()
        canv.setFillColor(MUTED)
        canv.setFont("Helvetica", 8.5)
        canv.drawString(MARGIN, 0.28 * inch, "BLACKBOX - decision preflight with evidence")
        canv.drawRightString(PAGE[0] - MARGIN, 0.28 * inch, f"{canv.getPageNumber()}")
        canv.restoreState()

    frame = Frame(MARGIN, 0.5 * inch, PAGE[0] - 2 * MARGIN, PAGE[1] - 1.2 * inch, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=on_page)])

    flow: list = []
    if only_diagram:
        flow.append(Paragraph("BLACKBOX - architecture and decision flow", styles["h"]))
        flow.append(Spacer(1, 8))
        flow.append(Diagram(PAGE[0] - 2 * MARGIN))
        doc.build(flow)
        return

    _cover(flow, styles)

    sl = Slide(flow, styles, "The problem", "01 / why this exists")
    sl.bullets([
        "Critical decisions - a payment authorization, a fraud block, a credit approval - "
        "must be made in <b>milliseconds</b> at immense volume.",
        "The tools that genuinely <b>test</b> a decision (counterfactual stress simulation, "
        "multi-scenario crash tests) are <b>too expensive</b> to run on every case.",
        "So which cases deserve expensive scrutiny is decided by hand-tuned rules or a raw "
        "risk score.",
        "Result: dangerous cases get skipped, safe cases burn scarce capacity, and afterwards "
        "the evidence behind a committed decision is <b>missing</b>.",
    ])
    sl.gap(6)
    sl.para("<b>The gap is not prediction. It is accountable, evidence-backed "
            "decision-making under load.</b>")
    sl.end()

    sl = Slide(flow, styles, "Our approach", "02 / two-speed decisions")
    sl.bullets([
        "<b>Score cheaply, simulate rarely, record everything.</b> A millisecond Impact Gate "
        "decides which cases are worth expensive simulation.",
        "Selected cases are tested, not predicted: counterfactual forks, three stress "
        "scenarios, and a <b>distance-to-failure</b> fragility search.",
        "Every decision - simulated or skipped - is committed with a <b>Decision "
        "Certificate</b> recording exactly what evidence existed.",
        "IBM Granite adds an <b>advisory</b> plain-language narrative; it never changes a "
        "score or a decision.",
    ])
    sl.gap(4)
    sl.para("Hardest step: the gate must be honest about its own limits - so we publish its "
            "blind spots and the MVP parameters.", "small")
    sl.end()

    sl = Slide(flow, styles, "How it works", "03 / architecture")
    sl.flow.append(Diagram(PAGE[0] - 2 * MARGIN, height=360, scale=0.9))
    sl.end()

    sl = Slide(flow, styles, "The Impact Gate", "04 / explainable by construction")
    sl.para("Active policy (human-authorized): "
            "<font name='Courier-Bold'>I = 0.45*A + 0.30*W + 0.15*D + 0.10*L</font>, "
            "simulate iff I &gt;= 0.60.", "mono")
    sl.gap(8)
    sl.bullets([
        "<b>M</b> magnitude - amount vs the account's own baseline (explainable statistic).",
        "<b>D</b> dependency - downstream exposure in the local graph (deterministic).",
        "<b>A</b> anomaly - IsolationForest score, empirical-CDF normalized (scikit-learn).",
        "<b>U</b> uncertainty - disagreement across the failure ensemble "
        "(RandomForest trees + XGBoost bootstrap models).",
        "<b>W / L</b> window and load pressure - dataset-context features.",
    ])
    sl.gap(4)
    sl.para("The frozen reference formula I = 0.30M + 0.30D + 0.25A + 0.15U remains "
            "implemented and contract-pinned; weights and threshold are declared MVP "
            "parameters, not claimed optimal.", "small")
    sl.end()

    sl = Slide(flow, styles, "The Decision Certificate", "05 / the evidence artifact")
    sl.bullets([
        "<b>Score and contributions</b> that always sum to the score - no opaque dump.",
        "<b>Forks tested</b> and per-scenario outcomes (normal vs stress).",
        "<b>Limitations</b> stated up front, plus policy version and model versions.",
        "<b>REVIEW</b> certificate on any internal failure - never a silent 'safe'.",
        "Rendered in the dashboard and exportable; the JSON is the source of truth.",
    ])
    sl.gap(6)
    sl.para("Empty fork table means <b>no simulation was run</b> - not 'safe under load'. "
            "That distinction is the whole point.", "small")
    sl.end()

    sl = Slide(flow, styles, "IBM Z / LinuxONE", "06 / running where decisions happen")
    sl.bullets([
        "<b>Verified on real s390x</b>: the full test suite, smoke tests and live HTTP run on "
        "a LinuxONE guest (Ubuntu 24.04.5); /health reports runtime:linuxone, "
        "architecture:s390x.",
        "<b>Cross-architecture reproducibility</b>: showcase gate scores are byte-identical "
        "between AMD64 and s390x.",
        "<b>Native s390x stack</b>: NumPy, scipy, scikit-learn and XGBoost compile from "
        "source on the guest; the app truthfully reports its active model backend.",
        "<b>Containerised on-platform</b>: the Docker image builds and runs natively on "
        "s390x from the s390x Python base image.",
        "<b>IBM Granite on-platform</b>: the narrative model runs locally on the guest - no "
        "transaction data leaves the environment.",
    ])
    sl.end()

    sl = Slide(flow, styles, "IBM Granite pairing", "07 / structured models + LLM reasoning")
    sl.bullets([
        "Structured models <b>decide</b>; Granite 4.2 3B (Apache-2.0, local via llama.cpp) "
        "<b>explains</b> the finished certificate in plain language.",
        "Rigorous one-way flow: certificate JSON -&gt; prompt -&gt; advisory text. The LLM "
        "never touches scores, the gate, or the certificate.",
        "Grounding by construction: the prompt carries only certificate facts and forbids "
        "inventing numbers.",
        "Honest degradation: if the model is unavailable, the UI says so - template text is "
        "never dressed up as LLM output.",
    ])
    sl.gap(4)
    sl.para("CPU latency is measured and disclosed (tens of seconds on 3 vCPU); the "
            "certificate stays authoritative.", "small")
    sl.end()

    sl = Slide(flow, styles, "Evidence (verified)", "08 / what we can actually claim")
    rows = [
        ("161/161 automated tests", "AMD64, CPython 3.12.10"),
        ("141/141 + smoke, live HTTP", "LinuxONE s390x guest"),
        ("Identical showcase scores", "AMD64 &lt;-&gt; s390x"),
        ("Docker image builds + runs on s390x", "native, from s390x base image"),
        ("Granite narrative live", "service /health loaded, certificate score unchanged"),
        ("Dataset SHA-256 pinned", "manifest verified"),
    ]
    for a, b in rows:
        sl.para(f"<b>{a}</b> &nbsp;&mdash;&nbsp; {b}", "bullet")
    sl.gap(4)
    sl.para("AMD64 results are never presented as LinuxONE results; each claim is labelled "
            "with its host.", "small")
    sl.end()

    sl = Slide(flow, styles, "Value & who benefits", "09 / impact")
    sl.bullets([
        "<b>Efficient scrutiny</b> - expensive simulation runs only where it can change an "
        "outcome.",
        "<b>Accountability</b> - a Decision Certificate is an audit trail a regulator can "
        "inspect.",
        "<b>Transparency</b> - contributions sum to the score, paired with an advisory "
        "Granite narrative.",
        "<b>Trustworthy by design</b> - known blind spots and MVP parameters are published.",
    ])
    sl.gap(4)
    sl.para("<b>Beneficiaries:</b> payments / fraud / lending operations reviewers on IBM Z; "
            "risk, compliance and audit teams; platform owners keeping AI inference inside the "
            "trusted environment; and the customers whose decisions hold up under peak load.")
    sl.end()

    sl = Slide(flow, styles, "Honesty as a feature", "10 / what we do not claim")
    sl.bullets([
        "The gate currently underperforms a simple anomaly baseline on failure recall at "
        "fixed budgets - documented, diagnosed, and kept visible.",
        "Weights and the 0.60 threshold are declared MVP parameters, not optimal ones.",
        "The fixed demo transaction is skipped by the gate - a known blind spot, shown on "
        "purpose.",
        "Synthetic data only; the locked evaluation split is deliberately unused.",
        "No claim in this deck is made without a labelled evidence bundle behind it.",
    ])
    sl.end()

    sl = Slide(flow, styles, "Next & links", "11 / submission")
    sl.bullets([
        "<b>Code</b> (public repository / zip) - see the submission form link.",
        "<b>Demo video</b> (max 3 min) - see the submission form link.",
        "<b>Architecture diagram</b> - BLACKBOX_Architecture_Diagram.pdf (also page 3 here).",
        "Roadmap: calibrate the gate on real (anonymised) workloads, wire certificates into "
        "existing audit systems, and validate graduate evolution on LinuxONE.",
    ])
    sl.gap(6)
    sl.para("Don't predict the future. Test it first.", "subtitle")
    sl.end()

    doc.build(flow)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    build(OUT_DIR / "BLACKBOX_Pitch_Deck.pdf", only_diagram=False)
    build(OUT_DIR / "BLACKBOX_Architecture_Diagram.pdf", only_diagram=True)
    for name in ("BLACKBOX_Pitch_Deck.pdf", "BLACKBOX_Architecture_Diagram.pdf"):
        p = OUT_DIR / name
        print(f"{name}: {p.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
