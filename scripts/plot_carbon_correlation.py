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

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.analysis.stratified_correlations import REGION_SETS  # noqa: E402
from src.data.electricitymaps import load_all_zones, to_wide  # noqa: E402

FIGDIR = Path("figures")


def _save(fig, stem: str) -> list[Path]:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    out = []
    for ext in ("pdf", "png"):
        p = FIGDIR / f"{stem}.{ext}"
        fig.savefig(p, dpi=200, bbox_inches="tight")
        out.append(p)
    return out


def _short(name: str) -> str:
    """Compact zone label: 'US-CAL-CISO' -> 'CISO', 'CA-ON' -> 'CA-ON'."""
    parts = name.split("-")
    return parts[-1] if name.startswith("US-") else name


def _heatmap(ax, corr: pd.DataFrame, title: str, show_y: bool = True):
    labels = [_short(c) for c in corr.columns]
    im = ax.imshow(corr.values, vmin=0, vmax=1, cmap="viridis")
    ax.set_xticks(range(len(corr)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(corr)))
    if show_y:
        ax.set_yticklabels(labels, fontsize=9)
    else:
        ax.set_yticklabels([])
    for i in range(len(corr)):
        for j in range(len(corr)):
            v = corr.values[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="white" if v < 0.6 else "black", fontsize=9)
    ax.set_title(title, fontsize=11)
    return im


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region-set", choices=tuple(REGION_SETS), default="taskc")
    ap.add_argument("--summer-week", default="2024-07-15")
    ap.add_argument("--winter-week", default="2024-01-15")
    args = ap.parse_args()

    cfg = REGION_SETS[args.region_set]
    zones, tz = cfg["zones"], cfg["tz"]
    wide = to_wide(load_all_zones(zones))[zones]
    loc = wide.tz_convert(tz)
    print(f"[{args.region_set}] {len(wide):,} hourly obs x {len(zones)} zones, tz={tz}")

    raw = wide.corr()
    resid = loc.groupby(loc.index.hour).transform(lambda s: s - s.mean()).corr()

    # --- Figure 1: correlation heatmaps (raw vs residual) ---
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
    _heatmap(axes[0], raw, "Raw hourly correlation", show_y=True)
    im = _heatmap(axes[1], resid, "Residual (hour-of-day mean removed)", show_y=False)
    fig.subplots_adjust(wspace=0.12)
    cbar = fig.colorbar(im, ax=axes, shrink=0.85, label="Pearson $r$", pad=0.02)
    fig.suptitle(f"Cross-region carbon-intensity correlation: {args.region_set} "
                 f"(2021–2025)", fontsize=13)
    for p in _save(fig, f"ci_corr_heatmap_{args.region_set}"):
        print(f"  wrote {p}")
    plt.close(fig)

    # --- Figure 2: standardized CI overlay, summer & winter week ---
    z = (loc - loc.mean()) / loc.std()
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharey=True)
    for ax, (start, lab) in zip(
        axes,
        [(args.summer_week, f"Summer week ({args.summer_week})"),
         (args.winter_week, f"Winter week ({args.winter_week})")],
    ):
        end = (pd.Timestamp(start) + pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        win = z.loc[start:end]
        for zn in zones:
            ax.plot(win.index, win[zn], linewidth=1.3, label=zn)
        ax.set_title(lab, fontsize=10)
        ax.set_ylabel("CI (z-score)")
        ax.grid(alpha=0.3, linewidth=0.5)
    axes[0].legend(ncol=len(zones), frameon=False, fontsize=8,
                   loc="upper center", bbox_to_anchor=(0.5, 1.28))
    fig.suptitle(f"Standardized carbon intensity - {args.region_set} "
                 "(shared shape => spatial correlation)", fontsize=12)
    for p in _save(fig, f"ci_overlay_{args.region_set}"):
        print(f"  wrote {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
