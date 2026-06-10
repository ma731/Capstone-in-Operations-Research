"""Tests for src.analysis.tail_dependence."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analysis.tail_dependence import (
    chi_lower_empirical,
    chi_upper_empirical,
    chi_upper_gaussian,
    pseudo_observations,
    tail_dependence_table,
)


def test_pseudo_observations_in_unit_interval():
    x = np.array([5.0, 1.0, 3.0, 2.0, 4.0])
    u = pseudo_observations(x)
    assert np.all(u > 0) and np.all(u < 1)
    # monotone: ranks preserve order
    assert np.argmax(u) == np.argmax(x)
    assert np.argmin(u) == np.argmin(x)


def test_comonotone_has_full_upper_tail_dependence():
    rng = np.random.default_rng(0)
    x = rng.normal(size=5000)
    u = pseudo_observations(x)
    # identical -> joint exceedance == marginal exceedance -> chi_U(q) ~ 1
    assert chi_upper_empirical(u, u, 0.95) == pytest.approx(1.0, abs=1e-9)
    assert chi_lower_empirical(u, u, 0.05) == pytest.approx(1.0, abs=1e-9)


def test_independence_has_low_tail_dependence():
    rng = np.random.default_rng(1)
    u = pseudo_observations(rng.normal(size=20000))
    v = pseudo_observations(rng.normal(size=20000))
    # independence: P(U>q,V>q)/(1-q) ~ (1-q) -> small at q=0.95
    assert chi_upper_empirical(u, v, 0.95) < 0.15


def test_gaussian_benchmark_decays_toward_zero_in_the_tail():
    # For rho < 1 the Gaussian copula is asymptotically tail-independent:
    # chi_U(q) decreases as q -> 1.
    rho = 0.5
    near = chi_upper_gaussian(rho, 0.90)
    far = chi_upper_gaussian(rho, 0.999)
    assert far < near
    assert far >= 0.0


def test_gaussian_benchmark_monotone_in_rho():
    q = 0.95
    assert chi_upper_gaussian(0.2, q) < chi_upper_gaussian(0.8, q)


def test_table_columns_and_excess_definition():
    rng = np.random.default_rng(2)
    n = 4000
    z = rng.normal(size=n)
    df = pd.DataFrame({
        "A": z + 0.3 * rng.normal(size=n),
        "B": z + 0.3 * rng.normal(size=n),
        "C": rng.normal(size=n),
    })
    tbl = tail_dependence_table(df, q=0.95)
    assert set(tbl.columns) == {
        "pair", "pearson_rho", "chi_U_emp", "chi_U_gauss", "chi_U_excess", "chi_L_emp",
    }
    assert len(tbl) == 3  # 3 unordered pairs
    # excess is exactly empirical minus Gaussian
    np.testing.assert_allclose(
        tbl["chi_U_excess"].to_numpy(),
        (tbl["chi_U_emp"] - tbl["chi_U_gauss"]).to_numpy(),
        atol=1e-12,
    )
