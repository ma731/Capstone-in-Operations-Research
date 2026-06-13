"""Copula-based scenario generation for Phase 2.

Phase 1 showed that the residual cross-region dependence of carbon intensity is
*non-elliptical* -- lower-tail dependent (regions go clean together, chi_L large)
but upper-tail independent (chi_U ~ 0) -- so a covariance ball (which forces
chi_L = chi_U) cannot represent it. Phase 2 asks whether a copula that *can*
represent it recovers any scheduling value.

We use **copula-coupled empirical resampling**, the direct generalization of the
Phase 1 shuffled-marginals test. Each region keeps its empirical pool of whole
daily carbon profiles (so every region's marginal distribution and intraday
autocorrelation are preserved exactly, with no parametric marginal model); the
copula governs only *which* day each region draws on a given scenario -- i.e. the
cross-region dependence. Three nested dependence models:

* ``independence`` -- each region draws an independent day (no cross-dependence);
  the Phase 1 "shuffled" arm.
* ``gaussian``     -- regions coupled by a Gaussian copula at the empirical
  rank-correlation (elliptical: what a covariance ball can see).
* ``clayton``      -- regions coupled by an exchangeable Clayton copula, which has
  lower-tail dependence lambda_L = 2^(-1/theta) and zero upper-tail dependence --
  matched to the Phase 1 finding's chi_L. The object the covariance ball cannot
  represent.

A scenario is built by drawing a copula sample u in [0,1]^R, then for each region
mapping u_r through the empirical quantile of that region's *daily summary*
(daily-mean intensity; low = clean) to select a training day, and taking that
day's full (T,) profile. Clayton's lower-tail coupling therefore makes regions
select clean days together, exactly the dependence structure under test.

All samplers are numpy-only (Marshall--Olkin frailty for Clayton), so there is no
external copula dependency.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

KINDS = ("independence", "gaussian", "clayton")


@dataclass
class CopulaModel:
    kind: str
    # per-region day pool of profiles, shape (N_days, T), one array per region
    region_profiles: np.ndarray            # (R, N_days, T)
    # daily summary used for the rank map (low = clean), shape (R, N_days)
    summary_rank_to_day: np.ndarray        # (R, N_days) day index sorted by summary
    gaussian_chol: np.ndarray | None       # (R, R) Cholesky of rank-correlation
    clayton_theta: float | None
    kendall_tau: float                     # mean pairwise Kendall tau (provenance)


# ----------------------------------------------------------------------
# Fitting
# ----------------------------------------------------------------------

def _daily_summary(panel: np.ndarray) -> np.ndarray:
    """Daily-mean intensity per region: (N, R, T) -> (N, R). Low = clean day."""
    return panel.mean(axis=2)


def _kendall_tau(x: np.ndarray, y: np.ndarray) -> float:
    """O(n^2) Kendall's tau-b for modest n (we have ~1460 train days)."""
    n = len(x)
    sx = np.sign(x[:, None] - x[None, :])
    sy = np.sign(y[:, None] - y[None, :])
    iu = np.triu_indices(n, k=1)
    num = float(np.sum(sx[iu] * sy[iu]))
    # tau-a denominator n(n-1)/2; ties are rare in continuous intensity
    den = n * (n - 1) / 2.0
    return num / den if den > 0 else 0.0


def fit_copula(kind: str, train_panel: np.ndarray, dates=None) -> CopulaModel:
    """Fit one of the nested dependence models on the training panel.

    Parameters
    ----------
    kind : {"independence", "gaussian", "clayton"}
    train_panel : (N, R, T) training daily carbon panels.
    """
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    N, R, T = train_panel.shape
    summary = _daily_summary(train_panel)                 # (N, R)

    # Day index sorted by daily summary, per region: rank u -> day with that rank.
    summary_rank_to_day = np.argsort(summary, axis=0).T   # (R, N)
    region_profiles = np.transpose(train_panel, (1, 0, 2))  # (R, N, T)

    # mean pairwise Kendall tau of the daily summaries (provenance + Clayton fit)
    taus = []
    for a in range(R):
        for b in range(a + 1, R):
            taus.append(_kendall_tau(summary[:, a], summary[:, b]))
    mean_tau = float(np.mean(taus)) if taus else 0.0

    gaussian_chol = None
    clayton_theta = None

    if kind == "gaussian":
        # Gaussian copula at the empirical *rank* correlation (Spearman -> normal
        # scores). Use normal-scores correlation, PD-regularized for Cholesky.
        ranks = np.argsort(np.argsort(summary, axis=0), axis=0) + 1.0  # (N,R), 1..N
        z = _ppf((ranks) / (N + 1.0))                                  # normal scores
        corr = np.corrcoef(z, rowvar=False)
        corr = np.atleast_2d(corr)
        corr += 1e-6 * np.eye(R)
        gaussian_chol = np.linalg.cholesky(corr)
    elif kind == "clayton":
        # Exchangeable Clayton: theta from mean Kendall tau, theta = 2 tau/(1-tau).
        tau = min(max(mean_tau, 1e-3), 0.95)
        clayton_theta = 2.0 * tau / (1.0 - tau)

    return CopulaModel(
        kind=kind,
        region_profiles=region_profiles,
        summary_rank_to_day=summary_rank_to_day,
        gaussian_chol=gaussian_chol,
        clayton_theta=clayton_theta,
        kendall_tau=mean_tau,
    )


