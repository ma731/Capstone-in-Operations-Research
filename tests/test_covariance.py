"""Tests for src.models.covariance.

Test pyramid:
  1. Convention tests (flatten/unflatten/block-diag indexing) - pure numpy,
     no statistics. These pin the row-major convention; if these fail, every
     downstream test is meaningless.
  2. Synthetic statistical tests - generate samples from a known
     distribution, verify estimator recovers it.
  3. Numerical tests - ridge regularization, Cholesky orientation.
  4. Integration smoke test - hits real Electricity Maps data on disk; skips
     gracefully if the CSVs aren't there.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.covariance import (
    REGION_ORDER,
    T_HOURS,
    block_diagonal_by_region,
    build_daily_panel,
    cholesky_factor,
    condition_number,
    daily_panel_to_matrix,
    estimate_mean_and_covariance,
    flatten_space_time,
    per_region_temporal_shuffle,
    regularize_covariance,
    unflatten_space_time,
)


# =============================================================================
# 1. Convention tests
# =============================================================================

class TestFlatteningConvention:
    """Pin the row-major flattening: vec[r*T + t] = matrix[r, t]."""

    def test_flatten_row_major_indexing(self):
        R, T = 4, 24
        arr = np.arange(R * T).reshape(R, T)
        vec = flatten_space_time(arr)

        # First T entries are region 0 across all hours
        assert vec[0] == arr[0, 0] == 0
        assert vec[T - 1] == arr[0, T - 1] == 23

        # Next T entries are region 1
        assert vec[T] == arr[1, 0] == 24
        assert vec[2 * T - 1] == arr[1, T - 1] == 47

        # Last block is region R-1
        assert vec[(R - 1) * T] == arr[R - 1, 0]
        assert vec[R * T - 1] == arr[R - 1, T - 1] == R * T - 1

    def test_flatten_unflatten_roundtrip(self):
        R, T = 4, 24
        rng = np.random.default_rng(0)
        arr = rng.normal(size=(R, T))
        vec = flatten_space_time(arr)
        restored = unflatten_space_time(vec, R=R, T=T)
        np.testing.assert_array_equal(restored, arr)

    def test_unflatten_flatten_roundtrip(self):
        R, T = 3, 5
        rng = np.random.default_rng(1)
        vec = rng.normal(size=R * T)
        arr = unflatten_space_time(vec, R=R, T=T)
        re_vec = flatten_space_time(arr)
        np.testing.assert_array_equal(re_vec, vec)

    def test_flatten_rejects_non_2d(self):
        with pytest.raises(ValueError, match="2-D"):
            flatten_space_time(np.arange(10))

    def test_unflatten_rejects_wrong_size(self):
        with pytest.raises(ValueError, match="length"):
            unflatten_space_time(np.arange(20), R=4, T=24)

    def test_unflatten_rejects_non_1d(self):
        with pytest.raises(ValueError, match="1-D"):
            unflatten_space_time(np.zeros((4, 24)), R=4, T=24)


class TestDailyPanelToMatrix:
    """The (N, R, T) -> (N, R*T) reshape uses the same row-major convention."""

    def test_each_row_is_one_day_flattened(self):
        N, R, T = 5, 4, 24
        panel = np.arange(N * R * T).reshape(N, R, T)
        mat = daily_panel_to_matrix(panel)
        assert mat.shape == (N, R * T)

        # Row i should equal flatten of panel[i]
        for i in range(N):
            np.testing.assert_array_equal(
                mat[i],
                flatten_space_time(panel[i]),
            )

    def test_rejects_non_3d(self):
        with pytest.raises(ValueError, match="3-D"):
            daily_panel_to_matrix(np.zeros((4, 24)))


class TestBlockDiagonalByRegion:
    """The shuffle: zero off-region blocks, keep within-region blocks."""

    def test_preserves_diagonal_blocks(self):
        R, T = 4, 24
        D = R * T
        rng = np.random.default_rng(2)
        cov = rng.normal(size=(D, D))
        cov = cov @ cov.T  # PSD

        shuf = block_diagonal_by_region(cov, R=R, T=T)

        for r in range(R):
            a, b = r * T, (r + 1) * T
            np.testing.assert_array_equal(shuf[a:b, a:b], cov[a:b, a:b])

    def test_zeros_off_diagonal_blocks(self):
        R, T = 4, 24
        D = R * T
        rng = np.random.default_rng(3)
        cov = rng.normal(size=(D, D))
        cov = cov @ cov.T

        shuf = block_diagonal_by_region(cov, R=R, T=T)

        for r in range(R):
            for s in range(R):
                if r == s:
                    continue
                ra, rb = r * T, (r + 1) * T
                ca, cb = s * T, (s + 1) * T
                assert np.all(shuf[ra:rb, ca:cb] == 0), (
                    f"block ({r}, {s}) should be zero"
                )

    def test_rejects_wrong_shape(self):
        with pytest.raises(ValueError, match="shape"):
            block_diagonal_by_region(np.zeros((50, 50)), R=4, T=24)

    def test_small_case_explicit(self):
        """R=2, T=3: build cov by hand, check block-diag matches expectation."""
        R, T = 2, 3
        cov = np.array([
            [11, 12, 13,  1,  2,  3],
            [21, 22, 23,  4,  5,  6],
            [31, 32, 33,  7,  8,  9],
            [ 1,  4,  7, 44, 45, 46],
            [ 2,  5,  8, 54, 55, 56],
            [ 3,  6,  9, 64, 65, 66],
        ], dtype=float)

        expected = np.array([
            [11, 12, 13,  0,  0,  0],
            [21, 22, 23,  0,  0,  0],
            [31, 32, 33,  0,  0,  0],
            [ 0,  0,  0, 44, 45, 46],
            [ 0,  0,  0, 54, 55, 56],
            [ 0,  0,  0, 64, 65, 66],
        ], dtype=float)

        np.testing.assert_array_equal(
            block_diagonal_by_region(cov, R=R, T=T),
            expected,
        )


class TestPerRegionTemporalShuffle:
    """The sample-level shuffle that destroys cross-region day alignment."""

    def test_preserves_each_region_marginal_mean_exactly(self):
        """Means computed across N days, per (r, t), must be exactly preserved
        because each region is permuted (reordered) rather than resampled."""
        rng = np.random.default_rng(0)
        panel = rng.normal(size=(50, 4, 24))
        shuf_rng = np.random.default_rng(1)
        shuf = per_region_temporal_shuffle(panel, rng=shuf_rng)
        np.testing.assert_allclose(shuf.mean(axis=0), panel.mean(axis=0))

    def test_within_region_temporal_structure_preserved(self):
        """For each region, the set of T-vectors across days is preserved (a
        permutation of the original set). Check via sorted comparison."""
        rng = np.random.default_rng(2)
        panel = rng.normal(size=(20, 3, 5))
        shuf = per_region_temporal_shuffle(panel, rng=np.random.default_rng(3))

        for r in range(panel.shape[1]):
            # Each region's set of daily T-vectors must be the same set
            orig_rows = sorted(map(tuple, panel[:, r, :]))
            shuf_rows = sorted(map(tuple, shuf[:, r, :]))
            assert orig_rows == shuf_rows

    def test_destroys_cross_region_alignment(self):
        """If region 0 has values 1,2,3,...,N at hour 0 over the panel and
        region 1 has 1,2,3,...,N at hour 0 too (perfectly aligned by day),
        post-shuffle the day-by-day alignment must be broken in expectation."""
        N = 1000
        panel = np.zeros((N, 2, 1))
        panel[:, 0, 0] = np.arange(N, dtype=float)
        panel[:, 1, 0] = np.arange(N, dtype=float)
        # Pre-shuffle: identical across regions on every day; correlation = 1.0
        pre_corr = np.corrcoef(panel[:, 0, 0], panel[:, 1, 0])[0, 1]
        assert pre_corr > 0.999

        shuf = per_region_temporal_shuffle(panel, rng=np.random.default_rng(4))
        post_corr = np.corrcoef(shuf[:, 0, 0], shuf[:, 1, 0])[0, 1]
        # After shuffling region 1's days independently, day-by-day correlation
        # should be near zero (a random permutation of 1..N against itself
        # has expected correlation 0, SE = 1/sqrt(N-1) ~= 0.032)
        assert abs(post_corr) < 0.15, f"post-shuffle correlation = {post_corr:.3f}"

    def test_deterministic_with_seed(self):
        """Same Generator state must produce the same shuffle."""
        panel = np.random.default_rng(5).normal(size=(30, 4, 24))
        shuf_a = per_region_temporal_shuffle(panel, rng=np.random.default_rng(99))
        shuf_b = per_region_temporal_shuffle(panel, rng=np.random.default_rng(99))
        np.testing.assert_array_equal(shuf_a, shuf_b)

    def test_does_not_mutate_input(self):
        rng = np.random.default_rng(6)
        panel = rng.normal(size=(10, 2, 5))
        snapshot = panel.copy()
        _ = per_region_temporal_shuffle(panel, rng=np.random.default_rng(7))
        np.testing.assert_array_equal(panel, snapshot)

    def test_rejects_non_3d(self):
        with pytest.raises(ValueError, match="3-D"):
            per_region_temporal_shuffle(np.zeros((10, 4)))


# =============================================================================
# 2. Synthetic statistical tests
# =============================================================================

class TestEstimateMeanAndCovariance:
    """Mean/covariance estimator: wrapper correctness + statistical recovery."""

    def test_matches_numpy_directly(self):
        """The wrapper must exactly match np.mean and np.cov(rowvar=False, ddof=1).
        This is the strict regression check - no statistical noise."""
        rng = np.random.default_rng(42)
        samples = rng.normal(size=(100, 8))

        est_mean, est_cov = estimate_mean_and_covariance(samples)

        np.testing.assert_array_equal(est_mean, samples.mean(axis=0))
        np.testing.assert_array_equal(
            est_cov,
            np.cov(samples, rowvar=False, ddof=1),
        )

    def test_recovers_known_distribution(self):
        """Statistical recovery within standard-error bands derived from the
        analytical sampling variance of sample mean and covariance.

        For Gaussian samples, the sample mean has SE = sqrt(sigma_ii / N) per
        coordinate, and the sample covariance has approximate SE
            SE(Sigma_hat_ij) = sqrt((Sigma_ij^2 + Sigma_ii * Sigma_jj) / (N - 1)).
        A 5-sigma band is conservative against finite-sample noise across
        seeds while tight enough that a buggy estimator would fail most entries.

        This is preferable to a fixed atol/rtol because the allowed error
        scales correctly by entry: high-variance diagonals get larger absolute
        tolerance, small off-diagonals get smaller tolerance, both calibrated
        to actual sampling noise rather than a hand-picked constant."""
        rng = np.random.default_rng(42)
        D = 10
        N = 50_000

        true_mean = rng.normal(size=D)
        A = rng.normal(size=(D, D))
        true_cov = A @ A.T + 0.5 * np.eye(D)

        samples = rng.multivariate_normal(true_mean, true_cov, size=N)
        est_mean, est_cov = estimate_mean_and_covariance(samples)

        # Mean: SE = sqrt(diag(cov) / N) per coordinate
        mean_se = np.sqrt(np.diag(true_cov) / N)
        np.testing.assert_array_less(
            np.abs(est_mean - true_mean),
            5.0 * mean_se + 1e-12,
        )

        # Covariance: SE_ij = sqrt((sigma_ij^2 + sigma_ii * sigma_jj) / (N - 1))
        cov_se = np.sqrt(
            (true_cov ** 2 + np.outer(np.diag(true_cov), np.diag(true_cov)))
            / (N - 1)
        )
        np.testing.assert_array_less(
            np.abs(est_cov - true_cov),
            5.0 * cov_se + 1e-12,
        )

    def test_returns_symmetric_covariance(self):
        """Covariance must be symmetric to floating-point precision."""
        rng = np.random.default_rng(7)
        samples = rng.normal(size=(500, 20))
        _, cov = estimate_mean_and_covariance(samples)
        np.testing.assert_allclose(cov, cov.T, atol=1e-12)

    def test_rejects_too_few_samples(self):
        with pytest.raises(ValueError, match="2 samples"):
            estimate_mean_and_covariance(np.zeros((1, 5)))

    def test_rejects_non_2d(self):
        with pytest.raises(ValueError, match="2-D"):
            estimate_mean_and_covariance(np.zeros(10))


# =============================================================================
# 3. Numerical tests: regularization and Cholesky
# =============================================================================

class TestRegularizeCovariance:
    def test_makes_singular_matrix_psd(self):
        """A rank-deficient matrix should become PSD after ridge."""
        D = 10
        # Rank-1 matrix: outer product of a single vector
        v = np.random.default_rng(0).normal(size=D)
        cov = np.outer(v, v) + np.eye(D) * 1.0  # add some scale so trace > 0
        # Drop the identity to make it rank 1
        cov = np.outer(v, v) * 100.0  # rank 1, large scale

        reg = regularize_covariance(cov, eta=1e-3)
        # Cholesky should now succeed
        L = np.linalg.cholesky(reg)
        assert L.shape == (D, D)

    def test_scale_adaptive(self):
        """Doubling the input scale should double the ridge delta."""
        rng = np.random.default_rng(5)
        A = rng.normal(size=(8, 8))
        cov = A @ A.T

        eta = 1e-4
        D = cov.shape[0]
        delta_1 = eta * np.trace(cov) / D
        delta_2 = eta * np.trace(2 * cov) / D
        assert abs(delta_2 - 2 * delta_1) < 1e-10

        reg_1 = regularize_covariance(cov, eta=eta)
        reg_2 = regularize_covariance(2 * cov, eta=eta)

        # The added diagonal should be 2x in the second
        added_1 = (reg_1 - cov)[0, 0]
        added_2 = (reg_2 - 2 * cov)[0, 0]
        assert abs(added_2 - 2 * added_1) < 1e-10

    def test_rejects_non_square(self):
        with pytest.raises(ValueError, match="square"):
            regularize_covariance(np.zeros((4, 5)))

    def test_rejects_negative_eta(self):
        with pytest.raises(ValueError, match="non-negative"):
            regularize_covariance(np.eye(4), eta=-1e-3)

    def test_rejects_non_positive_trace(self):
        with pytest.raises(ValueError, match="trace"):
            regularize_covariance(np.zeros((4, 4)))


class TestCholeskyFactor:
    def test_reconstructs_input(self):
        """L @ L.T should equal cov_reg within float tolerance."""
        rng = np.random.default_rng(7)
        D = 12
        A = rng.normal(size=(D, D))
        cov = A @ A.T + np.eye(D)  # PSD

        L = cholesky_factor(cov)
        np.testing.assert_allclose(L @ L.T, cov, rtol=1e-10, atol=1e-10)

    def test_is_lower_triangular(self):
        """Numpy convention: L should be lower triangular (zeros above diag)."""
        rng = np.random.default_rng(8)
        D = 8
        A = rng.normal(size=(D, D))
        cov = A @ A.T + np.eye(D)

        L = cholesky_factor(cov)
        # Upper triangle (strictly above diagonal) should be zero
        upper = np.triu(L, k=1)
        np.testing.assert_array_equal(upper, np.zeros_like(upper))

    def test_mahalanobis_norm_via_LT(self):
        """The key Mahalanobis identity: x.T @ Sigma @ x == ||L.T @ x||_2^2.

        If this fails, the CVXPY Mahalanobis penalty `cp.norm(L.T @ x_vec, 2)`
        will compute the wrong quadratic form.
        """
        rng = np.random.default_rng(9)
        D = 8
        A = rng.normal(size=(D, D))
        cov = A @ A.T + np.eye(D)
        L = cholesky_factor(cov)

        x = rng.normal(size=D)

        quad = float(x.T @ cov @ x)
        via_LT = float(np.linalg.norm(L.T @ x) ** 2)

        assert abs(quad - via_LT) < 1e-9

    def test_raises_on_non_psd(self):
        """If caller forgets to regularize, Cholesky should raise."""
        # Negative-definite matrix
        cov = -np.eye(5)
        with pytest.raises(np.linalg.LinAlgError):
            cholesky_factor(cov)


# =============================================================================
# 4. Conditioning diagnostic
# =============================================================================

class TestConditionNumber:
    def test_identity_is_one(self):
        assert abs(condition_number(np.eye(10)) - 1.0) < 1e-10

    def test_diagonal_returns_ratio(self):
        d = np.diag([1.0, 2.0, 4.0, 8.0])
        assert abs(condition_number(d) - 8.0) < 1e-10

    def test_singular_returns_inf(self):
        rng = np.random.default_rng(10)
        v = rng.normal(size=6)
        cov = np.outer(v, v)  # rank 1
        assert condition_number(cov) == float("inf")


# =============================================================================
# 5. Build daily panel - small synthetic case
# =============================================================================

class TestBuildDailyPanelSynthetic:
    """Construct a tiny synthetic wide DataFrame and verify panel layout."""

    @staticmethod
    def _make_wide_df(n_days: int, zones: list[str], start: str = "2024-01-01") -> pd.DataFrame:
        # Build hourly UTC index spanning n_days. Use 8am UTC start so it
        # falls cleanly inside the same local-Pacific day for n_days=2 etc.
        # Actually, simpler: start at 00:00 local and go forward.
        # Using UTC start at 08:00 (= midnight Pacific PST in winter).
        idx = pd.date_range(
            start=f"{start} 08:00:00", periods=24 * n_days,
            freq="h", tz="UTC",
        )
        rng = np.random.default_rng(123)
        data = {z: rng.normal(loc=200 + 50 * i, scale=20, size=len(idx))
                for i, z in enumerate(zones)}
        return pd.DataFrame(data, index=idx)

    def test_panel_shape_matches_n_days_and_R_T(self):
        zones = list(REGION_ORDER)
        wide = self._make_wide_df(n_days=3, zones=zones)
        panel, dates = build_daily_panel(wide, region_order=zones)

        assert panel.shape == (3, len(zones), 24)
        assert len(dates) == 3

    def test_panel_axis1_matches_region_order(self):
        """panel[:, r, :] should correspond to region_order[r]."""
        zones = ["zone_A", "zone_B"]
        idx = pd.date_range("2024-01-01 08:00", periods=24, freq="h", tz="UTC")
        # zone_A is constant 100, zone_B is constant 999 - easy to tell apart
        wide = pd.DataFrame({"zone_A": 100.0, "zone_B": 999.0}, index=idx)

        panel, _ = build_daily_panel(wide, region_order=zones)
        assert panel.shape == (1, 2, 24)
        np.testing.assert_allclose(panel[0, 0, :], 100.0)
        np.testing.assert_allclose(panel[0, 1, :], 999.0)

    def test_panel_reordering_matches_request(self):
        """If wide_df columns are alphabetical and region_order isn't, the
        panel's region axis follows region_order, not wide_df.columns."""
        # wide_df will have columns alphabetical: zone_A, zone_B
        idx = pd.date_range("2024-01-01 08:00", periods=24, freq="h", tz="UTC")
        wide = pd.DataFrame({"zone_A": 100.0, "zone_B": 999.0}, index=idx)

        # Request the reverse order
        panel, _ = build_daily_panel(wide, region_order=["zone_B", "zone_A"])
        np.testing.assert_allclose(panel[0, 0, :], 999.0)  # B first
        np.testing.assert_allclose(panel[0, 1, :], 100.0)  # A second

    def test_rejects_unknown_zone(self):
        zones = ["zone_A", "zone_B"]
        wide = self._make_wide_df(n_days=2, zones=zones)
        with pytest.raises(ValueError, match="not in wide_df"):
            build_daily_panel(wide, region_order=["zone_A", "zone_C"])

    def test_incomplete_days_are_dropped(self):
        """A day with only 12 hours of data should be silently dropped."""
        zones = ["zone_A"]
        # 24 hours on day 1, then only 12 hours on day 2
        idx = pd.date_range("2024-01-01 08:00", periods=36, freq="h", tz="UTC")
        wide = pd.DataFrame({"zone_A": np.arange(36, dtype=float)}, index=idx)

        panel, dates = build_daily_panel(wide, region_order=zones)
        # Only the complete local-Pacific day should survive
        assert panel.shape[0] >= 1
        # If both happen to be complete (depending on tz boundary), that's
        # fine. The key is that no day with <24 hours appears.
        for i in range(panel.shape[0]):
            assert not np.isnan(panel[i]).any()


