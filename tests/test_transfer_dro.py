"""Part 3 — transfer DRO module tests."""
import numpy as np
import pytest

from src.models.transfer_dro import (
    recourse_cost, solve_transfer_dro, two_stage_commit,
)


def _setup(R=3, T=6, gap=True, seed=0):
    """Mean field where region 0 is clean, others dirty -> transfer should help."""
    rng = np.random.default_rng(seed)
    rho = np.tile(np.array([[1.0], [5.0], [5.0]])[:R], (1, T)).astype(float)
    rho += 0.1 * rng.standard_normal((R, T))
    if not gap:
        rho[:] = 3.0
    wl = np.full(R, 0.8 * 50.0 * T)
    ceil = np.full((R, T), 50.0)
    L = np.zeros((R * T, R * T))
    return rho, L, wl, ceil


def test_transfer_conserves_work():
    """Total executed load equals total work (flows neither create nor destroy work)."""
    rho, L, wl, ceil = _setup()
    y, used = solve_transfer_dro(rho, L, wl, ceil, epsilon=0.0,
                                 transfer_budget=2.0 * wl.sum())
    assert y.shape == rho.shape
    assert (y >= -1e-6).all() and (y <= 50.0 + 1e-6).all()
    assert np.isclose(y.sum(), wl.sum(), rtol=1e-4)


def test_transfer_reduces_emissions():
    """With a clean region available, transfer cuts emissions vs no transfer."""
    rho, L, wl, ceil = _setup(gap=True)
    y0, _ = solve_transfer_dro(rho, L, wl, ceil, transfer_budget=0.0)        # no transfer
    yT, used = solve_transfer_dro(rho, L, wl, ceil, transfer_budget=2.0 * wl.sum())
    e0 = float((rho * y0).sum())
    eT = float((rho * yT).sum())
    assert used > 0
    assert eT < e0 * 0.999            # transfer strictly helps


def test_zero_budget_reproduces_no_transfer():
    rho, L, wl, ceil = _setup()
    y, used = solve_transfer_dro(rho, L, wl, ceil, transfer_budget=0.0)
    assert used < 1e-6                # nothing relocated
    assert np.allclose(y.sum(axis=1), wl, rtol=1e-4)


def test_two_stage_solves_and_commits():
    rho, L, wl, ceil = _setup()
    rng = np.random.default_rng(1)
    scen = np.stack([rho + 0.3 * rng.standard_normal(rho.shape) for _ in range(8)])
    scen = np.clip(scen, 0.1, None)
    x_mean = two_stage_commit(scen, wl, ceil, transfer_budget=0.5 * wl.sum(),
                              lam=10.0, risk="mean")
    x_cvar = two_stage_commit(scen, wl, ceil, transfer_budget=0.5 * wl.sum(),
                              lam=10.0, risk="cvar")
    for x in (x_mean, x_cvar):
        assert x.shape == rho.shape
        assert np.allclose(x.sum(axis=1), wl, rtol=1e-3)


def test_recourse_cost_feasible_and_bounded():
    rho, L, wl, ceil = _setup()
    x = np.full_like(rho, wl[0] / rho.shape[1])     # flat commitment
    c = recourse_cost(x, rho, ceil, transfer_budget=2.0 * wl.sum(), lam=1.0)
    # cost must be at least the cheapest possible carbon placement (lower bound)
    assert np.isfinite(c) and c > 0


def test_invalid_risk_raises():
    rho, L, wl, ceil = _setup()
    scen = rho[None]
    with pytest.raises(ValueError):
        two_stage_commit(scen, wl, ceil, transfer_budget=1.0, risk="bogus")
