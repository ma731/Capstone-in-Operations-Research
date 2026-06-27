"""Poster figure: a 2D 'carbon landscape' (replaces the old 3D surface).

Mean carbon intensity by hour of day, one translucent filled ridge per Western-grid
region, layered back-to-front by level so it reads like a landscape with a clean
midday valley. Conveys the thesis mechanism at a glance: a large, shared diurnal
swing (the mean field that dominates) with every region moving together
(common-mode, so cross-region covariance buys no hedge). Unlike the 3D surface,
every value is readable off the y-axis.

Run:  python -m scripts.plot_carbon_landscape
Writes: poster/figs/carbon_landscape.png (300 dpi, ~1.57:1 for the poster slot).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.analysis.stratified_correlations import REGION_SETS
from src.data.electricitymaps import load_all_zones, to_wide
from src.models.covariance import build_daily_panel

NAVY, GOLD, SAGE, RUST, BLUE = "#1F3B63", "#C98A2B", "#6E8B6E", "#B3402F", "#3C6E9E"
OUT = Path(__file__).resolve().parents[1] / "poster" / "figs" / "carbon_landscape.png"
LABELS = {"US-CAL-CISO": "CISO", "US-CAL-BANC": "BANC", "US-CAL-LDWP": "LDWP",
          "US-NW-NEVP": "NEVP", "US-SW-AZPS": "AZPS"}


def main():
    cfg = REGION_SETS["us_west"]
    zones = list(cfg["zones"])
    wide = to_wide(load_all_zones(zones), value_col="ci_lifecycle")
    panel, _ = build_daily_panel(wide, region_order=zones, tz=cfg["tz"], expected_T=24)
    mean_field = panel.mean(axis=0)                      # (R, T) hour-of-day mean
    hours = np.arange(24)
    base = float(mean_field.min()) - 25.0

    # layer dirtiest (highest mean) at the back so cleaner ridges sit in front
    order = np.argsort(-mean_field.mean(axis=1))
    colors = [NAVY, BLUE, SAGE, GOLD, RUST]

    plt.rcParams.update({"font.family": "serif", "font.size": 12,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(6.3, 4.0), dpi=300)

    for k, r in enumerate(order):
        y = mean_field[r]
        c = colors[k % len(colors)]
        ax.fill_between(hours, base, y, color=c, alpha=0.34, zorder=k, linewidth=0)
        ax.plot(hours, y, color=c, lw=2.2, zorder=k + 0.5,
                label=LABELS.get(zones[r], zones[r]))

    # highlight the clean midday valley
    ax.axvspan(10, 15, color=GOLD, alpha=0.12, zorder=-1)
    ax.text(12.5, mean_field.max() * 1.005, "cleanest midday", ha="center", va="top",
            fontsize=10.5, style="italic", fontweight="bold", color="#8A5C16")

    # annotate the diurnal swing on the region that swings the most
    swing = mean_field.max(axis=1) / mean_field.min(axis=1)
    rr = int(np.argmax(swing))
    pk_h = int(np.argmax(mean_field[rr])); tr_h = int(np.argmin(mean_field[rr]))
    pk, tr = mean_field[rr, pk_h], mean_field[rr, tr_h]
    ax.annotate("", xy=(tr_h, pk), xytext=(tr_h, tr),
                arrowprops=dict(arrowstyle="<->", color=NAVY, lw=2.2))
    ax.text(tr_h + 0.6, (pk + tr) / 2, f"{swing[rr]:.1f}$\\times$\ndiurnal\nswing",
            ha="left", va="center", fontsize=10.5, fontweight="bold", color=NAVY)

    ax.set_xlim(0, 23); ax.set_ylim(base, mean_field.max() * 1.06)
    ax.set_xticks([0, 6, 12, 18, 23])
    ax.set_xlabel("hour of day"); ax.set_ylabel("carbon intensity (gCO$_2$/kWh)")
    ax.set_title("The carbon landscape: a large, shared diurnal swing",
                 fontsize=13, fontweight="bold", color=NAVY, pad=8)
    ax.grid(axis="y", color="0.85", lw=0.6)
    ax.legend(ncol=5, fontsize=9.5, loc="upper center", frameon=False,
              bbox_to_anchor=(0.5, -0.16), columnspacing=1.2, handlelength=1.4)
    fig.tight_layout()
    fig.savefig(OUT, bbox_inches="tight")
    print(f"wrote {OUT}  ({mean_field.shape[0]} regions, swing {pk/tr:.2f}x)")


if __name__ == "__main__":
    main()
