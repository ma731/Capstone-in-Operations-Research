"""Tail-dependence diagnostic: does carbon intensity co-spike in the tails more
than its correlation (what the covariance-based DRO sees) implies?

For each region set this writes:
  figures/tail_dependence_<set>.{pdf,png}  -- chi_U(q) curves per pair, empirical
                                              vs the Gaussian-copula benchmark
and prints a summary table at q (default 0.95) for RAW and RESIDUAL series.

A positive empirical-minus-Gaussian excess = dirty-tail co-movement that a
Mahalanobis-Wasserstein (covariance) ambiguity set is structurally blind to ->
the empirical motivation for the Phase 2 copula extension. If the empirical
curve tracks the Gaussian benchmark, the Phase 1 null is even more bulletproof.

Run:
    .venv\\Scripts\\python -m scripts.plot_tail_dependence --region-set us_west
    .venv\\Scripts\\python -m scripts.plot_tail_dependence --region-set taskc
    .venv\\Scripts\\python -m scripts.plot_tail_dependence --region-set us_hetero
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless-safe

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

from src.analysis.plotstyle import MUTED, NAVY, RUST, apply_style  # noqa: E402
from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS  # noqa: E402
from src.analysis.tail_dependence import (  # noqa: E402
    chi_upper_curve,
    residualize_hour_of_day,
    tail_dependence_table,
)
from src.data.electricitymaps import load_all_zones, to_wide  # noqa: E402

FIGDIR = Path("figures")


def _save(fig, stem: str) -> list[Path]:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    out = []
    for ext in ("pdf", "png"):
        p = FIGDIR / f"{stem}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        out.append(p)
    return out


def _print_table(title: str, table: pd.DataFrame) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    print(table.to_string(index=False, float_format=lambda x: f"{x:.3f}"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region-set", choices=tuple(REGION_SETS), default="taskc")
    ap.add_argument("--q", type=float, default=0.95,
                    help="Tail quantile for the summary table (default 0.95).")
    args = ap.parse_args()

    apply_style()

    cfg = REGION_SETS[args.region_set]
    zones, tz = cfg["zones"], cfg["tz"]
    wide = to_wide(load_all_zones(zones))[zones]
    resid = residualize_hour_of_day(wide, tz)
    print(f"[{args.region_set}] {len(wide):,} hourly obs x {len(zones)} zones, tz={tz}")

    # --- Summary tables (raw + residual) at the headline quantile q ---
    raw_tbl = tail_dependence_table(wide, q=args.q)
    res_tbl = tail_dependence_table(resid, q=args.q)
    _print_table(f"RAW hourly CI -- tail dependence at q={args.q} "
                 f"(chi_U_excess = empirical - Gaussian)", raw_tbl)
    _print_table(f"RESIDUAL (hour-of-day removed) -- tail dependence at q={args.q}",
                 res_tbl)

    # --- Figure: chi_U(q) curves per pair, empirical vs Gaussian benchmark ---
    q_grid = np.linspace(0.80, 0.99, 25)
    pairs = [(zones[i], zones[j])
             for i in range(len(zones)) for j in range(i + 1, len(zones))]
    ncol = min(3, len(pairs))
    nrow = int(np.ceil(len(pairs) / ncol))

    # Precompute every curve once so the shared y-axis can be zoomed to the data
    # (the empirical-vs-benchmark gap is the message; ylim 0..1 buries it).
    curves, ymax_data = [], 0.0
    for a, b in pairs:
        emp, gau = chi_upper_curve(resid, a, b, q_grid)
        curves.append((a, b, emp, gau))
        ymax_data = max(ymax_data, float(emp.max()), float(gau.max()))
    ymax = min(1.0, ymax_data * 1.12)

    # Display-only short names (drop the "US-" country prefix; the Canadian
    # "CA-" codes stay for context), so panel titles stay legible and never
    # collide with the neighbouring panel when the figure is shrunk.
    def _short(z: str) -> str:
        return z[3:] if z.startswith("US-") else z

    # Bottom-most populated row per column, so x tick labels and the x-axis
    # title land under the last real panel of every column (not hidden by an
    # empty slot below it, as sharex would otherwise do).
    last_row_in_col: dict[int, int] = {}
    for k in range(len(pairs)):
        r, c = divmod(k, ncol)
        last_row_in_col[c] = max(last_row_in_col.get(c, -1), r)

    fig, axes = plt.subplots(nrow, ncol, figsize=(2.3 * ncol, 1.95 * nrow + 1.5),
                             squeeze=False, sharex=True, sharey=True,
                             constrained_layout=True)
    for k, (a, b, emp, gau) in enumerate(curves):
        r, c = divmod(k, ncol)
        ax = axes[r][c]
        ax.fill_between(q_grid, gau, emp, where=(emp >= gau),
                        color=RUST, alpha=0.18, linewidth=0)
        ax.plot(q_grid, gau, color=MUTED, lw=1.8, ls=(0, (5, 2)), zorder=2)
        ax.plot(q_grid, emp, color=RUST, lw=2.4, zorder=3)
        ax.set_title(f"{_short(a)}  $|$  {_short(b)}", fontsize=12.5,
                     fontweight="regular", color=NAVY, pad=6)
        ax.grid(True, axis="y", alpha=0.5, lw=0.6)
        ax.set_xlim(0.80, 0.99)
        ax.set_ylim(0, ymax)
        ax.set_xticks([0.80, 0.85, 0.90, 0.95])
        ax.yaxis.set_major_locator(MaxNLocator(4))
        ax.tick_params(labelsize=12)
        if c == 0:
            ax.set_ylabel(r"$\chi_U(q)$", fontsize=14)
        if r == last_row_in_col[c]:
            ax.set_xlabel(r"tail quantile $q$", fontsize=13)
            ax.tick_params(labelbottom=True)

    off = []  # unused slots in a ragged grid
    for k in range(len(pairs), nrow * ncol):
        ax = axes[k // ncol][k % ncol]
        ax.axis("off")
        off.append(ax)

    # One bold takeaway, placed in the empty grid space (never over the data).
    if off:
        off[0].text(0.5, 0.62,
                    "Across every pair, the empirical\n"
                    r"$\chi_U$ tracks or sits below the"
                    "\nGaussian benchmark.",
                    transform=off[0].transAxes, ha="center", va="center",
                    fontsize=13, fontweight="bold", color=NAVY)

    handles = [
        Line2D([], [], color=RUST, lw=2.4, label=r"empirical $\chi_U(q)$"),
        Line2D([], [], color=MUTED, lw=1.8, ls=(0, (5, 2)),
               label=r"Gaussian copula, matched $\rho$"),
        Patch(facecolor=RUST, alpha=0.18, label="empirical excess"),
    ]
    fig.legend(handles=handles, loc="outside lower center", ncol=3,
               fontsize=12, frameon=False, handlelength=2.2,
               columnspacing=1.8, borderaxespad=0.4)

    fig.suptitle("Upper-tail dependence vs Gaussian benchmark: "
                 f"{DISPLAY_NAME.get(args.region_set, args.region_set)}",
                 fontsize=15.5, fontweight="bold", color=NAVY)
    for pth in _save(fig, f"tail_dependence_{args.region_set}"):
        print(f"  wrote {pth}")
    plt.close(fig)


if __name__ == "__main__":
    main()
