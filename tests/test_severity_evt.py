"""Tests for src.analysis.severity_evt (roadmap D3: EVT severity calibration)."""
from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import genpareto

from src.analysis.severity_evt import (
    bootstrap_return_period,
    daily_joint_severity,
    daily_zone_severity,
    decluster_exceedances,
    exceedance_probability,
    fit_gpd_tail,
    return_level,
    return_period_years,
)


# ---------- Severity series ----------

def test_joint_severity_mean_is_one():
    rng = np.random.default_rng(0)
    panel = rng.uniform(50, 400, size=(200, 4, 24))
    sev = daily_joint_severity(panel)
    assert sev.shape == (200,)
    assert sev.mean() == pytest.approx(1.0)


def test_joint_severity_detects_double_day():
    panel = np.full((100, 3, 24), 100.0)
    panel[7] *= 2.0  # one day exactly doubles
    sev = daily_joint_severity(panel)
    # grand mean = (99*100 + 200)/100 = 101
    assert sev[7] == pytest.approx(200.0 / 101.0)
    assert np.argmax(sev) == 7


def test_zone_severity_isolates_region():
    panel = np.full((50, 2, 24), 100.0)
    panel[3, 1, :] = 300.0  # spike only in region 1
    sev0 = daily_zone_severity(panel, 0)
    sev1 = daily_zone_severity(panel, 1)
    assert sev0.max() == pytest.approx(1.0)
    assert np.argmax(sev1) == 3


def test_severity_rejects_bad_input():
    with pytest.raises(ValueError):
        daily_joint_severity(np.zeros((5, 4)))
    with pytest.raises(ValueError):
        daily_zone_severity(np.zeros((5, 2, 24)) + 1.0, region_index=2)


# ---------- Declustering ----------

def test_decluster_merges_consecutive_runs():
    sev = np.array([0.9, 1.5, 1.7, 1.6, 0.8, 1.2, 0.9, 2.0])
    peaks = decluster_exceedances(sev, threshold=1.0)
    # runs above 1.0: [1.5,1.7,1.6] -> 1.7, [1.2] -> 1.2, [2.0] -> 2.0
    assert peaks.tolist() == [1.7, 1.2, 2.0]


def test_decluster_empty_when_no_exceedance():
    assert decluster_exceedances(np.ones(10) * 0.5, 1.0).size == 0


# ---------- GPD fit ----------

def test_fit_recovers_known_shape():
    rng = np.random.default_rng(42)
    # Build a series whose top 10% excesses are exactly GPD(xi=0.2, sigma=0.1).
    body = rng.uniform(0.5, 1.0, size=9000)
    tail = 1.0 + genpareto.rvs(0.2, loc=0, scale=0.1, size=1000, random_state=rng)
    sev = np.concatenate([body, tail])
    rng.shuffle(sev)  # break runs so declustering keeps most exceedances
    fit = fit_gpd_tail(sev, threshold_q=90.0)
    assert fit.shape == pytest.approx(0.2, abs=0.1)
    assert fit.scale == pytest.approx(0.1, abs=0.05)
    assert fit.n_total == 10000


def test_fit_raises_on_too_few_exceedances():
    with pytest.raises(ValueError):
        fit_gpd_tail(np.linspace(0.9, 1.1, 50), threshold_q=90.0)


# ---------- Return periods and levels ----------

def _toy_fit():
    rng = np.random.default_rng(7)
    body = rng.uniform(0.8, 1.05, size=4000)
    tail = 1.05 + genpareto.rvs(-0.1, loc=0, scale=0.08, size=400,
                                random_state=rng)
    sev = np.concatenate([body, tail])
    rng.shuffle(sev)
    return sev, fit_gpd_tail(sev, threshold_q=90.0)


def test_return_period_monotone_in_M():
    _, fit = _toy_fit()
    ms = np.linspace(fit.threshold + 0.01, fit.threshold + 0.3, 8)
    rps = [return_period_years(m, fit) for m in ms]
    assert all(a <= b for a, b in zip(rps, rps[1:]))


def test_return_period_infinite_beyond_bounded_endpoint():
    _, fit = _toy_fit()
    assert fit.shape < 0  # constructed bounded tail
    assert np.isfinite(fit.upper_endpoint)
    assert return_period_years(fit.upper_endpoint + 1.0, fit) == float("inf")


def test_return_level_inverts_return_period():
    _, fit = _toy_fit()
    for T in [1.0, 5.0, 10.0]:
        x = return_level(T, fit)
        assert return_period_years(x, fit) == pytest.approx(T, rel=1e-6)


def test_return_period_rejects_M_below_threshold():
    _, fit = _toy_fit()
    with pytest.raises(ValueError):
        exceedance_probability(fit.threshold - 0.1, fit)


def test_return_level_rejects_too_common_T():
    _, fit = _toy_fit()
    # An event as common as the threshold itself has no GPD return level.
    with pytest.raises(ValueError):
        return_level(1.0 / (fit.zeta * 365.25), fit)


# ---------- Bootstrap ----------

def test_bootstrap_brackets_point_estimate():
    sev, fit = _toy_fit()
    M = fit.threshold + 0.05
    rng = np.random.default_rng(123)
    point, lo, hi = bootstrap_return_period(
        sev, M, rng, threshold_q=90.0, n_boot=50)
    assert lo <= point <= hi
    assert point == pytest.approx(return_period_years(M, fit), rel=1e-6)


def test_bootstrap_requires_explicit_rng():
    sev, _ = _toy_fit()
    with pytest.raises(TypeError):
        bootstrap_return_period(sev, 1.1)  # rng is positional-required
