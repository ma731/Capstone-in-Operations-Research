"""Algorithm 1: Deterministic single-cluster carbon-aware scheduling.

The pedagogical baseline. Given a known forecast of carbon intensity and
demand over a 24-hour horizon, schedule compute to minimize total carbon
cost while completing all required work.

See docs/algorithm-spec.pdf, Section 4.
"""

from dataclasses import dataclass
from typing import Optional

import cvxpy as cp
import numpy as np

from src.models.feasible_set import build_feasible_constraints


@dataclass
class ScheduleResult:
    """Output of Algorithm 1."""

    schedule: np.ndarray         # x*[t] in MW for t = 0..T-1
    total_carbon: float          # sum_t rho_t * x_t (gCO2)
    work_completed: float        # sum_t x_t (MWh)
    solver_status: str           # cvxpy status string


def schedule_deterministic_single_cluster(
    carbon_intensity: np.ndarray,   # rho_t, length T (gCO2/kWh)
    demand: np.ndarray,             # s_t, length T (MW capacity demanded)
    capacity_max: float,            # C_max in MW
    total_work: float,              # S_total in MWh
    solver: Optional[str] = None,
    equality_work: bool = False,
) -> ScheduleResult:
    """Solve Algorithm 1.

    Args:
        carbon_intensity: Hourly carbon intensity forecast, gCO2/kWh.
        demand: Hourly compute demand cap, MW.
        capacity_max: Maximum hourly compute capacity, MW.
        total_work: Total compute work to complete over the horizon, MWh.
        solver: Optional cvxpy solver name (e.g., 'GUROBI', 'ECOS', 'CLARABEL').
                If None, cvxpy picks a default.
        equality_work: If True, use sum_t x_t == total_work; otherwise the
                default sum_t x_t >= total_work. For positive linear objectives
                with rho >= 0 the two are mathematically equivalent (the
                constraint binds at any optimum), but equality is the right
                semantic for robust formulations (Algorithm 2) where a
                ρ-dependent objective could in principle make over-completion
                attractive as a risk hedge. Default False to preserve
                backward compatibility with existing callers and tests.

    Returns:
        ScheduleResult with the optimal hourly compute schedule.
    """
    rho = np.asarray(carbon_intensity, dtype=float)
    s = np.asarray(demand, dtype=float)
    T = len(rho)

    if len(s) != T:
        raise ValueError(f"carbon_intensity and demand must have same length, got {T} vs {len(s)}")
    if (rho < 0).any():
        raise ValueError("carbon_intensity must be non-negative")
    if (s < 0).any() or capacity_max < 0 or total_work < 0:
        raise ValueError("demand, capacity_max, total_work must be non-negative")

    # Decision variable: hourly compute power
    x = cp.Variable(T, nonneg=True)

    # Effective capacity ceiling per hour
    ceiling = np.minimum(s, capacity_max)

    objective = cp.Minimize(rho @ x)
    work_constraint = (
        cp.sum(x) == total_work if equality_work else cp.sum(x) >= total_work
    )
    constraints = [
        work_constraint,
        x <= ceiling,
    ]

    problem = cp.Problem(objective, constraints)
    problem.solve(solver=solver)

    if problem.status not in ("optimal", "optimal_inaccurate"):
        raise RuntimeError(f"Solver returned status {problem.status}")

    x_val = np.asarray(x.value).flatten()

    return ScheduleResult(
        schedule=x_val,
        total_carbon=float(rho @ x_val),
        work_completed=float(x_val.sum()),
        solver_status=problem.status,
    )


def _demo():
    """Quick smoke test: solve a synthetic 24-hour problem and print results."""
    T = 24
    # Sinusoidal carbon: peak at hour 18, trough at hour 6 (solar-rich daytime)
    rho = 300 + 150 * np.sin((np.arange(T) - 6) * np.pi / 12)
    rho = np.clip(rho, 50, None)

    # Constant demand cap
    s = np.full(T, 50.0)

    result = schedule_deterministic_single_cluster(
        carbon_intensity=rho,
        demand=s,
        capacity_max=50.0,
        total_work=600.0,   # 600 MWh = 25 MW average
    )

    print(f"Solver status: {result.solver_status}")
    print(f"Total carbon: {result.total_carbon:,.0f} gCO2")
    print(f"Work completed: {result.work_completed:.1f} MWh")
    print("\nSchedule (MW per hour):")
    for t, (r, x) in enumerate(zip(rho, result.schedule)):
        bar = "#" * int(x / 2)
        print(f"  h{t:02d}  rho={r:6.1f}  x={x:5.1f}  {bar}")


