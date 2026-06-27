"""The DRO genuinely turns on: cross-validation CVaR vs. the ambiguity radius.

For each case, blocked 5-fold CV of the out-of-sample CVaR as a function of the
Wasserstein radius epsilon, for the joint and shuffled covariances. The minimum
sits at a non-trivial epsilon* (the DRO is active, not collapsed to the nominal
problem), and the joint and shuffled curves lie on top of each other (the spatial
null). This is the evidence behind the 'active null' framing.

Run: .venv\\Scripts\\python -m scripts.plot_cv_curve
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.analysis.metrics import cvar_upper_tail, per_day_emissions  # noqa: E402
from src.analysis.plotstyle import MUTED, NAVY, RUST, apply_style  # noqa: E402
from src.analysis.stratified_correlations import REGION_SETS  # noqa: E402
from src.data.electricitymaps import load_all_zones, to_wide  # noqa: E402
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro  # noqa: E402
from src.models.covariance import (  # noqa: E402
    block_diagonal_by_region, build_daily_panel, cholesky_factor,
    daily_panel_to_matrix, estimate_mean_and_covariance, regularize_covariance,
)

FIG = Path("figures")
CASES = ("us_west", "taskc", "us_hetero")
TITLE = {"us_west": "Western US", "taskc": "Eastern US–Canada", "us_hetero": "Diversified"}
EPS = [0.0, 0.1, 1.0, 10.0, 100.0, 1000.0]


def _folds(n, k=5):
    edges = np.linspace(0, n, k + 1).astype(int)
    out = []
    for i in range(k):
        val = np.arange(edges[i], edges[i + 1])
        fit = np.setdiff1d(np.arange(n), val)
        out.append((fit, val))
    return out


def cv_curve(train, shuffle, region_order):
    R, T = train.shape[1], train.shape[2]
    wl = np.full(R, 0.80 * 50.0 * T)
    ceil = np.full((R, T), 50.0)
    by_eps = {e: [] for e in EPS}
    for fit, val in _folds(len(train)):
        rho_bar = train[fit].mean(axis=0)
        _, sig = estimate_mean_and_covariance(daily_panel_to_matrix(train[fit]))
        if shuffle:
            sig = block_diagonal_by_region(sig, R=R, T=T)
        L = cholesky_factor(regularize_covariance(sig, eta=1e-5))
        for e in EPS:
            x = solve_mahalanobis_dro(rho_bar=rho_bar, L=L, workloads=wl, ceiling=ceil,
                                      epsilon=e, alpha=np.full(R, 0.5),
                                      ramp=np.full(R, 15.0),
                                      region_order=tuple(region_order)).schedule
            by_eps[e].append(cvar_upper_tail(per_day_emissions(x, train[val])))
    return np.array([np.mean(by_eps[e]) for e in EPS])


def main() -> None:
    apply_style()
    fig, axes = plt.subplots(1, 3, figsize=(13.6, 5.0), sharex=True,
                             constrained_layout=True)
    xs = np.arange(len(EPS))
    for ax, case in zip(axes, CASES):
        cfg = REGION_SETS[case]
        z = list(cfg["zones"])
        panel, dates = build_daily_panel(to_wide(load_all_zones(z)),
                                         region_order=z, tz=cfg["tz"])
        train = panel[np.array([d.year < 2025 for d in dates])]
        cj = cv_curve(train, False, z)
        cs = cv_curve(train, True, z)
        # normalize to the eps=0 (nominal) value, in %
        cj = 100 * (cj / cj[0] - 1)
        cs = 100 * (cs / cs[0] - 1)
        ax.plot(xs, cs, "--s", color=RUST, lw=1.8, ms=6, mfc="white",
                mec=RUST, mew=1.4, label="shuffled $\\Sigma$ (spatial null)",
                zorder=3)
        ax.plot(xs, cj, "-o", color=NAVY, lw=2.6, ms=6.5,
                label="joint $\\Sigma$", zorder=4)
        # mark the CV-optimal radius
        star = int(np.argmin(cj))
        ax.scatter([star], [cj[star]], s=240, facecolors="none",
                   edgecolors=NAVY, lw=2.2, zorder=6)
        ax.annotate("$\\varepsilon^\\star$", (star, cj[star]),
                    textcoords="offset points", xytext=(-11, 15),
                    ha="right", va="bottom", color=NAVY,
                    fontsize=15, fontweight="bold", zorder=7)
        ax.axhline(0, color=MUTED, lw=0.9, ls=(0, (1, 2)), zorder=1)
        ax.margins(x=0.06)
        ax.set_xticks(xs)
        ax.set_xticklabels([f"{e:g}" for e in EPS])
        ax.set_xlabel("Wasserstein radius $\\varepsilon$")
        ax.set_title(TITLE[case], pad=8)
        ax.grid(False, axis="x")

    axes[0].set_ylabel(
        "CV out-of-sample $\\mathrm{CVaR}_{0.95}$\n"
        "(% vs. nominal $\\varepsilon = 0$)")
    axes[0].legend(loc="upper left", frameon=False, handlelength=2.4,
                   borderaxespad=0.4, fontsize=11)

    fig.suptitle(
        "The DRO genuinely engages: CV selects a non-trivial $\\varepsilon^\\star$,\n"
        "and the joint and shuffled $\\Sigma$ curves coincide (the active null)",
        fontsize=15, fontweight="bold", color=NAVY)
    FIG.mkdir(exist_ok=True)
    for ext in ("pdf", "png"):
        p = FIG / f"cv_curve.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        print(f"  wrote {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
