"""Part 4 -- online, rolling-horizon robust transfer control.

The one-shot and two-stage models of Part 3 commit once against a fixed scenario
set. Real operation is *online*: each day a fresh forecast arrives, a schedule is
committed before carbon is realised, the day is observed, and the controller rolls
forward. This module runs that closed loop on a held-out year and compares a
deterministic (point-forecast) controller against a robust (CVaR over forecast-error
scenarios) one.

Per day the controller solves a single transfer allocation LP over the executed load
``y = x + inflow - outflow`` (work conserved, per-cell capacity, transfer budget):

  * deterministic: minimise <forecast, y>            (act on the point forecast)
  * robust:        minimise CVaR_beta over scenarios  (hedge forecast error)

Forecast = seasonal hour-of-day mean from the trailing training window; forecast-error
scenarios = forecast + resampled historical residuals. Realised cost = <actual, y>.
Everything is an LP, so a full year rolls in seconds-to-minutes.
"""
from __future__ import annotations

from typing import Optional

import cvxpy as cp
import numpy as np


def seasonal_forecast(train_panel: np.ndarray) -> np.ndarray:
    """Hour-of-day mean carbon field (R,T) from the training panel (N,R,T)."""
    return train_panel.mean(axis=0)


def residual_pool(train_panel: np.ndarray, forecast: np.ndarray) -> np.ndarray:
    """Historical forecast errors (N,R,T): actual minus the seasonal forecast."""
    return train_panel - forecast[None, :, :]


def _commit(forecast, ceiling, workloads, transfer_budget, *, scenarios=None,
            beta=0.95, lam=0.0, solver=None):
    """One transfer-allocation LP. If ``scenarios`` is given, minimise CVaR_beta of
    cost over them (robust); else minimise cost against ``forecast`` (deterministic).
    Returns the committed executed schedule y (R,T)."""
    R, T = forecast.shape
    x = cp.Variable((R, T), nonneg=True)
    f = cp.Variable((R, R, T), nonneg=True)
    y = x + cp.sum(f, axis=0) - cp.sum(f, axis=1)
    cons = [cp.sum(x, axis=1) == workloads, y >= 0, y <= ceiling,
            cp.sum(f) <= transfer_budget] + [f[r, r, :] == 0 for r in range(R)]
    migrate = lam * cp.sum(f)
    if scenarios is None:
        obj = cp.sum(cp.multiply(forecast, y)) + migrate
    else:
        S = scenarios.shape[0]
        tau = cp.Variable()
        z = cp.Variable(S, nonneg=True)
        costs = [cp.sum(cp.multiply(scenarios[s], y)) for s in range(S)]
        cons += [z[s] >= costs[s] - tau for s in range(S)]
        obj = tau + cp.sum(z) / ((1.0 - beta) * S) + migrate
    prob = cp.Problem(cp.Minimize(obj), cons)
    prob.solve(solver=solver or cp.HIGHS)
    if y.value is None:
        raise RuntimeError(f"online commit failed: {prob.status}")
    return np.asarray(y.value)


def rolling_eval(
    train_panel: np.ndarray,
    test_panel: np.ndarray,
    *,
    ceiling: np.ndarray,
    workloads: np.ndarray,
    transfer_budget: float,
    robust: bool,
    n_scenarios: int = 40,
    beta: float = 0.95,
    lam: float = 0.0,
    stride: int = 1,
    seed: int = 0,
    solver: Optional[str] = None,
) -> np.ndarray:
    """Roll a controller across ``test_panel`` (subsampled by ``stride``). Each step:
    forecast from training, commit (robust or deterministic), realise the actual day,
    record realised carbon cost. Returns the array of realised daily costs."""
    rng = np.random.default_rng(seed)
    forecast = seasonal_forecast(train_panel)
    pool = residual_pool(train_panel, forecast)
    days = range(0, len(test_panel), stride)
    out = np.empty(len(list(days)))
    for k, t in enumerate(range(0, len(test_panel), stride)):
        scen = None
        if robust:
            idx = rng.integers(0, len(pool), n_scenarios)
            scen = np.clip(forecast[None] + pool[idx], 0.0, None)
        y = _commit(forecast, ceiling, workloads, transfer_budget,
                    scenarios=scen, beta=beta, lam=lam, solver=solver)
        out[k] = float((test_panel[t] * y).sum())     # realised carbon cost
    return out
