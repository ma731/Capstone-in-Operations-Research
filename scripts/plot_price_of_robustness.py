"""plot_price_of_robustness.py -- the price-of-robustness Pareto frontier (#4).

Sweep the DRO ambiguity radius epsilon. For each, solve the Mahalanobis-Wasserstein
schedule and evaluate it out-of-sample: expected daily emissions (the premium you pay)
vs CVaR_0.95 worst-day emissions (the tail protection you buy). The curve is the
literal Bertsimas-Sim "price of robustness" for carbon scheduling: how much mean you
trade for how much tail. A steep/flat curve = robustness buys little; that is the
honest characterization of what the DRO does.

Run: .venv\\Scripts\\python -m scripts.plot_price_of_robustness
"""
from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt

from src.analysis.metrics import cvar_upper_tail, per_day_emissions
from src.analysis.plotstyle import apply_style, NAVY, GOLD, SAGE, MUTED, save
from src.analysis.stratified_correlations import REGION_SETS, DISPLAY_NAME
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import (build_daily_panel, daily_panel_to_matrix,
                                   estimate_mean_and_covariance, regularize_covariance,
                                   cholesky_factor, unflatten_space_time)
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro

apply_style()

CEIL, UTIL = 50.0, 0.80
EPS = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0]
GRIDS = [("us_west", NAVY), ("taskc", GOLD), ("us_hetero", SAGE)]


def frontier(grid):
    cfg = REGION_SETS[grid]; z = list(cfg["zones"])
    panel, dates = build_daily_panel(to_wide(load_all_zones(z)), region_order=z, tz=cfg["tz"])
    yrs = np.array([d.year for d in dates])
    tr, te = panel[yrs < 2025], panel[yrs == 2025]
    R, T = panel.shape[1], panel.shape[2]
    mean, cov = estimate_mean_and_covariance(daily_panel_to_matrix(tr))
    rho_bar = unflatten_space_time(mean, R, T)
    L = cholesky_factor(regularize_covariance(cov))
    wl = np.full(R, UTIL * CEIL * T); ceil = np.full((R, T), CEIL)
    pts = []
    for eps in EPS:
        r = solve_mahalanobis_dro(rho_bar=rho_bar, L=L, workloads=wl, ceiling=ceil,
                                  epsilon=eps, region_order=tuple(z))
        e = per_day_emissions(r.schedule, te)
        pts.append((e.mean(), cvar_upper_tail(e)))
    return np.array(pts)


def main():
    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    for grid, color in GRIDS:
        pts = frontier(grid)
        # normalize to the eps=0 (nominal) point: % change in mean vs % change in CVaR
        m0, c0 = pts[0]
        dmean = 100 * (pts[:, 0] - m0) / m0
        dcvar = 100 * (pts[:, 1] - c0) / c0
        ax.plot(dmean, dcvar, "-o", color=color, lw=2.4, ms=6,
                label=DISPLAY_NAME.get(grid, grid))
        ax.scatter([dmean[0]], [dcvar[0]], s=80, facecolor="white",
                   edgecolor=color, lw=2, zorder=5)
    ax.axhline(0, color=MUTED, lw=0.8); ax.axvline(0, color=MUTED, lw=0.8)
    ax.set_xlabel("mean emissions vs nominal [%]  (the premium you pay -->)")
    ax.set_ylabel("worst-day CVaR vs nominal [%]  (<-- tail protection bought)")
    ax.set_title("The price of robustness: little tail bought for the mean paid",
                 color=NAVY)
    ax.legend(title="grid", loc="best")
    ax.text(0.02, 0.02, "hollow = nominal (eps=0)\narrows of increasing eps",
            transform=ax.transAxes, fontsize=8.5, color=MUTED, va="bottom")
    fig.tight_layout()
    save(fig, "price_of_robustness")
    print("wrote figures/price_of_robustness.png")


if __name__ == "__main__":
    main()
