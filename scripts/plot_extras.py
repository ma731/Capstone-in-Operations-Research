"""Three supplementary figures:
  (A) correlation map  -- the three grids and their residual-correlation network;
  (B) scenario tail    -- daily-emission distribution under each copula (the tail
                          the CVaR targets), showing the copula barely moves it;
  (C) S-convergence     -- the Phase 2 gap is stable in the scenario count S.

Run: .venv\\Scripts\\python -m scripts.plot_extras
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.analysis.metrics import cvar_upper_tail, per_day_emissions  # noqa: E402
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS  # noqa: E402
from src.analysis.tail_dependence import residualize_hour_of_day  # noqa: E402
from src.data.electricitymaps import load_all_zones, to_wide  # noqa: E402
from src.models.copula_scenarios import fit_copula, generate_scenarios  # noqa: E402
from src.models.covariance import build_daily_panel  # noqa: E402
from src.models.cvar_saa import solve_cvar_saa  # noqa: E402

FIG = Path("figures")
NAVY, GOLD, RUST, SAGE = "#1F3B63", "#E69F00", "#B3402F", "#4A7C59"

# Approximate geographic centroids (lon, lat) per Electricity Maps zone.
COORD = {
    "US-CAL-CISO": (-120.0, 37.2), "US-CAL-BANC": (-121.5, 38.6),
    "US-CAL-LDWP": (-118.25, 34.05), "US-NW-NEVP": (-115.1, 36.1),
    "US-SW-AZPS": (-112.07, 33.45), "CA-ON": (-79.4, 44.0),
    "US-NY-NYIS": (-75.5, 42.9), "US-MIDW-MISO": (-90.0, 41.5),
    "US-MIDA-PJM": (-78.0, 40.2), "US-TEX-ERCO": (-99.0, 31.3),
    "US-NW-BPAT": (-121.2, 45.6),
}
CASE_COLOR = {"us_west": NAVY, "taskc": RUST, "us_hetero": SAGE}
CASE_LABEL = {"us_west": "Western US (WECC)", "taskc": "Eastern US–Canada",
              "us_hetero": "engineered (solar/wind/hydro)"}


def _short(z):
    p = z.split("-")
    return p[-1] if z.startswith("US-") else z


def _resid_corr(zones, tz):
    wide = to_wide(load_all_zones(zones))[zones]
    return residualize_hour_of_day(wide, tz).corr()


def fig_map():
    fig, ax = plt.subplots(figsize=(11, 6.4))
    for case in ("us_west", "taskc", "us_hetero"):
        cfg = REGION_SETS[case]
        zones, tz = list(cfg["zones"]), cfg["tz"]
        corr = _resid_corr(zones, tz)
        col = CASE_COLOR[case]
        # correlation edges (residual), thickness/alpha by strength
        for i in range(len(zones)):
            for j in range(i + 1, len(zones)):
                r = corr.iloc[i, j]
                x1, y1 = COORD[zones[i]]
                x2, y2 = COORD[zones[j]]
                ax.plot([x1, x2], [y1, y2], color=col, lw=max(0.3, 4 * abs(r)),
                        alpha=min(0.7, 0.25 + 0.55 * abs(r)), zorder=1)
        xs = [COORD[z][0] for z in zones]
        ys = [COORD[z][1] for z in zones]
        ax.scatter(xs, ys, s=130, color=col, edgecolors="white", lw=1.5,
                   zorder=3, label=CASE_LABEL[case])
        for z in zones:
            x, y = COORD[z]
            ax.annotate(_short(z), (x, y), textcoords="offset points",
                        xytext=(6, 5), fontsize=8, color="0.15", zorder=4)
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_xlim(-127, -71)
    ax.set_ylim(28, 49)
    ax.grid(alpha=0.25, lw=0.5)
    ax.legend(frameon=False, fontsize=10, loc="lower left")
    ax.set_title("The three grids and their residual correlation network "
                 "(edge weight $=$ de-seasonalized cross-region correlation)",
                 fontsize=12)
    _save(fig, "correlation_map")


def fig_scenario_tail(case="taskc"):
    cfg = REGION_SETS[case]
    zones, tz = list(cfg["zones"]), cfg["tz"]
    panel, dates = build_daily_panel(to_wide(load_all_zones(zones)),
                                     region_order=zones, tz=tz)
    train = panel[np.array([d.year < 2025 for d in dates])]
    test = panel[np.array([d.year == 2025 for d in dates])]
    R, T = panel.shape[1], panel.shape[2]
    wl = np.full(R, 0.80 * 50.0 * T)
    ceil = np.full((R, T), 50.0)
    kw = dict(alpha=np.full(R, 0.5), ramp=np.full(R, 15.0),
              deferral_windows=[(0, 7, 0.20)])
    arms = {"independence": NAVY, "clayton": RUST, "comonotone": GOLD}
    fig, ax = plt.subplots(figsize=(9, 5))
    for kind, col in arms.items():
        m = fit_copula(kind, train)
        scen = generate_scenarios(m, 1000, seed=20260613)
        x = solve_cvar_saa(scen, wl, ceil, beta=0.95, **kw).schedule
        em = per_day_emissions(x, test) / 1e6                       # real 2025 days
        ax.hist(em, bins=40, histtype="step", lw=1.8, color=col, density=True,
                label=f"{kind}  ($\\mathrm{{CVaR}}={cvar_upper_tail(em):.3f}$)")
        ax.axvline(cvar_upper_tail(em), color=col, ls=":", lw=1.3, alpha=0.9)
    ax.set_xlabel("real 2025 daily emissions under each fitted schedule  "
                  "[$10^6\\,\\mathrm{gCO_2}$]")
    ax.set_ylabel("density over test days")
    ax.legend(frameon=False, fontsize=9, title=f"{DISPLAY_NAME.get(case, case)}: schedule fitted under")
    ax.set_title("Out of sample the schedules are interchangeable: the three\n"
                 "emission distributions and their $\\mathrm{CVaR}_{0.95}$ (dotted) coincide",
                 fontsize=11)
    ax.grid(alpha=0.3, lw=0.5)
    fig.tight_layout()
    _save(fig, "scenario_tail")


def fig_convergence(case="taskc"):
    cfg = REGION_SETS[case]
    zones, tz = list(cfg["zones"]), cfg["tz"]
    panel, dates = build_daily_panel(to_wide(load_all_zones(zones)),
                                     region_order=zones, tz=tz)
    train = panel[np.array([d.year < 2025 for d in dates])]
    test = panel[np.array([d.year == 2025 for d in dates])]
    R, T = panel.shape[1], panel.shape[2]
    wl = np.full(R, 0.80 * 50.0 * T)
    ceil = np.full((R, T), 50.0)
    kw = dict(alpha=np.full(R, 0.5), ramp=np.full(R, 15.0),
              deferral_windows=[(0, 7, 0.20)])
    S_grid = [250, 500, 1000, 2000, 4000]
    seeds = [20260613, 1, 2, 3, 7]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    mi = fit_copula("independence", train)
    mc = fit_copula("comonotone", train)
    means, los, his = [], [], []
    for S in S_grid:
        gs = []
        for sd in seeds:
            xi = solve_cvar_saa(generate_scenarios(mi, S, sd), wl, ceil,
                                beta=0.95, **kw).schedule
            xc = solve_cvar_saa(generate_scenarios(mc, S, sd), wl, ceil,
                                beta=0.95, **kw).schedule
            base = cvar_upper_tail(per_day_emissions(xi, test))
            gs.append(100 * (base - cvar_upper_tail(per_day_emissions(xc, test))) / base)
        gs = np.array(gs)
        means.append(gs.mean()); los.append(gs.min()); his.append(gs.max())
    means, los, his = map(np.array, (means, los, his))
    ax.fill_between(S_grid, los, his, color=GOLD, alpha=0.25,
                    label="range over 5 scenario seeds")
    ax.plot(S_grid, means, "-o", color=RUST, lw=2, ms=6, label="mean gap")
    ax.axhline(0, color="0.3", lw=1)
    ax.axhspan(-0.1, 0.1, color="0.85", alpha=0.5, zorder=0)
    ax.axvline(1000, color="0.5", ls="--", lw=1)
    ax.set_xscale("log")
    ax.set_xticks(S_grid)
    ax.set_xticklabels([str(s) for s in S_grid])
    ax.set_xlabel("number of scenarios $S$")
    ax.set_ylabel("comonotone gap vs independence\n$\\mathrm{CVaR}_{0.95}$  [%]")
    ax.set_title("Even the maximal copula's gain is scenario-sampling noise:\n"
                 f"across seeds it centers on zero ({DISPLAY_NAME.get(case, case)}, $\\pm0.1\\%$ band)",
                 fontsize=11)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    ax.grid(alpha=0.3, lw=0.5)
    fig.tight_layout()
    _save(fig, "scenario_convergence")


def _save(fig, stem):
    FIG.mkdir(exist_ok=True)
    for ext in ("pdf", "png"):
        p = FIG / f"{stem}.{ext}"
        fig.savefig(p, dpi=200, bbox_inches="tight")
        print(f"  wrote {p}")
    plt.close(fig)


def main():
    fig_map()
    fig_scenario_tail("taskc")
    fig_convergence("taskc")


if __name__ == "__main__":
    main()
