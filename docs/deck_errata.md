# Defense-deck errata (`defense_fallback.pdf`)

Corrections for the 19-page defense deck, each checked against the repo's archived
snapshots and the **locked** `full_thesis/full_thesis.tex`. The deck PDF has **no build
source in this repo** (it is an external slide export), so these are manual slide edits,
listed most-important first. Every other number on the deck was verified and traces to an
archived file — see [`deck_provenance.md`](deck_provenance.md).

> Verified correct and needing **no** change: RQ1 transfer 4.0 / 9.9 / 9.0 %; RQ3
> crossover M\*≈3; joint severities 1.34 / 1.29 / 1.89×; BPAT 5.12×, CA-ON 2.57×,
> US-SW-PNM 1.90×; the +1.46 % positive control; the −0.233 % Diversified cell; the
> slide-17 χ_L/χ_U pairs; and the "144 test cells" count. See the provenance map.

---

## 1. Slide 12 — "17 zones across the US, Canada, **and Iberia–France**"  · fix required

**Change to:** "17 zones across the **US and Canada**." (Iberia–France may be mentioned
separately as a set-aside panel, but it is **not** part of the 17.)

**Why:** this contradicts the locked thesis. `carbon_ceiling_2026-06-24.csv` has exactly
17 `region` rows and **every one is US/Canada** (CA-AB, CA-ON, and 15 `US-*` zones) — zero
Iberian zones. The thesis states the crossover is "tested … across 17 zones"
(`full_thesis.tex` L135) and that "an Iberia–France European set … **is set aside as too
weak a test** … so the analysis rests on the US/Canada grids" (L672–675; also L1002: "the
central claim rests entirely on the US/Canada cases"). This error sits on the *trust /
rigor* slide, and an examiner who read the thesis will catch it immediately.

## 2. Slide 19 — "median of 17 **1.41×**"  · fix required

**Change to:** "**1.43×**" (or drop the second decimal to "**≈1.4×**" to match slides 10–11).

**Why:** the true median of the 17 `region` severities in `carbon_ceiling_2026-06-24.csv`
is **1.4269** (US-CAL-TIDC, the 9th of 17 sorted values) → **1.43×**. `1.41×` is the 8th
value (US-MIDW-AECI 1.4077) — an off-by-one. The repo's own `README.md` (L122) already
says **1.43**. Slides 10 & 11 say "≈1.4" / "1.4×", which round correctly and are fine.

## 3. Slide 19 — "Winter Storm Uri **1.30×**"  · fix required

**Change to:** "**1.28×**" (or "1.3×" at one decimal to match slides 10–11 and the thesis).

**Why:** the only archived Uri value is `carbon_ceiling_2026-06-24.csv`
`event,US-TEX-ERCO__Uri2021,1.2831…` → **1.28×** at two decimals. Every other label on
slide 19 is two-decimal, so `1.30×` is a genuine mis-round (self-inconsistent with the
slide's own precision).

## 4. Slide 9 — "everyday premium **1.0%**"  · label as schematic

**Change:** mark the `1.0%` as illustrative on this admitted-schematic diagram (as slide 2
already labels its shapes), or replace it with an archived quantity.

**Why:** `1.0%` traces to no archived file. The nearest archived robust *mean* premiums
(`_robust_value.out`) are **negative** (robust is worse on the mean: Western −1.87 %,
Eastern −0.07 %, Diversified −4.02 %). The only ~1 % positive figure is Western's
worst-single-day **gain** (+0.99 %), which is the opposite sign of a cost. Directionally "a
small everyday premium" is the right story, but the specific number is not measured — so
present it as a schematic, not a traced measurement.

## 5. Slides 5 / 11 / 14 — "4 to **10**%"  · optional, prefer precise form

**Optional:** use the deck's own precise phrasing "**4.0 to 9.9 %**" consistently.

**Why:** no single grid reaches 10 % (observed max is Eastern **9.91 %**). "4–10 %" is
*defensible* — it is the locked thesis's own headline bracket (`full_thesis.tex` L1759,
"Finding 1, 4–10 %") — but "4.0–9.9 %" (the thesis's precise form, L908) is safer if an
examiner asks which grid hits 10 %.

## 6. Slide 7 — "144 test cells"  · correct; be ready to explain

**No change.** The count is right. If an examiner counts rows in `bh_correction.csv` and
sees **198**, explain the split: **144 pre-committed null-family cells** (4 grid-runs × 9
regimes × 4 covariance estimators = 144; the slide-7 scatter) **+ 54 mean-ablation
positive-control cells** (the +1.46 % instrument on slide 18) = 198. BH q = 0.05 is applied
to the 144-cell family only. This matches the thesis (`full_thesis.tex` L1082–1085).

---

### Note on the repo-built deck (`deck/capstone_defense.pptx`)

The `scripts/build_deck.py` PowerPoint is *not* the attached PDF and is already more careful
(it does not fold Iberia into the 17). If you regenerate it, still prefer "explored and set
aside as too weak a test" over "external-validity anchor" for Iberia (line 384), to match
the locked thesis wording.
