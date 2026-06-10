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

from src.analysis.stratified_correlations import REGION_SETS  # noqa: E402
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
        fig.savefig(p, dpi=200, bbox_inches="tight")
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
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 3.4 * nrow),
                             squeeze=False, sharex=True, sharey=True)
    for k, (a, b) in enumerate(pairs):
        ax = axes[k // ncol][k % ncol]
        emp, gau = chi_upper_curve(resid, a, b, q_grid)
        ax.plot(q_grid, emp, color="C3", lw=1.8, label="empirical")
        ax.plot(q_grid, gau, color="0.4", lw=1.5, ls="--", label="Gaussian (matched rho)")
        ax.fill_between(q_grid, gau, emp, where=(emp >= gau), color="C3", alpha=0.15)
        ax.set_title(f"{a} | {b}", fontsize=9)
        ax.grid(alpha=0.3, lw=0.5)
        ax.set_ylim(0, 1)
        if k % ncol == 0:
            ax.set_ylabel(r"$\chi_U(q)$  (dirty-tail co-movement)")
        if k // ncol == nrow - 1:
            ax.set_xlabel("tail quantile q")
    for k in range(len(pairs), nrow * ncol):  # hide unused axes
        axes[k // ncol][k % ncol].axis("off")
    axes[0][0].legend(frameon=False, fontsize=8, loc="upper left")
    fig.suptitle(f"Upper-tail dependence vs Gaussian benchmark - {args.region_set} "
                 "(residual CI, 2021-2025)\nshaded = structure the covariance DRO "
                 "cannot see", fontsize=11)
    for pth in _save(fig, f"tail_dependence_{args.region_set}"):
        print(f"  wrote {pth}")
    plt.close(fig)


if __name__ == "__main__":
    main()
