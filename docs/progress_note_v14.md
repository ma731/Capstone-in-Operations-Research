# Progress note v14 — Iberia (ES-PT-FR) generalization (Task B)

**Date:** 2026-06-05 (UTC). **Builds on v13 (Task A).**
**Scope:** Apply the *exact* Task A machinery to a SECOND region set — Iberia +
France (ES, PT, FR) — and report the result SIDE BY SIDE with California so the
two cases are directly comparable. Transport, not redesign: the constraint set,
the DRO method (Algorithm 2b Mahalanobis–Wasserstein SOCP), the three-regime
design, the metric, the CV, the bootstrap, and the table format are **locked**
from Task A. Only the region set, the common clock, and the climate-dependent
constraint *parameters* differ.

---

## 1. Headline verdict

**Iberia REPLICATES the California null.** Across both region sets, all three
constraint regimes, and all three alpha levels, pairing the *joint* covariance
with the Mahalanobis–Wasserstein scheduler instead of the *block-diagonal
(shuffled)* covariance changes out-of-sample CVaR₀.₉₅ by a negligible amount,
and no beneficial spatial effect survives the robustness battery.

The more tightly-coupled MIBEL grid (ES-PT) did **not** produce a divergent
positive result. Two independent grids, same conclusion: **spatial correlation
of carbon intensity adds negligible robust value to the schedule.** A replicated
null across two distinct grids is the strong, general version of the Phase 1
finding.

**One honest caveat, reported in full (§4):** the Iberian R1/α=0.75 cell shows a
raw-level +0.32 % gap that is statistically detectable and the single largest
raw gap in either study. It does **not** survive: it appears only because the
shuffled arm's cross-validation selects a different (worse) Wasserstein radius
on raw levels; under residual-space estimation, where both arms select the same
radius, the sign flips to −0.03 % (joint marginally *worse*), and the locked
seasonal∧AR(1) agreement rule confirms that flip. So it is an ε-selection
artifact, not a spatial effect.

---

## 2. What is identical vs what changed (comparability ledger)

| element | California (A) | Iberia (B) | same? |
|---|---|---|---|
| DRO method (A2b SOCP) | ✓ | ✓ | identical |
| feasible set (drop cap; split+ramp+deadline+thermal) | ✓ | ✓ | identical |
| three regimes R3/R1/R2 | ✓ | ✓ | identical |
| metric (CVaR₀.₉₅ upper tail) | ✓ | ✓ | identical |
| blocked 5-fold CV, ε-grid {0,.1,1,10,100,1000} | ✓ | ✓ | identical |
| 1000-bootstrap CI, seed 20260524 | ✓ | ✓ | identical |
| alpha sweep {0.30,0.50,0.75}, util 0.80, ceiling 50 | ✓ | ✓ | identical |
| ramp 15, deadline window [0,7] γ=0.20 | ✓ | ✓ | identical |
| **R** | 4 | **3** | D=R·T = 96 → **72** |
| **regions** | US-CAL-CISO/BANC/LDWP, US-NW-NEVP | **ES, PT, FR** | different set |
| **common clock** | America/Los_Angeles | **Europe/Madrid** | PT is WET (+1h shift) |
| **thermal t_set** | 20 °C | **14 °C** | recalibrated (milder field) |

The R-parameterization was already in the math engine (build_daily_panel,
algorithm_2a/2b take region_order); no solver change was needed. The only
re-calibrated constraint parameter is the economizer set-point t_set (20→14 °C):
the Iberian annual-mean thermal field peaks ~21 °C (vs 26–27 °C in CA/NV), so a
lower set-point keeps 3b loosely active (binds ~22–26 % of cells, matching the CA
discipline). PUE shape, slope κ, floor pue0, and bar_P are unchanged.

**Comparability guardrail:** nothing structural diverged. Same metric, CV,
bootstrap, table. Only region/clock/climate-parameters differ — the intended
axis of the second case.

---

