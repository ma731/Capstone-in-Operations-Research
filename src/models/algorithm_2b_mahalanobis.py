"""Algorithm 2b: Mahalanobis-Wasserstein DRO.

Implements the Phase 1 algorithmic contribution: a joint spatio-temporal
optimizer whose worst-case carbon cost is regularized by the Mahalanobis
norm sqrt(x^T Sigma_hat x) of the schedule, where Sigma_hat is the empirical
(R*T, R*T) covariance of the daily carbon-intensity field.

Per progress note v8.3 Section 2 ("The Mahalanobis ground metric"):

    min_{x in X}  <rho_bar, x> + epsilon * sqrt(x^T Sigma_hat x)

with X = { x in R^{R x T}_{>=0} : x <= ceiling, sum_t x_{r,t} = W_r } and
Sigma_hat = L L^T (the caller passes L directly; see Design Decisions below).

The penalty is reformulated as a 2-norm via the identity

    sqrt(x^T Sigma_hat x) = sqrt(x^T L L^T x) = || L^T x ||_2

so the CVXPY expression is

    eps * cp.norm(L.T @ x_vec, 2)

This makes the problem a Second-Order Cone Program (SOCP), solvable by
CLARABEL / ECOS / SCS.

Comparison with Algorithm 2a:
    A2a is a thin wrapper around per-region Algorithm 1 calls because the
    ell_infinity penalty epsilon * ||x||_1 collapses to a constant under
    equality work constraints. A2b cannot decompose by region: the L^T x
    penalty couples regions through the off-diagonal blocks of Sigma_hat.
    This wrapper-vs-joint distinction IS the empirical signature of cross-
    region structure entering the optimizer.

Design decisions:
    - Caller supplies rho_bar and L directly. A2b does not estimate
      statistics or apply ridge regularization. The covariance pipeline
      lives in src.models.covariance; the experiment harness decides which
      L to pass (joint vs block-diagonal-by-region for the shuffled-
      marginals sensitivity experiment). This keeps the optimizer pure of
      statistical estimation and makes the joint-vs-shuffled experiment a
      one-line swap.
    - L is treated as any factor satisfying L L^T = Sigma_hat. The main
      pipeline uses the lower-triangular Cholesky factor from
      np.linalg.cholesky, but a symmetric square root from an eigen-
      decomposition is mathematically equivalent for the optimizer.
      Triangularity is NOT enforced.

Two silent-failure modes to guard against:

    1. Wrong Cholesky orientation. The penalty || L^T x ||_2 corresponds
       to x^T (L L^T) x = x^T Sigma_hat x. Passing L^T instead of L
       computes a different quadratic form and the solver returns
       plausible-but-wrong numbers. Guarded by the Mahalanobis-identity
       tests (pre-solve and post-solve) and by the joint-vs-shuffled
       wiring test.

    2. Wrong reshape order. cp.reshape's default order varies across CVXPY
       versions (Fortran in some, C in others), and `order="C"` is silently
       ignored on older versions. To eliminate this ambiguity entirely,
       the flattening is built via explicit cp.hstack of rows rather than
       relying on cp.reshape:

           x_vec = cp.hstack([x[r, :] for r in range(R)])

       which is unambiguously row-major (vec(x)[r*T + t] = x[r, t]) and
       matches the convention pinned in covariance.py. The wiring test
       (joint vs block-diagonal) is the additional behavioral guard.

See progress_note_v8_3.tex Section 2 for the full derivation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import cvxpy as cp
import numpy as np

from src.models.covariance import REGION_ORDER


@dataclass
class MahalanobisDROResult:
    """Output of Algorithm 2b.

    Attributes:
        schedule: (R, T) optimal schedule matrix in MW.
        schedule_per_region: dict mapping zone_id to (T,) schedule.
        rho_bar: (R, T) empirical mean field used.
        epsilon: Wasserstein radius used.
        mean_carbon_value: <rho_bar, x*>, the empirical-mean carbon cost
            of the optimal schedule.
        mahalanobis_norm: || L^T vec(x*) ||_2 = sqrt(x*^T Sigma_hat x*),
            computed post-solve in numpy. Cross-checks the CVXPY penalty.
        penalty: epsilon * mahalanobis_norm.
        robust_value: mean_carbon_value + penalty. Should equal CVXPY's
            objective_value within solver tolerance.
        objective_value: CVXPY-reported optimal value. Disagreement with
            robust_value flags a vectorization or post-solve accounting
            bug.
        solver_status: cvxpy problem status string.
        solver_name: solver actually used (after fallback resolution).
        region_order: zone identifiers in row-major order.
        n_samples: provenance only; the N used to estimate rho_bar / L
            upstream. None if not provided.
    """

    schedule: np.ndarray
    schedule_per_region: dict[str, np.ndarray]
    rho_bar: np.ndarray
    epsilon: float
    mean_carbon_value: float
    mahalanobis_norm: float
    penalty: float
    robust_value: float
    objective_value: float
    solver_status: str
    solver_name: str
    region_order: tuple[str, ...]
    n_samples: Optional[int] = None


def _select_solver(requested: Optional[str]) -> Optional[str]:
    """Pick a conic solver, preferring CLARABEL > ECOS > SCS if installed.

    Returns the requested solver unchanged if non-None. Returns None to
    delegate to CVXPY's default if none of the preferred conic solvers
    are available.
    """
    if requested is not None:
        return requested
    installed = set(cp.installed_solvers())
    for candidate in ("CLARABEL", "ECOS", "SCS"):
        if candidate in installed:
            return candidate
    return None


def solve_mahalanobis_dro(
    rho_bar: np.ndarray,
    L: np.ndarray,
    workloads: np.ndarray,
    ceiling: np.ndarray,
    epsilon: float,
    region_order: Sequence[str] = REGION_ORDER,
    solver: Optional[str] = None,
    n_samples: Optional[int] = None,
    # --- v11 operational components (all default None = original behavior) ---
    p_max: Optional[float] = None,            # C1: aggregate per-hour cap sum_r x_{r,t} <= p_max
    alpha: Optional[np.ndarray] = None,       # C2: per-region inflexible fraction in [0,1]
    intraday_shape: Optional[np.ndarray] = None,  # C2: (R,T) shape p, rows sum to 1; None => uniform
    ramp: Optional[np.ndarray] = None,        # C3: (R,) per-region ramp limit Delta, MW/h
    # --- Task A operational components (all default None/off = original behavior) ---
    deferral_windows: Optional[Sequence[tuple[int, int, float]]] = None,  # 3a
    temperature: Optional[np.ndarray] = None,  # 3b: (R,T) thermal field, deg C
    pue0: float = 1.10,                        # 3b: floor PUE
    kappa: float = 0.015,                      # 3b: PUE slope per deg C above t_set
    t_set: float = 20.0,                       # 3b: economizer set-point, deg C
    bar_P: Optional[object] = None,            # 3b: effective-power ceiling (scalar or (R,T))
    carbon_budget: Optional[float] = None,     # 3d: cap on nominal carbon <rho_bar, x>
) -> MahalanobisDROResult:
    """Solve Algorithm 2b: Mahalanobis-Wasserstein DRO.

    Args:
        rho_bar: (R, T) empirical mean carbon-intensity field, gCO2eq/kWh.
        L: (R*T, R*T) factor with L @ L.T = Sigma_hat. Main pipeline uses
            np.linalg.cholesky output (lower-triangular), but any factor
            satisfying the identity is accepted. Triangularity is NOT
            enforced. Recommended construction:
                L = covariance.cholesky_factor(
                        covariance.regularize_covariance(Sigma_hat)
                    )
        workloads: (R,) per-region work requirements W_r, MWh. Enforced
            as equality: sum_t x_{r,t} == W_r.
        ceiling: (R, T) per-hour capacity ceiling x_bar_{r,t}, MW.
        epsilon: Wasserstein radius >= 0. epsilon=0 reduces to the
            deterministic problem on rho_bar (regardless of L).
        region_order: zone identifiers in row-major order matching the R
            axis of rho_bar, L, and ceiling. Length must equal R. Default
            is the 4-zone REGION_ORDER from covariance.py.
        solver: optional CVXPY solver name. If None, prefers CLARABEL,
            falls back to ECOS, then SCS, then CVXPY default.
        n_samples: provenance only; passed through to the result for
            record-keeping.

    Returns:
        MahalanobisDROResult.

    Raises:
        ValueError: shape / sign / finiteness violations on inputs, or
            if per-region workload exceeds total ceiling capacity
            (infeasibility precheck).
        RuntimeError: if the solver returns a non-optimal status.
    """
    rho_bar = np.asarray(rho_bar, dtype=float)
    L = np.asarray(L, dtype=float)
    workloads = np.asarray(workloads, dtype=float)
    ceiling = np.asarray(ceiling, dtype=float)

    # ---- Shape checks ----
    if rho_bar.ndim != 2:
        raise ValueError(f"rho_bar must be 2-D (R, T), got shape {rho_bar.shape}")
    R, T = rho_bar.shape
    if ceiling.shape != (R, T):
        raise ValueError(
            f"ceiling must have shape (R, T) = ({R}, {T}), got {ceiling.shape}"
        )
    if workloads.shape != (R,):
        raise ValueError(
            f"workloads must have shape (R,) = ({R},), got {workloads.shape}"
        )
    expected_L_shape = (R * T, R * T)
    if L.shape != expected_L_shape:
        raise ValueError(
            f"L must have shape (R*T, R*T) = {expected_L_shape}, got {L.shape}"
        )
    if len(region_order) != R:
        raise ValueError(
            f"region_order has {len(region_order)} entries but rho_bar has R={R}"
        )

    # ---- Sign / finiteness checks ----
    if epsilon < 0:
        raise ValueError(f"epsilon must be non-negative, got {epsilon}")
    for name, arr in (
        ("rho_bar", rho_bar),
        ("L", L),
        ("ceiling", ceiling),
        ("workloads", workloads),
    ):
        if not np.all(np.isfinite(arr)):
            raise ValueError(f"{name} contains non-finite values")
    if (rho_bar < 0).any():
        raise ValueError("rho_bar must be non-negative")
    if (ceiling < 0).any():
        raise ValueError("ceiling must be non-negative")
    if (workloads < 0).any():
        raise ValueError("workloads must be non-negative")

    # ---- Feasibility precheck ----
    # Each region's total work must fit under the sum of its hourly ceilings.
    # Catch this before the solver returns an opaque infeasibility status.
    region_capacity = ceiling.sum(axis=1)
    tol = 1e-9
    infeasible = workloads > region_capacity + tol
    if infeasible.any():
        bad = [
            (region_order[r], float(workloads[r]), float(region_capacity[r]))
            for r in range(R)
            if infeasible[r]
        ]
        raise ValueError(
            "Infeasible: per-region workload exceeds total ceiling capacity. "
            f"Offending (zone, workload_MWh, ceiling_sum_MW): {bad}"
        )

    # ---- Build and solve the SOCP ----
    x = cp.Variable((R, T), nonneg=True)
    # Row-major flattening: vec(x)[r*T + t] = x[r, t]. Built via explicit
    # cp.hstack of rows rather than cp.reshape -- the latter's default order
    # varies across CVXPY versions (Fortran in some, C in others) and the
    # `order=` kwarg has been silently ignored on older releases. hstack of
    # rows is unambiguously row-major and matches the convention pinned in
    # covariance.py and the numpy post-solve accounting below.
    x_vec = cp.hstack([x[r, :] for r in range(R)])

    mean_term = cp.sum(cp.multiply(rho_bar, x))
    # || L^T x_vec ||_2 = sqrt(x_vec^T L L^T x_vec) = sqrt(x_vec^T Sigma_hat x_vec).
    # Writing `L @ x_vec` here would compute x_vec^T L^T L x_vec, a different
    # quadratic form, and the solver would silently return wrong numbers.
    penalty_term = epsilon * cp.norm(L.T @ x_vec, 2)
    objective = cp.Minimize(mean_term + penalty_term)

    constraints = [
        x <= ceiling,
    ]

    # --- C2: flexible/inflexible split (replaces the plain work equality) ---
    # When alpha is None, fall back to the original equality sum_t x_{r,t}=W_r.
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
        inflex_base = (alpha_arr * workloads)[:, None] * p_shape   # (R, T)
        x_flex = cp.Variable((R, T), nonneg=True)
        constraints += [x == inflex_base + x_flex]
        for r in range(R):
            constraints += [cp.sum(x_flex[r, :]) == (1.0 - alpha_arr[r]) * workloads[r]]
    else:
        constraints += [cp.sum(x, axis=1) == workloads]

    # --- C1: aggregate per-hour power cap -----------------------------------
    if p_max is not None:
        for t in range(T):
            constraints += [cp.sum(x[:, t]) <= p_max]

    # --- C3: inter-hour ramping limit ---------------------------------------
    if ramp is not None:
        ramp_arr = np.asarray(ramp, dtype=float).reshape(R)
        for r in range(R):
            for t in range(1, T):
                constraints += [cp.abs(x[r, t] - x[r, t - 1]) <= ramp_arr[r]]

    # --- 3a: windowed-demand (deferral-deadline) constraint -----------------
    # For each region r and each window (t1, t2, gamma):
    #     sum_{t in [t1, t2]} x_flex[r, t] >= gamma * (1 - alpha_r) * W_r
    # An AGGREGATE bound on deferral: a fraction gamma of the region's
    # FLEXIBLE work must be served within the window [t1, t2] (a deferral
    # deadline). It is explicitly NOT a per-job SLA. The flexible portion is
    # only well-defined under the C2 split, so this requires alpha.
    if deferral_windows is not None:
        if x_flex is None:
            raise ValueError(
                "deferral_windows requires the flexible/inflexible split "
                "(pass alpha); the window bounds the flexible work x_flex."
            )
        for (t1, t2, gamma) in deferral_windows:
            if not (0 <= t1 <= t2 < T):
                raise ValueError(
                    f"deferral window ({t1}, {t2}) out of range [0, {T - 1}]"
                )
            if not (0.0 <= gamma <= 1.0):
                raise ValueError(f"deferral gamma must lie in [0, 1], got {gamma}")
            for r in range(R):
                flex_r = (1.0 - alpha_arr[r]) * workloads[r]
                constraints += [
                    cp.sum(x_flex[r, t1:t2 + 1]) >= gamma * flex_r
                ]

    # --- 3b: temperature-coupled thermal (PUE) constraint -------------------
    # Effective power = PUE(T_{r,t}) * x_{r,t} with the hockey-stick model
    #     PUE(T) = pue0 + kappa * max(T - t_set, 0),
    # bounded per cell by bar_P. Temperature is data, so PUE is a constant
    # matrix and the constraint is linear (program stays an SOCP/LP).
    if temperature is not None:
        if bar_P is None:
            raise ValueError("temperature given but bar_P (effective-power ceiling) is None")
        temp_arr = np.asarray(temperature, dtype=float)
        if temp_arr.shape != (R, T):
            raise ValueError(f"temperature must be (R, T) = ({R}, {T}), got {temp_arr.shape}")
        pue = pue0 + kappa * np.maximum(temp_arr - t_set, 0.0)   # (R, T) constant
        constraints += [cp.multiply(pue, x) <= bar_P]

    # --- 3d: carbon budget --------------------------------------------------
    # Cap the NOMINAL carbon <rho_bar, x> <= B. rho_bar is data, so this is a
    # single linear constraint; the program stays an SOCP. (The budget is on the
    # mean field, not the robust value -- a deterministic operational cap.)
    if carbon_budget is not None:
        if carbon_budget < 0:
            raise ValueError(f"carbon_budget must be non-negative, got {carbon_budget}")
        constraints += [cp.sum(cp.multiply(rho_bar, x)) <= carbon_budget]

    problem = cp.Problem(objective, constraints)
    chosen_solver = _select_solver(solver)
    problem.solve(solver=chosen_solver)

    if problem.status not in ("optimal", "optimal_inaccurate"):
        raise RuntimeError(
            f"Solver returned status {problem.status}. "
            f"Solver: {chosen_solver or 'CVXPY default'}."
        )

    schedule = np.asarray(x.value, dtype=float)

    # ---- Post-solve accounting (numpy) ----
    # Match the CVXPY flattening exactly (row-major C-order).
    x_vec_value = schedule.reshape(-1, order="C")
    mean_carbon_value = float(np.sum(rho_bar * schedule))
    mahalanobis_norm = float(np.linalg.norm(L.T @ x_vec_value, ord=2))
    penalty = float(epsilon * mahalanobis_norm)
    robust_value = mean_carbon_value + penalty
    objective_value = float(problem.value)

    schedule_per_region = {
        region_order[r]: schedule[r].copy() for r in range(R)
    }

    return MahalanobisDROResult(
        schedule=schedule,
        schedule_per_region=schedule_per_region,
        rho_bar=rho_bar,
        epsilon=epsilon,
        mean_carbon_value=mean_carbon_value,
        mahalanobis_norm=mahalanobis_norm,
        penalty=penalty,
        robust_value=robust_value,
        objective_value=objective_value,
        solver_status=problem.status,
        solver_name=chosen_solver or "default",
        region_order=tuple(region_order),
        n_samples=n_samples,
    )


def _demo() -> None:
    """Quick smoke test: 2-zone, 4-hour synthetic problem; print summary."""
    R, T = 2, 4
    rho_bar = np.array([
        [100.0, 200.0, 300.0, 400.0],
        [400.0, 300.0, 200.0, 100.0],
    ])
    # Joint Sigma: identity within-region, negative cross-region block.
    Sigma = 100.0 * np.eye(R * T)
    Sigma[0:T, T:2 * T] = -50.0 * np.eye(T)
    Sigma[T:2 * T, 0:T] = -50.0 * np.eye(T)
    L = np.linalg.cholesky(Sigma)

    workloads = np.array([60.0, 60.0])
    ceiling = np.full((R, T), 50.0)

    print(f"{'eps':>8}  {'mean':>10}  {'mnorm':>8}  {'robust':>10}  {'obj':>10}  status")
    for eps in (0.0, 10.0, 100.0):
        result = solve_mahalanobis_dro(
            rho_bar=rho_bar,
            L=L,
            workloads=workloads,
            ceiling=ceiling,
            epsilon=eps,
            region_order=("REG_A", "REG_B"),
        )
        print(
            f"{eps:>8.1f}  "
            f"{result.mean_carbon_value:>10.2f}  "
            f"{result.mahalanobis_norm:>8.3f}  "
            f"{result.robust_value:>10.2f}  "
            f"{result.objective_value:>10.2f}  "
            f"{result.solver_status}  ({result.solver_name})"
        )


if __name__ == "__main__":
    _demo()
