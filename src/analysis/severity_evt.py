"""Extreme-value calibration of realized carbon-severity ratios.

Part 3 rigor upgrade (roadmap D3). The synthetic crossover experiment
(run_part3_emergency.py) finds robustness pays only past a severity M* ~ 3;
run_carbon_ceiling.py measures realized severity as a max/mean ratio and
run_part3_real_emergency.py evaluates the commitment on empirical top-5% days.
What none of them answer is *how rare* a crossover-grade day actually is.

This module fits a generalized Pareto (GPD) upper tail to the daily severity
series via peaks-over-threshold and converts it into return periods:

    "an M >= 3 joint day is a 1-in-N-year event (or is beyond the fitted
     tail's upper endpoint entirely)."

Severity axes (both dimensionless, licence-safe; matching run_carbon_ceiling):

  - joint severity:   daily portfolio-mean carbon / overall portfolio mean.
    The absolute-emissions axis the M* crossover lives on.
  - per-zone severity: daily zone-mean carbon / overall zone mean. The
    relative swing of a single region (can be large on clean grids).

Statistical caveats, stated up front: the daily series is autocorrelated, so
exceedances are declustered with a simple runs method (consecutive exceedance
days form one cluster; the cluster maximum is kept) before fitting, and the
GPD shape on ~5 years of data carries wide uncertainty, which is why the
runner reports bootstrap CIs and a threshold sweep rather than a point fit.

References: Coles (2001), An Introduction to Statistical Modeling of Extreme
Values, Ch. 4 (POT/GPD) and Ch. 5.3 (declustering).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.stats import genpareto

DAYS_PER_YEAR = 365.25


# ---------- Severity series ----------

def daily_joint_severity(panel: np.ndarray) -> np.ndarray:
    """Daily joint (portfolio) severity ratios from an (N, R, T) panel.

    ratio[i] = mean over regions and hours of day i / grand mean of the panel.

    By construction the ratios average to 1 across days, so "severity M"
    reads directly as "an M-times-worse-than-nominal day", the same axis as
    the M* crossover and run_carbon_ceiling's joint severity.

    Args:
        panel: (N, R, T) daily carbon panel (build_daily_panel output).

    Returns:
        (N,) array of dimensionless ratios.

    Raises:
        ValueError: if panel is not 3-D or its grand mean is non-positive.
    """
    panel = np.asarray(panel, dtype=float)
    if panel.ndim != 3:
        raise ValueError(f"Expected 3-D (N, R, T) array, got shape {panel.shape}")
    daily = panel.mean(axis=(1, 2))
    grand = daily.mean()
    if grand <= 0:
        raise ValueError(f"Grand mean must be positive, got {grand}")
    return daily / grand


def daily_zone_severity(panel: np.ndarray, region_index: int) -> np.ndarray:
    """Daily per-zone severity ratios for one region of an (N, R, T) panel.

    ratio[i] = mean over hours of day i for the zone / the zone's grand mean.

    Args:
        panel: (N, R, T) daily carbon panel.
        region_index: index r of the zone on axis 1.

    Returns:
        (N,) array of dimensionless ratios.

    Raises:
        ValueError: if panel is not 3-D, the index is out of range, or the
            zone's grand mean is non-positive.
    """
    panel = np.asarray(panel, dtype=float)
    if panel.ndim != 3:
        raise ValueError(f"Expected 3-D (N, R, T) array, got shape {panel.shape}")
    R = panel.shape[1]
    if not (0 <= region_index < R):
        raise ValueError(f"region_index {region_index} out of range for R={R}")
    daily = panel[:, region_index, :].mean(axis=1)
    grand = daily.mean()
    if grand <= 0:
        raise ValueError(f"Zone grand mean must be positive, got {grand}")
    return daily / grand


# ---------- Peaks-over-threshold fit ----------

@dataclass(frozen=True)
class GPDTailFit:
    """A fitted GPD upper tail from peaks-over-threshold.

    Attributes:
        threshold: the POT threshold u on the severity axis.
        threshold_q: the percentile (0-100) that produced u.
        shape: GPD shape xi (scipy's c). xi < 0 means a bounded tail with
            upper endpoint u - scale/xi.
        scale: GPD scale sigma (> 0).
        zeta: exceedance rate P(X > u), estimated as n_exceed / n_total
            (cluster maxima over total days, so declustering lowers zeta).
        n_exceed: number of (declustered) exceedances used in the fit.
        n_total: total number of days in the series.
    """
    threshold: float
    threshold_q: float
    shape: float
    scale: float
    zeta: float
    n_exceed: int
    n_total: int

    @property
    def upper_endpoint(self) -> float:
        """Finite upper endpoint of the fitted tail, or +inf if xi >= 0."""
        if self.shape >= 0:
            return float("inf")
        return self.threshold - self.scale / self.shape


def decluster_exceedances(
    severity: np.ndarray, threshold: float
) -> np.ndarray:
    """Runs declustering: keep the maximum of each run of consecutive
    exceedance days.

    The daily severity series is autocorrelated (multi-day droughts and
    heat events); fitting a GPD to raw exceedances would treat one 4-day
    event as 4 independent draws. Consecutive exceedances (adjacent day
    indices) form one cluster and contribute a single value, the cluster max.

    Args:
        severity: (N,) daily severity series, in day order.
        threshold: POT threshold u.

    Returns:
        1-D array of cluster maxima (values, not excesses), possibly empty.
    """
    severity = np.asarray(severity, dtype=float)
    idx = np.flatnonzero(severity > threshold)
    if idx.size == 0:
        return np.empty(0)
    maxima = []
    run_max = severity[idx[0]]
    for prev, cur in zip(idx[:-1], idx[1:]):
        if cur == prev + 1:
            run_max = max(run_max, severity[cur])
        else:
            maxima.append(run_max)
            run_max = severity[cur]
    maxima.append(run_max)
    return np.asarray(maxima)


def fit_gpd_tail(
    severity: np.ndarray,
    threshold_q: float = 90.0,
    decluster: bool = True,
    min_exceedances: int = 20,
) -> GPDTailFit:
    """Fit a GPD to threshold exceedances of a daily severity series.

    Args:
        severity: (N,) daily severity ratios, in day order.
        threshold_q: percentile (0-100) defining the POT threshold u.
        decluster: apply runs declustering before fitting (default True).
        min_exceedances: minimum exceedances required for a fit.

    Returns:
        GPDTailFit with the threshold, shape, scale, and exceedance rate.

    Raises:
        ValueError: if fewer than min_exceedances exceedances remain.
    """
    severity = np.asarray(severity, dtype=float)
    if severity.ndim != 1:
        raise ValueError(f"Expected 1-D series, got shape {severity.shape}")
    u = float(np.percentile(severity, threshold_q))
    if decluster:
        peaks = decluster_exceedances(severity, u)
    else:
        peaks = severity[severity > u]
    if peaks.size < min_exceedances:
        raise ValueError(
            f"Only {peaks.size} exceedances above u={u:.4f} "
            f"(q={threshold_q}); need >= {min_exceedances}. "
            f"Lower threshold_q or provide more data."
        )
    excess = peaks - u
    # loc pinned to 0: excesses over u are GPD(xi, sigma) by the POT theorem.
    shape, _, scale = genpareto.fit(excess, floc=0.0)
    zeta = peaks.size / severity.size
    return GPDTailFit(
        threshold=u,
        threshold_q=float(threshold_q),
        shape=float(shape),
        scale=float(scale),
        zeta=float(zeta),
        n_exceed=int(peaks.size),
        n_total=int(severity.size),
    )


# ---------- Return periods and return levels ----------

def exceedance_probability(M: float, fit: GPDTailFit) -> float:
    """P(daily severity > M) under the fitted tail, for M >= threshold.

    P(X > M) = zeta * (1 + xi * (M - u) / sigma)^(-1/xi)   (xi != 0)
             = zeta * exp(-(M - u) / sigma)                (xi == 0)

    Args:
        M: severity level, must be >= fit.threshold.
        fit: a GPDTailFit.

    Returns:
        Daily exceedance probability in [0, zeta]. 0.0 if M lies beyond a
        bounded tail's upper endpoint.

    Raises:
        ValueError: if M < fit.threshold (the GPD only models the tail;
            query the empirical distribution below u instead).
    """
    if M < fit.threshold:
        raise ValueError(
            f"M={M} is below the fitted threshold u={fit.threshold:.4f}; "
            f"the GPD tail is undefined there."
        )
    xi, sigma = fit.shape, fit.scale
    if xi == 0.0:
        return fit.zeta * float(np.exp(-(M - fit.threshold) / sigma))
    arg = 1.0 + xi * (M - fit.threshold) / sigma
    if arg <= 0.0:
        return 0.0  # beyond the upper endpoint of a bounded (xi < 0) tail
    return fit.zeta * float(arg ** (-1.0 / xi))


def return_period_years(
    M: float, fit: GPDTailFit, days_per_year: float = DAYS_PER_YEAR
) -> float:
    """Expected years between days with severity > M under the fitted tail.

    Args:
        M: severity level (>= fit.threshold).
        fit: a GPDTailFit.
        days_per_year: calendar conversion (default 365.25).

    Returns:
        Return period in years; +inf if M is beyond a bounded tail's endpoint.
    """
    p = exceedance_probability(M, fit)
    if p <= 0.0:
        return float("inf")
    return 1.0 / (p * days_per_year)


def return_level(
    T_years: float, fit: GPDTailFit, days_per_year: float = DAYS_PER_YEAR
) -> float:
    """Severity level exceeded once per T_years on average (inverse of
    return_period_years).

    Args:
        T_years: return period in years, must satisfy
            T_years * days_per_year * zeta > 1 (i.e. rarer than the
            threshold itself).
        fit: a GPDTailFit.
        days_per_year: calendar conversion.

    Returns:
        The severity return level x_T >= threshold.

    Raises:
        ValueError: if T_years is not rarer than the threshold event.
    """
    m = T_years * days_per_year  # expected days per exceedance
    if m * fit.zeta <= 1.0:
        raise ValueError(
            f"T={T_years}y is not rarer than the threshold event "
            f"(need T*days*zeta > 1, got {m * fit.zeta:.3f})."
        )
    xi, sigma, u = fit.shape, fit.scale, fit.threshold
    if xi == 0.0:
        return u + sigma * float(np.log(m * fit.zeta))
    return u + (sigma / xi) * float((m * fit.zeta) ** xi - 1.0)


def bootstrap_return_period(
    severity: np.ndarray,
    M: float,
    rng: np.random.Generator,
    threshold_q: float = 90.0,
    n_boot: int = 500,
    block_days: int = 7,
) -> tuple[float, float, float]:
    """Block-bootstrap CI for the return period of severity > M.

    Resamples the daily series in contiguous blocks (circular moving-block
    bootstrap, preserving short-range autocorrelation), refits the GPD tail
    on each replicate, and returns percentile bounds. Replicates where the
    fit fails (too few exceedances) or where M falls beyond a bounded
    replicate tail contribute +inf, which is the honest outcome ("this
    resample says the event is unreachable").

    Args:
        severity: (N,) daily severity series, in day order.
        M: severity level to query.
        rng: seeded numpy Generator, REQUIRED (mirrors
            per_region_temporal_shuffle: no silent irreproducibility).
        threshold_q: POT threshold percentile per replicate.
        n_boot: number of bootstrap replicates.
        block_days: bootstrap block length in days.

    Returns:
        (point, lo, hi): the full-sample return period and the 2.5%/97.5%
        percentile bounds across replicates (inf-aware: percentiles are
        taken on the replicate list with inf kept).
    """
    severity = np.asarray(severity, dtype=float)
    n = severity.size
    fit = fit_gpd_tail(severity, threshold_q=threshold_q)
    point = return_period_years(M, fit)

    n_blocks = int(np.ceil(n / block_days))
    reps = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, n, n_blocks)
        idx = (starts[:, None] + np.arange(block_days)[None, :]).ravel() % n
        sample = severity[idx[:n]]
        try:
            f = fit_gpd_tail(sample, threshold_q=threshold_q)
            reps[b] = return_period_years(M, f)
        except ValueError:
            reps[b] = float("inf")
    lo, hi = np.percentile(reps, [2.5, 97.5])
    return point, float(lo), float(hi)
