"""Sample-average-approximation CVaR scheduler (Phase 2).

Where Phase 1 robustifies against a covariance ball
(``min <rho_bar,x> + eps ||L^T x||_2``), Phase 2 minimizes the empirical
CVaR of emissions over a finite set of carbon-field *scenarios* drawn from a
fitted copula. Using the Rockafellar--Uryasev (2000) linear-programming form,

    min_{x in X, tau, z}  tau + 1/((1-beta) S) sum_s z_s
    s.t.                  z_s >= <rho^s, x> - tau,   z_s >= 0,   x in X

with scenarios ``rho^s`` (s = 1..S). The feasible set X is built by
:func:`src.models.feasible_set.build_feasible_constraints`, identical to Phase 1,
so the *only* thing that changes between dependence models is which scenarios
enter the objective. The dependence model is encoded entirely in how the
scenarios are sampled (independence / Gaussian / Clayton copula), so this solver
is agnostic to the copula and reused verbatim across all three arms.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cvxpy as cp
import numpy as np

from .feasible_set import build_feasible_constraints


@dataclass
class CVaRSAAResult:
    schedule: np.ndarray        # (R, T) optimal schedule [MW]
    in_sample_cvar: float       # CVaR_beta over the training scenarios [gCO2eq]
    var_tau: float              # optimal VaR threshold tau
    objective_value: float      # solver-reported optimum
    solver_status: str
    solver_name: str
    n_scenarios: int
    beta: float


def _select_solver() -> str:
    installed = set(cp.installed_solvers())
    for cand in ("HIGHS", "CLARABEL", "ECOS", "SCS"):
        if cand in installed:
            return cand
    return cp.installed_solvers()[0]


def solve_cvar_saa(
    scenarios: np.ndarray,          # (S, R, T) carbon-field scenarios [gCO2eq/kWh]
    workloads: np.ndarray,          # (R,) per-region work [MWh]
    ceiling: np.ndarray,            # (R, T) per-cell capacity [MW]
    *,
    beta: float = 0.95,
    solver: Optional[str] = None,
    **feasible_kwargs,
) -> CVaRSAAResult:
    """Minimize empirical CVaR_beta of emissions over ``scenarios`` subject to X.

    ``feasible_kwargs`` are forwarded to
    :func:`build_feasible_constraints` (alpha, intraday_shape, ramp,
    deferral_windows, temperature, carbon_budget, ...), so the feasible set
    matches the Phase 1 regime exactly.
    """
    scenarios = np.asarray(scenarios, dtype=float)
    if scenarios.ndim != 3:
        raise ValueError(f"scenarios must be (S, R, T), got {scenarios.shape}")
    S, R, T = scenarios.shape
    if not (0.0 < beta < 1.0):
        raise ValueError(f"beta must lie in (0, 1), got {beta}")

    x = cp.Variable((R, T), nonneg=True)
    tau = cp.Variable()
    z = cp.Variable(S, nonneg=True)

    # Per-scenario emissions <rho^s, x> as an affine expression in x.
    losses = cp.hstack([cp.sum(cp.multiply(scenarios[s], x)) for s in range(S)])
    cvar = tau + cp.sum(z) / ((1.0 - beta) * S)
    objective = cp.Minimize(cvar)

    constraints, _ = build_feasible_constraints(x, workloads, ceiling, **feasible_kwargs)
    constraints += [z >= losses - tau]

    problem = cp.Problem(objective, constraints)
    chosen = solver or _select_solver()
    problem.solve(solver=chosen)

    if x.value is None:
        raise RuntimeError(f"CVaR-SAA solve failed: status={problem.status}")

    return CVaRSAAResult(
        schedule=np.asarray(x.value),
        in_sample_cvar=float(cvar.value),
        var_tau=float(tau.value),
        objective_value=float(problem.value),
        solver_status=problem.status,
        solver_name=chosen,
        n_scenarios=S,
        beta=beta,
    )
