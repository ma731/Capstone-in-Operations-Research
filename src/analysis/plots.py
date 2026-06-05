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

# Task B (Iberia ES-PT-FR). Pairs are alphabetised the same way _pairs_long
# builds them (ES-FR, ES-PT, FR-PT in column order ES,PT,FR -> i<j gives
# ES-PT, ES-FR, PT-FR). No "US-CAL-" prefix to strip.
PAIR_COLORS_ES_PT_FR = {
    "ES-PT": "#0072B2",  # blue  (the tightly-coupled MIBEL pair)
    "ES-FR": "#E69F00",  # orange
    "PT-FR": "#009E73",  # green
}
PAIR_ORDER_ES_PT_FR = ["ES-PT", "ES-FR", "PT-FR"]

# Region-set display config: (zones, pair_order, pair_colors, strip_prefix,
# tz, clock_label, region_label).
REGION_SETS = {
    "us": {
        "zones": ["US-CAL-CISO", "US-CAL-BANC", "US-CAL-LDWP"],
        "pair_order": PAIR_ORDER, "pair_colors": PAIR_COLORS,
        "strip_prefix": "US-CAL-", "tz": "America/Los_Angeles",
        "clock_label": "local Pacific time", "region_label": "California sub-zones",
    },
    "es_pt_fr": {
        "zones": ["ES", "PT", "FR"],
        "pair_order": PAIR_ORDER_ES_PT_FR, "pair_colors": PAIR_COLORS_ES_PT_FR,
        "strip_prefix": "", "tz": "Europe/Madrid",
        "clock_label": "local CET/CEST (PT is WET, +1h)", "region_label": "Iberia + France",
        "stem_suffix": "_es_pt_fr",  # so Iberian figures do not overwrite the CA ones
    },
}
SEASON_ORDER = ["DJF", "MAM", "JJA", "SON"]
SEASON_LABELS = {
    "DJF": "Winter\n(DJF)",
    "MAM": "Spring\n(MAM)",
    "JJA": "Summer\n(JJA)",
    "SON": "Autumn\n(SON)",
}

FIGDIR = Path("figures")


def _strip_prefix(pair: str, prefix: str = "US-CAL-") -> str:
    """Drop a zone-id prefix from a pair label for compact display.

    Default 'US-CAL-' for the California figures; pass '' for Iberia (no prefix).
    """
    return pair.replace(prefix, "") if prefix else pair


def _save(fig, stem: str, save_dir: Path) -> list[Path]:
    """Save a figure as both PDF and PNG; return the written paths."""
    save_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in ("pdf", "png"):
        p = save_dir / f"{stem}.{ext}"
        fig.savefig(p, dpi=200, bbox_inches="tight")
        paths.append(p)
    return paths


def plot_correlation_by_hour(wide_df, save_dir: Path = FIGDIR,
                             rs: dict | None = None) -> list[Path]:
    """Line plot of pairwise correlation as a function of local hour-of-day."""
    rs = rs or REGION_SETS["us"]
    long = correlations_by_hour(wide_df, tz=rs["tz"])
    long = long.assign(pair=long["pair"].map(lambda p: _strip_prefix(p, rs["strip_prefix"])))

    fig, ax = plt.subplots(figsize=(8.0, 5.0))

    # Shade the solar window to anchor the visual story.
    ax.axvspan(8, 14, color="#FFD700", alpha=0.12, zorder=0)
    ax.text(11, 0.04, "solar window", ha="center", va="bottom",
            fontsize=9, color="#806000", style="italic")

    for pair in rs["pair_order"]:
        g = long[long["pair"] == pair].sort_values("stratum")
        ax.plot(g["stratum"], g["correlation"],
                marker="o", markersize=4, linewidth=2,
                color=rs["pair_colors"][pair], label=pair)

    ax.set_xlabel(f"Hour of day ({rs['clock_label']})")
    ax.set_ylabel("Pairwise Pearson correlation")
    ax.set_title("Carbon intensity correlation by hour of day\n"
                 f"{rs['region_label']}, 2021\u20132025")
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlim(-0.5, 23.5)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3, linewidth=0.5)
    ax.legend(title="Zone pair", frameon=False)
    fig.tight_layout()

    paths = _save(fig, "correlation_by_hour" + rs.get("stem_suffix", ""), save_dir)
    plt.close(fig)
    return paths


def plot_correlation_by_season(wide_df, save_dir: Path = FIGDIR,
                               rs: dict | None = None) -> list[Path]:
    """Grouped bar chart of pairwise correlation by meteorological season."""
    rs = rs or REGION_SETS["us"]
    long = correlations_by_season(wide_df, tz=rs["tz"])
    long = long.assign(pair=long["pair"].map(lambda p: _strip_prefix(p, rs["strip_prefix"])))

    fig, ax = plt.subplots(figsize=(8.0, 5.0))

    pair_order = rs["pair_order"]
    n_pairs = len(pair_order)
    bar_w = 0.8 / n_pairs
    x = np.arange(len(SEASON_ORDER))

    for i, pair in enumerate(pair_order):
        vals = []
        for s in SEASON_ORDER:
            row = long[(long["pair"] == pair) & (long["stratum"] == s)]
            vals.append(float(row["correlation"].iloc[0]) if len(row) else np.nan)
        offset = (i - (n_pairs - 1) / 2) * bar_w
        ax.bar(x + offset, vals, width=bar_w,
               color=rs["pair_colors"][pair], label=pair)

    ax.set_xlabel("Meteorological season")
    ax.set_ylabel("Pairwise Pearson correlation")
    ax.set_title("Carbon intensity correlation by season\n"
                 f"{rs['region_label']}, 2021\u20132025")
    ax.set_xticks(x)
    ax.set_xticklabels([SEASON_LABELS[s] for s in SEASON_ORDER])
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3, axis="y", linewidth=0.5)
    ax.legend(title="Zone pair", frameon=False,
              loc="center left", bbox_to_anchor=(1.02, 0.5))
    fig.tight_layout()

    paths = _save(fig, "correlation_by_season" + rs.get("stem_suffix", ""), save_dir)
    plt.close(fig)
    return paths


if __name__ == "__main__":
    import argparse

    from src.data.electricitymaps import load_all_zones, to_wide

    ap = argparse.ArgumentParser(description="Generate correlation figures.")
    ap.add_argument("--region-set", choices=tuple(REGION_SETS), default="us")
    args = ap.parse_args()
    rs = REGION_SETS[args.region_set]

    wide = to_wide(load_all_zones(rs["zones"]))
    print(f"[{args.region_set}] Loaded {len(wide):,} hourly observations "
          f"across {wide.shape[1]} zones.")
    for fn in (plot_correlation_by_hour, plot_correlation_by_season):
        for p in fn(wide, rs=rs):
            print(f"  wrote {p}")