if __name__ == "__main__":
    _demo()


# ===========================================================================
# v11 ADDITION: multi-region coupled deterministic baseline ("new Algorithm 1")
# ---------------------------------------------------------------------------
# This is ADDED alongside the single-cluster baseline above, not a replacement.
# The single-cluster `schedule_deterministic_single_cluster` is retained: its
# 1-D interface is depended on by tests/test_algorithm_1.py and Algorithm 2a.
#
# The coupled baseline is the deterministic counterpart of Algorithm 2b with
# the three operational components (aggregate cap, flexible/inflexible split,
# ramp). It is exactly solve_mahalanobis_dro at epsilon=0 over the same
# feasible set, and exists as a standalone so the "new baseline" can be solved
# and tested without constructing a covariance factor L. The triviality proof
# for WHY the original baseline needed this is in progress_note_v11 Section 2.
# ===========================================================================

from dataclasses import dataclass as _dataclass  # noqa: E402


@_dataclass
class CoupledScheduleResult:
    """Output of the multi-region coupled baseline."""

    schedule: np.ndarray          # (R, T) MW
    total_carbon: float           # sum_{r,t} rho_{r,t} x_{r,t} (gCO2)
    work_completed: np.ndarray    # (R,) MWh per region
    solver_status: str
    binding: Optional[dict] = None


