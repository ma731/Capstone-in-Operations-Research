"""Task A tests: the two NEW feasible-set constraints, mirroring the v11 suite.

Covers:
  * (4) drop-cap verification: p_max=None fully bypasses the aggregate cap.
  * (5) windowed-demand / deferral-deadline constraint (3a).
  * (6) temperature-coupled thermal / PUE constraint (3b).
  * eps=0 equivalence between coupled A1 and A2b with the new constraints.
  * backward-compatibility: new kwargs default off => identical to before.

Uses the REAL repo functions. The DRO method (A2b) is unchanged; only the
feasible set X changes, so every test pins a feasible-set behavior.
"""
import numpy as np
import pytest

from src.data.temperature import pue_from_temperature
from src.models.algorithm_1 import (
    greedy_sort_schedule_multiregion,
    schedule_deterministic_coupled,
)
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro

R, T = 3, 6
RHO = np.array([[300, 280, 150, 200, 250, 320],
                [310, 290, 180, 220, 240, 300],
                [305, 285, 160, 210, 245, 315]], float)
CEIL = np.full((R, T), 10.0)
W = np.array([36.0, 36.0, 36.0])
ALPHA = np.array([0.50] * 3)
RAMP = np.array([4.0] * 3)
RO = ("R0", "R1", "R2")
L_ID = np.linalg.cholesky(np.eye(R * T) * 100.0)

# A temperature field that is HOT (forces PUE up) in the cheap-carbon hours
# (t=2,3 are the lowest-rho hours) so the thermal cap actually bites where the
# scheduler most wants to put load.
TEMP = np.full((R, T), 18.0)
TEMP[:, 2:4] = 38.0   # 38 C in the two cheapest hours -> high PUE there


# ----------------------------------------------------------------------
# (4) Drop-cap verification
# ----------------------------------------------------------------------

def test_drop_cap_pmax_none_bypasses_aggregate_cap():
    """With p_max=None the per-hour aggregate sum is unconstrained: the optimum
    is free to pile the whole fleet into the single cheapest hour."""
    res = schedule_deterministic_coupled(RHO, W, CEIL)  # all off, no cap
    agg = res.schedule.sum(axis=0)
    # cheapest common hour is t=2; greedy piles there. Aggregate there far
    # exceeds any nominal cap (e.g. the old 22 in the v11 toy).
    assert agg.max() > 22.0
    assert "cap_tight_hours" not in res.binding  # cap diagnostics absent when off


def test_drop_cap_a2b_pmax_none_matches_greedy_when_all_off():
    """Sanity: components-off A2b at eps=0 equals the greedy sort (no cap)."""
    a2b = solve_mahalanobis_dro(RHO, L_ID, W, CEIL, 0.0, region_order=RO)
    g = greedy_sort_schedule_multiregion(RHO, W, CEIL)
    assert abs(a2b.mean_carbon_value - float((RHO * g).sum())) < 1e-2


# ----------------------------------------------------------------------
# (5) Windowed-demand / deferral-deadline constraint (3a)
# ----------------------------------------------------------------------

def test_deferral_requires_flex_split():
    """deferral_windows without alpha must raise (flex work undefined)."""
    with pytest.raises(ValueError, match="flex"):
        schedule_deterministic_coupled(
            RHO, W, CEIL, deferral_windows=[(0, 2, 0.5)]
        )


def test_deferral_forces_flex_into_window():
    """A binding window forces a gamma-fraction of flexible work into [t1,t2]."""
    # Window over the EXPENSIVE early hours (t=0,1) where the scheduler would
    # otherwise put nothing flexible. gamma=0.6 of flexible work must land there.
    win = [(0, 1, 0.6)]
    res = schedule_deterministic_coupled(
        RHO, W, CEIL, alpha=ALPHA, deferral_windows=win
    )
    # Recover the flexible part = x - inflexible base.
    inflex = res.binding["inflex_base"]
    x_flex = res.schedule - inflex
    flex_total = (1.0 - ALPHA[0]) * W[0]
    served_in_window = x_flex[:, 0:2].sum(axis=1)
    assert np.all(served_in_window >= 0.6 * flex_total - 1e-4)
    assert np.allclose(res.work_completed, W, atol=1e-4)
    assert "deferral_margins" in res.binding


def test_deferral_changes_objective_vs_unconstrained():
    """Forcing flex into an expensive window must (weakly) raise emissions, and
    here strictly raise them since the window is off the cheap hours."""
    base = schedule_deterministic_coupled(RHO, W, CEIL, alpha=ALPHA)
    win = schedule_deterministic_coupled(
        RHO, W, CEIL, alpha=ALPHA, deferral_windows=[(0, 1, 0.6)]
    )
    assert win.total_carbon > base.total_carbon + 1.0


