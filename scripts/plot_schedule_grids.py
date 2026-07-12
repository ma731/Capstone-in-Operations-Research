"""Three grids, one representative zone each: the spatial null seen directly.

Earlier `plot_schedule.py` showed three zones from a SINGLE grid. This variant
shows one representative zone from EACH of the three real grids, ordered
cleanest -> dirtiest, so the joint-vs-shuffled overlap (the spatial null) is
demonstrated across the full dependence spectrum rather than within one grid.

For every grid we solve the Mahalanobis-Wasserstein DRO twice -- once with the
full joint covariance and once with the region-block-diagonal (shuffled)
covariance -- and overlay the two schedules for one representative zone (the
zone whose mean carbon is the per-grid median). They coincide on every grid.

Run: .venv\\Scripts\\python -m scripts.plot_schedule_grids
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from src.analysis.stratified_correlations import REGION_SETS  # noqa: E402
from src.data.electricitymaps import load_all_zones, to_wide  # noqa: E402
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro  # noqa: E402
from src.models.covariance import (  # noqa: E402
    block_diagonal_by_region, build_daily_panel, cholesky_factor,
    daily_panel_to_matrix, estimate_mean_and_covariance, regularize_covariance,
)

NAVY, GOLD, RUST, SAGE = "#00338D", "#E8A33D", "#C0504D", "#4A7C59"
INK, MUTED = "#16202E", "#4A5568"
GRIDS = [("us_west", "Western US"), ("taskc", "Eastern US-Canada"),
         ("us_hetero", "Diversified")]
FIGS = [Path("poster/figs"), Path("figures")]


def _short(z: str) -> str:
    return z.split("-")[-1] if z.startswith("US-") else z


def _solve_grid(key: str, label: str) -> dict:
    cfg = REGION_SETS[key]
    zones, tz = list(cfg["zones"]), cfg["tz"]
    panel, dates = build_daily_panel(to_wide(load_all_zones(zones)),
                                     region_order=zones, tz=tz)
    train = panel[np.array([d.year < 2025 for d in dates])]
    R, T = panel.shape[1], panel.shape[2]
    rho_bar = train.mean(axis=0)
    _, sig = estimate_mean_and_covariance(daily_panel_to_matrix(train))
    Lj = cholesky_factor(regularize_covariance(sig, eta=1e-5))
    Ls = cholesky_factor(regularize_covariance(
        block_diagonal_by_region(sig, R=R, T=T), eta=1e-5))
    wl, ceil = np.full(R, 0.80 * 50.0 * T), np.full((R, T), 50.0)
    kw = dict(alpha=np.full(R, 0.5), ramp=np.full(R, 15.0),
              deferral_windows=[(0, 7, 0.20)], region_order=tuple(zones))
    xj = solve_mahalanobis_dro(rho_bar=rho_bar, L=Lj, workloads=wl,
                               ceiling=ceil, epsilon=1.0, **kw).schedule
    xs = solve_mahalanobis_dro(rho_bar=rho_bar, L=Ls, workloads=wl,
                               ceiling=ceil, epsilon=1.0, **kw).schedule
    r = int(np.argsort(rho_bar.mean(axis=1))[R // 2])      # median zone
    return dict(label=label, zone=_short(zones[r]), xj=xj[r], xs=xs[r],
                rho=rho_bar[r], gmean=float(rho_bar.mean()))


def main() -> None:
    panels = [_solve_grid(k, lab) for k, lab in GRIDS]
    panels.sort(key=lambda p: p["gmean"])                  # cleanest first
    tag = ["Cleanest Grid", "Mid Grid", "Dirtiest Grid"]
    plt.rcParams.update({"font.family": "serif", "text.color": INK})
    rhomax = max(p["rho"].max() for p in panels)
    T = 24
    hours = np.arange(T)
    fig, axes = plt.subplots(1, 3, figsize=(20.5, 4.4), sharey=True,
                             constrained_layout=True)
    for i, p in enumerate(panels):
        ax, ax2 = axes[i], axes[i].twinx()
        ax2.fill_between(hours, p["rho"], color=GOLD, alpha=0.18, zorder=0)
        ax2.plot(hours, p["rho"], color=GOLD, lw=4.5, zorder=1)
        ax.bar(hours, p["xj"], width=0.9, color=NAVY, alpha=0.85, zorder=2)
        ax.step(hours, p["xs"], where="mid", color=RUST, lw=3.6, zorder=3)
        ax.axvspan(-0.5, 7.5, color=SAGE, alpha=0.08, zorder=0)
        ax.set_title(f"{p['label']}  ({tag[i]})", fontsize=19, weight="bold",
                     color=NAVY)
        ax.set_xlabel("Hour of Day", fontsize=16)
        ax.set_xlim(-0.5, T - 0.5)
        ax.set_ylim(0, 55)
        ax2.set_ylim(0, rhomax * 1.12)
        ax2.set_yticks([])
        ax2.spines["right"].set_visible(False)
        if i == 0:
            ax.set_ylabel("Scheduled Load [MW]", fontsize=16)
        ax.tick_params(labelsize=14)
    leg = [Line2D([0], [0], color=NAVY, lw=9, alpha=0.85),
           Line2D([0], [0], color=RUST, lw=3.6),
           Line2D([0], [0], color=GOLD, lw=4.5)]
    fig.legend(leg, ["Load: joint covariance", "Load: shuffled covariance",
                     "Carbon intensity (the daily wave)"],
               frameon=False, loc="outside lower center", ncol=3, fontsize=16)
    for d in FIGS:
        d.mkdir(parents=True, exist_ok=True)
        fig.savefig(d / "schedule_3grid.png", dpi=300, bbox_inches="tight")
        print(f"  wrote {d / 'schedule_3grid.png'}")
    plt.close(fig)


if __name__ == "__main__":
    main()
