"""Shared evaluation metrics for the scheduling experiments.

These two pure functions were previously copy-pasted across the experiment
runners; they live here so every runner computes the headline numbers identically.
"""
from __future__ import annotations

import numpy as np

CVAR_ALPHA = 0.95


def cvar_upper_tail(values: np.ndarray, alpha: float = CVAR_ALPHA) -> float:
    """Empirical upper-tail CVaR_alpha of a 1-D array (mean of the worst
    ``1-alpha`` fraction). Used on per-day emissions."""
    values = np.asarray(values, dtype=float)
    n = len(values)
    n_tail = max(1, int(np.ceil(n * (1.0 - alpha))))
    return float(np.sort(values)[::-1][:n_tail].mean())


def per_day_emissions(schedule: np.ndarray, panel: np.ndarray) -> np.ndarray:
    """Per-day emissions of a schedule ``x`` (R,T) over a test panel (N,R,T):
    ``einsum('rt,nrt->n')`` = total gCO2eq per day."""
    return np.einsum("rt,nrt->n", schedule, panel)
