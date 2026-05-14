# Empirical Carbon Intensity Correlations — California Sub-Zones

**Date:** 14 May 2026
**Data:** Electricity Maps lifecycle hourly carbon intensity (gCO₂eq/kWh)
**Zones:** US-CAL-CISO, US-CAL-BANC, US-CAL-LDWP
**Period:** 2021-01-01 — 2025-12-31, hourly (UTC)
**Sample size:** 43,824 observations per zone (= 5 calendar years × 8,760h + 1 leap day; no missing hours after wide-format join)

## Mean carbon intensity (2024)

| Zone           | Mean (gCO₂eq/kWh) |
|----------------|-------------------|
| US-CAL-CISO    | 226.0             |
| US-CAL-BANC    | 272.7             |
| US-CAL-LDWP    | 393.6             |

LDWP averages ~74% above CAISO. Reflects LADWP's higher gas share vs CAISO's larger solar/wind fleet.

## Pairwise correlations (raw lifecycle CI, hourly)

### 2024 only
|       | BANC  | CISO  | LDWP  |
|-------|-------|-------|-------|
| BANC  | 1.000 | 0.489 | 0.557 |
| CISO  | 0.489 | 1.000 | 0.772 |
| LDWP  | 0.557 | 0.772 | 1.000 |

### Full 2021–2025
|       | BANC  | CISO  | LDWP  |
|-------|-------|-------|-------|
| BANC  | 1.000 | 0.426 | 0.586 |
| CISO  | 0.426 | 1.000 | 0.755 |
| LDWP  | 0.586 | 0.755 | 1.000 |

## Findings

1. **Goldilocks band (0.43–0.77).** All pairs strong enough that spatial structure exists, weak enough that joint modelling materially differs from independent marginals.
2. **Stable across 5 years.** All three pair correlations sit within ±0.06 of their 2024 values when computed over the full 2021–2025 panel. The result is not a single-year artifact.
3. **CISO ↔ LDWP is the strongest pair** (0.755). Consistent with the shared statewide solar fleet driving simultaneous midday CI troughs in both zones.
4. **BANC pairs are moderate** (0.426 with CISO, 0.586 with LDWP). BANC's significant hydro share gives it a generation signature partially decoupled from the solar-driven zones.
5. **Slight downward drift in BANC ↔ CISO** (0.489 → 0.426 from 2024 snapshot to 5-year mean). Likely tied to interannual variation in BANC hydro output (wet vs dry years). Flagged for stratified follow-up.

## Implications for the model

