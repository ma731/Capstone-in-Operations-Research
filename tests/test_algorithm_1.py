"""Tests for Algorithm 1."""

import numpy as np
import pytest

from src.models.algorithm_1 import schedule_deterministic_single_cluster


class TestBasicBehavior:
    def test_solver_succeeds_on_simple_problem(self):
        T = 24
        rho = np.ones(T) * 100
        result = schedule_deterministic_single_cluster(
            carbon_intensity=rho,
            demand=np.full(T, 10.0),
            capacity_max=10.0,
            total_work=100.0,
        )
        assert result.solver_status in ("optimal", "optimal_inaccurate")

    def test_work_completion_constraint_is_tight_when_minimizing(self):
        """When carbon is positive everywhere, optimal solution does the minimum required work."""
        T = 24
        rho = np.ones(T) * 100
        result = schedule_deterministic_single_cluster(
            carbon_intensity=rho,
            demand=np.full(T, 50.0),
            capacity_max=50.0,
            total_work=100.0,
        )
        np.testing.assert_allclose(result.work_completed, 100.0, atol=1e-4)

    def test_capacity_constraint_respected(self):
        T = 24
        rho = np.arange(T, dtype=float) * 10  # increasing carbon
        cap = 5.0
        result = schedule_deterministic_single_cluster(
            carbon_intensity=rho,
            demand=np.full(T, 100.0),  # demand high, capacity is the binding constraint
            capacity_max=cap,
            total_work=20.0,
        )
        assert (result.schedule <= cap + 1e-6).all()

    def test_demand_cap_respected(self):
        T = 24
        rho = np.ones(T) * 100
        s = np.full(T, 3.0)
        result = schedule_deterministic_single_cluster(
            carbon_intensity=rho,
            demand=s,
            capacity_max=100.0,
            total_work=20.0,
        )
        assert (result.schedule <= s + 1e-6).all()


class TestCarbonAwareBehavior:
    def test_prefers_low_carbon_hours(self):
        """Compute should concentrate in low-carbon hours when capacity allows."""
        T = 24
        rho = np.ones(T) * 500
        rho[0:6] = 50  # cheap hours: 0-5
        result = schedule_deterministic_single_cluster(
            carbon_intensity=rho,
            demand=np.full(T, 10.0),
            capacity_max=10.0,
            total_work=60.0,  # exactly fits in the 6 cheap hours
        )
        # Expect all work concentrated in hours 0-5
        np.testing.assert_allclose(result.schedule[0:6], 10.0, atol=1e-4)
        np.testing.assert_allclose(result.schedule[6:], 0.0, atol=1e-4)

    def test_objective_value_matches_manual_calculation(self):
        T = 24
        rho = np.ones(T) * 500
        rho[0:6] = 50
        result = schedule_deterministic_single_cluster(
            carbon_intensity=rho,
            demand=np.full(T, 10.0),
            capacity_max=10.0,
            total_work=60.0,
        )
        expected = 50 * 60  # 60 MWh at 50 gCO2/kWh
        np.testing.assert_allclose(result.total_carbon, expected, atol=1e-3)


class TestInputValidation:
    def test_negative_carbon_intensity_rejected(self):
        with pytest.raises(ValueError, match="non-negative"):
            schedule_deterministic_single_cluster(
                carbon_intensity=np.array([-1.0, 100.0]),
                demand=np.array([10.0, 10.0]),
                capacity_max=10.0,
                total_work=10.0,
            )

    def test_mismatched_lengths_rejected(self):
        with pytest.raises(ValueError, match="same length"):
            schedule_deterministic_single_cluster(
                carbon_intensity=np.ones(24),
                demand=np.ones(12),
                capacity_max=10.0,
                total_work=10.0,
            )