## 3. Data + gates (Iberia)

**Carbon (Gate B1):** Electricity Maps academic CSVs, ES/PT/FR (country-level
keys, confirmed against files), 2021–2025, lifecycle hourly. Panel via the same
build_daily_panel → **(1815, 3, 24)**, dates 2021-01-02→2025-12-31, **train
N=1452 / test N=363**, 0 % missing, 12 DST days dropped. Common clock
**Europe/Madrid (CET/CEST)**. *PT is WET (UTC+0/+1), one hour behind ES/FR; under
the single Madrid reference clock PT's panel hours are shifted +1 h. Stated in
the code constant, the panel build, and here — a deliberate common-clock choice,
not silenced.* Mean CI: ES 161.8, PT 159.6, **FR 50.5** (France nuclear-dominated
and far cleaner; ES/PT MIBEL-coupled and similar).

**Temperature (Gate B2):** Open-Meteo ERA5, one load-center per zone —
ES→Madrid (40.417, −3.704), PT→Lisbon (38.722, −9.139), FR→**Paris** (48.857,
2.352; France is large and heterogeneous, Paris/Île-de-France is the dominant
load centre and the load-weighted single-point choice). Aligned through the same
machinery → identical (1815,3,24) panel, dates match. tz spot-check: Madrid local
15:00 (13:00 UTC) = 30.2 °C, pre-dawn = 21.6 °C. Per-zone mean/max: ES 15.9/41.5,
PT 17.3/40.7, FR 12.5/39.1 °C; 0 % missing.

**Empirical correlation (corroborating context).** Stratified pairwise
correlations on the Iberian panel: **ES–PT 0.84–0.86** (MIBEL is tightly coupled,
and *higher* than any California pair, which sat at 0.43–0.77), while ES–FR ≈0.49
and FR–PT ≈0.40 (France is largely decoupled — nuclear baseload, weak diurnal
co-movement). This sharpens the headline: **even with an ES–PT correlation of
~0.85, the joint covariance buys no robust scheduling value over the
block-diagonal one.** High empirical correlation does not translate into
exploitable DRO value — the very point the shuffled-marginals test was built to
isolate. (Regenerate via `python -m src.analysis.stratified_correlations
--region-set iberia`.)

**Calibration / Goldilocks (Gate B3):** all 9 regime×alpha cells *loose-OK* —
constraints active (R2: ramp 12–15/69, thermal 16–19/72, deadline 1–2/3) but the
DRO retains **9.5–18.2 %** reallocation room (none frozen). Lower than CA's
24–32 %, reflecting Iberia's smaller carbon dispersion (FR flat/low ~50, ES/PT
~160) — less spatial spread to exploit, but the set is not frozen, so any null is
substantive.

---

## 4. Main result — side by side

Spatial gap = (shuf − joint) CVaR₀.₉₅ on held-out 2025; positive = joint better;
gap_% = gap / shuf_CVaR × 100. CVaR scale differs (CA ~1.59 M vs Iberia ~0.40 M)
because Iberian carbon intensity is lower — so the **% gap** is the comparable
quantity.

| regime | α | **CA gap_%** | CA detect | **Iberia gap_%** | IB detect |
|---|---|---|---|---|---|
| R3 | 0.30 | +0.058 | yes | +0.0000 | (ε*=0, ≡) |
| R3 | 0.50 | +0.036 | no | −0.0000 | (ε*=.1, ≡) |
| R3 | 0.75 | −0.012 | no | +0.021 | no |
| R1 | 0.30 | +0.016 | no | −0.002 | no |
| R1 | 0.50 | +0.027 | no | +0.015 | no |
| R1 | 0.75 | +0.002 | yes* | **+0.321** | **yes** ⚠ |
| R2 | 0.30 | +0.018 | yes | −0.007 | no |
| R2 | 0.50 | +0.026 | no | +0.000 | no |
| R2 | 0.75 | +0.002 | yes* | −0.016 | no |

