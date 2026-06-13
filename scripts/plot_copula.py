"""Phase 2 figures: (1) the copula the covariance ball cannot represent, and
(2) the result -- even that copula recovers no scheduling value.

Run: .venv\\Scripts\\python -m scripts.plot_copula
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.analysis.stratified_correlations import REGION_SETS  # noqa: E402
from src.data.electricitymaps import load_all_zones, to_wide  # noqa: E402
from src.models.copula_scenarios import fit_copula, sample_uniforms  # noqa: E402
from src.models.covariance import build_daily_panel  # noqa: E402

FIG = Path("figures")
RES = Path("results")
STAMP = "2026-06-13"
NAVY, GOLD, RUST, SAGE = "#1f3b63", "#E69F00", "#b3402f", "#4a7c59"
CASES = ("us_west", "taskc", "us_hetero")
LABEL = {"us_west": "us_west\n(CA/NV/AZ, $\\tau$=0.47)",
         "taskc": "taskc\n(Ontario belt, $\\tau$=0.31)",
         "us_hetero": "us_hetero\n(solar/wind/hydro, $\\tau$=0.20)"}


def _save(fig, stem):
    FIG.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        p = FIG / f"{stem}.{ext}"
        fig.savefig(p, dpi=200, bbox_inches="tight")
        print(f"  wrote {p}")
    plt.close(fig)


def _chi_lower(u, v, p):
    return np.mean((u < p) & (v < p)) / p


def _chi_upper(u, v, q):
    return np.mean((u > q) & (v > q)) / (1 - q)


def fig_copula_density(case="us_west"):
    """Gaussian vs Clayton copula samples for a representative region pair.
    Clayton clusters in the lower-left (joint clean days) -- the radial asymmetry
    chi_L > chi_U that an elliptical covariance ball forces to zero."""
    cfg = REGION_SETS[case]
    zones = list(cfg["zones"])
    wide = to_wide(load_all_zones(zones))
    panel, _ = build_daily_panel(wide, region_order=zones, tz=cfg["tz"])
    ga = fit_copula("gaussian", panel)
    cl = fit_copula("clayton", panel)
    rng = np.random.default_rng(7)
    ug = sample_uniforms(ga, 4000, rng)
    uc = sample_uniforms(cl, 4000, np.random.default_rng(7))

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 5.1))
    for ax, u, name, col in ((axes[0], ug, "Gaussian copula", NAVY),
                             (axes[1], uc, "Clayton copula", RUST)):
        ax.scatter(u[:, 0], u[:, 1], s=6, alpha=0.35, color=col, edgecolors="none")
        ax.add_patch(plt.Rectangle((0, 0), 0.1, 0.1, fill=False, ec=SAGE, lw=1.6, zorder=5))
        ax.add_patch(plt.Rectangle((0.9, 0.9), 0.1, 0.1, fill=False, ec=GOLD, lw=1.6, zorder=5))
        cl_, cu_ = _chi_lower(u[:, 0], u[:, 1], 0.1), _chi_upper(u[:, 0], u[:, 1], 0.9)
        ax.set_title(f"{name}\n$\\chi_L$={cl_:.2f} (clean)   $\\chi_U$={cu_:.2f} (dirty)",
                     fontsize=10)
        ax.set_xlabel(f"rank, {zones[0].split('-')[-1]}")
        ax.set_ylabel(f"rank, {zones[1].split('-')[-1]}")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect("equal")
    axes[0].text(0.05, 0.93, "clean\ncorner", color=SAGE, fontsize=7.5, ha="left", va="top")
    axes[1].annotate("Clayton piles into the clean\ncorner: regions go clean\ntogether ($\\chi_L>\\chi_U$)",
                     xy=(0.08, 0.08), xytext=(0.42, 0.30), fontsize=8, color=RUST,
                     arrowprops=dict(arrowstyle="->", color=RUST, lw=1))
    fig.suptitle("The dependence object a covariance ball cannot represent: "
                 "elliptical (symmetric) vs. lower-tail copula", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    _save(fig, "copula_density")


def fig_phase2_result():
    """Even the right copula recovers no value: gap vs independence for Gaussian
    and Clayton arms across the three cases, with the no-value band."""
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(12.5, 5.0))
    x = np.arange(len(CASES))
    w = 0.36
    gauss_means, clay_means, cvg = [], [], []
    for c in CASES:
        df = pd.read_csv(RES / f"{c}_copula_{STAMP}.csv")
        gauss_means.append(df.gap_gauss_pct.abs().max())
        clay_means.append(df.gap_clayton_pct.abs().max())
        cvg.append(df.gap_clayton_vs_gauss_pct.mean())

    # Panel A: max |gap| vs independence -- both arms flat against the no-value band
    axA.axhspan(0, 0.1, color="0.85", alpha=0.7, zorder=0)
    axA.bar(x - w / 2, gauss_means, w, color=NAVY, label="Gaussian copula")
    axA.bar(x + w / 2, clay_means, w, color=RUST, label="Clayton copula (lower-tail)")
    for i, (g, c) in enumerate(zip(gauss_means, clay_means)):
        axA.text(i - w / 2, g + 0.005, f"{g:.2f}", ha="center", fontsize=8)
        axA.text(i + w / 2, c + 0.005, f"{c:.2f}", ha="center", fontsize=8)
    axA.text(2.3, 0.06, "no-value band\n($<0.1\\%$)", color="0.4", fontsize=8, ha="right")
    axA.set_xticks(x)
    axA.set_xticklabels([LABEL[c] for c in CASES], fontsize=8)
    axA.set_ylabel("max $|$gap vs independence$|$  $\\mathrm{CVaR}_{0.95}$  [%]")
    axA.set_title("A. Neither copula beats independence\n(spatial value still null)", fontsize=10)
    axA.legend(frameon=False, fontsize=8.5, loc="upper left")
    axA.grid(alpha=0.3, axis="y", lw=0.5)

    # Panel B: Clayton minus Gaussian -- the faint asymmetry signal, by case tau
    taus = [0.47, 0.31, 0.20]
    colors = [SAGE if v > 0 else GOLD for v in cvg]
    axB.bar(x, cvg, 0.5, color=colors)
    for i, v in enumerate(cvg):
        axB.text(i, v + (0.004 if v >= 0 else -0.008), f"{v:+.3f}", ha="center",
                 va="bottom" if v >= 0 else "top", fontsize=8.5)
    axB.axhline(0, color="0.3", lw=1)
    axB.set_xticks(x)
    axB.set_xticklabels([f"{c}\n$\\tau$={t}" for c, t in zip(CASES, taus)], fontsize=8)
    axB.set_ylabel("mean (Clayton $-$ Gaussian) gap  [%]")
    axB.set_title("B. The copula DOES capture asymmetry\n"
                  "(Clayton edges Gaussian where dependence is heterogeneous)", fontsize=10)
    axB.grid(alpha=0.3, axis="y", lw=0.5)
    axB.annotate("positive = lower-tail copula\nhelps more than elliptical\n(but immaterial: $<0.1\\%$)",
                 xy=(2, cvg[2]), xytext=(0.7, max(cvg) * 0.75 + 0.02), fontsize=7.5,
                 color=SAGE, arrowprops=dict(arrowstyle="->", color=SAGE, lw=0.9))

    fig.suptitle("Phase 2: even a copula built for the $\\chi_L>\\chi_U$ structure "
                 "recovers no material scheduling value — the mean field dominates",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    _save(fig, "copula_result")


def main():
    fig_copula_density("us_west")
    fig_phase2_result()


if __name__ == "__main__":
    main()
