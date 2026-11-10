"""A one-day, day-ahead migration plan on real carbon data, using the thesis optimiser.

For a portfolio and a day:

1. Forecast: each region's carbon intensity per hour is forecast as the mean of the same
   hour over the previous 14 days (a simple seasonal forecast, so the plan never sees the
   day it is scheduling).
2. Plan twice with ``solve_transfer_dro`` (deterministic, epsilon = 0, which the thesis
   finds dominant on real grids): once with no transfer between regions (Phi = 0, time
   shifting only) and once with a transfer budget.
3. Score both plans on the carbon that actually happened that day.

This is a one-day illustration of RQ1 (migration pays), not the thesis metric: the
reported numbers are out-of-sample CVaR over many days, in ``results/``.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

HISTORY_DAYS = 14


def _hourly(zone: str, start: date, end: date) -> np.ndarray:
    """(days, 24) lifecycle carbon intensity, gCO2eq/kWh, UTC days [start, end]."""
    from src.data.electricitymaps import load_zone

    years = sorted({start.year, end.year})
    df = load_zone(zone, years=years)
    df = df[(df["timestamp_utc"].dt.date >= start) & (df["timestamp_utc"].dt.date <= end)]
    series = df.set_index("timestamp_utc")["ci_lifecycle"].interpolate(limit_direction="both")
    days = (end - start).days + 1
    values = series.to_numpy()
    if len(values) != days * 24:
        raise ValueError(f"{zone}: expected {days * 24} hourly values between {start} and {end}, got {len(values)}")
    return values.reshape(days, 24)


def forecast_and_actual(zones: list[str], day: date) -> tuple[np.ndarray, np.ndarray]:
    """(R, 24) forecast from the previous 14 days, and (R, 24) what actually happened."""
    start = day - timedelta(days=HISTORY_DAYS)
    fc, act = [], []
    for z in zones:
        panel = _hourly(z, start, day)
        fc.append(panel[:-1].mean(axis=0))
        act.append(panel[-1])
    return np.array(fc), np.array(act)


def plan_day(zones: list[str], day: date, *, transfer_share: float = 0.3,
             work_per_region_mwh: float = 24.0, headroom: float = 2.0) -> dict:
    """Compare time shifting only against time shifting plus moving work between regions."""
    from src.models.transfer_dro import solve_transfer_dro

    if not 0 <= transfer_share <= 1:
        raise ValueError("transfer_share must be between 0 and 1")
    fc, act = forecast_and_actual(zones, day)
    r, t = fc.shape
    work = np.full(r, work_per_region_mwh)
    ceiling = np.full((r, t), headroom * work_per_region_mwh / t)
    budget = transfer_share * work.sum()

    y_local, _ = solve_transfer_dro(fc, None, work, ceiling, epsilon=0.0, transfer_budget=0.0)
    y_move, moved = solve_transfer_dro(fc, None, work, ceiling, epsilon=0.0, transfer_budget=budget)

    def tonnes(y):  # MWh x gCO2eq/kWh = kgCO2eq; / 1000 = tonnes
        return float((y * act).sum() / 1000)

    local, move = tonnes(y_local), tonnes(y_move)
    shift = {z: round(float(y_move[i].sum() - work[i]), 2) for i, z in enumerate(zones)}
    return {
        "day": day.isoformat(), "zones": zones,
        "work_mwh": float(work.sum()), "transfer_budget_mwh": round(float(budget), 2),
        "moved_mwh": round(moved, 2),
        "net_shift_mwh_by_zone": shift,
        "tonnes_time_shift_only": round(local, 3), "tonnes_with_migration": round(move, 3),
        "saving_pct": round(100 * (local - move) / local, 2) if local else 0.0,
        "note": "One day, scored on realised carbon. The thesis metric is out-of-sample CVaR over many days.",
    }
