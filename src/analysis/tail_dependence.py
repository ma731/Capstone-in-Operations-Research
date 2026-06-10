"""Tail-dependence diagnostics for carbon-intensity co-movement.

WHY THIS EXISTS
---------------
The Mahalanobis-Wasserstein DRO (Algorithm 2b) is driven by the COVARIANCE
matrix -- a second-moment, *linear* summary of dependence. CVaR, however, is a
TAIL risk metric. The sharp question the Phase 1 null raises is: is there spatial
structure in the *tails* (regions spiking dirty together, or going clean
together, more than their correlation implies) that a covariance-based ambiguity
set is structurally blind to?

That structure is *tail dependence*. For a loss quantity like carbon intensity:
  * UPPER tail dependence (chi_U): both regions DIRTY at the same time -- the
    co-movement that actually drives joint emission spikes (CVaR-relevant).
  * LOWER tail dependence (chi_L): both regions CLEAN at the same time -- when
    chi_L is high there is rarely a clean region to shift load to (bad for
    spatial load-shifting); when low, a clean alternative usually exists.

THE GAUSSIAN BENCHMARK (the whole point)
----------------------------------------
A Gaussian copula -- equivalently, anything a covariance / Mahalanobis-Wasserstein
ball can represent -- has ZERO asymptotic tail dependence for any correlation
rho < 1. So if the EMPIRICAL chi_U(q) sits materially ABOVE the Gaussian-copula
value implied by the same Pearson rho, that excess is genuine tail structure the
covariance-based DRO cannot capture -- the empirical motivation for the Phase 2
copula (vine) extension. If the empirical curve tracks the Gaussian benchmark,
the null is even more bulletproof: there is nothing in the tails to exploit
either.

Estimators
----------
chi_U(q) = P(U > q, V > q) / (1 - q),   U, V = empirical-CDF pseudo-observations.
  Independence -> 0 as q -> 1;  comonotone -> 1.  (Coles-Heffernan-Tawn chi.)
chi_L(p) = P(U < p, V < p) / p.
Gaussian benchmark uses the bivariate-normal survival at the matched rho.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def pseudo_observations(x: np.ndarray) -> np.ndarray:
    """Rank-based pseudo-observations in (0, 1): rank / (n + 1)."""
    x = np.asarray(x, dtype=float)
    return stats.rankdata(x, method="average") / (len(x) + 1.0)


def chi_upper_empirical(u: np.ndarray, v: np.ndarray, q: float) -> float:
    """Empirical upper tail-dependence coefficient at quantile q in (0, 1).

    P(U > q, V > q) / (1 - q). u, v are pseudo-observations.
    """
    u, v = np.asarray(u), np.asarray(v)
    joint = float(np.mean((u > q) & (v > q)))
    return joint / (1.0 - q)


def chi_lower_empirical(u: np.ndarray, v: np.ndarray, p: float) -> float:
    """Empirical lower tail-dependence coefficient at quantile p in (0, 1).

    P(U < p, V < p) / p. u, v are pseudo-observations.
    """
    u, v = np.asarray(u), np.asarray(v)
    joint = float(np.mean((u < p) & (v < p)))
    return joint / p


def chi_upper_gaussian(rho: float, q: float) -> float:
    """Upper tail-dependence coefficient at level q for a Gaussian copula.

    Bivariate-normal survival P(Z1 > z, Z2 > z) / (1 - q) with z = Phi^{-1}(q)
    and correlation rho. -> 0 as q -> 1 for any rho < 1 (asymptotic tail
    independence), which is exactly what a covariance-based DRO can represent.
    """
    rho = float(np.clip(rho, -0.999, 0.999))
    z = stats.norm.ppf(q)
    cov = [[1.0, rho], [rho, 1.0]]
    # P(Z1 > z, Z2 > z) = Phi_2(-z, -z; rho) by symmetry of the bivariate normal.
    surv = float(stats.multivariate_normal.cdf([-z, -z], mean=[0.0, 0.0], cov=cov))
    return surv / (1.0 - q)


def tail_dependence_table(
    wide: pd.DataFrame,
    q: float = 0.95,
    p: float | None = None,
) -> pd.DataFrame:
    """Pairwise tail-dependence summary for every column pair in `wide`.

    Returns one row per unordered pair with: Pearson rho, empirical chi_U(q),
    Gaussian-copula chi_U(q) at the matched rho, the excess (empirical minus
    Gaussian), and empirical chi_L(p) (p defaults to 1 - q).

    A positive `chi_U_excess` is dependence in the dirty tail that a
    covariance / Mahalanobis-Wasserstein ambiguity set cannot represent.
    """
    if p is None:
        p = 1.0 - q
    cols = list(wide.columns)
    pseudo = {c: pseudo_observations(wide[c].to_numpy()) for c in cols}
    rho = wide.corr()
    rows = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            a, b = cols[i], cols[j]
            r = float(rho.loc[a, b])
            emp_u = chi_upper_empirical(pseudo[a], pseudo[b], q)
            gau_u = chi_upper_gaussian(r, q)
            emp_l = chi_lower_empirical(pseudo[a], pseudo[b], p)
            rows.append({
                "pair": f"{a} | {b}",
                "pearson_rho": r,
                "chi_U_emp": emp_u,
                "chi_U_gauss": gau_u,
                "chi_U_excess": emp_u - gau_u,
                "chi_L_emp": emp_l,
            })
    return pd.DataFrame(rows)


def chi_upper_curve(
    wide: pd.DataFrame,
    a: str,
    b: str,
    q_grid: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (empirical, gaussian) chi_U arrays over q_grid for the pair (a, b)."""
    u = pseudo_observations(wide[a].to_numpy())
    v = pseudo_observations(wide[b].to_numpy())
    r = float(wide[[a, b]].corr().iloc[0, 1])
    emp = np.array([chi_upper_empirical(u, v, q) for q in q_grid])
    gau = np.array([chi_upper_gaussian(r, q) for q in q_grid])
    return emp, gau


def residualize_hour_of_day(wide: pd.DataFrame, tz: str) -> pd.DataFrame:
    """Remove the per-zone hour-of-day mean (local time), matching the
    correlation-heatmap residualization in scripts/plot_carbon_correlation.py.
    Returns a frame on the original (UTC) index.
    """
    loc = wide.tz_convert(tz)
    resid = loc.groupby(loc.index.hour).transform(lambda s: s - s.mean())
    return resid.tz_convert("UTC")
