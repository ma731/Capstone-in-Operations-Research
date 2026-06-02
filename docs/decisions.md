# Design decisions

Every meaningful choice gets logged here. Date, decision, alternatives considered, reason.

The point: future-you (and Bissan) will ask "why did we do it this way?" and the answer should be findable.

---

## 2026-05-XX — Project scope and base model

**Decision:** Build on Hall et al. 2024 (Wasserstein DRO with VCCs) rather than Radovanović 2022 (CICS with quantile inflation).

**Alternatives considered:**
- Radovanović 2022 directly — simpler but less rigorous
- Custom from-scratch DRO formulation — too much reinvention

**Reason:** Hall's framework provides probabilistic performance guarantees and is the most recent state-of-the-art. Extension is well-defined.

---

## 2026-05-XX — Stochastic variable choice

**Decision:** Treat carbon intensity $\rho^{\text{carb}}$ as the stochastic vector; load $s$ deterministic.

**Alternatives considered:**
- Joint $(s, \rho^{\text{carb}})$ ambiguity — more ambitious but overlaps with teammate's scope
- Load-only stochastic (Hall's original) — doesn't capture the spatial-carbon angle

**Reason:** Clean scope separation from the joint load+carbon teammate. Isolates the spatial-carbon contribution.

---

## 2026-05-XX — Geographic framing

**Decision:** Regional ISO scale (CAISO sub-regions, ISO-NE zones) rather than continental (Germany-Spain).

**Alternatives considered:**
- Continental European grids — Bissan flagged these as too geographically separated
- Single ISO only — loses the spatial story

**Reason:** Within-ISO sub-regions share weather and dispatch constraints, giving meaningful hourly correlation. Cross-continental correlations are weaker and harder to motivate.

## Decision 4 — Data source: Electricity Maps academic-access bulk CSVs

**Date:** 14 May 2026
**Choice:** Electricity Maps academic-access bulk CSV downloads, lifecycle hourly carbon intensity, 2021–2025, three California sub-zones (US-CAL-CISO, US-CAL-BANC, US-CAL-LDWP).
**Alternative considered:** Pulling each balancing authority's data directly from EIA/CAISO/LADWP and computing carbon intensity from EPA emission factors.
**Why Electricity Maps:** Sub-zonal US data is available at academic tier (58 US balancing authorities, Tier A quality, 2017–present). Already engineered to high standard with consistent lifecycle methodology across zones. Rebuilding from raw generation + EPA factors would be ~2 weeks of engineering for no methodological gain and worse cross-zone comparability.

## Decision 5 — California geography confirmed empirically

**Date:** 14 May 2026
**Choice:** Three California sub-zones (CISO, BANC, LDWP) confirmed as Phase 1 scope.
**Evidence:** Pairwise correlations on 5-year hourly panel (n=43,824) sit in 0.43–0.77 band — strong enough for spatial structure to exist, weak enough for joint modelling to be non-trivial vs independent marginals. Asymmetric structure (CISO–LDWP at 0.755, BANC pairs at 0.43–0.59) is non-degenerate. See `correlation_findings.md`.
**NY/Boston pair:** Deferred to Phase 2 publication extension.

---

## Decision 6 — Drop the aggregate power cap; revise the feasible set (Task A)

**Date:** 2026-06-02
**Choice:** Remove the aggregate per-hour cap (`p_max=None`); keep per-cell
ceiling + flex/inflexible split + ramp; ADD a windowed-demand deadline (3a) and
a temperature-coupled thermal/PUE constraint (3b). DRO method unchanged.
**Alternatives considered:** Keep the cap and tune P_max (it dominated the
polytope geometry and was the main thing coupling regions deterministically);
add only one new constraint.
**Reason:** The cap was a single global knob that froze the operating point; the
deadline and thermal limits are more physically defensible and local. The new
set is still non-trivial (greedy infeasible, solver required) and not frozen
(24–32 % reallocation room in every regime), so the re-confirmed null is
substantive. See `docs/progress_note_v13.md`, `thesis/full_formulation.md`.
**Revisit if:** a different ISO/geography or a higher-fidelity thermal model
changes the binding structure.

## Decision 7 — Temperature data source: Open-Meteo ERA5, one load-center per zone

**Date:** 2026-06-02
**Choice:** Open-Meteo historical archive API (ERA5 reanalysis), hourly 2 m air
temperature 2021–2025, ONE representative load-weighted point per zone
(CISO→Fresno/Central Valley, BANC→Sacramento, LDWP→Los Angeles, NEVP→Las Vegas),
cached under `data/raw/temperature/`.
**Alternatives considered:** Multi-station spatial averaging per zone; NOAA/ISD
station data; coastal SF for CISO.
**Reason:** A single load-center point matches the fidelity of the assumed PUE
curve (a smooth function of one temperature); ERA5 is free (no key for academic
volumes), gap-free, and on a clean UTC grid. CISO mapped to warm inland Fresno
(not coastal SF) and distinct from LDWP=LA. Multi-station is a noted refinement,
not implemented. Verification Gate 1 passed (tz, shape, stats).
**Revisit if:** the thermal constraint becomes a headline result rather than a
tighter-regime sensitivity point — then multi-station averaging is worth it.

---

## Template for new entries

## YYYY-MM-DD — One-line decision summary

**Decision:** What was decided.

**Alternatives considered:** Other options on the table.

**Reason:** Why this choice.

**Revisit if:** Conditions that would force reconsidering.