# ----------------------------------------------------------------------
# Sampling
# ----------------------------------------------------------------------

def _ppf(u: np.ndarray) -> np.ndarray:
    """Standard-normal quantile via the rational Acklam approximation (numpy-only)."""
    u = np.clip(u, 1e-12, 1 - 1e-12)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    out = np.empty_like(u)
    lo = u < plow
    hi = u > phigh
    mid = ~(lo | hi)
    ql = np.sqrt(-2 * np.log(u[lo]))
    out[lo] = (((((c[0]*ql+c[1])*ql+c[2])*ql+c[3])*ql+c[4])*ql+c[5]) / \
              ((((d[0]*ql+d[1])*ql+d[2])*ql+d[3])*ql+1)
    qh = np.sqrt(-2 * np.log(1 - u[hi]))
    out[hi] = -(((((c[0]*qh+c[1])*qh+c[2])*qh+c[3])*qh+c[4])*qh+c[5]) / \
              ((((d[0]*qh+d[1])*qh+d[2])*qh+d[3])*qh+1)
    qm = u[mid] - 0.5
    rm = qm * qm
    out[mid] = (((((a[0]*rm+a[1])*rm+a[2])*rm+a[3])*rm+a[4])*rm+a[5])*qm / \
               (((((b[0]*rm+b[1])*rm+b[2])*rm+b[3])*rm+b[4])*rm+1)
    return out


def _cdf(z: np.ndarray) -> np.ndarray:
    """Standard-normal CDF via erf (numpy-only)."""
    from math import sqrt
    # vectorized erf through numpy's vectorize-free identity using np.special? use math.erf per-elem
    erf = np.vectorize(__import__("math").erf)
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))


def sample_uniforms(model: CopulaModel, S: int, rng: np.random.Generator) -> np.ndarray:
    """Draw S copula samples u in [0,1]^R under the model's dependence."""
    R = model.region_profiles.shape[0]
    if model.kind == "independence":
        return rng.random((S, R))
    if model.kind == "gaussian":
        zc = rng.standard_normal((S, R)) @ model.gaussian_chol.T
        return _cdf(zc)
    if model.kind == "clayton":
        theta = model.clayton_theta
        if theta is None or theta <= 1e-6:
            return rng.random((S, R))
        # Marshall--Olkin: V ~ Gamma(1/theta, 1); E_r ~ Exp(1); U_r=(1+E_r/V)^(-1/theta)
        V = rng.gamma(shape=1.0 / theta, scale=1.0, size=(S, 1))
        E = rng.exponential(scale=1.0, size=(S, R))
        return (1.0 + E / V) ** (-1.0 / theta)
    raise ValueError(model.kind)


def generate_scenarios(model: CopulaModel, S: int, seed: int) -> np.ndarray:
    """Generate (S, R, T) carbon-field scenarios under the copula model.

    Each region's marginal pool of daily profiles is preserved exactly; only the
    cross-region coupling differs by ``model.kind``.
    """
    rng = np.random.default_rng(seed)
    R, N, T = model.region_profiles.shape
    u = sample_uniforms(model, S, rng)                       # (S, R) in [0,1]
    # Map each uniform to a day rank, then to that region's day index.
    day_rank = np.clip((u * N).astype(int), 0, N - 1)        # (S, R)
    out = np.empty((S, R, T), dtype=float)
    for r in range(R):
        days = model.summary_rank_to_day[r][day_rank[:, r]]  # (S,) day indices
        out[:, r, :] = model.region_profiles[r][days]
    return out
