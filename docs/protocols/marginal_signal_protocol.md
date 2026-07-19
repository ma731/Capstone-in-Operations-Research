# D1 pre-registered protocol: does the dependence null survive a marginal signal?

Status: DRAFT scaffold, 2026-07-19. This document becomes binding when it is
commit-locked together with the experiment config, BEFORE any test-year read
of marginal data. Until data access lands it records the design so the
experiment cannot drift toward the data.

## Hypotheses (fixed in advance)

- H0 (survival): under a marginal-emissions signal, the shuffled-marginals
  gap in out-of-sample CVaR_0.95 stays below the 0.4% materiality margin on
  every grid, i.e. the dependence null is signal-independent.
- H1 (flip): the gap exceeds the margin with the pre-registered agreement
  rule satisfied (raw and residualized runs agree in sign and materiality).

Either outcome is reportable; the protocol does not privilege H0.

## Why this could flip the null (stated before seeing data)

The mean-dominance mechanism explains the average-CI null: the diurnal mean
field carries the value and the covariance is second order. Marginal signals
are spikier, less diurnally regular, and less spatially smooth than average
CI, so the mean field plausibly carries LESS of the signal and dependence
plausibly more. If mean dominance weakens, Part 5's ratio Delta should say so
in advance: the pre-registered prediction is that the sign of the outcome is
the sign Delta assigns (Delta computed on marginal training data, before the
test read).

## Design (mirrors the locked Phase 1 pipeline exactly)

1. Data: per-zone marginal CI at hourly resolution, 2021-2025, same zones as
   the average-CI panels, loaded via src/data/marginal_signal.py into the
   identical wide format. Provider: WattTime MOER (academic access) or
   Electricity Maps premium marginal; provider recorded in the locked config.
2. Same shared feasible set, same Mahalanobis-Wasserstein scheduler, same
   epsilon grid and selection rule, same train/validation/test years as the
   corresponding locked average-CI configs. NOTHING is re-tuned to the new
   signal.
3. Falsification: shuffled-marginals test (joint vs block-diagonal
   covariance), gap measured in out-of-sample CVaR_0.95 of the MARGINAL
   objective. Secondary readout: schedules optimized on marginal, evaluated
   on average CI (and vice versa), quantifying the e-Energy'24 signal-conflict
   on our decision axis.
4. Robustness battery (unchanged): Ledoit-Wolf, seasonal + AR(1)
   residualization, BH correction across cells, TOST equivalence at the 0.4%
   margin, agreement rule for any positive cell.
5. Gates, in order:
   a. Coverage dry-run: coverage_report >= 99% of carbon-grid hours per zone
      on train years; else the grid is excluded (recorded, not silently).
   b. Commit-lock this protocol + config (this file's hash cited in the
      locked config).
   c. Dry-run on train/validation years only.
   d. ONE read of the test year, results archived to docs/results_snapshots
      regardless of outcome.

## Data access status

- WattTime academic access: application pending (owner: Marco).
- Electricity Maps premium marginal: not covered by the current academic
  licence; would need an upgraded agreement.
- Marginal files live under data/raw/marginal/ (gitignored, licence-safe,
  never committed), one CSV per zone; schema in src/data/marginal_signal.py.

## Deliverable

Section in P1 (e-Energy 2027 fall cycle): "the null is signal-independent" or
"the null is a property of the average signal", either with the full battery
behind it. See docs/roadmap_papers.md.
