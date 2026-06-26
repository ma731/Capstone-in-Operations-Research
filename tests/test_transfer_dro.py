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
    lam, budget = 1.0, 2.0 * wl.sum()
    c = recourse_cost(x, rho, ceil, transfer_budget=budget, lam=lam)
    # Flows conserve work (sum y = sum commitment = total work W), so the realized
    # cost is bounded below by placing all work in the cheapest cell, and above by
    # the dirtiest placement plus the worst-case migration penalty.
    W = wl.sum()
    assert np.isfinite(c)
    assert rho.min() * W <= c <= rho.max() * W + lam * budget


def test_invalid_risk_raises():
    rho, L, wl, ceil = _setup()
    scen = rho[None]
    with pytest.raises(ValueError):
        two_stage_commit(scen, wl, ceil, transfer_budget=1.0, risk="bogus")


def test_transfer_value_headline_matches_snapshot():
    """Pin the RQ1 headline (4.0-9.9% CVaR_0.95 reduction over the Phi=0 baseline)
    to its archived, license-safe snapshot so a code change cannot silently drift
    the reported number. Source of truth:
    docs/results_snapshots/part3_transfer_value_2026-06-15.csv, produced by
    scripts/run_part3_transfer_value.py."""
    import csv
    from pathlib import Path

    snap = (Path(__file__).resolve().parents[1] / "docs" / "results_snapshots"
            / "part3_transfer_value_2026-06-15.csv")
    rows = {r["grid"]: r for r in csv.DictReader(snap.open())}

    expected_1dp = {"us_west": 4.0, "taskc": 9.9, "us_hetero": 9.0}
    for grid, headline in expected_1dp.items():
        r = rows[grid]
        red = float(r["reduction_pct"])
        assert round(red, 1) == headline, f"{grid}: reduction_pct {red} != {headline}"
        # Internal consistency: reduction_pct = (no_transfer - transfer)/no_transfer.
        c0, cT = float(r["cvar_no_transfer"]), float(r["cvar_transfer"])
        assert cT < c0, f"{grid}: transfer did not reduce CVaR"
        assert abs((c0 - cT) / c0 * 100.0 - red) < 1e-6

    reds = [float(rows[g]["reduction_pct"]) for g in expected_1dp]
    assert abs(min(reds) - 4.0) < 0.05   # published lower bound
    assert abs(max(reds) - 9.9) < 0.05   # published upper bound
