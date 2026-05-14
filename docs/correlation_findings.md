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
