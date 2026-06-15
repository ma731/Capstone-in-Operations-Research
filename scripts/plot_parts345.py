"""plot_parts345.py -- house-style figures for Parts 3, 4, 5 of the extended thesis.

Reads the archived snapshots and writes:
  figures/part3_crossover.pdf  -- robust gain vs emergency severity, with 95% CI bands
  figures/part4_online.pdf     -- closed-loop robust-vs-deterministic CVaR gap, with CIs
  figures/part5_delta.pdf      -- the mean-dominance ratio Delta along the flattening sweep
"""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

SNAP, FIG = Path("docs/results_snapshots"), Path("figures")
FIG.mkdir(exist_ok=True)
NAVY, GOLD, RUST, SAGE, CREAM = "#0c1e3e", "#b89535", "#8b3a0e", "#5d7a5a", "#faf7f0"
GRIDCOL = {"us_west": NAVY, "taskc": GOLD, "us_hetero": RUST}
GNAME = {"us_west": "Western US", "taskc": "Eastern US--Canada", "us_hetero": "Diversified"}
GLAB = {"us_west": "Western US", "taskc": "Eastern US-Canada", "us_hetero": "Diversified"}

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times", "DejaVu Serif"], "font.size": 10,
    "axes.edgecolor": NAVY, "axes.labelcolor": NAVY, "xtick.color": "#5a5a5a",
    "ytick.color": "#5a5a5a", "axes.facecolor": CREAM, "figure.facecolor": CREAM,
    "savefig.facecolor": CREAM, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#c9bfa6", "grid.linestyle": ":", "grid.linewidth": 0.5,
})


def _latest(stem):
    return sorted(glob.glob(str(SNAP / f"{stem}_*.csv")))[-1]


def part3():
    df = pd.read_csv(_latest("part3_emergency"))
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for g in ["us_west", "taskc", "us_hetero"]:
        d = df[df.grid == g].sort_values("M")
        c = GRIDCOL[g]
        ax.plot(d.M, d.gain_pct, "-o", color=c, ms=4, lw=1.8, label=GLAB[g], zorder=3)
        ax.fill_between(d.M, d.ci_lo, d.ci_hi, color=c, alpha=0.12, zorder=1)
        sig = d[d.significant]
        if len(sig):
            mstar = sig.M.min()
            ax.axvline(mstar, color=c, ls=":", lw=1, alpha=0.5)
    ax.axhline(0, color="#444", lw=1)
    ax.set_xlabel("emergency severity $M$ (carbon multiplier)")
    ax.set_ylabel("robust gain vs risk-neutral (% of CVaR$_{0.95}$)")
    ax.set_title("Part 3: the tail-risk crossover (bands = 95% bootstrap CI)",
                 color=NAVY, fontsize=12, pad=8)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.text(0.98, 0.03, "robustness pays only past a grid-specific\nseverity $M^\\star$"
            " (dotted lines)", transform=ax.transAxes, ha="right", va="bottom",
            fontsize=8.5, style="italic", color="#444")
    plt.tight_layout(); plt.savefig(FIG / "part3_crossover.pdf", bbox_inches="tight")
    plt.savefig(FIG / "part3_crossover.png", dpi=150, bbox_inches="tight"); plt.close()


def part4():
    df = pd.read_csv(_latest("part4_online")).set_index("grid")
    grids = ["us_west", "taskc", "us_hetero"]
    x = np.arange(len(grids)); w = 0.36
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    det = [df.loc[g, "det_cvar"] / 1e6 for g in grids]
    rob = [df.loc[g, "rob_cvar"] / 1e6 for g in grids]
    ax.bar(x - w/2, det, w, color=NAVY, label="deterministic (point forecast)")
    ax.bar(x + w/2, rob, w, color=GOLD, label="robust (CVaR over forecast error)")
    for i, g in enumerate(grids):
        gap, lo, hi = df.loc[g, "cvar_gap_pct"], df.loc[g, "ci_lo"], df.loc[g, "ci_hi"]
        verdict = "null" if lo <= 0 <= hi else ("robust wins" if lo > 0 else "robust loses")
        ax.text(i, max(det[i], rob[i]) + 0.03,
                f"gap {gap:+.2f}%\n[{lo:.2f},{hi:.2f}]\n{verdict}",
                ha="center", va="bottom", fontsize=7.8, color="#333")
    ax.set_xticks(x); ax.set_xticklabels([GLAB[g] for g in grids])
    ax.set_ylabel("realised CVaR$_{0.95}$ (MtCO2-eq, scaled)")
    ax.set_ylim(0, max(det + rob) * 1.28)
    ax.set_title("Part 4: online closed-loop, robust vs deterministic",
                 color=NAVY, fontsize=12, pad=8)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    plt.tight_layout(); plt.savefig(FIG / "part4_online.pdf", bbox_inches="tight")
    plt.savefig(FIG / "part4_online.png", dpi=150, bbox_inches="tight"); plt.close()


def part5():
    sw = pd.read_csv(_latest("part5_sweep"))
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for g in ["us_west", "taskc", "us_hetero"]:
        d = sw[sw.grid == g].sort_values("kappa")
        ax.plot(d.kappa, d.Delta, "-o", color=GRIDCOL[g], ms=4, lw=1.8, label=GLAB[g])
    ax.axhspan(0, 1, color=SAGE, alpha=0.10)
    ax.text(0.97, 0.7, "$\\Delta<1$:\ndependence\nprovably\nimmaterial",
            transform=ax.transAxes, ha="right", fontsize=8, color=SAGE)
    ax.set_xlabel("mean-flattening $\\kappa$  (1 = real grid $\\to$ 0 = mean-ablated)")
    ax.set_ylabel("mean-dominance ratio $\\Delta = B/M$")
    ax.invert_xaxis()
    ax.set_title("Part 5: $\\Delta$ rises as the mean flattens (regime indicator)",
                 color=NAVY, fontsize=12, pad=8)
    ax.annotate("dependence value:\n~0 at $\\kappa{=}1$,  +1.46% as $\\kappa{\\to}0$",
                xy=(0.1, sw[sw.grid=="taskc"].sort_values("kappa").Delta.iloc[1]),
                xytext=(0.45, 45), fontsize=8.5, color="#444", style="italic",
                arrowprops=dict(arrowstyle="->", color="#888", lw=0.8))
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    plt.tight_layout(); plt.savefig(FIG / "part5_delta.pdf", bbox_inches="tight")
    plt.savefig(FIG / "part5_delta.png", dpi=150, bbox_inches="tight"); plt.close()


if __name__ == "__main__":
    part3(); part4(); part5()
    print("wrote figures/part3_crossover.pdf, part4_online.pdf, part5_delta.pdf")
