# Which Constraints Actually Move the Results?

Generated 2026-07-12 by `python -m scripts.analyze_constraint_sensitivity`, which reads only the committed license-safe snapshots — anyone can regenerate this table without the raw data. Source snapshot: `constraint_sensitivity_2026-07-12.csv`.

Two different questions hide inside "which constraint matters most," and they have different answers:

- **Axis A — conclusion impact:** how much does a knob shift the *spatial-null gap* (the RQ2 headline: joint-vs-shuffled covariance, in percentage points of CVaR), measured cell-by-cell across matched regime × alpha cells?
- **Axis B — magnitude impact:** how much does the knob rescale the *problem itself* (the joint schedule's absolute CVaR level, in %)?

## Ranked table (max over grid families; A descending)

| Knob | Family | A: max gap shift (pp) | A: mean (pp) | B: mean CVaR shift (%) |
|---|---|---|---|---|
| Walk-forward test year 2023 | test-year | 0.42 | 0.08 | 10.3 |
| Walk-forward test year 2022 | test-year | 0.33 | 0.06 | 7.7 |
| Seasonal residualization | estimator | 0.29 | 0.06 | 0.05 |
| Utilization 0.50 (slack) | feasibility | 0.28 | 0.05 | **38.7** |
| Utilization 0.95 (tight) | feasibility | 0.24 | 0.06 | **20.2** |
| Walk-forward test year 2024 | test-year | 0.24 | 0.07 | 4.6 |
| AR(1) residualization | estimator | 0.23 | 0.07 | 0.07 |
| Ramp limit 5%/step | feasibility | 0.23 | 0.05 | 0.31 |
| Risk tail CVaR_0.99 | metric | 0.15 | 0.05 | 4.9 |
| Risk tail CVaR_0.90 | metric | 0.05 | 0.02 | 2.3 |
| Ledoit–Wolf shrinkage | estimator | **0.007** | 0.0004 | 0.0003 |

## The three findings in the table

**1. Capacity is the constraint that matters — for magnitude, not for conclusions.** Utilization dominates axis B by an order of magnitude (a slack fleet at 0.50 shifts the absolute CVaR level by ~39%, a tight one at 0.95 by ~20%), yet moves the scientific conclusion by at most 0.28pp. In deployment terms: how much headroom your fleet has is the number that controls the size of everything; in scientific terms, the null does not care. The `part5_sweep` supplement makes the mechanism exact: the theoretical bound Δ scales as 1/κ *precisely* (verified ratio-constant across all three grids) — capacity tightness κ is the single knob that linearly controls the Proposition-1 bound.

**2. The largest conclusion-mover is the test year — and it is still small.** Choosing 2023 as the held-out year produces the biggest cell-level shift of the null gap anywhere in the battery (0.42pp on a stress cell; mean 0.08pp). That the *worst* knob at the *worst* cell moves the gap by well under half a percentage point is the strongest single sentence available for the null's robustness — and it is exactly why the walk-forward replication exists.

**3. The estimator barely matters, and Ledoit–Wolf matters least of all — which is itself evidence.** Swapping the covariance estimator moves the gap by ≤0.29pp (seasonal/AR1) and by 0.007pp for Ledoit–Wolf: effectively nothing on either axis. If the RQ2 null were an artifact of covariance estimation error, better-conditioned estimation would move it. It does not — consistent with the mean-dominance mechanism, where the covariance term is dominated regardless of how well it is estimated.

## RQ3 supplements

**Tail level (dro_tail_sensitivity):** the DRO-vs-deterministic gap stays null across CVaR_0.90/0.95/0.99 on us_west and taskc (all ≤0.47%), while us_hetero is *adversely negative at every tail* (−8.6 to −10.3%) — the disclosed adverse result is tail-robust too, i.e., it is not an artifact of the 0.95 choice.

**Capacity tightness (part5_sweep):** Δ ∝ 1/κ exactly on all grids (Δ spanning e.g. 1.9→38.5 on us_west as κ goes 1.0→0.05). Practical reading: the a-priori certificate loosens hyperbolically as fleets run tighter; tight-capacity deployments are where the bound is least informative and the empirical battery carries the weight.

## One caution on reading axis A
Axis A measures the max/mean |shift| of gap_pct across *all* matched regime × alpha cells, including deliberately stressed regimes; it is a different (and stricter, cell-wise) quantity than the headline walk-forward statement about the null gap itself. Both are reported; neither contradicts the other.
