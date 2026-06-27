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

import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.analysis.metrics import cvar_upper_tail, per_day_emissions  # noqa: E402
from src.analysis.plotstyle import GOLD, INK, MUTED, NAVY, RUST, SAGE, apply_style  # noqa: E402
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS  # noqa: E402
from src.analysis.tail_dependence import residualize_hour_of_day  # noqa: E402
from src.data.electricitymaps import load_all_zones, to_wide  # noqa: E402
from src.models.copula_scenarios import fit_copula, generate_scenarios  # noqa: E402
from src.models.covariance import build_daily_panel  # noqa: E402
from src.models.cvar_saa import solve_cvar_saa  # noqa: E402

FIG = Path("figures")

# Font sizes tuned so the figures stay legible when embedded at ~0.75 text width.
TITLE_FS = 15.5
LABEL_FS = 14
TICK_FS = 12.5
LEG_FS = 12
NOTE_FS = 11.5
ANNOT_FS = 12.5

# A white halo so node labels read clearly even on top of dark correlation edges.
_HALO = [pe.withStroke(linewidth=2.6, foreground="white")]

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
    # Hand-tuned label offsets (in points) so node names sit in clear space and
    # never collide in the dense Western cluster.
    label_off = {
        "US-CAL-BANC": (-7, 9, "right", "bottom"),
        "US-CAL-CISO": (-9, -2, "right", "center"),
        "US-CAL-LDWP": (-2, -15, "center", "top"),
        "US-NW-NEVP": (9, 6, "left", "bottom"),
        "US-SW-AZPS": (9, -10, "left", "top"),
        "US-NW-BPAT": (0, 11, "center", "bottom"),
        "US-TEX-ERCO": (0, -15, "center", "top"),
        "CA-ON": (0, 11, "center", "bottom"),
        "US-NY-NYIS": (9, 2, "left", "center"),
        "US-MIDW-MISO": (-9, 2, "right", "center"),
        "US-MIDA-PJM": (8, -11, "left", "top"),
    }
    fig, ax = plt.subplots(figsize=(10, 6.2), constrained_layout=True)
    labeled = set()
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
                ax.plot([x1, x2], [y1, y2], color=col, lw=max(0.5, 4.5 * abs(r)),
                        alpha=min(0.7, 0.25 + 0.55 * abs(r)),
                        solid_capstyle="round", zorder=1)
        xs = [COORD[z][0] for z in zones]
        ys = [COORD[z][1] for z in zones]
        ax.scatter(xs, ys, s=150, color=col, edgecolors="white", lw=1.6,
                   zorder=3, label=CASE_LABEL[case])
        for z in zones:
            if z in labeled:
                continue
            labeled.add(z)
            x, y = COORD[z]
            dx, dy, ha, va = label_off[z]
            ax.annotate(_short(z), (x, y), textcoords="offset points",
                        xytext=(dx, dy), fontsize=NOTE_FS, color=INK,
                        ha=ha, va=va, zorder=5, path_effects=_HALO)
    ax.set_xlabel("longitude", fontsize=LABEL_FS)
    ax.set_ylabel("latitude", fontsize=LABEL_FS)
    ax.set_xlim(-128, -69)
    ax.set_ylim(27, 50)
    ax.tick_params(labelsize=TICK_FS)
    ax.grid(True, color="#e3e8ef", lw=0.7, alpha=0.9)
    leg = ax.legend(frameon=False, fontsize=LEG_FS, loc="lower left",
                    handletextpad=0.5, borderaxespad=0.8, title="grid case")
    leg.get_title().set_fontsize(LEG_FS)
    leg.get_title().set_color(INK)
    # One concise, regular-weight note explaining the edge encoding (placed in
    # the empty lower-right, clear of the legend at lower-left).
    ax.text(0.985, 0.04, "Edge thickness scales with the de-seasonalized "
            "cross-region correlation.",
            transform=ax.transAxes, fontsize=NOTE_FS, style="italic",
            color=MUTED, ha="right", va="bottom")
    ax.set_title("Three grids, one residual correlation network",
                 fontsize=TITLE_FS, pad=14)
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
    fig, ax = plt.subplots(figsize=(8.8, 5.2), constrained_layout=True)
    # Shared bin edges so the three step outlines are directly comparable.
    all_em = []
    cvars = []
    for kind in arms:
        m = fit_copula(kind, train)
        scen = generate_scenarios(m, 1000, seed=20260613)
        x = solve_cvar_saa(scen, wl, ceil, beta=0.95, **kw).schedule
        all_em.append(per_day_emissions(x, test) / 1e6)            # real 2025 days
    bins = np.linspace(min(e.min() for e in all_em),
                       max(e.max() for e in all_em), 27)
    for (kind, col), em in zip(arms.items(), all_em):
        c = cvar_upper_tail(em)
        cvars.append(c)
        ax.hist(em, bins=bins, histtype="step", lw=2.2, color=col, density=True,
                label=f"{kind}   ($\\mathrm{{CVaR}}_{{0.95}}={c:.3f}$)")
        ax.axvline(c, color=col, ls=":", lw=1.4, alpha=0.9, zorder=1)
    ax.set_xlabel("real 2025 daily emissions under each fitted schedule  "
                  "[$10^6\\,\\mathrm{gCO_2}$]", fontsize=LABEL_FS)
    ax.set_ylabel("density over test days", fontsize=LABEL_FS)
    ax.tick_params(labelsize=TICK_FS)
    ax.margins(x=0.02)
    leg = ax.legend(frameon=False, fontsize=LEG_FS, loc="upper left",
                    title=f"{DISPLAY_NAME.get(case, case)}: schedule fitted under")
    leg.get_title().set_fontsize(LEG_FS)
    leg.get_title().set_color(INK)
    # One bold takeaway: the three tail risks land on the same point.
    cmax = max(cvars)
    ax.annotate("the three $\\mathrm{CVaR}_{0.95}$ lines coincide",
                xy=(cmax, 0.95), xytext=(cmax - 0.02, 2.9),
                fontsize=ANNOT_FS, fontweight="bold", color=NAVY, ha="right",
                va="center",
                arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.4,
                                connectionstyle="arc3,rad=0.25"))
    ax.set_title("Out of sample the schedules are interchangeable:\n"
                 "the three emission distributions and their tail risk coincide",
                 fontsize=TITLE_FS, pad=12)
    ax.grid(True, color="#e3e8ef", lw=0.7, alpha=0.9)
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
    fig, ax = plt.subplots(figsize=(8.4, 5.0), constrained_layout=True)
    ax.axhspan(-0.1, 0.1, color="#e9edf3", zorder=0,
               label="$\\pm0.1\\%$ sampling-noise band")
    ax.axhline(0, color=MUTED, lw=1.1, zorder=1)
    ax.fill_between(S_grid, los, his, color=GOLD, alpha=0.30, lw=0,
                    label="range over 5 scenario seeds", zorder=2)
    ax.plot(S_grid, means, "-o", color=RUST, lw=2.4, ms=7,
            markeredgecolor="white", markeredgewidth=1.2,
            label="mean gap", zorder=4)
    ax.axvline(1000, color=MUTED, ls="--", lw=1.1, zorder=1)
    ax.set_xscale("log")
    ax.set_xticks(S_grid)
    ax.set_xticklabels([str(s) for s in S_grid])
    ax.tick_params(labelsize=TICK_FS)
    ax.set_xlabel("number of scenarios $S$", fontsize=LABEL_FS)
    ax.set_ylabel("comonotone gap vs independence\n$\\mathrm{CVaR}_{0.95}$  [%]",
                  fontsize=LABEL_FS)
    ax.set_xlim(min(S_grid) * 0.85, max(S_grid) * 1.18)
    # Label the operating point inline, regular weight, clear of the data.
    ax.text(1000, ax.get_ylim()[1], " operating point $S=1000$", rotation=90,
            ha="right", va="top", fontsize=NOTE_FS, color=MUTED)
    ax.set_title("Even the maximal copula's gain is scenario-sampling noise:\n"
                 f"across seeds the gap centers on zero ({DISPLAY_NAME.get(case, case)})",
                 fontsize=TITLE_FS, pad=12)
    handles, labels = ax.get_legend_handles_labels()
    order = [labels.index(x) for x in
             ("mean gap", "range over 5 scenario seeds",
              "$\\pm0.1\\%$ sampling-noise band")]
    ax.legend([handles[i] for i in order], [labels[i] for i in order],
              frameon=False, fontsize=LEG_FS, loc="lower right")
    ax.grid(True, color="#e3e8ef", lw=0.7, alpha=0.9)
    _save(fig, "scenario_convergence")


def _save(fig, stem):
    FIG.mkdir(exist_ok=True)
    for ext in ("pdf", "png"):
        p = FIG / f"{stem}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        print(f"  wrote {p}")
    plt.close(fig)


def main():
    apply_style()
    fig_map()
    fig_scenario_tail("taskc")
    fig_convergence("taskc")


if __name__ == "__main__":
    main()