def schedule_deterministic_coupled(
    carbon_intensity: np.ndarray,   # (R, T) gCO2/kWh
    workloads: np.ndarray,          # (R,) MWh per region
    ceiling: np.ndarray,            # (R, T) MW per-cell ceiling
    p_max: Optional[float] = None,        # C1: aggregate per-hour cap
    alpha: Optional[np.ndarray] = None,   # C2: (R,) inflexible fraction in [0,1]
    intraday_shape: Optional[np.ndarray] = None,  # C2: (R,T) rows sum to 1; None => uniform
    ramp: Optional[np.ndarray] = None,    # C3: (R,) ramp limit Delta MW/h
    # --- Task A components (default None/off) ---
    deferral_windows: Optional[list] = None,   # 3a: list of (t1, t2, gamma)
    temperature: Optional[np.ndarray] = None,  # 3b: (R,T) thermal field, deg C
    pue0: float = 1.10,                        # 3b
    kappa: float = 0.015,                      # 3b
    t_set: float = 20.0,                       # 3b
    bar_P: Optional[object] = None,            # 3b: effective-power ceiling (scalar or (R,T))
    carbon_budget: Optional[float] = None,     # 3d: cap on nominal carbon <rho, x>
    solver: Optional[str] = None,
) -> CoupledScheduleResult:
    """Solve the new (coupled) deterministic baseline.

    Disabling all three components (p_max=None, alpha=None, ramp=None) recovers
    a per-region-decoupled LP whose optimum equals the greedy sort -- the
    triviality the redesign fixes. With any component active the program is
    genuinely coupled and a solver is required.
    """
    rho = np.asarray(carbon_intensity, dtype=float)
    R, T = rho.shape
    W = np.asarray(workloads, dtype=float).reshape(R)
    ceil_arr = np.asarray(ceiling, dtype=float)
    if ceil_arr.shape != (R, T):
        raise ValueError(f"ceiling must be (R, T) = ({R}, {T}), got {ceil_arr.shape}")
    if (rho < 0).any():
        raise ValueError("carbon_intensity must be non-negative")

    x = cp.Variable((R, T), nonneg=True)
    # Delegate the feasible set to the single shared builder so this baseline,
    # the Phase 1 DRO, and the Phase 2 CVaR scheduler optimize over the exact
    # same region X. This function used to re-implement the constraints inline,
    # which had begun to drift from feasible_set (e.g. the intraday-shape
    # row-sum check); routing through the builder removes that drift.
    constraints, x_flex = build_feasible_constraints(
        x, W, ceil_arr,
        p_max=p_max, alpha=alpha, intraday_shape=intraday_shape, ramp=ramp,
        deferral_windows=deferral_windows, temperature=temperature,
        pue0=pue0, kappa=kappa, t_set=t_set, bar_P=bar_P,
        carbon_budget=carbon_budget, rho_bar=rho,
    )

    problem = cp.Problem(cp.Minimize(cp.sum(cp.multiply(rho, x))), constraints)
    problem.solve(solver=solver)
    if problem.status not in ("optimal", "optimal_inaccurate"):
        raise RuntimeError(f"Solver returned status {problem.status}")

    x_val = np.asarray(x.value, dtype=float)

    # Recompute the small derived quantities the binding-diagnostics block below
    # reports on (the constraints themselves now live in feasible_set).
    alpha_arr = None
    inflex_base = None
    if alpha is not None:
        alpha_arr = np.asarray(alpha, dtype=float).reshape(R)
        p_shape = (np.full((R, T), 1.0 / T) if intraday_shape is None
                   else np.asarray(intraday_shape, dtype=float))
        inflex_base = (alpha_arr * W)[:, None] * p_shape
    pue = None
    if temperature is not None:
        pue = pue0 + kappa * np.maximum(
            np.asarray(temperature, dtype=float) - t_set, 0.0
        )

    binding = {}
    if p_max is not None:
        agg = x_val.sum(axis=0)
        binding["cap_tight_hours"] = int(np.sum(np.abs(agg - p_max) < 1e-3))
    if ramp is not None:
        ramp_arr = np.asarray(ramp, dtype=float).reshape(R)
        binding["ramp_tight_transitions"] = sum(
            1 for r in range(R) for t in range(1, T)
            if abs(abs(x_val[r, t] - x_val[r, t - 1]) - ramp_arr[r]) < 1e-3
        )
    if deferral_windows is not None and x_flex is not None:
        xf = np.asarray(x_flex.value, dtype=float)
        tight = []
        for (t1, t2, gamma) in deferral_windows:
            for r in range(R):
                flex_r = (1.0 - alpha_arr[r]) * W[r]
                served = xf[r, t1:t2 + 1].sum()
                req = gamma * flex_r
                # margin: how much served work exceeds the window requirement
                tight.append((r, t1, t2, float(served - req)))
        binding["deferral_margins"] = tight
        binding["deferral_tight_windows"] = sum(
            1 for (_, _, _, m) in tight if m < 1e-3
        )
    if pue is not None:
        eff = pue * x_val
        bar = np.asarray(bar_P, dtype=float)
        binding["thermal_tight_cells"] = int(np.sum(np.abs(eff - bar) < 1e-3))
        binding["thermal_min_margin"] = float(np.min(bar - eff))
    if carbon_budget is not None:
        used = float(np.sum(rho * x_val))
        binding["carbon_used"] = used
        binding["carbon_budget_margin"] = float(carbon_budget - used)
    if inflex_base is not None:
        binding["inflex_base"] = inflex_base

    return CoupledScheduleResult(
        schedule=x_val,
        total_carbon=float(np.sum(rho * x_val)),
        work_completed=x_val.sum(axis=1),
        solver_status=problem.status,
        binding=binding,
    )


def greedy_sort_schedule_multiregion(
    carbon_intensity: np.ndarray, workloads: np.ndarray, ceiling: np.ndarray,
) -> np.ndarray:
    """Per-region greedy sort (cleanest hours first). The closed-form optimum
    of the components-OFF coupled baseline; used to prove C1/C2."""
    rho = np.asarray(carbon_intensity, dtype=float)
    R, T = rho.shape
    W = np.asarray(workloads, dtype=float).reshape(R)
    ceil_arr = np.asarray(ceiling, dtype=float)
    x = np.zeros((R, T))
    for r in range(R):
        remaining = W[r]
        for t in np.argsort(rho[r]):
            fill = min(ceil_arr[r, t], remaining)
            x[r, t] = fill
            remaining -= fill
            if remaining <= 1e-12:
                break
    return x
