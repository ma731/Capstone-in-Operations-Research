"""Part 3 — spatially-coupled transfer DRO (clean, tested module).

Promotes the Part 3 prototypes to a maintainable API. Inter-region load flows
``f[r,s,t] >= 0`` let work migrate between regions; the executed load is
``y[r,t] = x[r,t] + inflow - outflow``, emissions are evaluated on ``y``, and a
transfer budget ``Phi`` (and optional per-unit migration cost ``lam``) bound the
relocation. Everything is linear in ``(x, f)``, so the one-shot problem is an
SOCP and the two-stage / recourse problems are LPs.

Three entry points:
  * ``solve_transfer_dro``  -- one-shot: min <rho_bar,y> + eps||L^T y|| + lam*sum f.
  * ``two_stage_commit``    -- commit x before carbon is known; costly recourse after;
                               objective is the mean (risk-neutral) or CVaR (robust)
                               of cost over scenarios. Returns the stage-1 commitment.
  * ``recourse_cost``       -- given a fixed commitment and a realized carbon field,
                               the best costly transfer and the realized cost.
"""
from __future__ import annotations

from typing import Optional

import cvxpy as cp
import numpy as np


def _executed(x, f):
    """Executed load y = x + inflow(into r) - outflow(out of r) from flows f[r,s,t]."""
    return x + cp.sum(f, axis=0) - cp.sum(f, axis=1)


def _no_self_loops(f, R):
    return [f[r, r, :] == 0 for r in range(R)]


def _pick_solver(prefer):
    installed = set(cp.installed_solvers())
    for cand in ([prefer] if prefer else []) + ["HIGHS", "CLARABEL", "ECOS", "SCS"]:
        if cand in installed:
            return cand
    return cp.installed_solvers()[0]


def solve_transfer_dro(
    rho_bar: np.ndarray,          # (R,T) mean carbon field
    L: np.ndarray,               # (R*T, R*T) Cholesky factor; ignored if epsilon=0
    workloads: np.ndarray,       # (R,) per-region work [MWh]
    ceiling: np.ndarray,         # (R,T) per-cell executed-load capacity [MW]
    *,
    epsilon: float = 0.0,
    transfer_budget: float,
    lam: float = 0.0,
    solver: Optional[str] = None,
):
    """One-shot transfer DRO. Returns ``(y, transfer_used)`` with ``y`` the executed
    schedule (R,T) and ``transfer_used`` the total relocated work."""
    R, T = rho_bar.shape
    x = cp.Variable((R, T), nonneg=True)
    f = cp.Variable((R, R, T), nonneg=True)
    y = _executed(x, f)
    obj = cp.sum(cp.multiply(rho_bar, y))
    if epsilon:
        y_vec = cp.hstack([y[r, :] for r in range(R)])
        obj = obj + epsilon * cp.norm(L.T @ y_vec, 2)
    if lam:
        obj = obj + lam * cp.sum(f)
    cons = [cp.sum(x, axis=1) == workloads, y >= 0, y <= ceiling,
            cp.sum(f) <= transfer_budget] + _no_self_loops(f, R)
    prob = cp.Problem(cp.Minimize(obj), cons)
    prob.solve(solver=_pick_solver(solver))
    if x.value is None:
        raise RuntimeError(f"transfer DRO solve failed: {prob.status}")
    return np.asarray(y.value), float(cp.sum(f).value)


def two_stage_commit(
    scenarios: np.ndarray,       # (S,R,T) day-ahead carbon scenarios
    workloads: np.ndarray,
    ceiling: np.ndarray,
    *,
    transfer_budget: float,
    lam: float = 0.0,
    beta: float = 0.95,
    risk: str = "cvar",          # 'mean' (risk-neutral) or 'cvar' (robust)
    solver: Optional[str] = None,
) -> np.ndarray:
    """Two-stage program: commit x before carbon is known, costly recourse f^s per
    scenario after. Minimize the mean or CVaR_beta of cost over scenarios. Returns
    the stage-1 commitment ``x`` (R,T)."""
    if risk not in ("mean", "cvar"):
        raise ValueError("risk must be 'mean' or 'cvar'")
    S, R, T = scenarios.shape
    x = cp.Variable((R, T), nonneg=True)
    f = [cp.Variable((R, R, T), nonneg=True) for _ in range(S)]
    cons = [cp.sum(x, axis=1) == workloads]
    costs = []
    for s in range(S):
        y = _executed(x, f[s])
        cons += [y >= 0, y <= ceiling, cp.sum(f[s]) <= transfer_budget]
        cons += _no_self_loops(f[s], R)
        costs.append(cp.sum(cp.multiply(scenarios[s], y)) + lam * cp.sum(f[s]))
    if risk == "mean":
        obj = sum(costs) / S
    else:
        tau = cp.Variable()
        z = cp.Variable(S, nonneg=True)
        cons += [z[s] >= costs[s] - tau for s in range(S)]
        obj = tau + cp.sum(z) / ((1.0 - beta) * S)
    prob = cp.Problem(cp.Minimize(obj), cons)
    prob.solve(solver=_pick_solver(solver))
    if x.value is None:
        raise RuntimeError(f"two-stage commit failed: {prob.status}")
    return np.asarray(x.value)


def recourse_cost(
    commitment: np.ndarray,      # (R,T) fixed stage-1 schedule
    rho: np.ndarray,             # (R,T) realized carbon
    ceiling: np.ndarray,
    *,
    transfer_budget: float,
    lam: float = 0.0,
    solver: Optional[str] = None,
) -> float:
    """Best costly transfer for a realized carbon field given a fixed commitment;
    returns the realized cost (carbon + migration)."""
    R, T = rho.shape
    f = cp.Variable((R, R, T), nonneg=True)
    y = commitment + cp.sum(f, axis=0) - cp.sum(f, axis=1)
    cons = [y >= 0, y <= ceiling, cp.sum(f) <= transfer_budget] + _no_self_loops(f, R)
    cost = cp.sum(cp.multiply(rho, y)) + lam * cp.sum(f)
    prob = cp.Problem(cp.Minimize(cost), cons)
    prob.solve(solver=_pick_solver(solver))
    if f.value is None:
        raise RuntimeError(f"recourse solve failed: {prob.status}")
    return float(cost.value)
