"""Phase 2: copula scenarios + CVaR-SAA scheduler tests."""
import numpy as np
import pytest

from src.models.copula_scenarios import (
    KINDS, fit_copula, generate_scenarios, sample_uniforms,
)
from src.models.cvar_saa import solve_cvar_saa
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro


def _chi_lower(u, v, p):
    return np.mean((u < p) & (v < p)) / p


def _chi_upper(u, v, q):
    return np.mean((u > q) & (v > q)) / (1 - q)


def _correlated_panel(N=600, R=3, T=24, rho=0.7, seed=0):
    """Daily panels whose daily-mean intensity is positively correlated."""
    rng = np.random.default_rng(seed)
    L = np.linalg.cholesky(rho * np.ones((R, R)) + (1 - rho) * np.eye(R))
    daily = np.exp(3.0 + 0.4 * (rng.standard_normal((N, R)) @ L.T))   # (N,R)
    shape = np.abs(rng.standard_normal((N, R, T))) * 0.1 + 1.0
    return daily[:, :, None] * shape


def test_kinds_fit_and_sample():
    panel = _correlated_panel()
    for kind in KINDS:
        m = fit_copula(kind, panel)
        scen = generate_scenarios(m, 200, seed=1)
        assert scen.shape == (200, panel.shape[1], panel.shape[2])
        assert np.isfinite(scen).all()


def test_clayton_is_lower_tail_asymmetric():
    """Clayton must show chi_L > chi_U; Gaussian must be roughly symmetric."""
    panel = _correlated_panel(rho=0.7)
    cl = fit_copula("clayton", panel)
    assert cl.clayton_theta > 0.3                     # real coupling on tau~0.5
    u = sample_uniforms(cl, 40000, np.random.default_rng(2))
    chiL = _chi_lower(u[:, 0], u[:, 1], 0.05)
    chiU = _chi_upper(u[:, 0], u[:, 1], 0.95)
    assert chiL > chiU + 0.1                          # clearly lower-tail dependent

    ga = fit_copula("gaussian", panel)
    ug = sample_uniforms(ga, 40000, np.random.default_rng(2))
    gL = _chi_lower(ug[:, 0], ug[:, 1], 0.05)
    gU = _chi_upper(ug[:, 0], ug[:, 1], 0.95)
    assert abs(gL - gU) < 0.08                        # symmetric


def test_comonotone_is_perfectly_rank_coupled():
    """Comonotone (upper Frechet) must give rank correlation ~1 and chi_L=chi_U=1."""
    panel = _correlated_panel(rho=0.5)
    cm = fit_copula("comonotone", panel)
    u = sample_uniforms(cm, 20000, np.random.default_rng(5))
    assert np.corrcoef(u[:, 0], u[:, 1])[0, 1] > 0.999
    assert _chi_lower(u[:, 0], u[:, 1], 0.05) > 0.95
    assert _chi_upper(u[:, 0], u[:, 1], 0.95) > 0.95


def test_independence_destroys_cross_dependence():
    panel = _correlated_panel(rho=0.8)
    ind = fit_copula("independence", panel)
    u = sample_uniforms(ind, 40000, np.random.default_rng(3))
    # near-zero rank correlation between regions
    assert abs(np.corrcoef(u[:, 0], u[:, 1])[0, 1]) < 0.05


def test_cvar_saa_respects_feasible_set():
    panel = _correlated_panel()
    m = fit_copula("clayton", panel)
    scen = generate_scenarios(m, 250, seed=4)
    R, T = panel.shape[1], panel.shape[2]
    workloads = np.full(R, 0.80 * 50.0 * T)
    ceiling = np.full((R, T), 50.0)
    res = solve_cvar_saa(scen, workloads, ceiling, beta=0.95,
                         alpha=np.full(R, 0.5), ramp=np.full(R, 15.0),
                         deferral_windows=[(0, 7, 0.20)])
    assert res.solver_status in ("optimal", "optimal_inaccurate")
    assert (res.schedule <= 50.0 + 1e-6).all()
    assert np.allclose(res.schedule.sum(axis=1), workloads, atol=1e-3)


def test_feasible_set_matches_phase1():
    """eps=0 Mahalanobis DRO and a single-scenario CVaR-SAA minimize the same
    linear objective over the same X, so the schedules must coincide."""
    panel = _correlated_panel(seed=7)
    R, T = panel.shape[1], panel.shape[2]
    rho_bar = panel.mean(axis=0)                       # (R,T)
    workloads = np.full(R, 0.80 * 50.0 * T)
    ceiling = np.full((R, T), 50.0)
    L = np.zeros((R * T, R * T))                       # eps=0 -> penalty irrelevant

    kw = dict(alpha=np.full(R, 0.5), ramp=np.full(R, 15.0),
              deferral_windows=[(0, 7, 0.20)])
    x_dro = solve_mahalanobis_dro(rho_bar=rho_bar, L=L, workloads=workloads,
                                  ceiling=ceiling, epsilon=0.0,
                                  region_order=tuple(f"z{r}" for r in range(R)),
                                  **kw).schedule
    # single scenario == rho_bar  =>  CVaR_beta = <rho_bar, x>
    x_cvar = solve_cvar_saa(rho_bar[None, :, :], workloads, ceiling,
                            beta=0.95, **kw).schedule
    # same minimized emissions value (schedules may differ on degenerate faces)
    assert abs(float((rho_bar * x_dro).sum()) - float((rho_bar * x_cvar).sum())) < 1e-3
