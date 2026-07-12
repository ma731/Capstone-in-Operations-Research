"""Build the viva defense deck (16:9 PowerPoint), final plain-language edition.

Structure follows thesis-defense best practice: say the findings first, then
why -> how -> results -> so what, with the contribution stated twice (up front
and in full near the end), assertion-style slide titles, one idea per slide,
slide numbers on every slide, and backup slides for deep questions.

House style: plain words, short sentences, no em dashes, no ellipses.
Every number traces to an archived file in docs/results_snapshots/
(see docs/deck_provenance.md); wording follows the LOCKED thesis (Iberia was
explored and set aside, the 17 zones are US/Canada, median 1.43x, Uri 1.28x).

Run:  .venv/Scripts/python -m scripts.build_defense_deck
Output: deck/capstone_defense_v2.pptx + Desktop Capstone_Defense_v2.pptx
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
DESKTOP = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "OneDrive" / "Escritorio"

# ---- brand palette (matches poster/design-system.css) ----
NAVY = RGBColor(0x0E, 0x2A, 0x52)
NAVY2 = RGBColor(0x1F, 0x3B, 0x63)
GOLD = RGBColor(0xE6, 0x9F, 0x00)
GOLD_D = RGBColor(0xB5, 0x7D, 0x00)
RUST = RGBColor(0xB3, 0x40, 0x2F)
SAGE = RGBColor(0x4A, 0x7C, 0x59)
INK = RGBColor(0x16, 0x20, 0x2E)
MUTED = RGBColor(0x5B, 0x66, 0x75)
LINE = RGBColor(0xD9, 0xDE, 0xE6)
TINT = RGBColor(0xF3, 0xF6, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CLOUD = RGBColor(0xCD, 0xD6, 0xE4)

SERIF = "Georgia"
SANS = "Segoe UI"

SW, SH = 13.333, 7.5
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


def _title_bar(slide, kicker, title, num):
    _rect(slide, 0, 0, SW, 1.16, NAVY)
    _rect(slide, 0, 1.16, SW, 0.055, GOLD)
    _text(slide, 0.62, 0.13, SW - 1.4, 0.34,
          [[(kicker.upper(), SANS, 12.5, GOLD, True)]])
    _text(slide, 0.62, 0.42, SW - 1.4, 0.66, [[(title, SERIF, 26, WHITE, True)]],
          anchor=MSO_ANCHOR.TOP)
    _oval(slide, SW - 0.94, 0.33, 0.5, GOLD)
    _text(slide, SW - 0.94, 0.33, 0.5, 0.5, [[(str(num), SERIF, 20, NAVY, True)]],
          align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def _footer(slide, num):
    _rect(slide, 0.62, SH - 0.42, SW - 1.24, 0.012, LINE)
    _text(slide, 0.62, SH - 0.40, 8.0, 0.34,
          [[("The Price of Sophistication · carbon-aware data-center scheduling", SANS, 10, MUTED, False)]],
          anchor=MSO_ANCHOR.MIDDLE)
    _text(slide, SW - 2.62, SH - 0.40, 2.0, 0.34,
          [[("M. Ortiz Togashi · " + str(num), SANS, 10, MUTED, False)]],
          align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)


def content(kicker, title, num):
    s = prs.slides.add_slide(BLANK)
    _set_bg(s, WHITE)
    _title_bar(s, kicker, title, num)
    _footer(s, num)
    return s


def _stat(slide, x, y, w, value, label, *, vcolor=NAVY, vsize=40):
    """A big-number stat block."""
    _text(slide, x, y, w, 0.75, [[(value, SERIF, vsize, vcolor, True)]])
    _text(slide, x, y + 0.72, w, 0.75, [[(label, SANS, 13, MUTED, False)]],
          line_spacing=1.05)


def _card(slide, x, y, w, h, accent, head, body, *, dark=False, head_color=None,
          head_size=18, body_y=0.66, body_size=14.5):
    _rect(slide, x, y, w, h, NAVY if dark else TINT)
    _rect(slide, x, y, 0.13, h, accent)
    _text(slide, x + 0.32, y + 0.16, w - 0.55, body_y - 0.16,
          [[(head, SERIF, head_size, head_color or (WHITE if dark else NAVY), True)]])
    _text(slide, x + 0.32, y + body_y, w - 0.55, h - body_y - 0.14,
          [[(body, SANS, body_size, CLOUD if dark else INK, False)]], line_spacing=1.14)


def _caption(slide, x, y, w, txt):
    _text(slide, x, y, w, 0.4, [[(txt, SANS, 11.5, MUTED, False)]], align=PP_ALIGN.CENTER)


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

# =============================================================================== SLIDES

# ---- 1. Title ----
s = prs.slides.add_slide(BLANK)
_set_bg(s, NAVY)
_rect(s, 0, 0, 0.28, SH, GOLD)
logo = ROOT / "poster" / "figs" / "ie_logo_white.png"
if logo.exists():
    _pic(s, logo, 0.95, 0.55, w=1.5)
_text(s, 0.95, 2.32, 11.7, 1.1, [[("The Price of Sophistication", SERIF, 40, WHITE, True)]])
_text(s, 0.95, 3.26, 11.7, 1.3, [
    [("When does a fancier model actually pay in carbon-aware", SERIF, 21, CLOUD, False)],
    [("data-center scheduling?", SERIF, 21, CLOUD, False)],
], space_after=3)
_rect(s, 1.0, 4.5, 3.2, 0.05, GOLD)
_text(s, 0.95, 4.74, 11.6, 0.9, [[(
    "We built a real scheduler, then put a price on three upgrades. "
    "One pays. Two do not.", SANS, 18, GOLD, True)]], line_spacing=1.15)
_text(s, 0.95, 6.06, 11.0, 1.2, [
    [("Marco Ortiz Togashi", SANS, 17, WHITE, True),
     ("    ·    IE University · MSc Business Analytics & Data Science", SANS, 14.5, CLOUD, False)],
    [("Supervisor: Prof. Bissan Ghaddar    ·    Viva · 7 July 2026", SANS, 14.5, CLOUD, False)],
], space_after=4)

# ---- 2. The thesis in one slide ----
s = content("The case in one slide", "One operator, three decisions", 2)
cw = (SW - 1.24 - 0.5) / 3
_card(s, 0.62, 1.55, cw, 2.75, SAGE,
      "Move work between regions?",
      "Yes. Worst-day emissions fall 4.0 to 9.9%, roughly $1.7M a year (gross). No "
      "statistics needed. This is the lever.",
      head_size=15.5, body_y=1.0)
_card(s, 0.62 + cw + 0.25, 1.55, cw, 2.75, RUST,
      "Model how regions co-move?",
      "No. It adds under 0.4%, worth about $37k gross and not reliable. Skip it, and "
      "we show why.",
      head_size=15.5, body_y=1.0)
_card(s, 0.62 + 2 * (cw + 0.25), 1.55, cw, 2.75, GOLD,
      "Plan for worse than forecast?",
      "Only if carbon can spike to triple. Real grids peak near 1.4 times, far below "
      "that, so on observed data, skip it.",
      head_size=15.5, body_y=1.0)
_rect(s, 0.62, 4.62, SW - 1.24, 1.0, TINT)
_rect(s, 0.62, 4.62, 0.13, 1.0, GOLD)
_text(s, 0.95, 4.76, SW - 1.85, 0.8, [[
    ("The contribution: ", SERIF, 16.5, NAVY, True),
    ("a rule that tells you when a dependence model can ever pay, and a fair way to "
     "put a price on any modelling layer.", SERIF, 16.5, INK, False)]], line_spacing=1.15)
_text(s, 0.62, 5.9, SW - 1.24, 0.7, [[(
    "The operator is a stand-in for the real study: three grids, 17 US and Canada zones. "
    "We priced all three upgrades on a year of real data it never saw, under a "
    "pre-committed test. 202 tests, every number archived.", SANS, 14, MUTED, False)]], line_spacing=1.2)

# ---- 3. The opportunity ----
s = content("The setup · meet the operator", "Electricity is not equally clean all day, everywhere", 3)
_bullets(s, 0.62, 1.58, 5.9, 4.1, [
    ("You run a fleet of data centers across the US and Canada, with a carbon promise "
     "to keep. Every evening you choose where tomorrow's flexible work runs.", None, False),
    ("The work can wait. Training and batch jobs can start a few hours later, or run "
     "in a cleaner region, and nobody notices.", None, False),
    ("The grid will not wait. Clean power comes and goes by the hour and by region. So "
     "you send the work to the cleanest hour and place.", None, False),
], size=16.5, gap=12, lead="You run compute across regions")
_rect(s, 0.62, 5.74, 5.9, 1.0, TINT)
_rect(s, 0.62, 5.74, 0.13, 1.0, GOLD)
_text(s, 0.92, 5.92, 5.4, 0.72, [[(
    "The question is not whether to do this. It is how fancy the model needs to be.",
    SERIF, 17, NAVY, True)]], line_spacing=1.14)
_pic(s, FIG / "correlation_map.png", 6.95, 1.62, max_w=5.8, max_h=4.75)
_caption(s, 6.95, 6.5, 5.8, "Carbon intensity differs across regions, and it keeps moving.")

# ---- 4. The gap ----
s = content("The catch", "Nobody had priced the upgrades one at a time", 4)
for i, (head, body) in enumerate([
    ("Savings were never separated",
     "Papers change many things at once and report one big saving. Nobody can say "
     "which part earned what."),
    ("No fair baseline",
     "Richer models get compared against weaker setups under different rules. The "
     "model and the setup are mixed together."),
    ("The closest work stops at one region",
     "Hall et al. 2024 builds robust carbon scheduling for a single region. Whether "
     "links across regions pay was an open question."),
]):
    _card(s, 0.62 + i * (cw + 0.25), 1.62, cw, 2.5, GOLD, head, body,
          head_size=16, body_y=1.06)
_rect(s, 0.62, 4.4, SW - 1.24, 1.0, TINT)
_text(s, 0.92, 4.56, SW - 1.8, 0.75, [[(
    "Our fix: one scheduler, the same rules for everyone, add one layer at a time, "
    "and price each layer on data it has never seen.", SERIF, 18, NAVY, True)]], line_spacing=1.12)
_text(s, 0.62, 5.68, SW - 1.24, 1.1, [
    [("RQ1", SANS, 16, GOLD_D, True), ("  moving work between regions. Does it pay, and how much?", SANS, 16, INK, False)],
    [("RQ2", SANS, 16, GOLD_D, True), ("  modelling how regions move together. Does that add anything?", SANS, 16, INK, False)],
    [("RQ3", SANS, 16, GOLD_D, True), ("  planning for a worse day than the forecast. When is that worth it?", SANS, 16, INK, False)],
], space_after=7)

# ---- 5. The machine and the yardstick ----
s = content("How we tested it", "A day-ahead scheduler, scored on its worst days", 5)
_bullets(s, 0.62, 1.62, 5.9, 4.5, [
    ("Every evening: forecast tomorrow's carbon per region, plan where and when the "
     "work runs, execute, score. Repeat for a full held-out year (2025).", None, False),
    ("The fair-test rule: every version of the scheduler runs under identical "
     "constraints. Only the brain changes, so any difference is the brain's doing.", None, False),
    ("The baseline is the same scheduler with the transfer channel switched off "
     "(Φ = 0). Like for like.", None, False),
    ("The score: CVaR, the average of the worst 5% of days.", NAVY, True),
], size=16, gap=10, lead="Forecast, plan, execute, score")
_rect(s, 0.62, 5.5, 5.9, 1.22, TINT)
_rect(s, 0.62, 5.5, 0.13, 1.22, GOLD)
_text(s, 0.94, 5.62, 5.5, 1.05, [[
    ("The constraints: ", SANS, 13.5, NAVY, True),
    ("a capacity ceiling, ramp limits, a work deadline, and a thermal (PUE) limit, "
     "plus the transfer budget Φ. The full model is written out on the last backup "
     "slide.", SANS, 13.5, INK, False)]], line_spacing=1.16)
_pic(s, FIG / "model_validation.png", 6.95, 1.62, max_w=5.8, max_h=4.75)
_caption(s, 6.95, 6.5, 5.8, "Check: on small problems the scheduler finds the exact best answer.")

# ---- 6. The data ----
s = content("How we tested it", "Real data, and grids picked to work against us", 6)
_bullets(s, 0.62, 1.62, 5.9, 4.9, [
    ("Real hourly carbon data (Electricity Maps), 2021 to 2025, 17 zones across the "
     "US and Canada. Trained up to 2024, tested once on 2025.", None, False),
    ("US West: regions strongly linked, all moving together.", None, False),
    ("Eastern US and Canada belt: middle of the road.", None, False),
    ("A built portfolio of solar, wind and hydro zones: barely linked, on purpose. "
     "The best possible case for the co-movement layer.", None, False),
    ("Iberia and France: checked early, set aside as too weak a test. The robust "
     "machinery does not engage there, so a zero from it would prove nothing.", MUTED, False),
], size=16.5, gap=12, lead="If the layer can pay anywhere, it is here")
_pic(s, FIG / "ci_corr_heatmap_us_west.png", 6.95, 1.62, max_w=5.8, max_h=4.7)
_caption(s, 6.95, 6.45, 5.8, "The links are real, up to 0.78 out of 1 on the US West, close to a perfect match. Value is the question.")

# ---- 7. RQ1: the lever pays ----
s = content("Decision 1 · Move the work?", "Let the work chase the clean region. It pays.", 7)
_pic(s, FIG / "transfer_value_curve.png", 0.62, 1.62, max_w=7.3, max_h=4.9)
_stat(s, 8.3, 1.7, 4.3, "4.0 to 9.9%", "cut in worst-day emissions, against the same "
      "scheduler with transfer switched off", vcolor=SAGE, vsize=36)
_bullets(s, 8.3, 3.35, 4.4, 3.3, [
    ("Per grid: Western 4.0%, Eastern 9.9%, Diversified 9.0%. On the Eastern fleet, "
     "roughly $1.7M a year, before the cost of moving work.", None, False),
    ("Savings flatten out near a 20% transfer budget. A modest channel captures "
     "nearly all the value.", None, False),
    ("And it needs no statistics at all. This is the lever.", NAVY, True),
], size=16, gap=12)

# ---- 8. Where the value lives ----
s = content("The verdict so far", "One jump, then flat", 8)
_pic(s, FIG / "complexity_frontier.png", 0.62, 1.62, max_w=7.3, max_h=4.6)
_bullets(s, 8.3, 1.75, 4.4, 4.2, [
    ("Every model we built, on one line: value against complexity. Same rules, same "
     "test year.", None, False),
    ("Transfer is the single jump. Everything after it adds almost no height.", SAGE, True),
    ("The rest of this talk explains why the line goes flat, and when it would not.",
     NAVY, True),
], size=16.5, gap=13, lead="The whole thesis in one image")
_caption(s, 0.62, 6.35, 7.3,
         "y-axis: savings vs a carbon-blind scheduler; the 4.0 to 9.9% headline is CVaR "
         "vs Φ = 0 (archived: complexity_frontier_2026-07-05.csv).")

# ---- 9. RQ2: the null ----
s = content("Decision 2 · Model the links?", "Knowing how regions move together adds nothing", 9)
_text(s, 0.62, 1.38, SW - 1.24, 1.4, [
    [("The test, fixed in advance:  ", SANS, 16, NAVY, True),
     ("fit the schedule with the real links between regions, then with the links "
      "destroyed. Across 144 pre-committed cells the gap never leaves a plus or minus "
      "0.4% band, and its sign flips.", SANS, 16, INK, False)],
    [("An active zero:  ", SANS, 16, NAVY, True),
     ("the machinery was on and engaged, so this is a real zero, not a switched-off "
      "one. Skip this layer.", SANS, 16, INK, False)],
], line_spacing=1.16, space_after=8)
_pic(s, FIG / "cv_curve.png", 0.0, 2.9, max_w=12.0, max_h=3.9, center_x=SW / 2)

# ---- 10. RQ2 mechanism ----
s = content("The twist: a real signal that still does not pay", "A wave and a ripple: the signal was there all along", 10)
_bullets(s, 0.62, 1.62, 5.9, 4.7, [
    ("Carbon follows a big daily wave, driven by sun and demand. It is large, shared, "
     "and easy to predict.", None, False),
    ("The links between regions live in a small ripple on top, 2 to 4 times smaller "
     "than the wave. The schedule barely reacts to it.", None, False),
    ("The proof the test works: flatten the wave artificially, and the same layer "
     "suddenly pays +1.46%. Far above the 0.4% bar.", RUST, True),
    ("So the signal is real, just too small and shaky to bank. It loses to the wave.", None, False),
], size=17, gap=13, lead="The signal is real, but the wave hides it")
_rect(s, 6.95, 1.72, 5.75, 4.5, TINT)
_text(s, 7.25, 1.95, 5.2, 4.1, [
    [("The wave-and-ripple rule", SERIF, 19, NAVY, True)],
    [("A dependence layer can only move the schedule when the ripple rivals the "
      "wave.", SANS, 15.5, INK, False)],
    [("On every grid we measured, the wave is 2 to 4 times bigger. So the layer "
      "cannot pay there.", SANS, 15.5, INK, False)],
    [("This is the part that travels: a simple check anyone can run on their own "
      "grid, before spending anything.", SANS, 15.5, NAVY, True)],
], space_after=11, line_spacing=1.14)

# ---- 11. RQ3: why robustify ----
s = content("Decision 3 · Buy insurance?", "Forecasts miss, so the plan should expect worse", 11)
_bullets(s, 0.62, 1.62, 5.9, 4.6, [
    ("Planning a day ahead means planning under forecast error.", None, False),
    ("The robust plan does not trust one forecast. It draws a ball of plausible "
     "tomorrows around it and plans against the worst one inside.", None, False),
    ("Like packing for weather a bit worse than predicted.", None, False),
    ("More caution buys protection on bad days, and costs a small premium every day. "
     "Insurance, in one dial.", NAVY, True),
], size=17, gap=13, lead="Hedging the forecast")
_rect(s, 6.95, 2.25, 5.75, 1.5, TINT)
_pic(s, EQ_DRO, 6.95, 2.6, max_w=5.4, max_h=0.95, center_x=9.83)
_text(s, 6.95, 4.05, 5.75, 2.1, [[(
    "The first term carries the saving. The second term prices the caution. "
    "So the real question: how bad must the bad day be before the insurance pays "
    "for itself?", SANS, 15.5, MUTED, False)]], line_spacing=1.2)

# ---- 12. RQ3 crossover ----
s = content("Decision 3 · Buy insurance?", "Insurance pays past a tripling. Observed grids fall far short.", 12)
_pic(s, FIG / "crossover.png", 0.62, 1.62, max_w=7.3, max_h=4.9)
_bullets(s, 8.3, 1.7, 4.4, 4.9, [
    ("We injected emergencies into the test year and turned the severity up step by "
     "step. The robust plan starts to win past M = 3: carbon spiking to triple.", None, False),
    ("Reality check, 17 zones, 5 years: the median worst spike is about 1.43 times. "
     "Even Winter Storm Uri reached only 1.28 times.", RUST, True),
    ("One caveat, stated up front: this holds for single-region emergencies. For "
     "storms that hit every region at once, there is nowhere clean to move the work "
     "anyway.", None, False),
    ("So robustness is an option you price, not a free win.", NAVY, True),
], size=15.5, gap=11)

# ---- 13. The decision rule ----
s = content("The playbook", "A decision rule the operator can use tomorrow", 13)
cw2 = (SW - 1.24 - 0.3) / 2
_card(s, 0.62, 1.62, cw2, 2.3, SAGE, "Layer 1 · Always",
      "Schedule per region, day ahead. Riding the daily carbon wave is the free "
      "baseline everyone should run.")
_card(s, 0.62 + cw2 + 0.3, 1.62, cw2, 2.3, GOLD, "Layer 2 · The lever",
      "Add transfer between regions: 4.0 to 9.9% off worst-day emissions. A modest "
      "channel near a 20% budget captures nearly all of it.")
_card(s, 0.62, 4.2, cw2, 2.3, RUST, "Layer 3 · Skip",
      "The co-movement models. Covariance and copulas add under 0.4%, below the "
      "noise, while the daily wave dominates.")
_card(s, 0.62 + cw2 + 0.3, 4.2, cw2, 2.3, GOLD, "Layer 4 · Conditional",
      "Buy robustness only if you expect emergencies past a tripling. Real grids "
      "have not come close.", dark=True)

# ---- 14. Why trust a zero ----
s = content("Why you can trust a no", "Built so that a zero is a result, not an excuse", 14)
_text(s, 0.62, 1.4, SW - 1.24, 1.55, [
    [("Locked first. ", SANS, 15.5, NAVY, True),
     ("The pass-or-fail rule went into version control before we read 2025. An "
      "equivalence test, built to prove smallness rather than just miss it, rules out "
      "any effect above 0.4%, and holds down to a 0.31% bar. A correction for testing "
      "many cells, a resampling check that keeps nearby days together, and re-runs on "
      "2022 to 2024 all give the same zero.  ",
      SANS, 15.5, INK, False),
     ("The +1.46% positive control proves the test can fire.", SANS, 15.5, RUST, True)]],
    line_spacing=1.24)
_pic(s, FIG / "robustness.png", 0.0, 3.2, max_w=11.4, max_h=3.5, center_x=SW / 2)
_caption(s, 0.62, 6.78, SW - 1.24,
         "The gap stays inside the 0.4% band under every check, and the test had the "
         "power to catch any real gap down to 0.015 to 0.11%. Every number is archived.")

# ---- 15. The 202 tests ----
s = content("Why you can trust a no", "202 tests: the thesis's claims run as code", 15)
rows = [
    ("70", "Models against known answers", "every scheduler is solved on small test "
     "problems where we know the exact best answer, and must match it", NAVY),
    ("59", "Covariance and dependence tools", "the estimators, the link-destroying "
     "shuffle, the correlation and tail measures", NAVY),
    ("25", "The shared rulebook", "capacity, ramp and budget constraints. The "
     "fair-test rule, enforced in code", NAVY),
    ("16", "Data pipelines", "loading the carbon data (13 tests need the licensed "
     "files, so the automatic test runner runs 189) and the weather data (3)", MUTED),
    ("11", "The thesis's math, run as tests", "key claims from the thesis are checked "
     "by code on every push. If a claim breaks, the build goes red", RUST),
    ("21", "Frozen numbers and guards", "the headline numbers are re-checked against "
     "their archived files, so nothing can drift quietly", NAVY),
]
y = 1.42
for val, head, body, c in rows:
    _rect(s, 0.62, y, 0.95, 0.7, TINT)
    _text(s, 0.62, y + 0.05, 0.95, 0.6, [[(val, SERIF, 23, c, True)]],
          align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    _text(s, 1.78, y - 0.02, 10.9, 0.4, [[(head + ".  ", SANS, 14, NAVY, True),
                                          (body, SANS, 13, INK, False)]],
          line_spacing=1.04)
    y += 0.84
_text(s, 0.62, y, 11.9, 0.5, [[(
    "Why so many? Because the weak point of finding nothing is: you did not look "
    "hard enough. The tests are how we prove we looked.",
    SERIF, 14.5, NAVY, True)]], line_spacing=1.08)

# ---- 16. Contributions ----
s = content("The contribution", "What this thesis adds", 16)
_card(s, 0.62, 1.62, SW - 1.24, 1.85, GOLD, "1. A rule for when the dependence layer can pay",
      "It can only pay when the ripple rivals the wave. We show how to split the score "
      "into the big daily wave and the small leftover ripple, give a limit you can check "
      "before touching any data, and back it with a measurement that has a working "
      "positive control. Carbon grids are not in that regime, and that is a rule about a "
      "whole class of problems, not one number.")
_card(s, 0.62, 3.68, SW - 1.24, 1.85, NAVY2, "2. A fair way to price a modelling layer",
      "Lock the pass-or-fail rule first. Keep everything else identical. Compare "
      "against a like-for-like baseline and an economic bar. The field added this "
      "layer by default. We put a price on it.")
_text(s, 0.62, 5.78, SW - 1.24, 1.0, [[(
    "Plus: the measured 4.0 to 9.9% transfer saving, the priced robustness rule, and "
    "a pipeline anyone can re-run. 202 tests, archived numbers, free solvers.",
    SANS, 16, INK, False)]], line_spacing=1.2)

# ---- 17. Limitations ----
s = content("Where it could break", "Stated plainly", 17)
_bullets(s, 0.62, 1.7, SW - 1.24, 4.8, [
    ("One workload shape: jobs that can split across hours and sites, with ramp "
     "limits. A very different cost shape could change the answer.", None, False),
    ("One main test year. Re-runs on 2022 to 2024 agree, but the truly independent "
     "evidence is a handful of yearly reads, not 362 days. A longer evaluation is "
     "the named next step.", None, False),
    ("A pattern, not a law: the rule holds where the daily wave dominates. That is "
     "every grid we measured, but we hand you the check, not a theorem.", None, False),
    ("The crossover is characterized, not observed: no real grid in our data ever "
     "crossed it. It is reported at the pre-committed caution and tail level, not "
     "tuned to a number, and we say exactly where that line is.", None, False),
], size=17.5, gap=16)

# ---- 18. Close ----
s = prs.slides.add_slide(BLANK)
_set_bg(s, NAVY)
_rect(s, 0, 0, 0.28, SH, GOLD)
_text(s, 0.95, 0.85, 11.4, 1.0, [[("The rule in one line", SERIF, 32, WHITE, True)]])
_rect(s, 0.95, 1.72, 2.6, 0.05, GOLD)
_text(s, 0.95, 1.95, 11.4, 0.9, [[(
    "Fancier is not safer. It is a bill, and it pays only when the ripple rivals the "
    "wave.", SERIF, 20, GOLD, True)]], line_spacing=1.12)
_bullets(s, 0.95, 3.0, 11.4, 2.7, [
    ("Always schedule with the daily wave.", CLOUD, False),
    ("Add the transfer channel. That is the lever: 4.0 to 9.9%.", GOLD, True),
    ("Skip the co-movement models: under 0.4%, below the noise.", CLOUD, False),
    ("Buy robustness only past a tripling. Real grids are not there.", CLOUD, False),
], size=18, gap=13, color=CLOUD)
_text(s, 0.95, 5.85, 11.4, 0.6, [[("Thank you. Questions welcome.", SERIF, 24, GOLD, True)]])
_text(s, 0.95, 6.6, 11.4, 0.5, [[(
    "Every number on these slides traces to an archived file in the repository "
    "(docs/deck_provenance.md).", SANS, 13, CLOUD, False)]])
_text(s, SW - 2.62, SH - 0.40, 2.0, 0.34,
      [[("M. Ortiz Togashi · 18", SANS, 10, CLOUD, False)]],
      align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)

# =============================================================================== BACKUPS

# ---- 19. Backup: falsification test ----
s = content("Backup · RQ2", "The test in detail: destroy the links, keep everything else", 19)
_text(s, 0.62, 1.4, SW - 1.24, 1.5, [
    [("Keep each region, cut the links. ", SANS, 15.5, NAVY, True),
     ("Fit the schedule on the real links between regions. Then refit on a copy where "
      "each region keeps its own exact daily pattern, but every cross-region link is "
      "destroyed. Score both on the held-out worst days. The rule, fixed in advance: if "
      "spatial structure matters, the real-links schedule must win.  ", SANS, 15.5, INK, False),
     ("It does not.", SANS, 15.5, NAVY, True)]],
    line_spacing=1.24)
_pic(s, FIG / "schedule_us_west.png", 0.0, 3.22, max_w=11.6, max_h=3.5, center_x=SW / 2)
_caption(s, 0.62, 6.78, SW - 1.24,
         "Western US, joint (filled) vs shuffled (outline) schedules. They overlap almost everywhere.")

# ---- 20. Backup: tail dependence ----
s = content("Backup · RQ2", "The leftover dependence has the wrong shape", 20)
_pic(s, FIG / "tail_dependence_us_west.png", 0.62, 1.62, max_w=7.0, max_h=4.9)
_bullets(s, 7.95, 1.7, 4.75, 4.9, [
    ("Regions hit their clean extremes together far more than their dirty ones. "
     "CISO/LDWP: 0.48 clean vs 0.25 dirty. BANC/LDWP: 0.40 vs 0.17.", None, False),
    ("A simple co-movement model is symmetric: it treats clean-together and "
     "dirty-together as the same size. Real grids do not, so it cannot capture this "
     "shape.", None, False),
    ("And the structure sits in the clean tail, which a risk-averse scheduler "
     "ignores anyway.", NAVY, True),
    ("Archived: tail_dependence_2026-07-05.csv (residual series).", MUTED, False),
], size=15.5, gap=12, lead="Clean together, dirty apart")

# ---- 21. Backup: the 144 cells ----
s = content("Backup · Statistics", "144 cells, 198 rows: the anatomy of the test", 21)
_stat(s, 0.62, 1.7, 3.0, "144", "pre-committed null-family cells", vcolor=NAVY)
_stat(s, 3.9, 1.7, 3.0, "+ 54", "positive-control cells (wave flattened)", vcolor=RUST)
_stat(s, 7.2, 1.7, 3.4, "= 198", "rows in bh_correction.csv", vcolor=MUTED)
_bullets(s, 0.62, 3.4, SW - 1.24, 3.3, [
    ("144 = 4 grid-runs x 9 regime cells x 4 covariance estimators. The "
     "multiple-testing correction applies to this family.", None, False),
    ("Biggest gap among the 144: 0.355%, inside the 0.4% band. And the test had the "
     "power to catch any real gap down to 0.015 to 0.11% (80% power, TOST at alpha "
     "0.05), an order of magnitude below the bar.", None, False),
    ("The 54 extra rows are the instrument check: flatten the wave and the test "
     "fires at +1.46%, well above the bar, by design.", RUST, True),
    ("The claim is a conjunction: every cell must rule out a material effect, so it "
     "is only as strong as its hardest case, the Diversified grid, which still clears "
     "the bar comfortably (z = 3.7). Conservative without extra correction.", NAVY, True),
], size=16, gap=12)

# ---- 22. Backup: the 0.4% margin ----
s = content("Backup · Statistics", "Why 0.4%? An economics bar, and it only cuts one way", 22)
_bullets(s, 0.62, 1.7, SW - 1.24, 4.9, [
    ("0.4% is the smallest saving that covers building and running a covariance "
     "layer. And that layer can itself hurt: up to 0.233% on the Diversified grid.", None, False),
    ("It was not tuned to get the result: the conclusion keeps holding for any bar "
     "down to 0.31%.", None, False),
    ("Push the bar to 0.1% and only one cell flips: Diversified at minus 0.233%, and "
     "it flips to clearly negative. A tighter bar makes skipping the layer stronger, "
     "not weaker.", RUST, True),
    ("Scale: on the Eastern facility the covariance channel is worth about $37k a "
     "year, and not reliably positive. The transfer lever is worth about $1.7M.", None, False),
], size=17, gap=15, lead="The bar, defended")

# ---- 23. Backup: the 5.1x zone ----
s = content("Backup · RQ3", "Why BPAT's 5.12x does not break the crossover", 23)
_bullets(s, 0.62, 1.7, SW - 1.24, 4.9, [
    ("BPAT is a hydro zone with near-zero baseline carbon. A 5.12x jump on a tiny "
     "base is a small change in grams. It barely moves the portfolio.", None, False),
    ("What the schedule's risk actually feels is the portfolio-level worst day: "
     "Western 1.34x, Eastern 1.29x, Diversified 1.89x. All well under the tripling.", None, False),
    ("Context: CA-ON 2.57x, US-SW-PNM 1.90x, median of the 17 zones 1.43x, Winter "
     "Storm Uri 1.28x. (carbon_ceiling_2026-06-24.csv)", None, False),
    ("And the decisive check: draw emergencies from each region's own real worst "
     "days, and the robust plan still does not pay.", NAVY, True),
], size=17, gap=15, lead="A big ratio on a tiny base is not risk")

# ---- 24. Backup: the full model ----
s = content("Backup · The full model", "The scheduler, written out", 24)
_text(s, 0.62, 1.42, 5.85, 0.4,
      [[("The problem is a second-order cone program:", SANS, 15, NAVY, True)]])
_rect(s, 0.62, 1.9, 5.85, 1.2, TINT)
_pic(s, EQ_DRO, 0.62, 2.16, max_w=5.45, max_h=0.82, center_x=3.55)
_text(s, 0.62, 3.3, 5.85, 3.0, [
    [("x", SANS, 14, NAVY, True),
     (" is the schedule (power per region, per hour), ", SANS, 14, INK, False),
     ("ρ̄", SANS, 14, NAVY, True), (" is forecast carbon, ", SANS, 14, INK, False),
     ("ε", SANS, 14, NAVY, True), (" is how cautious, ", SANS, 14, INK, False),
     ("Σ", SANS, 14, NAVY, True), (" is how the regions co-vary.", SANS, 14, INK, False)],
    [("At ε = 0 it is a plain linear program on the forecast. The cone term is "
      "the only place covariance can act, which is exactly what Decision 2 prices.",
      SANS, 14, MUTED, False)],
], line_spacing=1.22, space_after=9)
_text(s, 6.85, 1.42, 5.85, 0.4, [[("Subject to (the feasible set):", SANS, 15, NAVY, True)]])
_bullets(s, 6.85, 1.95, 5.85, 4.6, [
    ("Ceiling: 0 ≤ x ≤ capacity. A site cannot exceed its installed power.", None, False),
    ("Work and flexible split: each region serves its daily work. A fixed fraction is "
     "inflexible (pinned shape); the rest is free to move.", None, False),
    ("Ramp: hour-to-hour change ≤ 15 MW. Power cannot jump, so the greedy "
     "cheapest-hour schedule is infeasible.", None, False),
    ("Deadline: at least 20% of flexible work done in the morning window. You cannot "
     "defer everything to the cheap hour.", None, False),
    ("Thermal (PUE): hotter hours cost more cooling, so less usable compute. This is "
     "why weather enters the model.", None, False),
    ("Transfer (Part 3): work can move between regions up to a budget Φ, and "
     "flows conserve work. Φ = 0 is the honest baseline.", NAVY, True),
], size=13.5, gap=8)
_text(s, 6.85, 6.5, 5.85, 0.45, [[(
    "Calibrated on training data to bind loosely, so the schedule still moves 25 to "
    "30% and covariance gets its best shot.", SANS, 11.5, MUTED, False)]], line_spacing=1.14)

# ---- 25. Backup: future work ----
s = content("Backup · Future work", "The null is a sharpened mandate, not a dead end", 25)
cwf = (SW - 1.24 - 0.3) / 2
_card(s, 0.62, 1.6, cwf, 2.18, GOLD, "1. Settle the crossover",
      "Build a calibrated outage model from grid-operator data, not the carbon tail, "
      "with a pre-committed evaluation and affine recourse. Does real emergency risk "
      "ever reach the 3x the robust plan needs?", body_size=13.5)
_card(s, 0.62 + cwf + 0.3, 1.6, cwf, 2.18, NAVY2, "2. Make the null model-free",
      "A copula-ambiguity Wasserstein DRO (Fan-Ji-Lejeune) on a fitted vine, "
      "robustifying the dependence structure itself. Mean-dominance predicts it still "
      "will not pay, but this closes the last objection.", body_size=13.5)
_card(s, 0.62, 3.98, cwf, 2.18, SAGE, "3. Transfer, online and multistage",
      "Forecasts arrive in sequence, with demand and transmission themselves uncertain, "
      "and the ambiguity ball centred on a learned forecast. This is where the online "
      "loss on the Diversified grid could flip.", body_size=13.5)
_card(s, 0.62 + cwf + 0.3, 3.98, cwf, 2.18, GOLD, "4. A general screening rule",
      "Turn mean-dominance into a condition for when cross-region dependence can ever "
      "help a robust allocation. Carbon-aware scheduling is one instance of a wider "
      "class.", dark=True, body_size=13.5)
_text(s, 0.62, 6.42, SW - 1.24, 0.6, [[(
    "Plus broader external validity: a longer multi-year rolling evaluation, grids with "
    "different generation mixes (hydro-thermal with seasonal storage), and hard-deadline "
    "objectives. Every direction is named in the thesis Future Work section.",
    SANS, 12.5, MUTED, False)]], line_spacing=1.16)

# =============================================================================== save
out_repo = DECK / "capstone_defense_v2.pptx"
prs.save(str(out_repo))
print("wrote", out_repo, "with", len(prs.slides._sldIdLst), "slides")
out_desktop = DESKTOP / "Capstone_Defense_v2.pptx"
try:
    prs.save(str(out_desktop))
    print("wrote", out_desktop)
except PermissionError:
    print("skipped Desktop copy (file open in PowerPoint):", out_desktop)
