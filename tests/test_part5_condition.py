"""Part 5 -- mean-dominance ratio computation tests."""
import numpy as np

from scripts.run_part5_condition import flatten_mean, mean_value_range


def test_flatten_mean_endpoints():
    rho = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    assert np.allclose(flatten_mean(rho, 1.0), rho)          # kappa=1 -> identity
    assert np.allclose(flatten_mean(rho, 0.0), rho.mean())   # kappa=0 -> constant
    # flattening preserves the grand mean
    assert np.isclose(flatten_mean(rho, 0.5).mean(), rho.mean())


def test_mean_value_range_known_case():
    """One region, T=4, cap=10, W=20 (two full cells). Cheapest two hours vs dirtiest
    two hours of carbon [1,2,3,4]: min = 10*(1+2)=30, max = 10*(4+3)=70, range=40."""
    rho = np.array([[1.0, 2.0, 3.0, 4.0]])
    M = mean_value_range(rho, cap=10.0, W=20.0)
    assert np.isclose(M, 40.0)


def test_mean_value_range_zero_when_flat():
    """A flat mean field offers no exploitable spread -> M = 0."""
    rho = np.full((2, 5), 3.0)
    assert np.isclose(mean_value_range(rho, cap=10.0, W=30.0), 0.0)


def test_flatter_mean_has_smaller_range():
    rng = np.random.default_rng(0)
    rho = 3.0 + rng.standard_normal((3, 8))
    full = mean_value_range(rho, 10.0, 40.0)
    half = mean_value_range(flatten_mean(rho, 0.5), 10.0, 40.0)
    assert half < full                       # flattening shrinks exploitable value
