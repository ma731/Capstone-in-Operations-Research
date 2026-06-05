"""Covariance utilities for Mahalanobis--Wasserstein scheduling.

Provides the flattening conventions and statistical primitives used by
Algorithm 2 (both the ell_infinity baseline and the Mahalanobis SOCP variant).

Flattening convention (row-major / C-order):

    vec(x)[r*T + t] = x[r, t]

with region as the outer index and hour as the inner index. This is the
single convention used everywhere in this module; all downstream code that
constructs CVXPY variables must use the same order (cp.reshape with
order='C'). The convention pins the block structure of Sigma_hat:

    Sigma_hat = | Sigma_00  Sigma_01  Sigma_02  Sigma_03 |
                | Sigma_10  Sigma_11  Sigma_12  Sigma_13 |
                | Sigma_20  Sigma_21  Sigma_22  Sigma_23 |
                | Sigma_30  Sigma_31  Sigma_32  Sigma_33 |

where each block is T x T. Sigma_rr is the within-region temporal covariance
for region r; Sigma_rs is the cross-region temporal covariance between r and s.
The block-diagonal-by-region shuffle zeros all off-diagonal blocks.

See progress_note_v8_2.tex Section 2 ("Mahalanobis ground metric") and
Section 6 ("Covariance estimation utility") for the full mathematical context.
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd

# Canonical region ordering for the 4-zone case study. Pinned here so it
# cannot drift between estimator, optimizer, and shuffle code.
REGION_ORDER: tuple[str, ...] = (
    "US-CAL-CISO",
    "US-CAL-BANC",
    "US-CAL-LDWP",
    "US-NW-NEVP",
)

DEFAULT_TZ = "America/Los_Angeles"
T_HOURS = 24  # one scheduling horizon = one local day

# --- Task B (Iberia ES-PT-FR) region set. A SECOND case, not a replacement; ---
# the US REGION_ORDER above is untouched (Task A depends on it). R=3 here, so
# every consumer must pass region_order/tz EXPLICITLY -- do not inherit the US
# defaults. The math engine is already parameterized (build_daily_panel,
# algorithm_2a/2b take region_order and validate len==R).
REGION_ORDER_IBERIA: tuple[str, ...] = (
    "ES",   # Spain
    "PT",   # Portugal
    "FR",   # France
)
# Common reference clock for the Iberian panel. ES and FR are CET (UTC+1/+2);
# PT is WET (UTC+0/+1), i.e. ONE HOUR BEHIND. The panel uses a SINGLE common tz
# for all regions, so under this Madrid clock PT's local hours are shifted +1h
# from PT's true wall-clock. This is a deliberate common-reference-clock choice
# (mirrors Task A using one LA clock for all US zones); it is stated explicitly
# here, in build_daily_panel callers, and in the Task B docs. Do not silence it.
DEFAULT_TZ_IBERIA = "Europe/Madrid"


# ---------- Flattening conventions ----------

def flatten_space_time(matrix: np.ndarray) -> np.ndarray:
    """Flatten an (R, T) array to (R*T,) using row-major / C-order.

    vec[r*T + t] = matrix[r, t]

    Args:
        matrix: (R, T) array of any numeric dtype.

    Returns:
        1-D array of length R*T.

    Raises:
        ValueError: if matrix is not 2-D.
    """
    matrix = np.asarray(matrix)
    if matrix.ndim != 2:
        raise ValueError(f"Expected 2-D (R, T) array, got shape {matrix.shape}")
    return matrix.reshape(-1, order="C")


def unflatten_space_time(vector: np.ndarray, R: int, T: int) -> np.ndarray:
    """Inverse of flatten_space_time. Returns (R, T) matrix.

    Args:
        vector: 1-D array of length R*T.
        R: Number of regions.
        T: Number of time steps.

    Returns:
        (R, T) array.

    Raises:
        ValueError: if vector.size != R*T or vector is not 1-D.
    """
    vector = np.asarray(vector)
    if vector.ndim != 1:
        raise ValueError(f"Expected 1-D array, got shape {vector.shape}")
    if vector.size != R * T:
        raise ValueError(
            f"Expected vector of length R*T = {R*T}, got length {vector.size}"
        )
    return vector.reshape(R, T, order="C")


def daily_panel_to_matrix(panel: np.ndarray) -> np.ndarray:
    """Convert (N, R, T) daily panel to (N, R*T) sample matrix.

    Each row of the output is one daily horizon flattened with the same
    row-major convention as flatten_space_time. This is the input format
    expected by estimate_mean_and_covariance.

    Args:
        panel: (N, R, T) array of N daily samples.

    Returns:
        (N, R*T) array.

    Raises:
        ValueError: if panel is not 3-D.
    """
    panel = np.asarray(panel)
    if panel.ndim != 3:
        raise ValueError(f"Expected 3-D (N, R, T) array, got shape {panel.shape}")
    N, R, T = panel.shape
    return panel.reshape(N, R * T, order="C")


# ---------- Panel construction from Electricity Maps wide DataFrame ----------

def build_daily_panel(
    wide_df: pd.DataFrame,
    region_order: Optional[Sequence[str]] = None,
    tz: str = DEFAULT_TZ,
    expected_T: int = T_HOURS,
) -> tuple[np.ndarray, pd.DatetimeIndex]:
    """Convert a wide-format CI DataFrame (one column per zone, UTC index)
    into a (N, R, T) panel of complete local-tz days.

    Days that do not contain exactly `expected_T` hourly observations after
    timezone conversion are skipped (DST transitions in spring/fall produce
    23- and 25-hour days; these are dropped rather than imputed). For the
    standard Pacific-time case study this drops ~10 days per 5-year span.

    Args:
        wide_df: Output of src.data.electricitymaps.to_wide. Index must be
            datetime; if tz-naive it is assumed UTC.
        region_order: Zone ids in the desired row order. Defaults to
            REGION_ORDER. Every entry must be present in wide_df.columns.
        tz: Timezone for day boundaries. Default Pacific.
        expected_T: Expected hours per day. Default 24.

    Returns:
        (panel, dates) where panel has shape (N, R, T) with
        panel[i, r, t] = CI for region region_order[r] at hour t (local) of
        day dates[i], and dates is a DatetimeIndex of length N giving the
        local date of each panel row.

    Raises:
        ValueError: if region_order references zones not in wide_df, or if
            no complete days are found.
    """
    if region_order is None:
        region_order = REGION_ORDER
    region_order = list(region_order)

    missing = [z for z in region_order if z not in wide_df.columns]
    if missing:
        raise ValueError(
            f"region_order references zones not in wide_df: {missing}. "
            f"Available: {list(wide_df.columns)}"
        )

    # Subset and reorder columns so panel axis 1 matches region_order.
    df = wide_df[region_order].copy()

    # Convert index to local time so day boundaries align with operations.
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(tz)

    # Group by local date; keep only days with exactly expected_T hours.
    panel_rows = []
    dates = []
    for date, day_df in df.groupby(df.index.date):
        if len(day_df) != expected_T:
            continue  # skip DST-transition days and any data gaps
        # day_df is (expected_T rows x R cols); we want (R, T) per day,
        # so transpose. Sort by index first to be safe.
        day_df = day_df.sort_index()
        panel_rows.append(day_df.values.T)  # (R, T)
        dates.append(pd.Timestamp(date))

    if not panel_rows:
        raise ValueError("No complete days found in wide_df")

    panel = np.stack(panel_rows, axis=0)  # (N, R, T)
    return panel, pd.DatetimeIndex(dates)


# ---------- Statistical estimation ----------

def estimate_mean_and_covariance(
    samples: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Empirical mean and unbiased covariance from (N, D) sample matrix.

    Args:
        samples: (N, D) sample matrix; each row is one D-dimensional sample.

    Returns:
        (mean, cov) of shapes (D,) and (D, D). Covariance uses ddof=1.

    Raises:
        ValueError: if samples is not 2-D or has fewer than 2 rows.
    """
    samples = np.asarray(samples)
    if samples.ndim != 2:
        raise ValueError(f"Expected 2-D (N, D) array, got shape {samples.shape}")
    N, D = samples.shape
    if N < 2:
        raise ValueError(f"Need at least 2 samples for covariance, got N={N}")

    mean = samples.mean(axis=0)
    cov = np.cov(samples, rowvar=False, ddof=1)
    cov = np.atleast_2d(cov)  # guard against degenerate D=1 case
    return mean, cov


