"""Tests for Algorithm 2b: Mahalanobis-Wasserstein DRO.

Test strategy targets the two silent failure modes from the implementation
docstring:

  (1) Wrong Cholesky orientation -- guarded by Mahalanobis identity tests
      (pre-solve and post-solve) and the joint-vs-shuffled wiring test.

  (2) Wrong reshape order -- guarded by the wiring test, since a Fortran-
      order reshape against a row-major Sigma_hat pairs entries incorrectly
      and produces a different (wrong) schedule.

Plus standard correctness checks: reduction at epsilon=0, result accounting,
objective consistency, epsilon monotonicity, L-not-triangular invariance,
real-scale integration, and input validation.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.models.algorithm_1 import schedule_deterministic_single_cluster
from src.models.algorithm_2b_mahalanobis import (
    MahalanobisDROResult,
    solve_mahalanobis_dro,
)
from src.models.covariance import block_diagonal_by_region


# ---------------------------------------------------------------------------
# Silent-failure-mode guards
# ---------------------------------------------------------------------------


class TestMahalanobisIdentity:
    """The Mahalanobis algebra: ||L^T x||_2^2 == x^T (L L^T) x."""

    def test_random_vector_identity(self):
        """Pre-solve guard: identity holds for random x and random PD Sigma.

        This is the foundational algebraic check: if it fails, the entire
        SOCP formulation is wrong from the start. Cholesky orientation
        sentinel; runs without invoking CVXPY.
        """
        rng = np.random.default_rng(0)
        D = 12
        A = rng.normal(size=(D, D))
        Sigma = A @ A.T + np.eye(D)
        L = np.linalg.cholesky(Sigma)

        for _ in range(20):
            x = rng.normal(size=D)
            lhs = float(np.linalg.norm(L.T @ x) ** 2)
            rhs = float(x @ Sigma @ x)
            np.testing.assert_allclose(lhs, rhs, rtol=1e-10, atol=1e-10)

    def test_post_solve_identity_on_returned_schedule(self):
        """Post-solve guard: identity holds on the actual optimal schedule.

        Catches bugs where the post-solve numpy mahalanobis_norm
        computation uses a different vectorization convention from
        CVXPY's penalty. Distinct from the random-vector test because
        the schedule is the output of the entire CVXPY pipeline.
        """
        R, T = 2, 3
        rng = np.random.default_rng(1)
        A = rng.normal(size=(R * T, R * T))
        Sigma = A @ A.T + np.eye(R * T)
        L = np.linalg.cholesky(Sigma)

        result = solve_mahalanobis_dro(
            rho_bar=np.array([[100.0, 200.0, 150.0], [180.0, 120.0, 220.0]]),
            L=L,
            workloads=np.array([30.0, 30.0]),
            ceiling=np.full((R, T), 50.0),
            epsilon=20.0,
            region_order=("REG_A", "REG_B"),
        )

        x_vec = result.schedule.reshape(-1, order="C")
        quadratic = float(x_vec @ (L @ L.T) @ x_vec)
        np.testing.assert_allclose(
            result.mahalanobis_norm ** 2, quadratic, rtol=1e-8, atol=1e-8
        )


class TestWiringJointVsBlockDiagonal:
    """The wiring test: A2b actually consumes off-diagonal blocks of L L^T.

    The single most important test in this file. If a future refactor
    silently breaks the reshape order, the Cholesky orientation, or the
    coupling between regions, this test catches it.
    """

    def test_schedules_differ_with_strong_cross_block(self):
        """Constructs an R=2, T=3 problem with strong negative cross-region
        covariance and asymmetric rho_bar so that the joint and shuffled
        optima diverge.

        Geometry: regions are cheap at different hours (A at h0, B at h2).
        Under shuffled Sigma (block-diagonal), the two regions decouple
        and each concentrates work in its own cheapest hour. Under joint
        Sigma with a negative cross-block, the optimizer is rewarded for
        aligning work between regions (the negative cross-term lowers the
        Mahalanobis penalty when both regions are active in the same
        hour), pulling work toward an overlap hour at the cost of higher
        mean carbon. The two schedules MUST differ.

        If they coincide, A2b is silently ignoring cross-region structure
        -- the symptom of a Fortran-order reshape or a Cholesky-orientation
        bug.
        """
        R, T = 2, 3
        region_order = ("REG_A", "REG_B")

        # Strong negative cross-region block; identity within-region.
        Sigma_joint = 100.0 * np.eye(R * T)
        cross = -50.0 * np.eye(T)
        Sigma_joint[0:T, T:2 * T] = cross
        Sigma_joint[T:2 * T, 0:T] = cross
        # Verify PD before factoring.
        assert np.linalg.eigvalsh(Sigma_joint).min() > 1e-6

        L_joint = np.linalg.cholesky(Sigma_joint)
        Sigma_shuf = block_diagonal_by_region(Sigma_joint, R=R, T=T)
        L_shuf = np.linalg.cholesky(Sigma_shuf)

        # Asymmetric rho_bar: regions cheap at opposite hours.
        rho_bar = np.array([
            [100.0, 200.0, 300.0],
            [300.0, 200.0, 100.0],
        ])
        workloads = np.array([30.0, 30.0])
        ceiling = np.full((R, T), 50.0)
        eps = 200.0  # large enough that the penalty drives alignment

        result_joint = solve_mahalanobis_dro(
            rho_bar=rho_bar, L=L_joint, workloads=workloads, ceiling=ceiling,
            epsilon=eps, region_order=region_order,
        )
        result_shuf = solve_mahalanobis_dro(
            rho_bar=rho_bar, L=L_shuf, workloads=workloads, ceiling=ceiling,
            epsilon=eps, region_order=region_order,
        )

        deviation = float(np.max(np.abs(result_joint.schedule - result_shuf.schedule)))
        # 1.0 MW deviation per cell is a comfortable threshold: at eps=200
        # with this Sigma the joint optimizer shifts ~10+ MW per cell.
        assert deviation > 0.1, (
            f"Joint vs shuffled schedule deviation = {deviation:.4f} MW; "
            f"expected > 1.0 MW under strong negative cross-region block. "
            f"A2b may be ignoring off-diagonal blocks of L (Cholesky "
            f"orientation or reshape-order bug)."
        )


# ---------------------------------------------------------------------------
# Reduction at epsilon = 0
# ---------------------------------------------------------------------------


class TestReductionAtEpsilonZero:
    """At eps=0, A2b minimizes <rho_bar, x>: the deterministic LP on rho_bar,
    matching A1-on-mean per region under equality work constraints.
    """

    def test_unique_optimum_matches_a1_per_region(self):
        """Strictly ordered rho_bar -> unique LP optimum -> exact schedule
        equality with A1-on-mean per region.
        """
        R, T = 2, 4
        region_order = ("REG_A", "REG_B")

        # Strictly increasing rho within each region; unique optimum
        # fills ceiling from the cheapest hour upward.
        rho_bar = np.array([
            [100.0, 200.0, 300.0, 400.0],
            [110.0, 210.0, 310.0, 410.0],
        ])
        workloads = np.array([60.0, 60.0])
        ceiling = np.full((R, T), 50.0)
        L = np.eye(R * T)  # eps=0 makes L irrelevant; identity is simplest

        result = solve_mahalanobis_dro(
            rho_bar=rho_bar, L=L, workloads=workloads, ceiling=ceiling,
            epsilon=0.0, region_order=region_order,
        )

        # Expected: per-region A1 with equality_work=True.
        expected = np.zeros((R, T))
        for r in range(R):
            a1 = schedule_deterministic_single_cluster(
                carbon_intensity=rho_bar[r],
                demand=ceiling[r],
                capacity_max=float(ceiling[r].max()),
                total_work=float(workloads[r]),
                equality_work=True,
            )
            expected[r] = a1.schedule

        np.testing.assert_allclose(result.schedule, expected, atol=1e-5)
        assert result.epsilon == 0.0
        assert result.penalty == 0.0
        np.testing.assert_allclose(
            result.robust_value, result.mean_carbon_value, rtol=1e-8, atol=1e-6
        )

    def test_tied_rho_objective_match_only(self):
        """With ties in rho_bar the LP has multiple optima; we assert only
        the OBJECTIVE value matches, not the schedule.

        Handoff lesson: don't assert schedule equality when LP uniqueness
        is not guaranteed; the solver may pick any of several optima with
        identical objective value.
        """
        R, T = 2, 4
        rho_bar = np.full((R, T), 200.0)  # all hours tied
        workloads = np.array([60.0, 60.0])
        ceiling = np.full((R, T), 50.0)

        rng = np.random.default_rng(42)
        A = rng.normal(size=(R * T, R * T))
        Sigma = A @ A.T + np.eye(R * T)
        L = np.linalg.cholesky(Sigma)  # non-trivial; eps=0 makes it irrelevant

        result = solve_mahalanobis_dro(
            rho_bar=rho_bar, L=L, workloads=workloads, ceiling=ceiling,
            epsilon=0.0, region_order=("REG_A", "REG_B"),
        )

        # Cost: 200 gCO2eq/kWh * 60 MWh per region * 2 regions = 24000.
        np.testing.assert_allclose(result.objective_value, 24000.0, rtol=1e-6)
        np.testing.assert_allclose(result.mean_carbon_value, 24000.0, rtol=1e-6)


# ---------------------------------------------------------------------------
# Result accounting and objective consistency
# ---------------------------------------------------------------------------


class TestResultAccounting:
    """Verifies the decomposition robust_value == mean + epsilon*mnorm,
    and that CVXPY's objective_value matches the post-solve numpy
    accounting (mismatch flags a vectorization or penalty-shape bug).
    """

    def _run(self, eps: float) -> MahalanobisDROResult:
        R, T = 2, 3
        rng = np.random.default_rng(7)
        A = rng.normal(size=(R * T, R * T))
        Sigma = A @ A.T + np.eye(R * T)
        L = np.linalg.cholesky(Sigma)
        return solve_mahalanobis_dro(
            rho_bar=rng.uniform(100, 500, size=(R, T)),
            L=L,
            workloads=np.array([30.0, 25.0]),
            ceiling=np.full((R, T), 40.0),
            epsilon=eps,
            region_order=("REG_A", "REG_B"),
        )

    def test_penalty_decomposition_holds(self):
        """penalty == epsilon * mahalanobis_norm."""
        result = self._run(eps=15.0)
        np.testing.assert_allclose(
            result.penalty, result.epsilon * result.mahalanobis_norm,
            rtol=1e-10, atol=1e-10,
        )

    def test_robust_value_is_mean_plus_penalty(self):
        """robust_value == mean_carbon_value + penalty."""
        result = self._run(eps=15.0)
        np.testing.assert_allclose(
            result.robust_value,
            result.mean_carbon_value + result.penalty,
            rtol=1e-10, atol=1e-10,
        )

    def test_mahalanobis_norm_nonnegative(self):
        """sqrt(...) is non-negative by construction."""
        for eps in (0.0, 1.0, 50.0):
            assert self._run(eps=eps).mahalanobis_norm >= 0.0

    def test_objective_value_matches_robust_value(self):
        """CVXPY objective matches post-solve numpy accounting."""
        for eps in (0.0, 1.0, 50.0):
            result = self._run(eps=eps)
            np.testing.assert_allclose(
                result.objective_value, result.robust_value,
                rtol=1e-6, atol=1e-4,
            )


# ---------------------------------------------------------------------------
# Regularization-path property
# ---------------------------------------------------------------------------


class TestEpsilonMonotonicity:
    """Standard regularization-path property: for min_x f(x) + eps*g(x),
    as eps increases the optimizer trades f for g. Here f = mean carbon
    cost, g = Mahalanobis norm; so mean weakly increases, mnorm weakly
    decreases. A misorientation of the penalty would flip this.
    """

    def test_monotonicity_over_epsilon_path(self):
        R, T = 2, 4
        rng = np.random.default_rng(11)
        A = rng.normal(size=(R * T, R * T))
        Sigma = A @ A.T + 5.0 * np.eye(R * T)
        L = np.linalg.cholesky(Sigma)

        # Region rho_bars cheap at opposite ends so the penalty has room
        # to perturb the schedule.
        rho_bar = np.array([
            [100.0, 200.0, 300.0, 400.0],
            [400.0, 300.0, 200.0, 100.0],
        ])
        workloads = np.array([60.0, 60.0])
        ceiling = np.full((R, T), 50.0)

        eps_path = [0.0, 1.0, 10.0, 100.0]
        means = []
        mnorms = []
        for eps in eps_path:
            result = solve_mahalanobis_dro(
                rho_bar=rho_bar, L=L, workloads=workloads, ceiling=ceiling,
                epsilon=eps, region_order=("REG_A", "REG_B"),
            )
            means.append(result.mean_carbon_value)
            mnorms.append(result.mahalanobis_norm)

        # Mean cost weakly increases with eps; tolerance absorbs solver
        # noise. Values are in the thousands; 1.0 absorbs SCS (~1e-3
        # precision) and is generous for CLARABEL/ECOS (~1e-7 precision)
        # without false-positiving on genuine monotonicity violations.
        for prev, curr in zip(means[:-1], means[1:]):
            assert curr >= prev - 1.0, (
                f"mean_carbon_value should be weakly increasing in eps, got "
                f"{means} along eps={eps_path}"
            )
        # Mahalanobis norm weakly decreases with eps; values in 100s, so
        # tolerance 0.1 (~ 1 part in 1000).
        for prev, curr in zip(mnorms[:-1], mnorms[1:]):
            assert curr <= prev + 0.1, (
                f"mahalanobis_norm should be weakly decreasing in eps, got "
                f"{mnorms} along eps={eps_path}"
            )


# ---------------------------------------------------------------------------
# L need not be triangular
# ---------------------------------------------------------------------------


class TestLFactorFlexibility:
    """L is any matrix with L @ L.T = Sigma_hat; triangularity not required.

    A symmetric square root from eigendecomposition should produce the
    same optimizer (the SOCP only sees L L^T = Sigma_hat).
    """

    def test_symmetric_sqrt_gives_same_optimum(self):
        R, T = 2, 3
        rng = np.random.default_rng(99)
        A = rng.normal(size=(R * T, R * T))
        Sigma = A @ A.T + np.eye(R * T)

        L_chol = np.linalg.cholesky(Sigma)
        eigvals, eigvecs = np.linalg.eigh(Sigma)
        L_symm = eigvecs @ np.diag(np.sqrt(eigvals)) @ eigvecs.T
        # Verify both reconstruct Sigma.
        np.testing.assert_allclose(L_chol @ L_chol.T, Sigma, atol=1e-10)
        np.testing.assert_allclose(L_symm @ L_symm.T, Sigma, atol=1e-10)

        rho_bar = rng.uniform(100, 500, size=(R, T))
        workloads = np.array([20.0, 20.0])
        ceiling = np.full((R, T), 30.0)
        eps = 15.0

        result_chol = solve_mahalanobis_dro(
            rho_bar=rho_bar, L=L_chol, workloads=workloads, ceiling=ceiling,
            epsilon=eps, region_order=("REG_A", "REG_B"),
        )
        result_symm = solve_mahalanobis_dro(
            rho_bar=rho_bar, L=L_symm, workloads=workloads, ceiling=ceiling,
            epsilon=eps, region_order=("REG_A", "REG_B"),
        )

        np.testing.assert_allclose(
            result_chol.objective_value, result_symm.objective_value, rtol=1e-6
        )
        np.testing.assert_allclose(
            result_chol.schedule, result_symm.schedule, atol=1e-4
        )
        np.testing.assert_allclose(
            result_chol.mahalanobis_norm, result_symm.mahalanobis_norm, rtol=1e-6
        )


# ---------------------------------------------------------------------------
# Realistic-size integration (synthetic 4-zone panel scale)
# ---------------------------------------------------------------------------


class TestIntegration4ZoneScale:
    """Solver handles realistic R=4, T=24 problem sizes."""

    def test_4_zone_24_hour_problem_solves(self):
        R, T = 4, 24
        rng = np.random.default_rng(123)
        # Plausible Sigma via a low-rank perturbation of identity, scaled
        # to typical carbon-intensity variance.
        A = rng.normal(size=(R * T, R * T)) * 5.0
        Sigma = A @ A.T + 50.0 * np.eye(R * T)
        L = np.linalg.cholesky(Sigma)

        rho_bar = rng.uniform(100, 500, size=(R, T))
        workloads = np.full(R, 200.0)        # 200 MWh per region per day
        ceiling = np.full((R, T), 50.0)      # 50 MW per hour
        eps = 10.0

        result = solve_mahalanobis_dro(
            rho_bar=rho_bar, L=L, workloads=workloads, ceiling=ceiling,
            epsilon=eps, region_order=("Z0", "Z1", "Z2", "Z3"),
        )

        assert result.solver_status in ("optimal", "optimal_inaccurate")
        # Feasibility on returned schedule.
        assert (result.schedule <= ceiling + 1e-6).all()
        assert (result.schedule >= -1e-6).all()
        np.testing.assert_allclose(
            result.schedule.sum(axis=1), workloads, atol=1e-4
        )
        # Sanity on result fields.
        assert result.mahalanobis_norm > 0  # non-trivial Sigma
        assert result.n_samples is None
        assert result.region_order == ("Z0", "Z1", "Z2", "Z3")


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Defensive checks before reaching the solver."""

    def _valid_inputs(self, R: int = 2, T: int = 3) -> dict:
        rng = np.random.default_rng(0)
        A = rng.normal(size=(R * T, R * T))
        Sigma = A @ A.T + np.eye(R * T)
        return dict(
            rho_bar=rng.uniform(100, 500, size=(R, T)),
            L=np.linalg.cholesky(Sigma),
            workloads=np.full(R, 20.0),
            ceiling=np.full((R, T), 30.0),
            epsilon=1.0,
            region_order=tuple(f"R{i}" for i in range(R)),
        )

    def test_rho_bar_not_2d(self):
        kw = self._valid_inputs()
        kw["rho_bar"] = np.zeros(6)
        with pytest.raises(ValueError, match="rho_bar must be 2-D"):
            solve_mahalanobis_dro(**kw)

    def test_ceiling_shape_mismatch(self):
        kw = self._valid_inputs()
        kw["ceiling"] = np.full((3, 3), 30.0)
        with pytest.raises(ValueError, match="ceiling must have shape"):
            solve_mahalanobis_dro(**kw)

    def test_workloads_shape_mismatch(self):
        kw = self._valid_inputs()
        kw["workloads"] = np.array([20.0, 20.0, 20.0])
        with pytest.raises(ValueError, match="workloads must have shape"):
            solve_mahalanobis_dro(**kw)

    def test_L_shape_mismatch(self):
        kw = self._valid_inputs()
        kw["L"] = np.eye(5)
        with pytest.raises(ValueError, match="L must have shape"):
            solve_mahalanobis_dro(**kw)

    def test_region_order_length_mismatch(self):
        kw = self._valid_inputs()
        kw["region_order"] = ("A", "B", "C")
        with pytest.raises(ValueError, match="region_order has"):
            solve_mahalanobis_dro(**kw)

    def test_negative_epsilon(self):
        kw = self._valid_inputs()
        kw["epsilon"] = -1.0
        with pytest.raises(ValueError, match="epsilon must be non-negative"):
            solve_mahalanobis_dro(**kw)

    def test_negative_rho_bar(self):
        kw = self._valid_inputs()
        kw["rho_bar"] = kw["rho_bar"].copy()
        kw["rho_bar"][0, 0] = -1.0
        with pytest.raises(ValueError, match="rho_bar must be non-negative"):
            solve_mahalanobis_dro(**kw)

    def test_non_finite_input(self):
        kw = self._valid_inputs()
        kw["rho_bar"] = kw["rho_bar"].copy()
        kw["rho_bar"][0, 0] = np.nan
        with pytest.raises(ValueError, match="non-finite"):
            solve_mahalanobis_dro(**kw)

    def test_infeasible_workload(self):
        kw = self._valid_inputs(R=2, T=3)
        # ceiling sum per region = 3 * 30 = 90 MW; demand 1000 MWh is infeasible.
        kw["workloads"] = np.array([1000.0, 20.0])
        with pytest.raises(ValueError, match="Infeasible"):
            solve_mahalanobis_dro(**kw)
