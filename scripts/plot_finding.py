"""The Phase 1 finding in one figure: correlation is real, spatial value is zero
(but the covariance is masked, not worthless).

Panel A -- spatial gap vs. correlation strength. x = each case's mean residual
           cross-region correlation (hetero ~0 -> west/east ~0.5); y = the
           baseline spatial gap for all 9 (regime x alpha) cells. The cloud stays
           on zero across the whole correlation range: value does NOT track
           correlation. "Validity of the spatial assumption =/= value from it."
Panel B -- mean-ablation: the same gap in the real problem (~0) vs. the
           covariance-only world (mean removed). The covariance DOES carry
           value -- it is simply swamped by the mean field in the real problem.

Run: .venv\\Scripts\\python -m scripts.plot_finding
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.analysis.plotstyle import GOLD, MUTED, NAVY, SAGE, apply_style  # noqa: E402
from src.analysis.stratified_correlations import REGION_SETS  # noqa: E402
from src.analysis.tail_dependence import residualize_hour_of_day  # noqa: E402
from src.data.electricitymaps import load_all_zones, to_wide  # noqa: E402

CASES = ("us_hetero", "taskc", "us_west")
LABEL = {"us_hetero": "Diversified\n(solar/wind/hydro)", "taskc": "Eastern US–Canada\n(Ontario+belt)",
         "us_west": "Western US\n(CA/NV/AZ)"}
COLOR = {"us_hetero": SAGE, "taskc": GOLD, "us_west": NAVY}
RES = Path("results")
FIG = Path("figures")


def mean_residual_corr(case: str) -> float:
    cfg = REGION_SETS[case]
    wide = to_wide(load_all_zones(cfg["zones"]))[cfg["zones"]]
    c = residualize_hour_of_day(wide, cfg["tz"]).corr().to_numpy()
    iu = np.triu_indices_from(c, k=1)
    return float(np.mean(c[iu]))


def main() -> None:
    apply_style()
    FIG.mkdir(parents=True, exist_ok=True)
    # readable annotation sizes that survive embedding at ~0.75 text width
    NOTE = 11
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13.5, 5.8), constrained_layout=True)
    fig.set_constrained_layout_pads(w_pad=0.12, h_pad=0.06, wspace=0.04)

    # --- Panel A: gap vs correlation strength ---
    for case in CASES:
        x = mean_residual_corr(case)
        gp = pd.read_csv(RES / f"{case}_regimes_2026-06-10.csv")["gap_pct"].to_numpy()
        axA.scatter(np.full_like(gp, x), gp, color=COLOR[case], s=58, alpha=0.9,
                    edgecolors="white", linewidths=0.6, zorder=3,
                    label=LABEL[case].replace("\n", " "))
    axA.axhspan(-0.05, 0.05, color=SAGE, alpha=0.10, zorder=0)
    axA.axhline(0, color=MUTED, lw=1.1, zorder=1)
    # band label parked in the empty left edge, inside the band, off the data
    axA.text(-0.03, 0.031, "no-value band  ($\\pm0.05\\%$)", ha="left", va="center",
             fontsize=NOTE - 0.5, color=MUTED)
    # takeaway: high correlation, still zero value (points to the right-hand clusters)
    axA.annotate("correlation reaches $0.5$,\nspatial value stays at $0$",
                 xy=(0.52, 0.005), xytext=(0.40, -0.135), ha="center", va="top",
                 fontsize=NOTE, color=NAVY,
                 arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.2,
                                 connectionstyle="arc3,rad=-0.15"))
    # the low-correlation case has the largest spread (and can go negative)
    axA.annotate("low correlation, largest spread:\njoint covariance can even hurt",
                 xy=(0.219, -0.205), xytext=(0.255, -0.185), ha="left", va="center",
                 fontsize=NOTE, color=SAGE,
                 arrowprops=dict(arrowstyle="->", color=SAGE, lw=1.1))
    axA.set_xlim(-0.06, 0.66)
    axA.set_ylim(-0.27, 0.10)
    axA.set_xlabel("mean residual cross-region correlation  (weak $\\rightarrow$ strong)")
    axA.set_ylabel("spatial gap (shuf $-$ joint) $\\mathrm{CVaR}_{0.95}$  [%]")
    axA.set_title("A. Spatial value does not track correlation")
    axA.legend(loc="lower right", fontsize=NOTE, handletextpad=0.4,
               borderaxespad=0.6, labelspacing=0.5)

    # --- Panel B: mean-ablation (real vs covariance-only) ---
    xs = np.arange(len(CASES))
    real, cov_only = [], []
    for case in CASES:
        real.append(pd.read_csv(RES / f"{case}_regimes_2026-06-10.csv")["gap_pct"].abs().median())
        f = RES / f"{case}_regimes_2026-06-10_ablate-flat.csv"
        cov_only.append(pd.read_csv(f)["gap_pct"].clip(lower=0).max())
    axB.bar(xs - 0.2, real, 0.4, label="real problem (mean present)",
            color="0.78", edgecolor="white", linewidth=0.6, zorder=2)
    axB.bar(xs + 0.2, cov_only, 0.4, label="covariance-only (mean removed)",
            color=[COLOR[c] for c in CASES], edgecolor="white", linewidth=0.6,
            zorder=2)
    for i, (r, c) in enumerate(zip(real, cov_only)):
        axB.text(i - 0.2, r + 0.03, f"{r:.2f}", ha="center", va="bottom",
                 fontsize=NOTE, color=MUTED)
        axB.text(i + 0.2, c + 0.03, f"{c:.2f}", ha="center", va="bottom",
                 fontsize=NOTE, color=COLOR[CASES[i]])
    axB.set_xticks(xs)
    axB.set_xticklabels([LABEL[c] for c in CASES], fontsize=NOTE)
    axB.set_ylim(0, 1.65)
    axB.set_ylabel("spatial gap $\\mathrm{CVaR}_{0.95}$  [%]")
    axB.set_title("B. The covariance is masked, not worthless\n"
                  "remove the mean field, and joint covariance pays off")
    axB.legend(loc="upper right", fontsize=NOTE, handletextpad=0.5,
               borderaxespad=0.6, labelspacing=0.5)
    axB.annotate("Western US exception:\nstrong common-mode correlation,\n"
                 "no value even in isolation",
                 xy=(2.2, 0.05), xytext=(1.62, 0.62), ha="center", va="center",
                 fontsize=NOTE, color=NAVY,
                 arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.1,
                                 connectionstyle="arc3,rad=0.2"))

    fig.suptitle("Carbon correlation is real, but adds no robust scheduling value: "
                 "the mean field dominates", fontsize=16, fontweight="bold")
    for ext in ("pdf", "png"):
        p = FIG / f"finding.{ext}"
        fig.savefig(p, dpi=300)
        print(f"  wrote {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