# ---------- Regularization and factorization ----------

def regularize_covariance(cov: np.ndarray, eta: float = 1e-5) -> np.ndarray:
    """Add scale-adaptive ridge delta*I to a covariance matrix.

    delta = eta * tr(cov) / D

    where D is the dimension. This makes the regularization proportional to
    the average eigenvalue scale, so eta has the same effect across panels
    with different absolute magnitudes (gCO2eq/kWh vs anything else).

    Args:
        cov: (D, D) covariance matrix.
        eta: Dimensionless ridge factor. Default 1e-5 is small enough to
            preserve dependence structure while large enough to guarantee
            PSD against finite-sample near-singularities.

    Returns:
        (D, D) regularized covariance.

    Raises:
        ValueError: if cov is not square 2-D.
        ValueError: if eta is negative.
    """
    cov = np.asarray(cov, dtype=float)
    if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
        raise ValueError(f"Expected square 2-D matrix, got shape {cov.shape}")
    if eta < 0:
        raise ValueError(f"eta must be non-negative, got {eta}")

    D = cov.shape[0]
    trace = np.trace(cov)
    if trace <= 0:
        raise ValueError(
            f"Covariance has non-positive trace ({trace}); cannot apply "
            f"scale-adaptive ridge. Check the input data."
        )
    delta = eta * trace / D
    return cov + delta * np.eye(D)


