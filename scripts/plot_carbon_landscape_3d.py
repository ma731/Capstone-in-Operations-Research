"""Poster figure: the 3D 'carbon landscape' surface.

One big, shared daily wave: every Western-grid region dips at midday and peaks
at night together (common-mode), so cross-region covariance is a thin ripple on
a dominant mean field.

This reproduces the original poster figure exactly; the only change from the
first cut is the colourbar pad, nudged out so its tick numbers no longer collide
with the z-axis numbers.

Run:    python -m scripts.plot_carbon_landscape_3d
Writes: poster/figs/carbon_landscape_3d.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from src.analysis.stratified_correlations import REGION_SETS  # noqa: E402
from src.data.electricitymaps import load_all_zones, to_wide  # noqa: E402
from src.models.covariance import build_daily_panel  # noqa: E402

NAVY = "#00338D"
GOLD = "#E8A33D"
MUTED = "#4A5568"
INK = "#16202E"
OUT = Path(__file__).resolve().parents[1] / "poster" / "figs" / "carbon_landscape_3d.png"


def main() -> None:
    plt.rcParams.update({"font.family": "serif", "text.color": INK})
    cfg = REGION_SETS["us_west"]
    zones = list(cfg["zones"])
    wide = to_wide(load_all_zones(zones), value_col="ci_lifecycle")
    panel, _ = build_daily_panel(wide, region_order=zones, tz=cfg["tz"], expected_T=24)
    mf = panel.mean(axis=0)
    R, T = mf.shape
    mf = mf[np.argsort(mf.mean(axis=1))]
    X, Y = np.meshgrid(np.arange(T), np.arange(R))

    cmap = LinearSegmentedColormap.from_list("cm", [GOLD, "#efd9a6", "#8aa0c6", NAVY])
    fig = plt.figure(figsize=(9.0, 6.2))
    ax = fig.add_subplot(111, projection="3d")
    surf = ax.plot_surface(X, Y, mf, cmap=cmap, rstride=1, cstride=1,
                           linewidth=0.15, edgecolor="white", antialiased=True)
    ax.set_xticks([0, 6, 12, 18, 23])
    ax.tick_params(axis="x", labelsize=16, colors=MUTED)
    ax.set_xlabel("Hour of Day", fontsize=18, labelpad=16)
    ax.set_yticks([])
    ax.set_zticks([200, 300, 400, 500])
    ax.tick_params(axis="z", labelsize=15, colors=MUTED)
    ax.set_box_aspect((2.7, 1.1, 1.0))
    ax.view_init(elev=30, azim=-52)
    ax.set_title("Carbon is a big daily wave, shared by every grid",
                 fontsize=20, weight="bold", color=NAVY, pad=8, y=1.0)
    ax.text2D(0.015, 0.93, "about 2x dirtier at night than midday",
              transform=ax.transAxes, color=NAVY, fontsize=16, weight="bold", va="top")
    # colourbar nudged out (pad 0.02 -> 0.13) so its numbers clear the z-axis numbers
    cb = fig.colorbar(surf, ax=ax, shrink=0.55, aspect=14, pad=0.13)
    cb.set_label("Carbon Intensity (gCO$_2$/kWh)", fontsize=15)
    cb.ax.tick_params(labelsize=13, colors=MUTED)
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.pane.set_facecolor("white")
        a.pane.set_edgecolor("#e2e8f1")
    fig.savefig(OUT, dpi=300, bbox_inches="tight")
    print(f"wrote {OUT}  ({R}x{T})")


if __name__ == "__main__":
    main()
