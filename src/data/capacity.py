"""Carbon-free-availability capacity field (Task C addition).

Variable-capacity constraint adapted from Wijayawardana & Chien (SoCC '25),
"Scheduling Cloud VMs on Variable Capacity Datacenters": a data center's usable
capacity tracks the availability of clean / stranded power. We operationalize
this DETERMINISTICALLY -- the per-cell ceiling x_bar_{r,t} is a function of the
training-mean carbon-free-energy fraction CFE_{r,t} (the Electricity Maps
`cfe_pct` column), exactly as the 3b thermal constraint treats the training-mean
temperature field. Because CFE is data (a fixed feasible-set parameter, never
re-estimated per CV fold and never read from the test set), the ceiling is a
constant matrix and the program stays an SOCP/LP.

Thesis rationale: CFE is spatially correlated (shared weather drives renewable
output across regions), so a CFE-driven ceiling makes CAPACITY co-vary across
regions -- a SECOND spatial channel, on top of the carbon-cost coupling that
enters through the off-diagonal blocks of Sigma_hat. This is the mechanism by
which Task C might surface a spatial effect that Tasks A/B did not.
See docs/decisions.md (Decision 8) and thesis/full_formulation.md (Task C, 3c).

Scope guardrail: capacity is treated as DATA, not as a second stochastic vector.
Making capacity stochastic would change the ambiguity set to (rho, capacity) and
collide with the joint-uncertainty teammate's scope (Decision 2). Keep it data.
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence

import numpy as np
import pandas as pd

from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import (
    DEFAULT_TZ,
    T_HOURS,
    build_daily_panel,
)


def capacity_from_cfe(cfe: np.ndarray, x_min: float, x_max: float) -> np.ndarray:
    """Variable per-cell capacity ceiling as a linear function of CFE%.

        x_bar_{r,t} = x_min + (x_max - x_min) * clip(CFE_{r,t}, 0, 100) / 100

    More carbon-free energy available -> more usable (clean) capacity. CFE is in
    percent (0..100); inputs are clipped to [0, 100] before mapping so noisy
    values cannot push the ceiling outside [x_min, x_max].

    This is the capacity analogue of ``pue_from_temperature``: a pure function of
    a given data field, so inside the optimizer it is a per-cell CONSTANT and the
    ceiling constraint x <= x_bar stays linear (the program remains an SOCP/LP).

    Args:
        cfe: array of carbon-free-energy percentages (any shape), 0..100.
        x_min: ceiling floor (MW) -- usable capacity when CFE = 0.
        x_max: ceiling cap   (MW) -- usable capacity when CFE = 100.

    Returns:
        Array of the same shape as ``cfe``, every value in [x_min, x_max].

    Raises:
        ValueError: if x_min < 0 or x_max < x_min.
    """
    cfe = np.asarray(cfe, dtype=float)
    if x_min < 0:
        raise ValueError(f"x_min must be non-negative, got {x_min}")
    if x_max < x_min:
        raise ValueError(f"x_max ({x_max}) must be >= x_min ({x_min})")
    frac = np.clip(cfe, 0.0, 100.0) / 100.0
    return x_min + (x_max - x_min) * frac


def build_cfe_panel(
    zones: Sequence[str],
    years: Optional[Iterable[int]] = None,
    tz: str = DEFAULT_TZ,
    expected_T: int = T_HOURS,
) -> tuple[np.ndarray, pd.DatetimeIndex]:
    """(N, R, T) panel of carbon-free-energy fraction, aligned like the carbon panel.

    Uses the SAME loader, wide pivot (on ``cfe_pct``), and ``build_daily_panel``
    machinery as the carbon field, so the CFE panel is day-for-day and
    hour-for-hour identical in shape and indexing to the carbon panel. Pass the
    same ``zones``/``tz`` you use for the carbon panel.
    """
    long_df = load_all_zones(zones, years=years)
    wide = to_wide(long_df, value_col="cfe_pct")
    return build_daily_panel(wide, region_order=list(zones), tz=tz, expected_T=expected_T)


def cfe_field(
    cfe_panel: np.ndarray,
    dates: pd.DatetimeIndex,
    years: Optional[Iterable[int]] = None,
) -> np.ndarray:
    """Per-cell mean CFE field (R, T) over the given years (training mean).

    The representative carbon-free-availability field used as a fixed parameter
    of the feasible set (analogous to ``temperature_field`` / ``rho_bar``).
    Defaults to all years; pass the TRAINING years to keep the test set out of
    the feasible-set parameters.
    """
    if years is None:
        sel = np.ones(len(dates), dtype=bool)
    else:
        yrs = set(years)
        sel = np.array([d.year in yrs for d in dates])
    if not sel.any():
        raise ValueError(f"No panel days in years={years}")
    return cfe_panel[sel].mean(axis=0)