def cholesky_factor(cov_reg: np.ndarray) -> np.ndarray:
    """Lower-triangular Cholesky factor L such that L @ L.T = cov_reg.

    Uses numpy convention (lower-triangular L). The Mahalanobis penalty
    sqrt(x.T @ Sigma @ x) is then implemented as cp.norm(L.T @ x_vec, 2)
    in CVXPY, since x.T @ L @ L.T @ x = (L.T @ x).T @ (L.T @ x) = ||L.T @ x||_2^2.

    The caller is expected to have applied regularize_covariance first.

    Args:
        cov_reg: (D, D) positive-definite matrix.

    Returns:
        (D, D) lower-triangular L with L @ L.T = cov_reg.

    Raises:
        np.linalg.LinAlgError: if cov_reg is not positive-definite. Means
            the caller did not regularize, or eta was set too small.
    """
    return np.linalg.cholesky(np.asarray(cov_reg, dtype=float))


# ---------- Block-diagonal-by-region shuffle ----------

def block_diagonal_by_region(cov: np.ndarray, R: int, T: int) -> np.ndarray:
    """Construct Sigma_shuf: zero all cross-region T x T blocks; preserve
    within-region T x T blocks.

    This is the matrix analogue of independently bootstrapping each region's
    daily samples while destroying the alignment of samples across regions.
    It preserves each zone's marginal distribution AND its within-zone
    temporal autocorrelation, isolating cross-zone dependence as the only
    difference between Sigma_joint and Sigma_shuf.

    The implementation assumes the row-major flattening convention: region r
    occupies rows/columns r*T through r*T + T - 1.

    Args:
        cov: (R*T, R*T) covariance matrix in row-major layout.
        R: Number of regions.
        T: Number of time steps per region.

    Returns:
        (R*T, R*T) matrix; diagonal R blocks of size T x T equal the
        corresponding blocks of cov, all off-diagonal blocks are zero.

    Raises:
        ValueError: if cov shape is not (R*T, R*T).
    """
    cov = np.asarray(cov)
    expected_dim = R * T
    if cov.shape != (expected_dim, expected_dim):
        raise ValueError(
            f"Expected covariance of shape ({expected_dim}, {expected_dim}), "
            f"got {cov.shape}"
        )

    out = np.zeros_like(cov)
    for r in range(R):
        start = r * T
        stop = (r + 1) * T
        out[start:stop, start:stop] = cov[start:stop, start:stop]
    return out


