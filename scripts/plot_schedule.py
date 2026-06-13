"""The scheduler made visible: optimal load vs. carbon intensity over the day.

Shows that the DRO concentrates compute in low-carbon hours (and that the joint
vs. shuffled schedules are nearly identical -- the spatial null, seen directly).

Run: .venv\\Scripts\\python -m scripts.plot_schedule --region-set us_west
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.analysis.stratified_correlations import REGION_SETS  # noqa: E402
from src.data.electricitymaps import load_all_zones, to_wide  # noqa: E402
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro  # noqa: E402
from src.models.covariance import (  # noqa: E402
    block_diagonal_by_region, build_daily_panel, cholesky_factor,
    daily_panel_to_matrix, estimate_mean_and_covariance, regularize_covariance,
)

FIG = Path("figures")
NAVY, GOLD, RUST, SAGE = "#1F3B63", "#E69F00", "#B3402F", "#4A7C59"


def _short(z: str) -> str:
    p = z.split("-")
    return p[-1] if z.startswith("US-") else z


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region-set", choices=tuple(REGION_SETS), default="us_west")
    args = ap.parse_args()
    cfg = REGION_SETS[args.region_set]
    zones, tz = list(cfg["zones"]), cfg["tz"]

    panel, dates = build_daily_panel(to_wide(load_all_zones(zones)),
                                     region_order=zones, tz=tz)
    train = panel[np.array([d.year < 2025 for d in dates])]
    R, T = panel.shape[1], panel.shape[2]
    rho_bar = train.mean(axis=0)                              # (R,T) mean carbon field
    _, sig = estimate_mean_and_covariance(daily_panel_to_matrix(train))
    Lj = cholesky_factor(regularize_covariance(sig, eta=1e-5))
    Ls = cholesky_factor(regularize_covariance(
        block_diagonal_by_region(sig, R=R, T=T), eta=1e-5))
    wl = np.full(R, 0.80 * 50.0 * T)
    ceil = np.full((R, T), 50.0)
    kw = dict(alpha=np.full(R, 0.5), ramp=np.full(R, 15.0),
              deferral_windows=[(0, 7, 0.20)], region_order=tuple(zones))
    xj = solve_mahalanobis_dro(rho_bar=rho_bar, L=Lj, workloads=wl, ceiling=ceil,
                               epsilon=1.0, **kw).schedule
    xs = solve_mahalanobis_dro(rho_bar=rho_bar, L=Ls, workloads=wl, ceiling=ceil,
                               epsilon=1.0, **kw).schedule

    ncol = R
    fig, axes = plt.subplots(1, ncol, figsize=(2.7 * ncol, 4.2),
                             sharey=True, squeeze=False)
    hours = np.arange(T)
    for r in range(R):
        ax = axes[0][r]
        ax2 = ax.twinx()
        # carbon intensity (mean field) as the backdrop
        ax2.fill_between(hours, rho_bar[r], color=GOLD, alpha=0.18, zorder=0)
        ax2.plot(hours, rho_bar[r], color=GOLD, lw=1.6, zorder=1,
                 label="carbon intensity")
        # scheduled load: joint (bars) vs shuffled (step) -- visually identical
        ax.bar(hours, xj[r], width=0.9, color=NAVY, alpha=0.8, zorder=2,
               label="load (joint $\\Sigma$)")
        ax.step(hours, xs[r], where="mid", color=RUST, lw=1.4, zorder=3,
                label="load (shuffled $\\Sigma$)")
        ax.axvspan(-0.5, 7.5, color=SAGE, alpha=0.08, zorder=0)
        ax.set_title(_short(zones[r]), fontsize=10)
        ax.set_xlabel("hour", fontsize=8)
        ax.set_xlim(-0.5, T - 0.5)
        ax.set_ylim(0, 55)
        ax2.set_ylim(0, np.nanmax(rho_bar) * 1.1)
        if r == 0:
            ax.set_ylabel("scheduled load [MW]", fontsize=9)
        if r == R - 1:
            ax2.set_ylabel("carbon intensity [$\\mathrm{gCO_2/kWh}$]", fontsize=9,
                           color=GOLD)
        ax2.tick_params(axis="y", labelcolor=GOLD, labelsize=7)
        ax.tick_params(labelsize=7)
    # one combined legend
    h1, l1 = axes[0][0].get_legend_handles_labels()
    h2, l2 = axes[0][0].twinx().get_legend_handles_labels()
    axes[0][0].legend(h1, l1, frameon=False, fontsize=7.5, loc="upper right")
    fig.suptitle(f"Joint vs.\\ shuffled-covariance schedules are visually "
                 f"indistinguishable ({args.region_set}): the spatial null, seen "
                 f"directly. Load (bars) tracks the low-carbon hours.", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    FIG.mkdir(exist_ok=True)
    for ext in ("pdf", "png"):
        p = FIG / f"schedule_{args.region_set}.{ext}"
        fig.savefig(p, dpi=200, bbox_inches="tight")
        print(f"  wrote {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