The Wasserstein DRO ambiguity set must be defined over the joint distribution in ℝ³. A shuffled-marginals baseline (which enforces independence while preserving each zone's marginal) should produce visibly worse worst-case schedules than the joint formulation — this is the cleanest empirical test for whether spatial correlation matters for the optimization, and is the primary sensitivity experiment for Phase 1.

The asymmetric structure (one strong pair, two moderate pairs) means the joint distribution is genuinely non-degenerate, not trivially close to the product of marginals.

## Caveat — raw vs residual correlations

These figures are computed on raw hourly CI, which is dominated by the diurnal solar cycle. A trivial persistence forecaster would capture most of this signal for free. The defensible claim that *forecastable spatial structure* exists requires correlation of **forecast residuals**, not raw CI. Slated for the next analysis block once a baseline forecaster (persistence + AR(1)) is implemented.

## Next analyses

- Stratified correlations: hour-of-day, season, weekday/weekend
- Residual correlations after persistence and AR(1) baselines
- Conditional copula diagnostics (Kendall's τ, tail dependence) — input for Phase 2 vine copula extension

---

# Update — 14 May 2026: Stratified Analysis

Building on the aggregate result above, pairwise correlations were re-computed conditional on hour-of-day, season, and day-type. All stratification uses **local Pacific time** (America/Los_Angeles), since the operationally relevant dynamics — solar cycle, dispatch, business hours — follow local time, not UTC. Full results are stored in `docs/stratified_results.txt`; the analysis module is `src/analysis/stratified_correlations.py` (10 passing tests).

## Hour-of-day

Three regimes emerge:

| Regime | Hours (local) | Pattern |
|---|---|---|
| Overnight | 22:00–05:00 | All pairs correlate uniformly at ~0.70–0.78. |
| Solar window | 08:00–14:00 | BANC–CISO collapses to 0.37–0.43. CISO–LDWP stays at 0.70+. BANC–LDWP at ~0.58. Pair behavior diverges. |
| Evening transition | 17:00–21:00 | CISO–LDWP weakens to ~0.62; BANC–CISO recovers to ~0.65. |

BANC–CISO ranges from 0.374 at 10:00 to 0.778 at 02:00 — roughly a factor-of-two swing within a single day. CISO–LDWP stays in a tighter band (0.62–0.77). The pair-specific intraday signature is consistent with the generation-mix hypothesis: CISO and LDWP both have heavy solar exposure and move together during the solar window, while BANC's larger hydro share decouples it from CISO when solar dominates dispatch.

## Season (meteorological)

|  | BANC–CISO | BANC–LDWP | CISO–LDWP | n |
|---|---|---|---|---|
| DJF (winter) | 0.304 | 0.441 | 0.622 | 10,824 |
| MAM (spring) | 0.251 | 0.428 | 0.760 | 11,035 |
| JJA (summer) | 0.326 | 0.510 | 0.687 | 11,040 |
| SON (autumn) | **0.188** | **0.245** | 0.752 | 10,925 |

Autumn shows the weakest correlations across BANC pairs — plausibly tied to seasonally low hydro output and shifting weather systems. CISO–LDWP is relatively stable across seasons (0.62–0.76), reinforcing the interpretation that this pair is dominated by the shared statewide solar fleet. The BANC–CISO seasonal range (0.19 → 0.33) is large enough to constitute a regime-dependence finding, not noise.

## Day-type

|  | BANC–CISO | BANC–LDWP | CISO–LDWP | n |
|---|---|---|---|---|
| Weekday | 0.440 | 0.605 | 0.748 | 31,296 |
| Weekend | 0.385 | 0.539 | 0.768 | 12,528 |

Modest differences (≤0.07). BANC pairs slightly stronger on weekdays — consistent with more uniform industrial load — and CISO–LDWP slightly stronger on weekends. Not the headline story.

## Implications

1. **The diurnal cycle does not explain away spatial correlation.** If it did, hour-conditional correlations would collapse to near-zero. They don't; they reveal additional pair-specific structure. The aggregate BANC–CISO correlation (0.43) is in fact *lower* than the typical hour-conditional value (~0.58), indicating the diurnal cycle slightly *decorrelates* this pair (BANC and CISO have different diurnal shapes). The aggregate is therefore a conservative under-estimate of the conditional dependence relevant for short-horizon scheduling.

2. **Dependence is regime-dependent.** BANC–CISO ranges from 0.19 (autumn) to 0.78 (overnight summer). A scalar uncertainty model cannot represent this. An independent-marginals model preserves the marginal distributions but discards the regime structure entirely. The joint Wasserstein DRO in the proposed extension is the simplest formulation capable of capturing both.

3. **Phase 2 hook.** Regime-conditional or regime-switching ambiguity sets are a natural follow-up direction for the publication track. The stratified evidence here motivates that work without requiring it for the capstone.

## Caveats specific to this analysis

- All correlations are **Pearson** (linear dependence). With right-skewed CI distributions, rank-based and copula-based measures may reveal additional tail dependence. Slated as part of the Phase 2 vine-copula block.
- Operational interpretations (e.g., "BANC's hydro decouples from solar") are **plausible hypotheses, not verified causal claims**. Cross-checking against EIA generation-by-fuel decomposition is a worthwhile follow-up before committing to these stories in print.
- These remain **raw-CI correlations**, not forecast-residual correlations. The residual-correlation analysis (persistence and AR(1) baselines) remains the next major analytical block and is necessary for any rigorous operational-value claim.
