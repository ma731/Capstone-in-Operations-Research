"""Tests for the carbon-budget constraint (Task C, constraint 3d).

Covers both the deterministic coupled baseline (algorithm_1) and the DRO
(algorithm_2b). Key semantics, verified here:

  * In the pure-min baseline the objective already minimizes carbon, so a budget
    >= the achievable minimum is SLACK (no effect) and a budget below it is
    INFEASIBLE. The constraint is a no-op-or-infeasible there by design.
  * In the DRO, robustness (large epsilon) can inflate NOMINAL carbon above the
    deterministic minimum; a budget between the two BINDS and caps nominal carbon.
"""

import numpy as np
import pytest

from src.models.algorithm_1 import schedule_deterministic_coupled
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro


def _toy():
    R, T = 2, 4
    rho = np.array([
        [100.0, 200.0, 300.0, 400.0],
        [400.0, 300.0, 200.0, 100.0],
    ])
    ceiling = np.full((R, T), 50.0)
    W = np.array([60.0, 60.0])
    return rho, ceiling, W


class TestBaselineBudget:
    def test_slack_budget_matches_unconstrained(self):
        rho, ceiling, W = _toy()
        base = schedule_deterministic_coupled(rho, W, ceiling)
        budg = schedule_deterministic_coupled(
            rho, W, ceiling, carbon_budget=base.total_carbon * 2.0
        )
        assert np.allclose(base.schedule, budg.schedule, atol=1e-5)
        assert budg.binding["carbon_budget_margin"] > 0

    def test_budget_below_minimum_is_infeasible(self):
        rho, ceiling, W = _toy()
        base = schedule_deterministic_coupled(rho, W, ceiling)
        with pytest.raises(RuntimeError):
            schedule_deterministic_coupled(
                rho, W, ceiling, carbon_budget=base.total_carbon * 0.5
            )

    def test_negative_budget_raises(self):
        rho, ceiling, W = _toy()
        with pytest.raises(ValueError):
            schedule_deterministic_coupled(rho, W, ceiling, carbon_budget=-1.0)


class TestDROBudget:
    def _L(self, R, T):
        # Identity within-region, negative cross-region block (matches the
        # algorithm_2b demo): robustness pulls the schedule off the carbon min.
        Sigma = 100.0 * np.eye(R * T)
        Sigma[0:T, T:2 * T] = -50.0 * np.eye(T)
        Sigma[T:2 * T, 0:T] = -50.0 * np.eye(T)
        return np.linalg.cholesky(Sigma)

    def test_budget_caps_nominal_carbon_in_dro(self):
        rho, ceiling, W = _toy()
        R, T = rho.shape
        L = self._L(R, T)
        det = solve_mahalanobis_dro(rho, L, W, ceiling, epsilon=0.0,
                                    region_order=("A", "B"))
        rob = solve_mahalanobis_dro(rho, L, W, ceiling, epsilon=100.0,
                                    region_order=("A", "B"))
        if rob.mean_carbon_value <= det.mean_carbon_value + 1.0:
            pytest.skip("toy robustness did not inflate nominal carbon; budget non-binding")
        B = 0.5 * (det.mean_carbon_value + rob.mean_carbon_value)
        capped = solve_mahalanobis_dro(rho, L, W, ceiling, epsilon=100.0,
                                       region_order=("A", "B"), carbon_budget=B)
        assert capped.mean_carbon_value <= B + 1e-3
        # Budget binds -> schedule differs from the unconstrained robust one.
        assert not np.allclose(capped.schedule, rob.schedule, atol=1e-4)

    def test_negative_budget_raises_in_dro(self):
        rho, ceiling, W = _toy()
        R, T = rho.shape
        L = self._L(R, T)
        with pytest.raises(ValueError):
            solve_mahalanobis_dro(rho, L, W, ceiling, epsilon=1.0,
                                  region_order=("A", "B"), carbon_budget=-5.0)
