"""Carbon-intensity correlation diagnostics: heatmap + time-series overlay.

Bissan's ask (2026-06-08 meeting): plot the carbon intensity across regions to
SEE whether they share a pattern, and confirm the spatial correlation the DRO
assumes is actually present. Per region set this writes:

  figures/ci_corr_heatmap_<set>.{pdf,png}  -- raw + residual correlation heatmaps
  figures/ci_overlay_<set>.{pdf,png}       -- standardized CI, a summer & winter week

Run:
    .venv\\Scripts\\python -m scripts.plot_carbon_correlation --region-set taskc
    .venv\\Scripts\\python -m scripts.plot_carbon_correlation --region-set us_west
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless-safe

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.analysis.plotstyle import INK, MUTED, NAVY, apply_style  # noqa: E402
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS  # noqa: E402
from src.data.electricitymaps import load_all_zones, to_wide  # noqa: E402

FIGDIR = Path("figures")

# Type sizes are set generously: both figures are wide multi-panel layouts that
# the report embeds at ~0.75 of text width, so on-page glyphs end up well under
# native size. Erring large keeps ticks, labels, and cell values legible there.
TICK_FS = 13
ANNOT_FS = 14
PANEL_FS = 14
SUPTITLE_FS = 17
CBAR_FS = 13


def _save(fig, stem: str) -> list[Path]:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    out = []
    for ext in ("pdf", "png"):
        p = FIGDIR / f"{stem}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        out.append(p)
    return out


def _short(name: str) -> str:
    """Compact zone label: 'US-CAL-CISO' -> 'CISO', 'CA-ON' -> 'CA-ON'."""
    parts = name.split("-")
    return parts[-1] if name.startswith("US-") else name


def _heatmap(ax, corr: pd.DataFrame, title: str, show_y: bool = True):
    labels = [_short(c) for c in corr.columns]
    ax.grid(False)
    im = ax.imshow(corr.values, vmin=0, vmax=1, cmap="viridis")
    ax.set_xticks(range(len(corr)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=TICK_FS,
                       color=INK)
    ax.set_yticks(range(len(corr)))
    if show_y:
        ax.set_yticklabels(labels, fontsize=TICK_FS, color=INK)
    else:
        ax.set_yticklabels([])
    ax.tick_params(length=0)
    # Hairline white gridlines between cells read cleaner than touching blocks.
    ax.set_xticks([k - 0.5 for k in range(1, len(corr))], minor=True)
    ax.set_yticks([k - 0.5 for k in range(1, len(corr))], minor=True)
    ax.grid(which="minor", color="white", linewidth=1.4)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for i in range(len(corr)):
        for j in range(len(corr)):
            v = corr.values[i, j]
            # Luminance crossover for viridis sits near r = 0.55: dark glyphs on
            # the bright green/yellow cells, white on the dark blue/purple ones.
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="white" if v < 0.55 else INK, fontsize=ANNOT_FS)
    ax.set_title(title, fontsize=PANEL_FS, fontweight="normal", color=NAVY,
                 pad=10)
    return im


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region-set", choices=tuple(REGION_SETS), default="taskc")
    ap.add_argument("--summer-week", default="2024-07-15")
    ap.add_argument("--winter-week", default="2024-01-15")
    args = ap.parse_args()

    apply_style()

    cfg = REGION_SETS[args.region_set]
    zones, tz = cfg["zones"], cfg["tz"]
    wide = to_wide(load_all_zones(zones))[zones]
    loc = wide.tz_convert(tz)
    print(f"[{args.region_set}] {len(wide):,} hourly obs x {len(zones)} zones, tz={tz}")

    raw = wide.corr()
    resid = loc.groupby(loc.index.hour).transform(lambda s: s - s.mean()).corr()

    # --- Figure 1: correlation heatmaps (raw vs residual) ---
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.7), constrained_layout=True)
    _heatmap(axes[0], raw, "Raw hourly correlation", show_y=True)
    im = _heatmap(axes[1], resid, "Residual (hour-of-day mean removed)", show_y=False)
    cbar = fig.colorbar(im, ax=axes, shrink=0.82, pad=0.025)
    cbar.set_label("Pearson correlation $r$", fontsize=CBAR_FS, color=INK)
    cbar.ax.tick_params(labelsize=TICK_FS - 1, color=MUTED, labelcolor=MUTED)
    cbar.outline.set_visible(False)
    fig.suptitle(
        "Cross-region carbon-intensity correlation: "
        f"{DISPLAY_NAME.get(args.region_set, args.region_set)} (2021 to 2025)",
        fontsize=SUPTITLE_FS, fontweight="bold", color=NAVY, y=1.06,
    )
    for p in _save(fig, f"ci_corr_heatmap_{args.region_set}"):
        print(f"  wrote {p}")
    plt.close(fig)

    # --- Figure 2: standardized CI overlay, summer & winter week ---
    z = (loc - loc.mean()) / loc.std()
    fig, axes = plt.subplots(2, 1, figsize=(11, 7.6), sharey=True,
                             constrained_layout=True)
    for ax, (start, lab) in zip(
        axes,
        [(args.summer_week, f"Summer week ({args.summer_week})"),
         (args.winter_week, f"Winter week ({args.winter_week})")],
    ):
        end = (pd.Timestamp(start) + pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        win = z.loc[start:end]
        ax.axhline(0, color=MUTED, linewidth=0.8, alpha=0.45, zorder=0)
        for zn in zones:
            ax.plot(win.index, win[zn], linewidth=1.6, alpha=0.9, label=zn)
        ax.set_title(lab, fontsize=PANEL_FS, fontweight="normal", color=NAVY,
                     pad=8)
        ax.set_ylabel("CI (z-score)", fontsize=TICK_FS, color=INK)
        ax.set_xlim(win.index[0], win.index[-1])
        ax.margins(x=0)
        ax.grid(True, axis="y", alpha=0.3, linewidth=0.6)
        ax.grid(False, axis="x")
        ax.tick_params(labelsize=TICK_FS - 1)
        ax.xaxis.set_major_locator(mdates.DayLocator(tz=loc.index.tz))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d", tz=loc.index.tz))
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=len(zones), frameon=False,
               fontsize=TICK_FS - 1, loc="outside lower center",
               handlelength=1.6, columnspacing=1.6)
    fig.suptitle(
        "Standardized carbon intensity: "
        f"{DISPLAY_NAME.get(args.region_set, args.region_set)}, "
        "a shared shape indicates spatial correlation",
        fontsize=SUPTITLE_FS - 1, fontweight="bold", color=NAVY,
    )
    for p in _save(fig, f"ci_overlay_{args.region_set}"):
        print(f"  wrote {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
