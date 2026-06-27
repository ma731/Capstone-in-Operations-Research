"""Poster figure: the three study grids on a stylized US/Canada map.

Hand-built (no geo dependencies): a simplified continental-US outline plus the real
zone locations, so the map is not sparse. The Western grid is a tight Southwest
cluster, the Eastern US-Canada grid shows all four zones across the Great Lakes /
Northeast (it previously read as a single dot), and the Diversified grid is three
deliberately spread zones (California solar, Texas wind, Pacific-Northwest hydro).

Run:  python -m scripts.plot_us_grids_map
Writes: poster/figs/us_regions_map.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon

NAVY, CER, SAGE, GOLDD, INK = "#1F3B63", "#0098E0", "#5E8C6A", "#8A5C16", "#1A1A1A"
OUT = Path(__file__).resolve().parents[1] / "poster" / "figs" / "us_regions_map.png"

# simplified continental-US outline (lon, lat), clockwise from the NW corner
US = [(-124.6, 48.4), (-110, 49), (-95, 49), (-87, 48), (-84.5, 46.3), (-82.5, 45.2),
      (-82.9, 41.7), (-79.2, 42.9), (-76.8, 43.6), (-73.4, 45.0), (-69.2, 47.4),
      (-67.1, 44.8), (-70.7, 43.2), (-71.2, 41.5), (-74.0, 40.5), (-75.5, 38.5),
      (-76.0, 37.0), (-75.6, 35.5), (-78.5, 33.9), (-80.9, 32.0), (-81.4, 30.7),
      (-80.1, 26.8), (-80.4, 25.2), (-82.0, 26.5), (-82.8, 28.0), (-84.0, 30.0),
      (-85.6, 29.7), (-88.3, 30.3), (-89.4, 29.1), (-91.5, 29.5), (-93.8, 29.7),
      (-96.5, 28.4), (-97.4, 27.0), (-99.2, 26.4), (-101.4, 29.8), (-103.0, 29.0),
      (-104.9, 30.6), (-106.5, 31.8), (-108.2, 31.3), (-111.1, 31.3), (-114.8, 32.5),
      (-117.1, 32.5), (-118.4, 34.0), (-120.6, 34.5), (-122.0, 37.0), (-124.0, 40.4),
      (-124.2, 43.3), (-124.7, 47.3)]

# zone lon/lat per grid
WEST = {"CISO": (-120.6, 37.2), "BANC": (-121.5, 38.6), "LDWP": (-118.2, 34.2),
        "NEVP": (-116.9, 39.3), "AZPS": (-112.1, 33.4)}
EAST = {"CA-ON": (-80.0, 44.5), "NYISO": (-75.4, 42.9), "MISO": (-93.6, 44.6),
        "PJM": (-77.5, 40.2)}
DIV = {"CISO ": (-120.6, 37.2), "ERCO": (-98.5, 31.3), "BPAT": (-120.6, 46.0)}


def main():
    plt.rcParams.update({"font.family": "serif"})
    fig, ax = plt.subplots(figsize=(7.0, 4.6), dpi=300)
    ax.add_patch(Polygon(US, closed=True, facecolor="#EAF1F9", edgecolor="#9BB4D4",
                         lw=1.6, joinstyle="round", zorder=1))

    def cluster(d, color, marker="o", size=150, label=None):
        xy = np.array(list(d.values()))
        c = xy.mean(0)
        for p in xy:
            ax.plot([c[0], p[0]], [c[1], p[1]], color=color, lw=1.5, alpha=0.45, zorder=2)
        ax.scatter(xy[:, 0], xy[:, 1], s=size, c=color, marker=marker,
                   edgecolor="white", lw=1.3, zorder=4, label=label)

    cluster(WEST, NAVY, label="Western US  ($\\rho$ up to 0.78)")
    cluster(EAST, CER, label="Eastern US–Canada  (4 zones)")
    cluster(DIV, SAGE, marker="D", size=120,
            label="Diversified  (CA solar · TX wind · NW hydro)")

    leg = ax.legend(loc="lower left", fontsize=10, frameon=True, framealpha=0.95,
                    edgecolor="#9BB4D4", borderpad=0.7, labelspacing=0.6,
                    handletextpad=0.5, bbox_to_anchor=(0.0, 0.0))
    leg.set_zorder(6)

    ax.set_xlim(-127, -65); ax.set_ylim(24, 50.5)
    ax.set_aspect(1.28)            # gentle aspect correction for the latitude band
    ax.axis("off")
    ax.set_title("Three grids studied across the US and Canada",
                 fontsize=13.5, fontweight="bold", color=INK, pad=6)
    fig.tight_layout()
    fig.savefig(OUT, bbox_inches="tight")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
