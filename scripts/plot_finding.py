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

from src.analysis.stratified_correlations import REGION_SETS  # noqa: E402
from src.analysis.tail_dependence import residualize_hour_of_day  # noqa: E402
from src.data.electricitymaps import load_all_zones, to_wide  # noqa: E402

CASES = ("us_hetero", "taskc", "us_west")
LABEL = {"us_hetero": "us_hetero\n(solar/wind/hydro)", "taskc": "taskc\n(Ontario+belt)",
         "us_west": "us_west\n(CA/NV/AZ)"}
COLOR = {"us_hetero": "C2", "taskc": "C1", "us_west": "C0"}
RES = Path("results")
FIG = Path("figures")


def mean_residual_corr(case: str) -> float:
    cfg = REGION_SETS[case]
    wide = to_wide(load_all_zones(cfg["zones"]))[cfg["zones"]]
    c = residualize_hour_of_day(wide, cfg["tz"]).corr().to_numpy()
    iu = np.triu_indices_from(c, k=1)
    return float(np.mean(c[iu]))


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13, 5.2))

    # --- Panel A: gap vs correlation strength ---
    for case in CASES:
        x = mean_residual_corr(case)
        gp = pd.read_csv(RES / f"{case}_regimes_2026-06-10.csv")["gap_pct"].to_numpy()
        axA.scatter(np.full_like(gp, x), gp, color=COLOR[case], s=40, alpha=0.85,
                    zorder=3, label=LABEL[case].replace("\n", " "))
    axA.axhline(0, color="0.3", lw=1.2, zorder=1)
    axA.axhspan(-0.05, 0.05, color="0.82", alpha=0.6, zorder=0)
    axA.text(0.62, 0.02, "no-value band\n($\\pm$0.05%)", ha="right", va="bottom",
             fontsize=7.5, color="0.4")
    axA.annotate("correlation spans 0 $\\rightarrow$ 0.5,\nvalue stays at 0",
                 xy=(0.30, 0.0), xytext=(0.30, -0.15), ha="center", fontsize=8.5,
                 color="navy", arrowprops=dict(arrowstyle="->", color="navy", lw=1))
    axA.text(0.12, -0.21, "negative = joint\ncovariance hurts", fontsize=7,
             color="C2", ha="center")
    axA.set_xlim(-0.05, 0.65)
    axA.set_xlabel("mean residual cross-region correlation  (weak $\\rightarrow$ strong)")
    axA.set_ylabel("spatial gap (shuf $-$ joint) $\\mathrm{CVaR}_{0.95}$  [%]")
    axA.set_title("A. Spatial value does NOT track correlation", fontsize=10)
    axA.legend(frameon=False, fontsize=8, loc="lower right")
    axA.grid(alpha=0.3, lw=0.5)

    # --- Panel B: mean-ablation (real vs covariance-only) ---
    xs = np.arange(len(CASES))
    real, cov_only = [], []
    for case in CASES:
        real.append(pd.read_csv(RES / f"{case}_regimes_2026-06-10.csv")["gap_pct"].abs().median())
        f = RES / f"{case}_regimes_2026-06-10_ablate-flat.csv"
        cov_only.append(pd.read_csv(f)["gap_pct"].clip(lower=0).max())
    axB.bar(xs - 0.2, real, 0.4, label="real problem (mean present)", color="0.6")
    axB.bar(xs + 0.2, cov_only, 0.4, label="covariance-only (mean removed)",
            color=[COLOR[c] for c in CASES])
    for i, (r, c) in enumerate(zip(real, cov_only)):
        axB.text(i - 0.2, r + 0.02, f"{r:.2f}", ha="center", fontsize=8)
        axB.text(i + 0.2, c + 0.02, f"{c:.2f}", ha="center", fontsize=8)
    axB.set_xticks(xs)
    axB.set_xticklabels([c.replace("\n", " ") for c in (LABEL[c] for c in CASES)], fontsize=8)
    axB.set_ylabel("spatial gap $\\mathrm{CVaR}_{0.95}$  [%]")
    axB.set_title("B. The covariance is masked, not worthless\n"
                  "(remove the mean $\\rightarrow$ joint covariance pays off)", fontsize=10)
    axB.legend(frameon=False, fontsize=8, loc="upper right")
    axB.grid(alpha=0.3, axis="y", lw=0.5)
    axB.annotate("us_west exception:\nstrong common-mode corr,\nno value even isolated",
                 xy=(2.2, 0.02), xytext=(1.55, 0.9), fontsize=7, color="C0",
                 arrowprops=dict(arrowstyle="->", color="C0", lw=0.8))

    fig.suptitle("Phase 1: carbon correlation is real, but adds no robust scheduling "
                 "value — because the mean field dominates", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    for ext in ("pdf", "png"):
        p = FIG / f"finding.{ext}"
        fig.savefig(p, dpi=200, bbox_inches="tight")
        print(f"  wrote {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