# =============================================================================
# 6. Integration smoke test: real Electricity Maps data
# =============================================================================

class TestRealDataIntegration:
    """Hits real data on disk. Skips if not present so unit-test runs stay
    fast and CI-friendly. Run with `pytest -k Integration` to exercise."""

    @pytest.fixture(scope="class")
    def wide_panel(self):
        try:
            from src.data.electricitymaps import load_all_zones, to_wide
        except ImportError:
            pytest.skip("Electricity Maps loader not importable")

        try:
            long_df = load_all_zones(list(REGION_ORDER))
        except FileNotFoundError:
            pytest.skip("4-zone CSVs not present on disk")

        return to_wide(long_df)

    def test_build_panel_yields_expected_shape(self, wide_panel):
        panel, dates = build_daily_panel(wide_panel)
        N, R, T = panel.shape
        assert R == 4
        assert T == T_HOURS
        # ~5 years * 365.25 days - ~10 DST days. Allow some slack.
        assert 1800 < N < 1830, f"expected ~1826 daily samples, got {N}"
        assert len(dates) == N

    def test_covariance_pipeline_end_to_end(self, wide_panel):
        """Build panel -> sample matrix -> mean+cov -> regularize -> Cholesky."""
        panel, _ = build_daily_panel(wide_panel)
        samples = daily_panel_to_matrix(panel)
        assert samples.shape == (panel.shape[0], 4 * T_HOURS)

        mean, cov = estimate_mean_and_covariance(samples)
        assert mean.shape == (4 * T_HOURS,)
        assert cov.shape == (4 * T_HOURS, 4 * T_HOURS)

        cov_reg = regularize_covariance(cov, eta=1e-5)
        L = cholesky_factor(cov_reg)  # should succeed
        np.testing.assert_allclose(L @ L.T, cov_reg, rtol=1e-9, atol=1e-9)

        # Condition number after ridge should be finite and not absurd
        cond = condition_number(cov_reg)
        assert np.isfinite(cond)
        assert cond < 1e12, f"ridge too small; condition number = {cond:.2e}"

    def test_block_diagonal_joint_vs_shuf_differ(self, wide_panel):
        """Sigma_joint and Sigma_shuf should differ - empirical sanity that
        there ARE non-trivial cross-zone covariances in the real panel."""
        panel, _ = build_daily_panel(wide_panel)
        samples = daily_panel_to_matrix(panel)
        _, cov = estimate_mean_and_covariance(samples)

        cov_shuf = block_diagonal_by_region(cov, R=4, T=T_HOURS)
        # They had better differ - the cross-zone empirical correlations we
        # documented in section 4 (CISO-NEVP = 0.885, etc.) live in the
        # off-diagonal blocks.
        assert not np.allclose(cov, cov_shuf)
        # And the diagonal blocks should be exactly equal.
        for r in range(4):
            a, b = r * T_HOURS, (r + 1) * T_HOURS
            np.testing.assert_array_equal(cov[a:b, a:b], cov_shuf[a:b, a:b])
