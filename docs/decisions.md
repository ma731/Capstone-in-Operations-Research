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

## Decision 8 — Variable carbon-coupled capacity ceiling (Task C, 3c)

**Date:** 2026-06-09
**Choice:** For Task C, replace the flat per-cell ceiling with a CFE-driven one:
`x_bar_{r,t} = x_min + (x_max - x_min) * CFE_{r,t} / 100`, where `CFE` is the
training-mean carbon-free-energy fraction (Electricity Maps `cfe_pct`). Adapted
from Wijayawardana & Chien (SoCC '25), "Scheduling Cloud VMs on Variable Capacity
Datacenters."
**Alternatives considered:** (a) keep the flat ceiling (no capacity channel);
(b) drive capacity off `RE%` (renewables only) instead of `CFE%`; (c) make
capacity STOCHASTIC.
**Reason:** CFE% is the truer "clean capacity available" signal — RE% excludes
the nuclear/hydro baseload that dominates Ontario. Treated as DATA (training-mean
field, exactly like the 3b thermal field) so the program stays an SOCP and the
carbon-only-stochastic scope (Decision 2) is preserved. Thesis motivation: CFE is
spatially correlated through shared weather, so a CFE-driven ceiling makes
CAPACITY co-vary across regions — a second spatial channel beyond the carbon-cost
coupling in Sigma_hat, and the mechanism by which Task C might break the A/B null.
**Rejected stochastic capacity:** would change the ambiguity set to
(rho, capacity) and collide with the joint-uncertainty teammate's scope. Not
without Bissan's sign-off.
**Calibration (CLOSED, 2026-06-11):** `x_min, x_max` calibrated to the loosely-
binding "Goldilocks" regime on TRAINING data via `scripts/calibrate_capacity.py`,
which sweeps candidate bounds and reports the R2-schedule binding fraction, mean
slack, and per-region capacity margin (no test-set peek — CFE field + schedule on
train years only). Selected **`x_min=50, x_max=75`**: a single pair that is
Goldilocks across all three cases (us_west bind 0.33 / slack 35% / margin 41%;
taskc 0.37 / 37% / 47%; us_hetero 0.28 / 39% / 51%) — the constraint is active
(~1/3 of cells at the ceiling) but the schedule keeps real freedom and the problem
stays feasible with headroom. Supersedes the provisional `(42, 65)`, which pinned
~50% of cells (too tight). Functional form reconciled against SoCC'25 §2.1
(constant carbon budget → capacity falls as carbon intensity rises).

## Decision 9 — Carbon-budget constraint (Task C, 3d)

**Date:** 2026-06-09
**Choice:** Optional cap on NOMINAL carbon `sum_{r,t} rho_bar_{r,t} x_{r,t} <= B`,
added to both `schedule_deterministic_coupled` and `solve_mahalanobis_dro`
(`carbon_budget` kwarg, default `None` = off). Adapted from the ZCCloud
carbon-budget framing.
**Alternatives considered:** (a) robust budget `mean + eps*penalty <= B`;
(b) penalize carbon in the objective rather than constrain it.
**Reason:** A nominal-carbon cap is the standard, SOCP-preserving choice and a
clean operational constraint. SEMANTICS to note: in the pure-min deterministic
baseline the objective already minimizes carbon, so a budget is slack-or-
infeasible there (no-op above the achievable minimum); it only meaningfully BINDS
in the DRO, where robustness (large eps) inflates nominal carbon above the
deterministic minimum and the budget caps that trade-off. Verified in
`tests/test_carbon_budget.py`.
**Revisit if / open:** `B` is not yet calibrated; set it as a loose multiple
(e.g. 1.05x) of a reference schedule's carbon during the Goldilocks pass.
Consider the robust-budget variant if Bissan wants the cap on worst-case carbon.

## 2026-06-13 — Phase 2: copula schedulers (independence / Gaussian / Clayton)

**Decision:** Generalize the shuffled-marginals falsification from the covariance
ball to the full copula via **copula-coupled empirical resampling** + a CVaR-SAA
LP scheduler. Three nested dependence models — independence (the Phase 1 "shuf"
arm), Gaussian (elliptical), and exchangeable Clayton (lower-tail, λ_L=2^(-1/θ),
fit by Kendall τ) — each generate S=1000 scenarios that feed a Rockafellar–Uryasev
CVaR LP over the *same* feasible set X. New code: `src/models/feasible_set.py`
(shared X), `src/models/cvar_saa.py`, `src/models/copula_scenarios.py`,
`scripts/run_copula_experiment.py`, `scripts/plot_copula.py`,
`tests/test_phase2_copula.py` (5 tests incl. feasible-set equivalence to Phase 1).

**Alternatives considered:** (a) full copula-ambiguity Wasserstein DRO
(Fan–Ji–Lejeune) — too heavy for the timeline, left as future work; (b)
pyvinecopulib R-vines — extra dependency, and exchangeable Clayton already isolates
the lower-tail hypothesis with numpy-only Marshall–Olkin sampling; (c) parametric
marginals — rejected in favor of empirical day-pool resampling (no marginal
misspecification, mirrors Phase 1 exactly).

**Reason:** Forecloses the "you used the wrong dependence object" objection to the
Phase 1 null. Result: the null is **total** — max |gap vs independence| = 0.13%
(us_hetero), none sign-stable; Clayton edges Gaussian only in the heterogeneous
case (+0.07%), confirming the copula captures the asymmetry but it is immaterial.
Formalized by the mean-dominance Proposition (CVaR translation invariance splits
the copula-independent mean term from the residual tail; the mean-ablation measures
the copula's leverage Λ directly). Snapshots: `*_copula_2026-06-13.csv`.

**Revisit if:** Bissan wants the full copula-ambiguity DRO, or the transfer channel
(the one route the mean-dominance bound does *not* close).

## Template for new entries

## YYYY-MM-DD — One-line decision summary

**Decision:** What was decided.

**Alternatives considered:** Other options on the table.

**Reason:** Why this choice.

**Revisit if:** Conditions that would force reconsidering.
