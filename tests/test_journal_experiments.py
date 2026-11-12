"""Unit tests for the journal-submission experiment scripts (July 2026):
run_external_baselines and run_transfer_penalty_sweep.

All tests run on synthetic panels -- no licensed data, no network. They verify
the POLICY LOGIC (feasibility, correct ordering, break-even interpolation), not
the empirical results, which require the Electricity Maps data.
"""
import numpy as np
import pytest

from scripts.run_external_baselines import (
    carbon_agnostic,
    greedy_time_shift,
    threshold_policy,
    _water_fill_uniform,
    evaluate,
)
from scripts.run_transfer_penalty_sweep import break_even, penalty_curve

R, T = 3, 24
RNG = np.random.default_rng(20260712)


def _fixture():
    ceiling = np.full((R, T), 50.0)
    workloads = np.full(R, 0.8 * 50.0 * T)
    rho_bar = 100.0 + 60.0 * RNG.random((R, T))
    # synthetic test panel: mean field plus noise, 90 "days"
    panel = rho_bar[None] + 10.0 * RNG.standard_normal((90, R, T))
    return rho_bar, workloads, ceiling, panel


def _assert_feasible(x, workloads, ceiling):
    assert np.all(x >= -1e-9)
    assert np.all(x <= ceiling + 1e-9)
    np.testing.assert_allclose(x.sum(axis=1), workloads, rtol=0, atol=1e-6)


def test_all_policies_feasible():
    rho, wl, ceil, _ = _fixture()
    for x in (carbon_agnostic(wl, ceil),
              greedy_time_shift(rho, wl, ceil),
              threshold_policy(rho, wl, ceil)):
        _assert_feasible(x, wl, ceil)


def test_greedy_beats_agnostic_on_mean_field():
    """On the training mean field itself, packing clean hours must not be worse
    than ignoring carbon entirely."""
    rho, wl, ceil, _ = _fixture()
    cost = lambda x: float((x * rho).sum())
    assert cost(greedy_time_shift(rho, wl, ceil)) <= cost(carbon_agnostic(wl, ceil)) + 1e-6


def test_threshold_relaxes_when_clean_hours_insufficient():
    """q so small that the clean set cannot carry the load: the policy must
    relax (admit more hours) rather than fail."""
    rho, wl, ceil, _ = _fixture()
    x = threshold_policy(rho, wl, ceil, q=0.05)
    _assert_feasible(x, wl, ceil)


def test_water_fill_respects_caps_and_raises_on_infeasible():
    cap = np.array([10.0, 5.0, 0.0, 20.0])
    x = _water_fill_uniform(30.0, cap)
    assert np.all(x <= cap + 1e-9) and abs(x.sum() - 30.0) < 1e-6
    with pytest.raises(ValueError):
        _water_fill_uniform(100.0, cap)


def test_evaluate_returns_cvar_at_least_mean():
    rho, wl, ceil, panel = _fixture()
    cv, mean = evaluate(carbon_agnostic(wl, ceil), panel)
    assert cv >= mean  # upper-tail CVaR of any distribution >= its mean


def test_break_even_interpolates():
    rows = [dict(lam_frac=0.0, cvar_reduction_pct=8.0),
            dict(lam_frac=0.5, cvar_reduction_pct=4.0),
            dict(lam_frac=1.0, cvar_reduction_pct=0.0)]
    be = break_even(rows, tol=0.05)
    assert 0.99 <= be <= 1.0
    assert break_even([dict(lam_frac=0.0, cvar_reduction_pct=5.0)]) is None


@pytest.mark.slow
def test_penalty_curve_monotone_transfer_usage_on_toy():
    """Higher migration cost must never increase relocated work (solver-backed,
    tiny toy so it stays fast; marked slow because it invokes cvxpy)."""
    rho, wl, ceil, panel = _fixture()
    rows = penalty_curve(rho, wl, ceil, panel, phi=0.2 * float(wl.sum()),
                         lam_fracs=[0.0, 0.5, 2.0])
    used = [r["transfer_used"] for r in rows]
    assert used[0] + 1e-6 >= used[1] >= used[2] - 1e-6
