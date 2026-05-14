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

## Template for new entries

## YYYY-MM-DD — One-line decision summary

**Decision:** What was decided.

**Alternatives considered:** Other options on the table.

**Reason:** Why this choice.

**Revisit if:** Conditions that would force reconsidering.