`*` CA cells: detectable but 0.0017 % — economically meaningless (near-identical
schedules). `⚠` Iberia R1/α0.75: see §4.1.

Both studies: the gap is a few hundredths of a percent of CVaR essentially
everywhere. Neither shows an economically meaningful, robust spatial benefit.

### 4.1 The Iberian R1/α=0.75 cell (the one apparent exception)

| estimator | ε* joint/shuf | gap_% | detectable | clean? |
|---|---|---|---|---|
| sample cov | 1 / **10** | **+0.321** | yes | no — ε* diverge |
| Ledoit-Wolf shrinkage | 1 / **10** | **+0.321** | yes | no — ε* diverge |
| seasonal residual | 1 / 1 | **−0.032** | yes | yes |
| AR(1) residual | 1 / 1 | **−0.037** | yes | yes |

The raw-level +0.32 % materializes *only* when CV gives the shuffled arm ε*=10
(a poorly-fitting radius for the block-diagonal covariance) while the joint arm
gets ε*=1. That is an artifact of comparing two arms at different penalties, not
evidence that the joint covariance is informative. Under residual-space
estimation both arms select ε*=1 and the gap **flips negative** (joint marginally
worse, ~−0.03 %); seasonal and AR(1) **agree** on that flip, so the locked
agreement rule records **no beneficial spatial effect**. Reported transparently;
not spun into a divergence.

---

## 5. Robustness (Iberia, R1+R2)

- **Ledoit–Wolf shrinkage:** reproduces every raw-level gap (including the R1/α0.75
  artifact) — does not create or widen a robust separation.
- **Residual-space (seasonal & AR(1), agreement rule):** the only cell where
  seasonal∧AR(1) agree in sign is R1/α0.75, where they agree the joint is
  *marginally worse* (−0.03 %). AR(1) drives ε*→0 for several cells (DRO off →
  joint≡shuf → machine-noise gaps), as in California. No agreed *beneficial*
  spatial effect anywhere.

Same qualitative robustness picture as California: shrinkage-invariant, and no
residual-space agreement on a positive spatial effect.

---

## 6. Repo state

- Branch `taskB-iberia` off merged `main` (Task A at 353fe46). Config
  commit-locked at `180e2a9` before the 2025 test set was touched; dry-run gate
  passed first.
- Parameterization (additive; US/Task A untouched): `REGION_ORDER_IBERIA` +
  `DEFAULT_TZ_IBERIA` in covariance.py; ES/PT/FR coords in temperature.py;
  `--region-set` in fetch_temperature.py.
- New scripts: `run_shuffled_marginals_iberia_experiment.py`,
  `calibrate_iberia_regimes.py`, `report_binding_margins_iberia.py`.
- New tests: `tests/test_iberia.py` (4). Suite: **145 passed** (141 Task A + 4).
- Results: `results/iberia_regimes_2026-06-05*.csv/.pkl` (main + 4 robustness ×
  {R1,R2}). Cached temperature: `data/raw/temperature/openmeteo_{ES,PT,FR}_*.csv`.

---

## 7. Hand-back to planning-Claude

1. **Side-by-side tables** (§4) + **binding margins** (§3): Iberia replicates the
   California null. Both grids: spatial gap a few hundredths of a percent, no
   robust beneficial effect, sets not frozen (substantive null).
2. **One-line verdict:** *Iberia replicates — it does NOT diverge.* The more-coupled
   MIBEL grid does not surface spatial value; the lone detectable raw cell
   (R1/α0.75, +0.32 %) is an ε-selection artifact that reverses under
   residualization.
3. **Thesis framing:** "more than one case" is now a **replicated null across two
   independent grids (CAISO/NV and MIBEL+FR)** — a robust general finding, not a
   single-region fluke. The honest treatment of the R1/α0.75 artifact is itself a
   methodological strength (the residual-space + agreement-rule machinery caught a
   CV-selection false positive).
