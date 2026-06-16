"""Build the capstone defense deck (16:9 PowerPoint) from the IE design system.

Generates ``deck/capstone_defense.pptx``: an on-brand, editable ~18-slide talk that
reuses the thesis figures and the poster palette. Equations are rendered crisply with
matplotlib mathtext into ``deck/_eq_*.png`` so they stay sharp at any zoom.

Run:  .venv/Scripts/python scripts/build_deck.py
"""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
DECK = ROOT / "deck"
DECK.mkdir(exist_ok=True)

# ---- brand palette (matches poster/design-system.css) ----
NAVY = RGBColor(0x0E, 0x2A, 0x52)
NAVY2 = RGBColor(0x1F, 0x3B, 0x63)
GOLD = RGBColor(0xE6, 0x9F, 0x00)
RUST = RGBColor(0xB3, 0x40, 0x2F)
SAGE = RGBColor(0x4A, 0x7C, 0x59)
INK = RGBColor(0x16, 0x20, 0x2E)
MUTED = RGBColor(0x5B, 0x66, 0x75)
LINE = RGBColor(0xD9, 0xDE, 0xE6)
TINT = RGBColor(0xF3, 0xF6, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CLOUD = RGBColor(0xCD, 0xD6, 0xE4)

SERIF = "Georgia"          # display / titles (universally present on Windows)
SANS = "Segoe UI"          # body / UI

EMU_IN = 914400
SW, SH = 13.333, 7.5       # 16:9 widescreen inches

prs = Presentation()
prs.slide_width = Inches(SW)
prs.slide_height = Inches(SH)
BLANK = prs.slide_layouts[6]


# ----------------------------------------------------------------------------- helpers
def _set_bg(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def _rect(slide, x, y, w, h, color, line=None, line_w=0.75):
    sp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sp.fill.solid()
    sp.fill.fore_color.rgb = color
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(line_w)
    sp.shadow.inherit = False
    return sp


def _oval(slide, x, y, d, color):
    sp = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    sp.fill.solid()
    sp.fill.fore_color.rgb = color
    sp.line.fill.background()
    sp.shadow.inherit = False
    return sp


def _text(slide, x, y, w, h, runs, *, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
          space_after=6, line_spacing=1.06):
    """runs: list of paragraphs; each paragraph is a list of (text, font, size, color, bold)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space_after)
        p.space_before = Pt(0)
        p.line_spacing = line_spacing
        for (txt, font, size, color, bold) in para:
            r = p.add_run()
            r.text = txt
            r.font.name = font
            r.font.size = Pt(size)
            r.font.color.rgb = color
            r.font.bold = bold
    return tb


def _bullets(slide, x, y, w, h, items, *, size=18, gap=10, color=INK, lead=None):
    """items: list of (text, color_or_None, bold). Renders gold-dot bullets."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)
    first = True
    if lead:
        p = tf.paragraphs[0]
        first = False
        p.space_after = Pt(gap + 2)
        p.line_spacing = 1.12
        r = p.add_run(); r.text = lead
        r.font.name = SANS; r.font.size = Pt(size + 3); r.font.bold = True; r.font.color.rgb = NAVY
    for (txt, col, bold) in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(gap)
        p.space_before = Pt(0)
        p.line_spacing = 1.12
        rd = p.add_run(); rd.text = "●  "
        rd.font.name = SANS; rd.font.size = Pt(size - 4); rd.font.color.rgb = GOLD; rd.font.bold = True
        rt = p.add_run(); rt.text = txt
        rt.font.name = SANS; rt.font.size = Pt(size)
        rt.font.color.rgb = col or color; rt.font.bold = bold
    return tb


def _pic(slide, path, x, y, *, w=None, h=None, max_w=None, max_h=None, center_x=None):
    """Place an image preserving aspect. Provide w or h, or a max box (max_w,max_h)."""
    iw, ih = Image.open(path).size
    ar = iw / ih
    if max_w and max_h:
        if max_w / max_h > ar:
            h = max_h; w = max_h * ar
        else:
            w = max_w; h = max_w / ar
    elif w and not h:
        h = w / ar
    elif h and not w:
        w = h * ar
    if center_x is not None:
        x = center_x - w / 2
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))


