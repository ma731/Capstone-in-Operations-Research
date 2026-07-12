"""run_transfer_penalty_sweep.py -- is the transfer value robust to migration costs?

The headline transfer result (4.0--9.9% CVaR_0.95 reduction) treats inter-region
migration as free. Reviewers will object: moving work has costs (network egress,
latency risk, the energy of the transfer itself). solve_transfer_dro already
supports a per-unit migration cost ``lam`` (objective term lam * total relocated
work); this script sweeps it and reports, per grid:

  * the out-of-sample CVaR_0.95 reduction vs the no-transfer baseline at each lam
  * the BREAK-EVEN penalty lam* where the transfer value reaches zero

lam is expressed in the objective's own units (gCO2eq per unit relocated work) and
reported alongside a dimensionless interpretation: lam as a fraction of the mean
train-period carbon intensity rho_mean, i.e. "migrating one unit costs the same as
running it for lam/rho_mean hours at average intensity." This makes the break-even
quotable without committing to a specific egress-cost dollar figure.

Run:  python -m scripts.run_transfer_penalty_sweep
Writes: docs/results_snapshots/transfer_penalty_sweep_<date>.csv and a figure.
Added post-defense (July 2026) for the journal submission's cost-realism analysis.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analysis.metrics import cvar_upper_tail, per_day_emissions
from src.analysis.plotstyle import GOLD, MUTED, NAVY, SAGE, apply_style
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import build_daily_panel
from src.models.transfer_dro import solve_transfer_dro

CEIL, UTIL = 50.0, 0.80
GRIDS = ["us_west", "taskc", "us_hetero"]
PHI_FRAC = 0.20  # transfer budget at the knee of the value curve (see transfer_value_curve)
# penalty as a fraction of mean train-period carbon intensity
LAM_FRACS = [0.0, 0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 1.00, 1.50]


def penalty_curve(rho_bar: np.ndarray, wl: np.ndarray, ceil: np.ndarray,
                  test_panel: np.ndarray, phi: float,
                  lam_fracs=LAM_FRACS) -> list[dict]:
    """Pure computation: CVaR reduction vs no-transfer baseline across penalties.

    Separated from data loading so it is unit-testable on synthetic panels.
    """
    R, T = rho_bar.shape
    L = np.zeros((R * T, R * T))  # deterministic arm (epsilon=0), same as value curve
    rho_mean = float(rho_bar.mean())
    y0, _ = solve_transfer_dro(rho_bar, L, wl, ceil, epsilon=0.0, transfer_budget=0.0)
    c0 = cvar_upper_tail(per_day_emissions(np.asarray(y0), test_panel))
    rows = []
    for frac in lam_fracs:
        lam = frac * rho_mean
        yP, used = solve_transfer_dro(rho_bar, L, wl, ceil, epsilon=0.0,
                                      transfer_budget=phi, lam=lam)
        # Evaluation is on realized emissions only: lam is a *decision* cost that
        # disciplines the schedule; it is not added to the emissions metric.
        cP = cvar_upper_tail(per_day_emissions(np.asarray(yP), test_panel))
        rows.append(dict(lam_frac=frac, lam=lam,
                         cvar_reduction_pct=100.0 * (c0 - cP) / c0,
                         transfer_used=float(used)))
    return rows


def break_even(rows: list[dict], tol: float = 0.05) -> float | None:
    """First lam_frac at which the CVaR reduction falls to <= tol percent
    (linear interpolation between sweep points); None if it never does."""
    prev = None
    for r in rows:
        if r["cvar_reduction_pct"] <= tol:
            if prev is None:
                return r["lam_frac"]
            x0, y0 = prev["lam_frac"], prev["cvar_reduction_pct"]
            x1, y1 = r["lam_frac"], r["cvar_reduction_pct"]
            if y0 == y1:
                return x1
            return x0 + (y0 - tol) * (x1 - x0) / (y0 - y1)
        prev = r
    return None


def run_grid(grid: str) -> list[dict]:
    cfg = REGION_SETS[grid]
    z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
    yrs = np.array([d.year for d in dates])
    tr, te = panel[yrs < 2025], panel[yrs == 2025]
    R, T = panel.shape[1], panel.shape[2]
    rho_bar = tr.mean(axis=0)
    wl = np.full(R, UTIL * CEIL * T)
    ceil = np.full((R, T), CEIL)
    return penalty_curve(rho_bar, wl, ceil, te, phi=PHI_FRAC * float(wl.sum()))


COLORS = {"us_west": NAVY, "taskc": GOLD, "us_hetero": SAGE}


def main() -> None:
    apply_style()
    print("Transfer value under per-unit migration cost lam "
          "(as a fraction of mean train carbon intensity).\n")
    all_rows, curves = [], {}
    for g in GRIDS:
        rows = run_grid(g)
        curves[g] = rows
        be = break_even(rows)
        print(f"=== {DISPLAY_NAME.get(g, g)} ===")
        for r in rows:
            print(f"  lam = {r['lam_frac']:4.2f} x rho_mean : CVaR -{r['cvar_reduction_pct']:5.2f}%  "
                  f"(transfer used {r['transfer_used']:.0f})")
            all_rows.append(dict(grid=g, display=DISPLAY_NAME.get(g, g), **r))
        print(f"  -> break-even penalty lam* ~= "
              f"{'none within sweep' if be is None else f'{be:.2f} x rho_mean'}\n")

    stamp = dt.date.today().strftime("%Y-%m-%d")
    out = Path("docs/results_snapshots") / f"transfer_penalty_sweep_{stamp}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(all_rows).to_csv(out, index=False)
    print(f"Wrote {out}")

    Path("figures").mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.6, 4.8), constrained_layout=True)
    for g in GRIDS:
        xs = [r["lam_frac"] for r in curves[g]]
        ys = [r["cvar_reduction_pct"] for r in curves[g]]
        ax.plot(xs, ys, "-o", lw=2.6, ms=6.0, color=COLORS[g],
                label=DISPLAY_NAME.get(g, g))
    ax.axhline(0.0, color=MUTED, lw=1.0, ls=(0, (4, 4)), alpha=0.5)
    ax.set_xlabel("migration cost lam (fraction of mean carbon intensity)")
    ax.set_ylabel("out-of-sample CVaR$_{0.95}$ reduction vs no transfer (%)")
    ax.legend(frameon=False)
    fig.savefig(Path("figures") / f"transfer_penalty_sweep_{stamp}.png", dpi=200)
    print("Wrote figure.")


if __name__ == "__main__":
    main()
