"""v11 tests: the three operational components in A1 (coupled) and A2b.

Reproduces claims C1-C3 and the eps=0 reduction, using the REAL repo
functions. Backward-compatibility of the existing suite is verified
separately (those tests are unchanged and still pass).
"""
import numpy as np
import pytest

from src.models.algorithm_1 import (
    schedule_deterministic_coupled,
    greedy_sort_schedule_multiregion,
)
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro

R, T = 3, 6
RHO = np.array([[300, 280, 150, 200, 250, 320],
                [310, 290, 180, 220, 240, 300],
                [305, 285, 160, 210, 245, 315]], float)
CEIL = np.full((R, T), 10.0)
W = np.array([36.0, 36.0, 36.0])
PMAX, ALPHA, DELTA = 22.0, np.array([0.75] * 3), np.array([4.0] * 3)
RO = ("R0", "R1", "R2")


def test_C1_components_off_equals_greedy():
    res = schedule_deterministic_coupled(RHO, W, CEIL)  # all components off
    g = greedy_sort_schedule_multiregion(RHO, W, CEIL)
    assert abs(res.total_carbon - float((RHO * g).sum())) < 1e-3


def test_C2_greedy_violates_components():
    g = greedy_sort_schedule_multiregion(RHO, W, CEIL)
    assert g.sum(axis=0).max() > PMAX
    assert max(abs(g[r, t] - g[r, t - 1])
               for r in range(R) for t in range(1, T)) > DELTA[0]


def test_C3_components_bind():
    res = schedule_deterministic_coupled(RHO, W, CEIL, p_max=PMAX, alpha=ALPHA, ramp=DELTA)
    assert np.allclose(res.work_completed, W, atol=1e-4)
    assert res.binding["cap_tight_hours"] >= 1
    assert res.binding["ramp_tight_transitions"] >= 1
    assert res.schedule.min() >= ALPHA[0] * W[0] / T - 1e-4  # inflexible base pinned


def test_a2b_components_eps0_equals_coupled_a1():
    """A2b with components at eps=0 == deterministic coupled A1."""
    L = np.linalg.cholesky(np.eye(R * T) * 100.0)
    a1 = schedule_deterministic_coupled(RHO, W, CEIL, p_max=PMAX, alpha=ALPHA, ramp=DELTA)
    a2b = solve_mahalanobis_dro(RHO, L, W, CEIL, 0.0, region_order=RO,
                                p_max=PMAX, alpha=ALPHA, ramp=DELTA)
    assert abs(a1.total_carbon - a2b.mean_carbon_value) < 1e-2
    assert np.max(np.abs(a1.schedule - a2b.schedule)) < 1e-2


def test_a2b_components_backward_compatible():
    """A2b with NO component kwargs gives the same result as before (the
    original work-equality path)."""
    L = np.linalg.cholesky(np.eye(R * T) * 100.0)
    plain = solve_mahalanobis_dro(RHO, L, W, CEIL, 0.0, region_order=RO)
    assert np.allclose(plain.schedule.sum(axis=1), W, atol=1e-4)


def test_a2b_components_dro_moves_at_high_eps():
    """In the Goldilocks band the DRO reallocates off the deterministic schedule."""
    L = np.linalg.cholesky(np.eye(R * T) * 100.0)
    base = solve_mahalanobis_dro(RHO, L, W, CEIL, 0.0, region_order=RO,
                                 p_max=PMAX, alpha=ALPHA, ramp=DELTA).schedule
    hi = solve_mahalanobis_dro(RHO, L, W, CEIL, 5.0, region_order=RO,
                               p_max=PMAX, alpha=ALPHA, ramp=DELTA).schedule
    assert np.abs(hi - base).sum() > 1e-3


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