def _title_bar(slide, title, num):
    _rect(slide, 0, 0, SW, 1.04, NAVY)
    _rect(slide, 0, 1.04, SW, 0.06, GOLD)
    # number badge
    _oval(slide, 0.5, 0.27, 0.5, GOLD)
    _text(slide, 0.5, 0.27, 0.5, 0.5, [[(str(num), SERIF, 22, NAVY, True)]],
          align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    _text(slide, 1.2, 0.0, SW - 2.4, 1.04, [[(title, SERIF, 27, WHITE, True)]],
          anchor=MSO_ANCHOR.MIDDLE)


def _footer(slide, num):
    _rect(slide, 0.5, SH - 0.42, SW - 1.0, 0.012, LINE)
    _text(slide, 0.5, SH - 0.40, 8.0, 0.34,
          [[("Spatial correlation & carbon-aware DRO scheduling", SANS, 10, MUTED, False)]],
          anchor=MSO_ANCHOR.MIDDLE)
    _text(slide, SW - 2.5, SH - 0.40, 2.0, 0.34,
          [[("M. Ortiz Togashi  ·  " + str(num), SANS, 10, MUTED, False)]],
          align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)


def content(title, num):
    s = prs.slides.add_slide(BLANK)
    _set_bg(s, WHITE)
    _title_bar(s, title, num)
    _footer(s, num)
    return s


# ----------------------------------------------------------------------------- equations
def render_eq(tex, name, *, size=30, color="#0E2A52"):
    out = DECK / f"_eq_{name}.png"
    fig = plt.figure(figsize=(0.1, 0.1))
    fig.text(0.0, 0.0, f"${tex}$", fontsize=size, color=color)
    fig.savefig(out, dpi=300, transparent=True, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    return out


EQ_DRO = render_eq(
    r"\min_{x \in \mathcal{X}}\ \langle \bar{\rho},\, x \rangle \;+\; "
    r"\varepsilon\, \| L^{\top} x \|_2 \qquad LL^{\top} = \hat{\Sigma}", "dro")
EQ_BOUND = render_eq(
    r"| \mathrm{OPT}(\Sigma) - \mathrm{OPT}(\Sigma_{\mathrm{shuf}}) |"
    r"\;\leq\; \varepsilon\, \max\|x\|\, \sqrt{\,\|\Sigma_{\mathrm{off}}\|\,}", "bound", size=26)

# =============================================================================== SLIDES

# ---- 1. Title ----
s = prs.slides.add_slide(BLANK)
_set_bg(s, NAVY)
_rect(s, 0, 0, 0.28, SH, GOLD)               # gold spine
# white IE logo if available
logo = ROOT / "poster" / "figs" / "ie_logo_white.png"
if logo.exists():
    _pic(s, logo, 0.95, 0.72, w=2.0)
_text(s, 0.95, 2.62, 11.7, 2.2, [
    [("Does Spatial Correlation of Carbon Intensity", SERIF, 29, WHITE, True)],
    [("Improve Robust Carbon-Aware Data-Center Scheduling?", SERIF, 29, WHITE, True)],
], line_spacing=1.04, space_after=8)
_rect(s, 1.0, 4.78, 3.2, 0.05, GOLD)
_text(s, 0.95, 4.98, 11.4, 0.8,
      [[("A multi-grid falsification study: a causal mechanism, a copula test, "
         "and an active-transfer extension", SANS, 17, CLOUD, False)]])
_text(s, 0.95, 6.15, 11.0, 1.1, [
    [("Marco Ortiz Togashi", SANS, 17, WHITE, True),
     ("    ·    IE University  ·  MSc Business Analytics & Data Science", SANS, 15, CLOUD, False)],
    [("Supervisor: Prof. Bissan Ghaddar", SANS, 15, CLOUD, False)],
], space_after=4)

# ---- 2. Motivation ----
s = content("Data centers can move their work", 2)
_bullets(s, 0.7, 1.5, 6.0, 5.0, [
    ("Compute is unusually flexible: batch and AI-training jobs can shift in time "
     "and across sites.", None, False),
    ("Carbon intensity of electricity varies sharply by hour and by region.", None, False),
    ("So a scheduler can defer work to cleaner moments, cutting emissions for free.", None, False),
    ("Recent work makes this robust: model carbon as uncertain inside a "
     "distributionally robust optimization (DRO).", None, False),
], size=19, gap=16, lead="The opportunity")
_pic(s, FIG / "correlation_map.png", 7.0, 1.7, max_w=5.7, max_h=4.6)
_text(s, 7.0, 6.35, 5.7, 0.4, [[("Regional carbon intensity is spatially structured.",
      SANS, 12, MUTED, False)]], align=PP_ALIGN.CENTER)

# ---- 3. The idea on trial ----
s = content("The idea on trial", 3)
_bullets(s, 0.7, 1.6, 11.9, 4.8, [
    ("A natural next step: treat carbon intensity as a stochastic vector across "
     "coupled regions, not one region at a time.", None, False),
    ("Then spatial correlation between regions could inform the robust schedule.", None, False),
    ("Intuition: if neighbouring grids move together, a robust scheduler should be "
     "able to exploit that joint structure.", None, False),
], size=21, gap=18, lead="What if regions move together?")
_rect(s, 0.7, 5.55, 11.9, 1.15, TINT)
_text(s, 1.0, 5.62, 11.3, 1.0, [[(
    "This thesis asks one question: does that spatial structure actually carry any "
    "robust scheduling value?", SERIF, 20, NAVY, True)]], anchor=MSO_ANCHOR.MIDDLE)

# ---- 4. The gap ----
s = content("The gap in prior work", 4)
_bullets(s, 0.7, 1.6, 11.9, 4.5, [
    ("Existing carbon-aware DRO models treat each region in isolation: per-region "
     "marginal uncertainty only.", None, False),
    ("The cross-region dependence is never put on trial for scheduling value.", None, False),
    ("It is simply assumed to help, or ignored. Nobody has tested it directly.", None, False),
], size=21, gap=18, lead="Regions are modelled one at a time")
_rect(s, 0.7, 5.5, 11.9, 1.2, NAVY)
_text(s, 1.0, 5.56, 11.3, 1.05, [[(
    "We build the joint-covariance model, then design a test that can falsify its value.",
    SERIF, 20, WHITE, True)]], anchor=MSO_ANCHOR.MIDDLE)

# ---- 5. Research questions ----
s = content("Research questions", 5)
_rect(s, 0.7, 1.55, 11.9, 2.35, TINT)
_rect(s, 0.7, 1.55, 0.14, 2.35, SAGE)
_text(s, 1.1, 1.7, 11.0, 0.6, [[("RQ1   Is the spatial premise valid?", SERIF, 24, NAVY, True)]])
_text(s, 1.1, 2.45, 11.0, 1.3, [[(
    "Is carbon intensity genuinely correlated across the regions we study, so the "
    "joint model has something real to exploit?", SANS, 19, INK, False)]])
_rect(s, 0.7, 4.2, 11.9, 2.35, TINT)
_rect(s, 0.7, 4.2, 0.14, 2.35, RUST)
_text(s, 1.1, 4.35, 11.0, 0.6, [[("RQ2   Does spatial structure pay?", SERIF, 24, NAVY, True)]])
_text(s, 1.1, 5.1, 11.0, 1.3, [[(
    "Does scheduling to the joint covariance beat scheduling to the marginals alone, "
    "measured by out-of-sample tail risk?", SANS, 19, INK, False)]])

# ---- 6. Method: the model ----
s = content("Method 1: the robust model", 6)
_bullets(s, 0.7, 1.5, 6.1, 4.6, [
    ("Mahalanobis–Wasserstein DRO: hedge against carbon distributions close to "
     "the data in a covariance-aware metric.", None, False),
    ("It reduces to a second-order cone program (SOCP), solved exactly and fast.", None, False),
    ("ε sets the robustness radius; Σ̂ carries the spatial structure "
     "through L.", None, False),
], size=18, gap=15, lead="DRO as a second-order cone program")
_rect(s, 7.0, 2.2, 5.7, 1.5, TINT)
_pic(s, EQ_DRO, 7.0, 2.55, max_w=5.4, max_h=0.95, center_x=9.85)
_text(s, 7.0, 4.05, 5.7, 1.8, [[(
    "The covariance Σ̂ enters only through the cone term ε‖Lᵀx‖. "
    "Destroy the cross-region part of Σ̂ and we get a clean control.",
    SANS, 16, MUTED, False)]])

# ---- 7. Method: the falsification test ----
s = content("Method 2: the falsification test", 7)
_bullets(s, 0.7, 1.45, 6.1, 5.0, [
    ("Fit the schedule to the full joint covariance.", None, False),
    ("Refit it to a block-diagonal covariance: identical marginals, cross-region "
     "structure destroyed (shuffled).", None, False),
    ("Score both on out-of-sample CVaR₀.₉₅ of daily emissions.", None, False),
    ("Pre-registered. If spatial structure matters, the joint schedule must win.",
     NAVY, True),
], size=18, gap=14, lead="Shuffled marginals")
_pic(s, FIG / "schedule_us_west.png", 7.0, 1.6, max_w=5.7, max_h=4.6)
_text(s, 7.0, 6.3, 5.7, 0.4, [[(
    "Joint vs shuffled schedules, side by side.", SANS, 12, MUTED, False)]],
    align=PP_ALIGN.CENTER)

# ---- 8. Data ----
s = content("Data: three grids across the spectrum", 8)
_bullets(s, 0.7, 1.5, 6.1, 4.8, [
    ("US West: a strongly, uniformly correlated grid (common-mode).", None, False),
    ("Eastern Interconnection belt: an Ontario-anchored mid-correlation set.", None, False),
    ("Engineered solar / wind / hydro portfolio: low, heterogeneous correlation.", None, False),
    ("Iberia–France: an independent low-correlation anchor.", None, False),
], size=18, gap=14, lead="Real Electricity Maps carbon intensity")
_pic(s, FIG / "correlation_map.png", 7.0, 1.7, max_w=5.7, max_h=4.5)
_text(s, 7.0, 6.25, 5.7, 0.4, [[(
    "Chosen to span weak → strong spatial dependence.", SANS, 12, MUTED, False)]],
    align=PP_ALIGN.CENTER)

# ---- 9. RQ1 result ----
s = content("RQ1: the spatial premise is valid", 9)
_pic(s, FIG / "ci_corr_heatmap_us_west.png", 0.7, 1.55, max_w=7.4, max_h=4.9)
_bullets(s, 8.4, 1.7, 4.3, 4.6, [
    ("Cross-region correlation is real and strong, up to 0.78 on the US West.", SAGE, True),
    ("It is stable across hours and seasons.", None, False),
    ("So the joint model is not fighting a strawman: there is genuine structure to "
     "exploit.", None, False),
], size=18, gap=16, lead="Correlation is real")

# ---- 10. RQ2 result: the null ----
s = content("RQ2: a replicated null", 10)
_pic(s, FIG / "finding.png", 0.7, 1.5, max_w=12.0, max_h=3.7)
_rect(s, 0.7, 5.45, 11.9, 1.25, NAVY)
_text(s, 1.0, 5.5, 11.3, 1.15, [[(
    "The spatial gap never exceeds a few tenths of one percent. Joint and shuffled "
    "schedules coincide out of sample, on every grid.", SERIF, 20, WHITE, True)]],
    anchor=MSO_ANCHOR.MIDDLE)

# ---- 11. Robustness ----
s = content("The null is genuinely robust", 11)
_bullets(s, 0.7, 1.5, 6.1, 4.8, [
    ("Shrinkage and residualization of the covariance.", None, False),
    ("Benjamini–Hochberg correction across all cells.", None, False),
    ("Walk-forward out-of-sample validation, tighter-ramp sensitivity.", None, False),
    ("Multi-seed stability: the single-seed crossovers were scenario noise.", None, False),
    ("TOST equivalence: statistically equivalent, not merely not-significant.",
     NAVY, True),
], size=17, gap=12, lead="A pre-registered battery")
_pic(s, FIG / "robustness.png", 7.0, 1.7, max_w=5.7, max_h=4.6)

# ---- 12. Mechanism 1 ----
s = content("Mechanism 1: the mean dominates", 12)
_bullets(s, 0.7, 1.5, 6.1, 4.6, [
    ("Flatten the mean carbon field and the joint covariance suddenly pays, up to "
     "+1.46%.", RUST, True),
    ("So the spatial signal is real, but masked: dwarfed by the diurnal mean.", None, False),
    ("The schedule chases the big mean valley; the covariance is a ripple on top.",
     None, False),
], size=18, gap=15, lead="Mean-ablation (causal)")
_rect(s, 7.0, 1.7, 5.7, 4.5, TINT)
_text(s, 7.25, 1.95, 5.2, 4.1, [
    [("Why this happens", SERIF, 19, NAVY, True)],
    [("Carbon intensity is driven overwhelmingly by the time-of-day mean (solar, "
      "demand). That signal is shared, predictable, and huge.", SANS, 16, INK, False)],
    [("The cross-region covariance is a second-order wrinkle on a first-order wave, "
      "so it cannot move the optimal schedule.", SANS, 16, INK, False)],
], space_after=12)

# ---- 13. Mechanism 2 ----
s = content("Mechanism 2: the wrong object", 13)
_pic(s, FIG / "tail_dependence_taskc.png", 0.7, 1.55, max_w=7.2, max_h=4.9)
_bullets(s, 8.0, 1.7, 4.7, 4.8, [
    ("Residual dependence is non-elliptical: regions go clean together more than "
     "dirty together (χ_L > χ_U).", None, False),
    ("A covariance ball forces χ_L = χ_U by construction.", None, False),
    ("So an elliptical ambiguity set is the wrong object, blind to the only "
     "structure that is left.", NAVY, True),
], size=17, gap=14, lead="Tail dependence (structural)")

# ---- 14. Phase 2 ----
s = content("Foreclosing the rebuttal: copulas", 14)
_pic(s, FIG / "copula_result.png", 0.7, 1.5, max_w=7.2, max_h=4.9)
_bullets(s, 8.0, 1.7, 4.7, 4.8, [
    ("“Maybe covariance is just the wrong model.” We test richer ones.", None, False),
    ("Gaussian, lower-tail Clayton, and the maximal comonotone copula.", None, False),
    ("All leave the null intact; an a-priori bound caps the achievable gain.", SAGE, True),
], size=18, gap=15, lead="Richer dependence, same null")

# ---- 15. What it means ----
s = content("What the null means", 15)
_rect(s, 0.7, 1.55, 11.9, 2.2, TINT)
_rect(s, 0.7, 1.55, 0.14, 2.2, SAGE)
_text(s, 1.1, 1.75, 11.2, 1.9, [
    [("Per-region marginal schedulers capture essentially all the value.", SERIF, 23, NAVY, True)],
    [("Modelling the joint distribution adds complexity and solve time for no robust "
      "scheduling benefit.", SANS, 18, INK, False)],
], space_after=10)
_rect(s, 0.7, 4.05, 11.9, 2.2, NAVY)
_text(s, 1.1, 4.25, 11.2, 1.9, [
    [("Spatial value, if any, lives in an active transfer channel.", SERIF, 23, WHITE, True)],
    [("Not in a richer passive dependence model, but in actually moving load between "
      "regions. That is Phase 3.", SANS, 18, CLOUD, False)],
], space_after=10)

# ---- 16. Limitations ----
s = content("Limitations, stated honestly", 16)
_bullets(s, 0.7, 1.5, 11.9, 4.9, [
    ("Correlated grids are a best-case stress test: compute shifting is logical (over "
     "the network), not electrical, so we hand the joint model its best shot.", None, False),
    ("Results are specific to the grids and the study period; carbon series evolve.", None, False),
    ("CVaR₀.₉₅ is one risk measure; the mean-dominance mechanism, though, "
     "is measure-agnostic.", None, False),
    ("The transfer-channel result (Phase 3) is preliminary and deterministic.", None, False),
], size=19, gap=16, lead="Where the result could be pushed")

# ---- 17. Conclusions ----
s = content("Conclusions & contributions", 17)
_bullets(s, 0.7, 1.5, 11.9, 4.9, [
    ("A pre-registered falsification test for the scheduling value of spatial carbon "
     "structure.", None, False),
    ("A replicated null across the full dependence spectrum, with multi-seed and "
     "equivalence backing.", None, False),
    ("The mechanism: the diurnal mean dominates, and the residual dependence is "
     "non-elliptical, so covariance is both subordinate and the wrong object.", None, False),
    ("A clear, honest negative result that redirects effort to the active transfer "
     "channel.", NAVY, True),
], size=19, gap=15, lead="What this thesis delivers")

# ---- 18. Future work + thanks ----
s = prs.slides.add_slide(BLANK)
_set_bg(s, NAVY)
_rect(s, 0, 0, 0.28, SH, GOLD)
_text(s, 0.95, 0.9, 11.4, 1.0, [[("Future work, and thank you", SERIF, 32, WHITE, True)]])
_rect(s, 0.95, 1.78, 2.6, 0.05, GOLD)
_pic(s, FIG / "part3_preliminary.png", 0.95, 2.15, max_w=7.3, max_h=3.8)
_text(s, 8.5, 2.15, 4.2, 0.5, [[("Where the value actually is", SANS, 19, GOLD, True)]])
_bullets(s, 8.5, 2.75, 4.2, 3.4, [
    ("Phase 3: the active transfer channel, where moving load shows 4–10% "
     "deterministic value.", CLOUD, False),
    ("Stochastic and online versions of that channel.", CLOUD, False),
], size=16, gap=14, color=CLOUD)
_text(s, 0.95, 6.4, 11.4, 0.8, [[(
    "Thank you. Questions welcome.", SERIF, 22, GOLD, True)]])

# =============================================================================== save
out = DECK / "capstone_defense.pptx"
prs.save(str(out))
print("wrote", out, "with", len(prs.slides._sldIdLst), "slides")
