"""Publication-quality figures for the stratified carbon intensity analysis.

Generates two figures, each saved as both PDF (vector, for poster/thesis) and
PNG (raster, for slides):

  figures/correlation_by_hour.{pdf,png}    -- line plot, correlation vs hour
  figures/correlation_by_season.{pdf,png}  -- grouped bar chart, by season

Run from the repo root:

    python -m src.analysis.plots
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend; safe for headless script runs

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.analysis.stratified_correlations import (  # noqa: E402
    correlations_by_hour,
    correlations_by_season,
)

# Wong colourblind-safe palette.
PAIR_COLORS = {
    "BANC-CISO": "#0072B2",  # blue
    "BANC-LDWP": "#E69F00",  # orange
    "CISO-LDWP": "#009E73",  # green
}
PAIR_ORDER = ["BANC-CISO", "BANC-LDWP", "CISO-LDWP"]
SEASON_ORDER = ["DJF", "MAM", "JJA", "SON"]
SEASON_LABELS = {
    "DJF": "Winter\n(DJF)",
    "MAM": "Spring\n(MAM)",
    "JJA": "Summer\n(JJA)",
    "SON": "Autumn\n(SON)",
}

FIGDIR = Path("figures")


def _strip_prefix(pair: str) -> str:
    """Drop the 'US-CAL-' prefix from a pair label for compact display."""
    return pair.replace("US-CAL-", "")


def _save(fig, stem: str, save_dir: Path) -> list[Path]:
    """Save a figure as both PDF and PNG; return the written paths."""
    save_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in ("pdf", "png"):
        p = save_dir / f"{stem}.{ext}"
        fig.savefig(p, dpi=200, bbox_inches="tight")
        paths.append(p)
    return paths


def plot_correlation_by_hour(wide_df, save_dir: Path = FIGDIR) -> list[Path]:
    """Line plot of pairwise correlation as a function of local hour-of-day."""
    long = correlations_by_hour(wide_df)
    long = long.assign(pair=long["pair"].map(_strip_prefix))

    fig, ax = plt.subplots(figsize=(8.0, 5.0))

    # Shade the solar window to anchor the visual story.
    ax.axvspan(8, 14, color="#FFD700", alpha=0.12, zorder=0)
    ax.text(11, 0.04, "solar window", ha="center", va="bottom",
            fontsize=9, color="#806000", style="italic")

    for pair in PAIR_ORDER:
        g = long[long["pair"] == pair].sort_values("stratum")
        ax.plot(g["stratum"], g["correlation"],
                marker="o", markersize=4, linewidth=2,
                color=PAIR_COLORS[pair], label=pair)

    ax.set_xlabel("Hour of day (local Pacific time)")
    ax.set_ylabel("Pairwise Pearson correlation")
    ax.set_title("Carbon intensity correlation by hour of day\n"
                 "California sub-zones, 2021\u20132025")
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlim(-0.5, 23.5)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3, linewidth=0.5)
    ax.legend(title="Zone pair", frameon=False)
    fig.tight_layout()

    paths = _save(fig, "correlation_by_hour", save_dir)
    plt.close(fig)
    return paths


def plot_correlation_by_season(wide_df, save_dir: Path = FIGDIR) -> list[Path]:
    """Grouped bar chart of pairwise correlation by meteorological season."""
    long = correlations_by_season(wide_df)
    long = long.assign(pair=long["pair"].map(_strip_prefix))

    fig, ax = plt.subplots(figsize=(8.0, 5.0))

    n_pairs = len(PAIR_ORDER)
    bar_w = 0.8 / n_pairs
    x = np.arange(len(SEASON_ORDER))

    for i, pair in enumerate(PAIR_ORDER):
        vals = []
        for s in SEASON_ORDER:
            row = long[(long["pair"] == pair) & (long["stratum"] == s)]
            vals.append(float(row["correlation"].iloc[0]) if len(row) else np.nan)
        offset = (i - (n_pairs - 1) / 2) * bar_w
        ax.bar(x + offset, vals, width=bar_w,
               color=PAIR_COLORS[pair], label=pair)

    ax.set_xlabel("Meteorological season")
    ax.set_ylabel("Pairwise Pearson correlation")
    ax.set_title("Carbon intensity correlation by season\n"
                 "California sub-zones, 2021\u20132025")
    ax.set_xticks(x)
    ax.set_xticklabels([SEASON_LABELS[s] for s in SEASON_ORDER])
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3, axis="y", linewidth=0.5)
    ax.legend(title="Zone pair", frameon=False,
              loc="center left", bbox_to_anchor=(1.02, 0.5))
    fig.tight_layout()

    paths = _save(fig, "correlation_by_season", save_dir)
    plt.close(fig)
    return paths


if __name__ == "__main__":
    from src.data.electricitymaps import load_all_zones, to_wide

    zones = ["US-CAL-CISO", "US-CAL-BANC", "US-CAL-LDWP"]
    wide = to_wide(load_all_zones(zones))

    print(f"Loaded {len(wide):,} hourly observations across {wide.shape[1]} zones.")
    for fn in (plot_correlation_by_hour, plot_correlation_by_season):
        for p in fn(wide):
            print(f"  wrote {p}")
