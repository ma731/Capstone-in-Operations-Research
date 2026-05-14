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
) -> ScheduleResult:
    """Solve Algorithm 1.

    Args:
        carbon_intensity: Hourly carbon intensity forecast, gCO2/kWh.
        demand: Hourly compute demand cap, MW.
        capacity_max: Maximum hourly compute capacity, MW.
        total_work: Total compute work to complete over the horizon, MWh.
        solver: Optional cvxpy solver name (e.g., 'GUROBI', 'ECOS', 'CLARABEL').
                If None, cvxpy picks a default.

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
    constraints = [
        cp.sum(x) >= total_work,
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
    # Sinusoidal carbon — peak at hour 18, trough at hour 6 (solar-rich daytime)
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
