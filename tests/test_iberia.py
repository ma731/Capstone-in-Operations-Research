"""Task B tests: R=3 (ES-PT-FR) parameterization of the locked machinery.

The constraint LOGIC is already covered by tests/test_constraints_taskA.py
(which itself runs R=3). These tests pin the Task B-specific surface: the
Iberian region constant, the European clock, and that the full constraint stack
solves end-to-end with R=3 and region_order=REGION_ORDER_IBERIA, D=R*T=72.
"""
import numpy as np

from src.data.temperature import STATION_COORDS
from src.models.algorithm_1 import schedule_deterministic_coupled
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro
from src.models.covariance import (
    DEFAULT_TZ_IBERIA,
    REGION_ORDER,
    REGION_ORDER_IBERIA,
    block_diagonal_by_region,
)

R, T = 3, 24
RO = REGION_ORDER_IBERIA
RHO = np.tile(np.linspace(200, 100, T), (R, 1)) + np.array([[0], [5], [-5]])
CEIL = np.full((R, T), 50.0)
W = np.full(R, 0.6 * 50.0 * T)
ALPHA = np.array([0.5, 0.5, 0.5])
RAMP = np.full(R, 15.0)
TEMP = np.full((R, T), 12.0)
TEMP[:, 12:16] = 30.0           # hot midday -> thermal can bite
DEADLINE = [(0, 7, 0.20)]
L_ID = np.linalg.cholesky(np.eye(R * T) * 100.0)


def test_iberia_region_constant_is_three_and_distinct():
    assert REGION_ORDER_IBERIA == ("ES", "PT", "FR")
    assert len(REGION_ORDER_IBERIA) == 3
    assert set(REGION_ORDER_IBERIA).isdisjoint(set(REGION_ORDER))  # US untouched
    assert DEFAULT_TZ_IBERIA == "Europe/Madrid"
    for z in REGION_ORDER_IBERIA:
        assert z in STATION_COORDS                      # temp coords present


def test_block_diagonal_R3_dim72():
    """Shuffle on a 72x72 covariance zeros cross-region blocks, keeps within."""
    rng = np.random.default_rng(0)
    A = rng.normal(size=(R * T, R * T))
    Sigma = A @ A.T
    shuf = block_diagonal_by_region(Sigma, R=R, T=T)
    assert shuf.shape == (72, 72)
    # within-region block preserved, cross-region zeroed
    assert np.allclose(shuf[0:T, 0:T], Sigma[0:T, 0:T])
    assert np.allclose(shuf[0:T, T:2 * T], 0.0)


def test_iberia_full_stack_solves_R3():
    """All locked constraints (split+ramp+deadline+thermal, no cap) solve with
    R=3 and the Iberian region order; A1(eps=0) == A2b(eps=0)."""
    a1 = schedule_deterministic_coupled(
        RHO, W, CEIL, p_max=None, alpha=ALPHA, ramp=RAMP,
        deferral_windows=DEADLINE, temperature=TEMP, bar_P=57.0,
        pue0=1.10, kappa=0.015, t_set=14.0,
    )
    a2b = solve_mahalanobis_dro(
        RHO, L_ID, W, CEIL, 0.0, region_order=RO,
        p_max=None, alpha=ALPHA, ramp=RAMP,
        deferral_windows=DEADLINE, temperature=TEMP, bar_P=57.0,
        pue0=1.10, kappa=0.015, t_set=14.0,
    )
    assert a2b.schedule.shape == (3, 24)
    assert tuple(a2b.region_order) == RO
    assert np.allclose(a1.work_completed, W, atol=1e-4)
    assert abs(a1.total_carbon - a2b.mean_carbon_value) < 1e-1


def test_iberia_dro_moves_with_real_covariance_R3():
    """With a non-trivial joint L the DRO reallocates as epsilon grows (R=3)."""
    rng = np.random.default_rng(1)
    A = rng.normal(size=(R * T, R * T))
    L = np.linalg.cholesky(A @ A.T + np.eye(R * T))
    kw = dict(p_max=None, alpha=ALPHA, ramp=RAMP, deferral_windows=DEADLINE,
              temperature=TEMP, bar_P=57.0, pue0=1.10, kappa=0.015, t_set=14.0)
    x0 = solve_mahalanobis_dro(RHO, L, W, CEIL, 0.0, region_order=RO, **kw).schedule
    xhi = solve_mahalanobis_dro(RHO, L, W, CEIL, 100.0, region_order=RO, **kw).schedule
    assert np.abs(xhi - x0).sum() > 1e-3


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
