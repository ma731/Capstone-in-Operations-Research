"""Tests for src.models.algorithm_2a_linf.

The Phase 1 degeneracy result that A2a is designed to demonstrate:
    1. Schedule invariance with respect to epsilon (closed-form result).
    2. Schedule equals Algorithm 1 on rho_bar.
    3. Robust value decomposes as <rho_bar, x*> + epsilon * sum_r W_r exactly.
    4. Schedule invariance with respect to mean-preserving sample shuffles.

All four are theoretical consequences of equation (4) in progress note v8.3,
so violations would indicate either an estimator bug, a solver issue, or a
misimplementation of equality work constraints.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.models.algorithm_1 import schedule_deterministic_single_cluster
from src.models.algorithm_2a_linf import (
    LinfDROResult,
    solve_linf_dro_baseline,
)
from src.models.covariance import (
    REGION_ORDER,
    T_HOURS,
    per_region_temporal_shuffle,
)


# Synthetic panel fixture: small, deterministic, with non-trivial joint
# structure so the shuffled-vs-joint test isn't trivially equal pre-shuffle.
def _make_synthetic_panel(N=200, R=4, T=24, seed=0):
    """Build a (N, R, T) panel with regions sharing a common diurnal pattern
    plus per-region noise. Means and cross-region correlation are non-trivial."""
    rng = np.random.default_rng(seed)
    # Common diurnal driver: solar-trough at noon, peak at evening
    t = np.arange(T)
    diurnal = 200 + 100 * np.cos((t - 12) * np.pi / 12)  # (T,)
    panel = np.zeros((N, R, T))
    for i in range(N):
        common_shift = rng.normal(0, 30)
        for r in range(R):
            region_offset = 50 * r  # zones differ in mean CI
            noise = rng.normal(0, 20, size=T)
            panel[i, r, :] = diurnal + region_offset + common_shift + noise
    return np.maximum(panel, 0.0)  # CI is non-negative


def _make_workloads_and_ceiling(R=4, T=24):
    """Reasonable defaults: 600 MWh per region, flat 50 MW ceiling per hour."""
    workloads = np.full(R, 600.0)
    ceiling = np.full((R, T), 50.0)
    return workloads, ceiling


# =============================================================================
# 1. Schedule invariance with respect to epsilon
# =============================================================================

class TestEpsilonInvariance:
    """The headline degeneracy result: argmin is independent of epsilon."""

    def test_schedule_identical_across_epsilon_values(self):
        panel = _make_synthetic_panel()
        workloads, ceiling = _make_workloads_and_ceiling()

        epsilons = [0.0, 1.0, 10.0, 100.0, 1000.0]
        results = [
            solve_linf_dro_baseline(panel, workloads, ceiling, epsilon=e)
            for e in epsilons
        ]
        baseline = results[0].schedule
        for r in results[1:]:
            np.testing.assert_allclose(r.schedule, baseline, atol=1e-4)


# =============================================================================
# 2. Schedule matches Algorithm 1 on rho_bar
# =============================================================================

class TestMatchesAlgorithm1OnMean:
    """A2a should be identical to A1 run on the empirical mean field, per region."""

    def test_per_region_match(self):
        panel = _make_synthetic_panel()
        workloads, ceiling = _make_workloads_and_ceiling()
        R, T = ceiling.shape

        a2a = solve_linf_dro_baseline(panel, workloads, ceiling, epsilon=5.0)

        rho_bar = panel.mean(axis=0)
        for r in range(R):
            a1 = schedule_deterministic_single_cluster(
                carbon_intensity=rho_bar[r],
                demand=ceiling[r],
                capacity_max=float(ceiling[r].max()),
                total_work=float(workloads[r]),
                equality_work=True,
            )
            np.testing.assert_allclose(a2a.schedule[r], a1.schedule, atol=1e-4)


# =============================================================================
# 3. Robust value decomposition
# =============================================================================

class TestRobustValueDecomposition:
    """<rho_bar, x*> + epsilon * sum_r W_r must hold exactly."""

    def test_penalty_equals_epsilon_times_total_workload(self):
        panel = _make_synthetic_panel()
        workloads, ceiling = _make_workloads_and_ceiling()
        epsilon = 7.5

        result = solve_linf_dro_baseline(panel, workloads, ceiling, epsilon=epsilon)
        expected_penalty = epsilon * float(workloads.sum())
        assert abs(result.penalty - expected_penalty) < 1e-9

    def test_robust_value_equals_mean_plus_penalty(self):
        panel = _make_synthetic_panel()
        workloads, ceiling = _make_workloads_and_ceiling()
        result = solve_linf_dro_baseline(panel, workloads, ceiling, epsilon=3.0)
        assert abs(result.robust_value - (result.mean_carbon_value + result.penalty)) < 1e-9

    def test_robust_value_shifts_linearly_with_epsilon(self):
        """If schedule is epsilon-invariant, robust_value(eps) - robust_value(0)
        must equal eps * sum_r W_r exactly."""
        panel = _make_synthetic_panel()
        workloads, ceiling = _make_workloads_and_ceiling()
        r0 = solve_linf_dro_baseline(panel, workloads, ceiling, epsilon=0.0)
        r10 = solve_linf_dro_baseline(panel, workloads, ceiling, epsilon=10.0)
        expected_shift = 10.0 * float(workloads.sum())
        assert abs((r10.robust_value - r0.robust_value) - expected_shift) < 1e-6


# =============================================================================
# 4. Joint vs shuffled invariance (the second leg of the degeneracy)
# =============================================================================

class TestShuffledMarginalsInvariance:
    """Per-region temporal shuffle preserves rho_bar exactly, therefore A2a
    schedules must be identical under joint vs shuffled panel."""

    def test_shuffle_preserves_rho_bar_exactly(self):
        panel = _make_synthetic_panel()
        shuf = per_region_temporal_shuffle(panel, rng=np.random.default_rng(42))
        np.testing.assert_allclose(shuf.mean(axis=0), panel.mean(axis=0))

    def test_joint_and_shuffled_produce_identical_schedules(self):
        panel = _make_synthetic_panel()
        workloads, ceiling = _make_workloads_and_ceiling()
        shuf = per_region_temporal_shuffle(panel, rng=np.random.default_rng(42))

        a2a_joint = solve_linf_dro_baseline(panel, workloads, ceiling, epsilon=5.0)
        a2a_shuf = solve_linf_dro_baseline(shuf, workloads, ceiling, epsilon=5.0)
        np.testing.assert_allclose(a2a_joint.schedule, a2a_shuf.schedule, atol=1e-4)

    def test_joint_and_shuffled_produce_identical_robust_values(self):
        panel = _make_synthetic_panel()
        workloads, ceiling = _make_workloads_and_ceiling()
        shuf = per_region_temporal_shuffle(panel, rng=np.random.default_rng(42))

        a2a_joint = solve_linf_dro_baseline(panel, workloads, ceiling, epsilon=5.0)
        a2a_shuf = solve_linf_dro_baseline(shuf, workloads, ceiling, epsilon=5.0)
        assert abs(a2a_joint.robust_value - a2a_shuf.robust_value) < 1e-6


# =============================================================================
# 5. Output structure and wiring
# =============================================================================

class TestOutputStructure:
    def test_schedule_per_region_keys_match_region_order(self):
        panel = _make_synthetic_panel()
        workloads, ceiling = _make_workloads_and_ceiling()
        zones = ["A", "B", "C", "D"]
        result = solve_linf_dro_baseline(panel, workloads, ceiling, region_order=zones)
        assert list(result.schedule_per_region.keys()) == zones

    def test_schedule_per_region_matches_schedule_matrix(self):
        panel = _make_synthetic_panel()
        workloads, ceiling = _make_workloads_and_ceiling()
        zones = ["A", "B", "C", "D"]
        result = solve_linf_dro_baseline(panel, workloads, ceiling, region_order=zones)
        for r, zone in enumerate(zones):
            np.testing.assert_array_equal(result.schedule_per_region[zone], result.schedule[r])

    def test_work_constraint_binds_at_equality_per_region(self):
        panel = _make_synthetic_panel()
        workloads, ceiling = _make_workloads_and_ceiling()
        result = solve_linf_dro_baseline(panel, workloads, ceiling, epsilon=0.0)
        np.testing.assert_allclose(result.schedule.sum(axis=1), workloads, atol=1e-4)

    def test_ceiling_respected_per_region_per_hour(self):
        panel = _make_synthetic_panel()
        workloads, ceiling = _make_workloads_and_ceiling()
        result = solve_linf_dro_baseline(panel, workloads, ceiling, epsilon=0.0)
        assert (result.schedule <= ceiling + 1e-6).all()

    def test_n_samples_reported(self):
        panel = _make_synthetic_panel(N=137)
        workloads, ceiling = _make_workloads_and_ceiling()
        result = solve_linf_dro_baseline(panel, workloads, ceiling, epsilon=0.0)
        assert result.n_samples == 137


# =============================================================================
# 6. Input validation
# =============================================================================

class TestInputValidation:
    def test_rejects_non_3d_panel(self):
        with pytest.raises(ValueError, match="3-D"):
            solve_linf_dro_baseline(
                panel=np.zeros((4, 24)),
                workloads=np.full(4, 600.0),
                ceiling=np.full((4, 24), 50.0),
            )

    def test_rejects_wrong_workloads_shape(self):
        with pytest.raises(ValueError, match="workloads"):
            solve_linf_dro_baseline(
                panel=np.zeros((10, 4, 24)),
                workloads=np.full(3, 600.0),
                ceiling=np.full((4, 24), 50.0),
            )

    def test_rejects_wrong_ceiling_shape(self):
        with pytest.raises(ValueError, match="ceiling"):
            solve_linf_dro_baseline(
                panel=np.zeros((10, 4, 24)),
                workloads=np.full(4, 600.0),
                ceiling=np.full((4, 23), 50.0),
            )

    def test_rejects_negative_epsilon(self):
        with pytest.raises(ValueError, match="non-negative"):
            solve_linf_dro_baseline(
                panel=np.zeros((10, 4, 24)),
                workloads=np.full(4, 600.0),
                ceiling=np.full((4, 24), 50.0),
                epsilon=-1.0,
            )

    def test_rejects_region_order_length_mismatch(self):
        with pytest.raises(ValueError, match="region_order"):
            solve_linf_dro_baseline(
                panel=np.zeros((10, 4, 24)),
                workloads=np.full(4, 600.0),
                ceiling=np.full((4, 24), 50.0),
                region_order=("A", "B", "C"),  # only 3
            )


# =============================================================================
# 7. Real data integration
# =============================================================================

class TestRealDataIntegration:
    """End-to-end on the 4-zone Electricity Maps panel. Skips if data absent."""

    @pytest.fixture(scope="class")
    def real_panel(self):
        try:
            from src.data.electricitymaps import load_all_zones, to_wide
            from src.models.covariance import build_daily_panel
        except ImportError:
            pytest.skip("Electricity Maps loader not importable")
        try:
            long_df = load_all_zones(list(REGION_ORDER))
        except FileNotFoundError:
            pytest.skip("4-zone CSVs not present on disk")
        wide = to_wide(long_df)
        panel, _ = build_daily_panel(wide)
        return panel

    def test_epsilon_invariance_on_real_data(self, real_panel):
        R = real_panel.shape[1]
        workloads = np.full(R, 600.0)
        ceiling = np.full((R, T_HOURS), 50.0)

        epsilons = [0.0, 1.0, 100.0, 10_000.0]
        results = [
            solve_linf_dro_baseline(real_panel, workloads, ceiling, epsilon=e)
            for e in epsilons
        ]
        baseline = results[0].schedule
        for r in results[1:]:
            np.testing.assert_allclose(r.schedule, baseline, atol=1e-3)

    def test_joint_vs_shuffled_on_real_data(self, real_panel):
        R = real_panel.shape[1]
        workloads = np.full(R, 600.0)
        ceiling = np.full((R, T_HOURS), 50.0)

        shuf = per_region_temporal_shuffle(real_panel, rng=np.random.default_rng(0))
        a2a_joint = solve_linf_dro_baseline(real_panel, workloads, ceiling, epsilon=10.0)
        a2a_shuf = solve_linf_dro_baseline(shuf, workloads, ceiling, epsilon=10.0)

        # Means preserved exactly by per-region temporal shuffle.
        np.testing.assert_allclose(a2a_joint.rho_bar, a2a_shuf.rho_bar, atol=1e-9)
        # Therefore schedules identical.
        np.testing.assert_allclose(a2a_joint.schedule, a2a_shuf.schedule, atol=1e-3)
        # Therefore robust values identical.
        assert abs(a2a_joint.robust_value - a2a_shuf.robust_value) < 1e-3
