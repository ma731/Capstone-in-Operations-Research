# Algorithm 2a empirical degeneracy summary

Source: `scripts/run_algorithm2a_degeneracy_demo.py`, 4-zone panel
(N=1815, R=4, T=24), dates 2021-01-01 to 2025-12-30.
Workloads 600 MWh/region; flat 50 MW ceiling.

## Epsilon invariance

| epsilon | robust_value (gCO2) | max schedule deviation |
|---------|---------------------|------------------------|
| 0.0 | 723,313 | 0.00e+00 |
| 1.0 | 725,713 | 0.00e+00 |
| 100.0 | 963,313 | 0.00e+00 |
| 10000.0 | 24,723,313 | 0.00e+00 |

Max schedule deviation across the four epsilon values: **0.00e+00** -- 
within numerical tolerance of zero, empirically confirming the closed-form
result that the argmin is independent of epsilon.

## Joint vs shuffled invariance (epsilon = 100.0)

- Per-coordinate rho_bar deviation: **1.42e-12**
- Schedule max-element deviation: **2.98e-13**
- Robust value deviation: **1.16e-10** gCO2 on a base of 963,313 gCO2

The per-region temporal shuffle preserves rho_bar exactly (the residual
is floating-point noise), and consequently the A2a schedule and robust
value are identical to numerical precision. This is the empirical
confirmation of the joint-vs-shuffled degeneracy under ell_infinity.

## Closed-form decomposition

`robust_value = <rho_bar, x*> + epsilon * sum_r W_r`

- Mean term `<rho_bar, x*>`: 723,313 gCO2
- Penalty term `epsilon * sum_r W_r`: 240,000 gCO2
- Decomposition residual: 0.00e+00 gCO2

## Conclusion

The natural Wasserstein lift to R^(R*T) under the ell_infinity ground
metric is schedule-degenerate on this panel: epsilon does not affect
the optimal schedule, and the joint and per-region-shuffled ambiguity
balls yield identical schedules and identical robust values. The
Mahalanobis-Wasserstein reformulation of Algorithm 2b is therefore the
first formulation in this work in which the joint covariance structure
can affect the optimizer.
