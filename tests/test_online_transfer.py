"""Part 4 -- online rolling-horizon transfer controller tests."""
import numpy as np
import pytest

from src.models.online_transfer import (
    residual_pool, rolling_eval, seasonal_forecast,
)


def _panels(N=20, R=3, T=6, seed=0):
    rng = np.random.default_rng(seed)
    base = np.array([[1.0], [4.0], [4.0]])[:R]
    train = np.tile(base, (1, T))[None] + 0.3 * rng.standard_normal((N, R, T)) + 2.0
    test = np.tile(base, (1, T))[None] + 0.3 * rng.standard_normal((N, R, T)) + 2.0
    ceil = np.full((R, T), 50.0)
    wl = np.full(R, 0.8 * 50.0 * T)
    return np.clip(train, 0.1, None), np.clip(test, 0.1, None), ceil, wl


def test_seasonal_forecast_shape_and_value():
    train, _, _, _ = _panels()
    fc = seasonal_forecast(train)
    assert fc.shape == train.shape[1:]
    assert np.allclose(fc, train.mean(axis=0))


def test_residual_pool_is_zero_mean():
    train, _, _, _ = _panels()
    pool = residual_pool(train, seasonal_forecast(train))
    assert pool.shape == train.shape
    assert np.allclose(pool.mean(axis=0), 0.0, atol=1e-9)


def test_rolling_eval_runs_both_arms():
    train, test, ceil, wl = _panels()
    kw = dict(ceiling=ceil, workloads=wl, transfer_budget=2.0 * wl.sum(),
              n_scenarios=12, stride=2, seed=1)
    det = rolling_eval(train, test, robust=False, **kw)
    rob = rolling_eval(train, test, robust=True, **kw)
    assert det.shape == rob.shape
    assert len(det) == len(range(0, len(test), 2))
    assert np.isfinite(det).all() and np.isfinite(rob).all()
    assert (det > 0).all() and (rob > 0).all()


def test_committed_schedule_conserves_work():
    """Realised cost = <rho, y>; y must serve exactly the total work each day, so the
    cost is bounded below by cheapest placement and above by costliest."""
    train, test, ceil, wl = _panels()
    det = rolling_eval(train, test, robust=False, ceiling=ceil, workloads=wl,
                       transfer_budget=2.0 * wl.sum(), stride=5, seed=2)
    # cheapest feasible placement of total work W at the per-day minimum carbon
    W = wl.sum()
    for k, t in enumerate(range(0, len(test), 5)):
        lo = float(test[t].min()) * W
        hi = float(test[t].max()) * W
        assert lo - 1e-6 <= det[k] <= hi + 1e-6


def test_zero_transfer_budget_is_feasible():
    train, test, ceil, wl = _panels()
    out = rolling_eval(train, test, robust=False, ceiling=ceil, workloads=wl,
                       transfer_budget=0.0, stride=10, seed=3)
    assert np.isfinite(out).all() and (out > 0).all()
