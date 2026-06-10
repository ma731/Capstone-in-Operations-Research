"""Combined three-case summary figure: the whole Phase 1 spatial story on one page.

Panel A -- Spatial gap (shuf - joint) CVaR_0.95 with bootstrap 95% CI, every
           (case, regime, alpha) cell. All clustered on zero = the replicated
           null: joint covariance adds no robust scheduling value, anywhere on
           the correlation spectrum.
Panel B -- Upper-tail-dependence excess (empirical - Gaussian) per region pair.
           At or below zero = no dirty-tail co-movement the covariance DRO misses.
Panel C -- chi_L vs chi_U scatter. Points above the diagonal = regions go CLEAN
           together more than DIRTY together (radial asymmetry) -- non-elliptical
           structure a covariance/Mahalanobis-Wasserstein ball cannot represent.

Reads the latest baseline results/<case>_regimes_<date>.csv per case (no
residualize/shrinkage suffix) and computes tail tables live from the raw panels.

Run: .venv\\Scripts\\python -m scripts.plot_case_summary
"""
from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.analysis.stratified_correlations import REGION_SETS  # noqa: E402
from src.analysis.tail_dependence import (  # noqa: E402
    residualize_hour_of_day,
    tail_dependence_table,
)
from src.data.electricitymaps import load_all_zones, to_wide  # noqa: E402

CASES = ("us_west", "taskc", "us_hetero")
LABELS = {"us_west": "us_west (CA/NV/AZ)", "taskc": "taskc (Ontario+belt)",
          "us_hetero": "us_hetero (solar/wind/hydro)"}
COLORS = {"us_west": "C0", "taskc": "C1", "us_hetero": "C2"}
RESULTS = Path("results")
FIGDIR = Path("figures")


def _latest_baseline_csv(case: str) -> Path | None:
    # baseline = <case>_regimes_<date>.csv with no _seasonal/_ar1/_lw/_R* suffix
    pat = re.compile(rf"^{case}_regimes_\d{{4}}-\d{{2}}-\d{{2}}\.csv$")
    cands = sorted([p for p in RESULTS.glob(f"{case}_regimes_*.csv") if pat.match(p.name)])
    return cands[-1] if cands else None


def main() -> None:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

    # --- Panel A: spatial gap +- CI (CI is absolute; convert to % of shuf_CVaR
    #     to match gap_pct) ---
    ax = axes[0]
    xpos = 0
    for case in CASES:
        csv = _latest_baseline_csv(case)
        if csv is None:
            continue
        df = pd.read_csv(csv)
        gp = df["gap_pct"].to_numpy()
        lo = (df["gap_ci_lo"] / df["shuf_CVaR"] * 100).to_numpy()
        hi = (df["gap_ci_hi"] / df["shuf_CVaR"] * 100).to_numpy()
        xs = np.arange(xpos, xpos + len(df))
        ax.errorbar(xs, gp, yerr=[gp - lo, hi - gp], fmt="o", ms=4,
                    color=COLORS[case], ecolor=COLORS[case], elinewidth=1,
                    capsize=2, label=LABELS[case])
        xpos += len(df) + 1
    ax.axhline(0, color="0.3", lw=1)
    ax.set_ylabel("spatial gap (shuf - joint) CVaR$_{0.95}$  [% of shuf]")
    ax.set_title("A. Spatial value of the joint covariance\n(all cells on zero = the null)",
                 fontsize=10)
    ax.set_xticks([])
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    ax.grid(alpha=0.3, axis="y", lw=0.5)

    # --- Panels B & C: tail dependence (computed live, residual series) ---
    axB, axC = axes[1], axes[2]
    for case in CASES:
        cfg = REGION_SETS[case]
        zones, tz = cfg["zones"], cfg["tz"]
        wide = to_wide(load_all_zones(zones))[zones]
        resid = residualize_hour_of_day(wide, tz)
        tbl = tail_dependence_table(resid, q=0.95)
        x = np.arange(len(tbl))
        axB.scatter(x * 0 + CASES.index(case), tbl["chi_U_excess"],
                    color=COLORS[case], alpha=0.7, s=28)
        axC.scatter(tbl["chi_U_emp"], tbl["chi_L_emp"],
                    color=COLORS[case], alpha=0.75, s=30, label=LABELS[case])

    axB.axhline(0, color="0.3", lw=1)
    axB.set_xticks(range(len(CASES)))
    axB.set_xticklabels([c.replace("us_", "") for c in CASES], fontsize=8)
    axB.set_ylabel(r"$\chi_U$ excess (empirical $-$ Gaussian)")
    axB.set_title("B. Dirty-tail co-movement the DRO misses\n(<= 0 = nothing missed)",
                  fontsize=10)
    axB.grid(alpha=0.3, axis="y", lw=0.5)

    lim = 0.6
    axC.plot([0, lim], [0, lim], color="0.5", ls="--", lw=1)
    axC.set_xlim(0, lim); axC.set_ylim(0, lim)
    axC.set_xlabel(r"$\chi_U$  (dirty together)")
    axC.set_ylabel(r"$\chi_L$  (clean together)")
    axC.set_title("C. Radial asymmetry (above line = non-elliptical)\nclean-together "
                  "> dirty-together", fontsize=10)
    axC.legend(frameon=False, fontsize=7, loc="lower right")
    axC.grid(alpha=0.3, lw=0.5)

    fig.suptitle("Phase 1 spatial-DRO summary: covariance adds no value (A); "
                 "the tails are non-elliptical, not covariance-shaped (B, C)",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    for ext in ("pdf", "png"):
        p = FIGDIR / f"case_summary.{ext}"
        fig.savefig(p, dpi=200, bbox_inches="tight")
        print(f"  wrote {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