def test_deferral_a2b_eps0_equals_coupled_a1():
    win = [(0, 1, 0.4)]
    a1 = schedule_deterministic_coupled(
        RHO, W, CEIL, alpha=ALPHA, ramp=RAMP, deferral_windows=win
    )
    a2b = solve_mahalanobis_dro(
        RHO, L_ID, W, CEIL, 0.0, region_order=RO,
        alpha=ALPHA, ramp=RAMP, deferral_windows=win,
    )
    assert abs(a1.total_carbon - a2b.mean_carbon_value) < 1e-2
    assert np.max(np.abs(a1.schedule - a2b.schedule)) < 1e-2


# ----------------------------------------------------------------------
# (6) Temperature-coupled thermal / PUE constraint (3b)
# ----------------------------------------------------------------------

def test_pue_helper_hockey_stick():
    """PUE(T)=pue0 below set-point; rises linearly above it."""
    pue = pue_from_temperature(np.array([[10.0, 20.0, 30.0]]),
                               pue0=1.1, kappa=0.02, t_set=20.0)
    assert np.allclose(pue, [[1.1, 1.1, 1.1 + 0.02 * 10]])


def test_thermal_requires_bar_P():
    with pytest.raises(ValueError, match="bar_P"):
        schedule_deterministic_coupled(RHO, W, CEIL, temperature=TEMP)


def test_thermal_tightens_ceiling_in_hot_hours():
    """The effective-power cap PUE*x <= bar_P caps x below the nominal ceiling
    in the hot hours, so the scheduler cannot fully exploit the cheap hours."""
    bar_P = 10.5  # just above ceiling*pue0=10*1.1=11? choose to bite in hot hours
    # In hot hours PUE = 1.1 + 0.015*(38-20) = 1.1 + 0.27 = 1.37 -> x <= 10.5/1.37 = 7.66
    res = schedule_deterministic_coupled(
        RHO, W, CEIL, temperature=TEMP, bar_P=bar_P,
        pue0=1.10, kappa=0.015, t_set=20.0,
    )
    pue = pue_from_temperature(TEMP, 1.10, 0.015, 20.0)
    eff = pue * res.schedule
    assert np.all(eff <= bar_P + 1e-4)              # cap respected everywhere
    assert res.schedule[:, 2:4].max() < 10.0 - 1e-3  # hot cheap hours throttled
    assert res.binding["thermal_tight_cells"] >= 1


def test_thermal_a2b_eps0_equals_coupled_a1():
    bar_P = 12.0
    a1 = schedule_deterministic_coupled(
        RHO, W, CEIL, alpha=ALPHA, ramp=RAMP, temperature=TEMP, bar_P=bar_P,
    )
    a2b = solve_mahalanobis_dro(
        RHO, L_ID, W, CEIL, 0.0, region_order=RO,
        alpha=ALPHA, ramp=RAMP, temperature=TEMP, bar_P=bar_P,
    )
    assert abs(a1.total_carbon - a2b.mean_carbon_value) < 1e-2
    assert np.max(np.abs(a1.schedule - a2b.schedule)) < 1e-2


def test_thermal_wrong_shape_raises():
    with pytest.raises(ValueError, match="temperature"):
        solve_mahalanobis_dro(
            RHO, L_ID, W, CEIL, 0.0, region_order=RO,
            temperature=np.zeros((R, T + 1)), bar_P=12.0,
        )


# ----------------------------------------------------------------------
# Backward compatibility: new kwargs default off => identical to before
# ----------------------------------------------------------------------

def test_a2b_new_kwargs_default_off_is_backward_compatible():
    plain = solve_mahalanobis_dro(RHO, L_ID, W, CEIL, 0.0, region_order=RO)
    # explicit None for every new kwarg must give the identical schedule
    explicit = solve_mahalanobis_dro(
        RHO, L_ID, W, CEIL, 0.0, region_order=RO,
        deferral_windows=None, temperature=None, bar_P=None,
    )
    assert np.allclose(plain.schedule, explicit.schedule, atol=1e-6)
    assert np.allclose(plain.schedule.sum(axis=1), W, atol=1e-4)


def test_all_new_constraints_together_feasible_and_bind():
    """Lean+thermal+deadline together: feasible, and each new constraint binds."""
    win = [(0, 2, 0.3)]
    res = schedule_deterministic_coupled(
        RHO, W, CEIL, alpha=ALPHA, ramp=RAMP,
        deferral_windows=win, temperature=TEMP, bar_P=11.0,
    )
    assert np.allclose(res.work_completed, W, atol=1e-4)
    assert res.binding["thermal_tight_cells"] >= 1
    assert "deferral_margins" in res.binding


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