def per_region_temporal_shuffle(
    panel: np.ndarray,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """Permute days independently within each region.

    This is the sample-level analogue of block_diagonal_by_region at the
    covariance level: applied to a panel of N daily samples, the resulting
    panel's empirical covariance approaches the block-diagonal-by-region
    covariance of the original in expectation as N grows. Per-coordinate
    sample means are preserved exactly (the permutation only reorders rows
    within each region's slice), and each region's within-region temporal
    autocorrelation is preserved exactly (the T-vector for each day stays
    intact). Cross-region day alignment is destroyed: day i of region 0 is
    no longer matched to day i of region 1.

    Used by the Algorithm 2a degeneracy demo (shuffled-marginals invariance)
    and the Algorithm 2b shuffled-marginals sensitivity experiment.

    Args:
        panel: (N, R, T) daily panel.
        rng: numpy Generator; pass an explicit seeded Generator for
            reproducibility. Defaults to a fresh default_rng() per call.

    Returns:
        (N, R, T) shuffled panel; each region's data is independently
        permuted across days. Original panel is not mutated.

    Raises:
        ValueError: if panel is not 3-D.
    """
    panel = np.asarray(panel)
    if panel.ndim != 3:
        raise ValueError(f"Expected 3-D (N, R, T) array, got shape {panel.shape}")
    if rng is None:
        rng = np.random.default_rng()
    N, R, T = panel.shape
    result = np.empty_like(panel)
    for r in range(R):
        perm = rng.permutation(N)
        result[:, r, :] = panel[perm, r, :]
    return result


# ---------- Diagnostics ----------

def condition_number(cov: np.ndarray) -> float:
    """2-norm condition number (largest eigenvalue / smallest eigenvalue).

    Useful sanity check after regularization: condition number > 1e12 means
    the ridge is too small and Cholesky may be numerically unreliable.

    Args:
        cov: (D, D) symmetric matrix. Should be PSD; if not the function
            still returns the ratio of extreme eigenvalues but the result
            may be negative or non-meaningful.

    Returns:
        float; +inf if smallest eigenvalue is non-positive.
    """
    cov = np.asarray(cov, dtype=float)
    eigs = np.linalg.eigvalsh((cov + cov.T) / 2)  # symmetrize against tiny float asymmetry
    min_eig = float(eigs.min())
    max_eig = float(eigs.max())
    if min_eig <= 0:
        return float("inf")
    return max_eig / min_eig


# ---------- Ledoit-Wolf shrinkage estimation (v11 pre-registered test) ----------
# Statistical shrinkage, distinct from regularize_covariance (which adds a tiny
# numerical ridge for invertibility only). Ledoit-Wolf returns the asymptotically
# optimal convex combination (1-rho)*S + rho*F of the sample covariance S with a
# scaled-identity target F, with rho chosen to minimize expected quadratic loss.
# Motivated by the p~n regime (here p = R*T = 96, n ~ 1450 training days): the
# sample covariance is noisy and ill-conditioned, and its noisy off-diagonal
# cross-region blocks are exactly what failed to generalize in the ridge run.
#
# Reference: Ledoit, O. and Wolf, M. (2004). A well-conditioned estimator for
# large-dimensional covariance matrices. J. Multivariate Analysis 88(2):365-411.

def shrink_covariance_ledoit_wolf(samples: np.ndarray) -> tuple[np.ndarray, float]:
    """Ledoit-Wolf shrinkage covariance from an (N, D) sample matrix.

    Returns (Sigma_shrunk, shrinkage_intensity). The intensity rho in [0, 1] is
    reported so the experiment can log how much shrinkage was applied (rho near 0
    => sample covariance trusted; rho near 1 => heavily shrunk toward identity).

    Unlike regularize_covariance, the output is already well-conditioned and PD,
    so it can be passed straight to cholesky_factor without an added ridge.
    """
    from sklearn.covariance import LedoitWolf
    samples = np.asarray(samples, dtype=float)
    if samples.ndim != 2:
        raise ValueError(f"Expected 2-D (N, D) array, got shape {samples.shape}")
    lw = LedoitWolf(assume_centered=False).fit(samples)
    return np.asarray(lw.covariance_, dtype=float), float(lw.shrinkage_)
