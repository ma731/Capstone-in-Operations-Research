"""Algorithm 2a: ell_infinity Wasserstein DRO baseline.

Implements the degenerate closed-form lift of Hall et al. (2024) to the
multi-region setting under the ell_infinity ground metric. Per progress note
v8.3, equation (4):

    min_{x in X}  <rho_bar, x> + epsilon * ||x||_1

where x in R^{R x T}_{>= 0}, X enforces sum_t x_{r,t} == W_r (equality) and
x_{r,t} <= ceiling_{r,t}. With x >= 0, ||x||_1 = sum_{r,t} x_{r,t}; with the
work constraints binding at equality, this collapses to sum_r W_r, which is
constant in x. The optimizer is therefore independent of epsilon, equal to
the deterministic Algorithm 1 schedule on the mean field rho_bar.

This module is a thin wrapper around Algorithm 1. It exists to:
  (i) verify the degeneracy result numerically on real data,
 (ii) provide the empirical anchor for the Mahalanobis contribution (A2b),
(iii) report the closed-form decomposition <rho_bar, x*> + epsilon * sum W_r
      so the worst-case bound is auditable even though the schedule is not
      epsilon-dependent.

See progress_note_v8_3.tex Section 2 ("The ell_infinity baseline and its
degeneracy") for the full derivation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

from src.models.algorithm_1 import schedule_deterministic_single_cluster
from src.models.covariance import REGION_ORDER


@dataclass
class LinfDROResult:
    """Output of Algorithm 2a.

    Attributes:
        schedule: (R, T) optimal schedule matrix in MW.
        schedule_per_region: dict mapping zone_id to (T,) schedule.
        rho_bar: (R, T) empirical mean carbon-intensity field used.
        mean_carbon_value: <rho_bar, x*> (the empirical mean carbon).
        penalty: epsilon * sum_r W_r (the constant ell_1 penalty).
        robust_value: mean_carbon_value + penalty (closed-form worst case).
        epsilon: the Wasserstein radius used.
        n_samples: number of daily samples used to compute rho_bar.
    """

    schedule: np.ndarray
    schedule_per_region: dict[str, np.ndarray]
    rho_bar: np.ndarray
    mean_carbon_value: float
    penalty: float
    robust_value: float
    epsilon: float
    n_samples: int


def solve_linf_dro_baseline(
    panel: np.ndarray,
    workloads: np.ndarray,
    ceiling: np.ndarray,
    epsilon: float = 0.0,
    region_order: Sequence[str] = REGION_ORDER,
    solver: Optional[str] = None,
) -> LinfDROResult:
    """Solve the ell_infinity Wasserstein DRO baseline.

    Args:
        panel: (N, R, T) daily samples of carbon intensity (gCO2eq/kWh).
        workloads: (R,) per-region workload requirements W_r in MWh.
        ceiling: (R, T) per-hour capacity ceiling x_bar_{r,t} in MW.
        epsilon: Wasserstein radius >= 0. The optimal schedule is invariant
            to epsilon for this formulation (this is the Phase 1 finding);
            epsilon only affects the closed-form robust value.
        region_order: zone identifiers in row-major order matching the R
            axis of panel and ceiling. Used to build schedule_per_region.
        solver: optional CVXPY solver name passed through to Algorithm 1.

    Returns:
        LinfDROResult.

    Raises:
        ValueError: if shapes are inconsistent, epsilon is negative, or
            region_order length does not match the R axis of panel.
    """
    panel = np.asarray(panel, dtype=float)
    workloads = np.asarray(workloads, dtype=float)
    ceiling = np.asarray(ceiling, dtype=float)

    if panel.ndim != 3:
        raise ValueError(f"panel must be 3-D (N, R, T), got shape {panel.shape}")
    N, R, T = panel.shape
    if workloads.shape != (R,):
        raise ValueError(
            f"workloads must have shape (R,) = ({R},), got {workloads.shape}"
        )
    if ceiling.shape != (R, T):
        raise ValueError(
            f"ceiling must have shape (R, T) = ({R}, {T}), got {ceiling.shape}"
        )
    if epsilon < 0:
        raise ValueError(f"epsilon must be non-negative, got {epsilon}")
    if len(region_order) != R:
        raise ValueError(
            f"region_order has {len(region_order)} entries but panel has R={R}"
        )

    # Empirical mean field across daily samples.
    rho_bar = panel.mean(axis=0)  # (R, T)

    # The deterministic problem on rho_bar separates into R independent LPs
    # (one per region). For each region, solve Algorithm 1 with the equality
    # work constraint (per progress note v8.3 Section 1) and a ceiling
    # constructed so the effective cap equals the operator's x_bar_{r,t}.
    schedule = np.zeros((R, T))
    for r in range(R):
        # Pass the per-hour ceiling as `demand` and a non-binding capacity_max.
        # Since A1's effective ceiling is min(demand, capacity_max), setting
        # capacity_max = ceiling[r].max() guarantees min(demand_t, cap_max)
        # = demand_t for all t.
        cap_max_for_region = float(ceiling[r].max())
        result = schedule_deterministic_single_cluster(
            carbon_intensity=rho_bar[r],
            demand=ceiling[r],
            capacity_max=cap_max_for_region,
            total_work=float(workloads[r]),
            equality_work=True,
            solver=solver,
        )
        schedule[r] = result.schedule

    # Closed-form decomposition.
    mean_carbon_value = float(np.sum(rho_bar * schedule))
    penalty = float(epsilon * np.sum(workloads))  # = epsilon * sum_r W_r
    robust_value = mean_carbon_value + penalty

    schedule_per_region = {
        region_order[r]: schedule[r].copy() for r in range(R)
    }

    return LinfDROResult(
        schedule=schedule,
        schedule_per_region=schedule_per_region,
        rho_bar=rho_bar,
        mean_carbon_value=mean_carbon_value,
        penalty=penalty,
        robust_value=robust_value,
        epsilon=epsilon,
        n_samples=N,
    )
