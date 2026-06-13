"""Shared linear feasible set X for the scheduling problem.

Phase 1's Mahalanobis-Wasserstein DRO solver
(:func:`src.models.algorithm_2b_mahalanobis.solve_mahalanobis_dro`) and Phase 2's
copula-scenario CVaR solver (:func:`src.models.cvar_saa.solve_cvar_saa`) must
optimize over *exactly* the same feasible set so that any difference in the
schedule is attributable to the objective (covariance ball vs. copula scenarios),
not to a different constraint geometry. This module is the single source of truth
for that set: the constraint logic is a faithful extraction of the block in
``algorithm_2b_mahalanobis.py`` (C0 capacity, C2 flex/inflex split + work
conservation, C1 aggregate cap, C3 ramp, 3a deferral deadline, 3b thermal/PUE,
3d carbon budget). A unit test pins the two builders to the same region.

Row-major convention ``vec(x)[r*T + t] = x[r, t]`` is assumed throughout.
"""
from __future__ import annotations

from typing import Optional, Sequence

import cvxpy as cp
import numpy as np


def build_feasible_constraints(
    x: cp.Variable,                               # (R, T) nonneg decision
    workloads: np.ndarray,                        # (R,) per-region work [MWh]
    ceiling: np.ndarray,                          # (R, T) per-cell capacity [MW]
    *,
    p_max: Optional[float] = None,                # C1: aggregate hourly cap
    alpha: Optional[np.ndarray] = None,           # C2: (R,) inflexible fraction
    intraday_shape: Optional[np.ndarray] = None,  # C2: (R,T) shape, rows sum to 1
    ramp: Optional[np.ndarray] = None,            # C3: (R,) ramp limit [MW/h]
    deferral_windows: Optional[Sequence[tuple[int, int, float]]] = None,  # 3a
    temperature: Optional[np.ndarray] = None,     # 3b: (R,T) [deg C]
    pue0: float = 1.10,
    kappa: float = 0.015,
    t_set: float = 20.0,
    bar_P: Optional[object] = None,               # 3b: effective-power ceiling
    carbon_budget: Optional[float] = None,        # 3d: cap on <rho_bar, x>
    rho_bar: Optional[np.ndarray] = None,         # 3d: mean field for the budget
) -> tuple[list, Optional[cp.Variable]]:
    """Return ``(constraints, x_flex)`` defining the feasible set X for ``x``.

    The returned constraint list and (optional) flexible-load auxiliary variable
    are added to whatever objective the caller minimizes. Mirrors the logic in
    :func:`solve_mahalanobis_dro` exactly.
    """
    R, T = x.shape
    constraints = [x <= ceiling]

    # --- C2: flexible/inflexible split (replaces the plain work equality) ---
    x_flex = None
    alpha_arr = None
    if alpha is not None:
        alpha_arr = np.asarray(alpha, dtype=float).reshape(R)
        if ((alpha_arr < 0) | (alpha_arr > 1)).any():
            raise ValueError("alpha must lie in [0, 1]")
        if intraday_shape is None:
            p_shape = np.full((R, T), 1.0 / T)
        else:
            p_shape = np.asarray(intraday_shape, dtype=float)
            if p_shape.shape != (R, T):
                raise ValueError(f"intraday_shape must be (R, T) = ({R}, {T})")
            if not np.allclose(p_shape.sum(axis=1), 1.0, atol=1e-8):
                raise ValueError("intraday_shape rows must each sum to 1")
        inflex_base = (alpha_arr * workloads)[:, None] * p_shape
        x_flex = cp.Variable((R, T), nonneg=True)
        constraints += [x == inflex_base + x_flex]
        for r in range(R):
            constraints += [cp.sum(x_flex[r, :]) == (1.0 - alpha_arr[r]) * workloads[r]]
    else:
        constraints += [cp.sum(x, axis=1) == workloads]

    # --- C1: aggregate per-hour power cap ---
    if p_max is not None:
        for t in range(T):
            constraints += [cp.sum(x[:, t]) <= p_max]

    # --- C3: inter-hour ramping limit ---
    if ramp is not None:
        ramp_arr = np.asarray(ramp, dtype=float).reshape(R)
        for r in range(R):
            for t in range(1, T):
                constraints += [cp.abs(x[r, t] - x[r, t - 1]) <= ramp_arr[r]]

    # --- 3a: windowed-demand (deferral-deadline) constraint ---
    if deferral_windows is not None:
        if x_flex is None:
            raise ValueError(
                "deferral_windows requires the flexible/inflexible split (pass alpha)."
            )
        for (t1, t2, gamma) in deferral_windows:
            if not (0 <= t1 <= t2 < T):
                raise ValueError(f"deferral window ({t1}, {t2}) out of range [0, {T - 1}]")
            if not (0.0 <= gamma <= 1.0):
                raise ValueError(f"deferral gamma must lie in [0, 1], got {gamma}")
            for r in range(R):
                flex_r = (1.0 - alpha_arr[r]) * workloads[r]
                constraints += [cp.sum(x_flex[r, t1:t2 + 1]) >= gamma * flex_r]

    # --- 3b: temperature-coupled thermal (PUE) constraint ---
    if temperature is not None:
        if bar_P is None:
            raise ValueError("temperature given but bar_P (effective-power ceiling) is None")
        temp_arr = np.asarray(temperature, dtype=float)
        if temp_arr.shape != (R, T):
            raise ValueError(f"temperature must be (R, T) = ({R}, {T}), got {temp_arr.shape}")
        pue = pue0 + kappa * np.maximum(temp_arr - t_set, 0.0)
        constraints += [cp.multiply(pue, x) <= bar_P]

    # --- 3d: carbon budget on the nominal mean field ---
    if carbon_budget is not None:
        if carbon_budget < 0:
            raise ValueError(f"carbon_budget must be non-negative, got {carbon_budget}")
        if rho_bar is None:
            raise ValueError("carbon_budget requires rho_bar")
        constraints += [cp.sum(cp.multiply(np.asarray(rho_bar), x)) <= carbon_budget]

    return constraints, x_flex
