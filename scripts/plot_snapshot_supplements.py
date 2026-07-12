"""Build supplementary publication figures from archived aggregate snapshots.

These plots need no licensed raw inputs. They make the TeX sources buildable from
a clean public clone while keeping the plotted values tied to versioned CSVs.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

SNAP = Path("docs/results_snapshots")
FIG = Path("figures")
NAVY, GOLD, RUST, SAGE, CREAM = "#0c1e3e", "#b89535", "#8b3a0e", "#5d7a5a", "#faf7f0"
COLORS = {"us_west": NAVY, "taskc": GOLD, "us_hetero": RUST}
LABELS = {
    "us_west": "Western US",
    "taskc": "Eastern US–Canada",
    "us_hetero": "Diversified",
}


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times", "DejaVu Serif"],
            "font.size": 10,
            "axes.edgecolor": NAVY,
            "axes.labelcolor": NAVY,
            "axes.facecolor": CREAM,
            "figure.facecolor": CREAM,
            "savefig.facecolor": CREAM,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#c9bfa6",
            "grid.linestyle": ":",
            "grid.linewidth": 0.5,
        }
    )


def _save(fig: plt.Figure, stem: str) -> None:
    fig.tight_layout()
    fig.savefig(FIG / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{stem}.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_real_emergency() -> None:
    data = pd.read_csv(SNAP / "part3_real_emergency_2026-06-15.csv")
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for grid, group in data.groupby("grid", sort=False):
        group = group.sort_values("p")
        ax.errorbar(
            group["p"],
            group["mean"],
            yerr=group["std"],
            color=COLORS[grid],
            marker="o",
            capsize=3,
            linewidth=1.8,
            label=LABELS[grid],
        )
    ax.axhline(0, color="#444", linewidth=1)
    ax.set_xlabel("empirical emergency probability")
    ax.set_ylabel("robust gain vs risk-neutral (%)")
    ax.set_title("Observed-emergency stress test (mean ± one s.d.)", color=NAVY)
    ax.legend(frameon=False)
    _save(fig, "part3_real_emergency")


def plot_forecasts() -> None:
    data = pd.read_csv(SNAP / "part4_forecasts_2026-06-15.csv")
    forecasts = ["seasonal", "persistence", "lagged_week"]
    grids = ["us_west", "taskc", "us_hetero"]
    x = np.arange(len(forecasts))
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for offset, grid in zip((-0.22, 0, 0.22), grids):
        group = data[data.grid == grid].set_index("forecast").loc[forecasts]
        ax.errorbar(
            x + offset,
            group["mean"],
            yerr=group["std"],
            color=COLORS[grid],
            marker="o",
            linestyle="none",
            capsize=3,
            label=LABELS[grid],
        )
    ax.axhline(0, color="#444", linewidth=1)
    ax.set_xticks(x, ["Seasonal", "Persistence", "Lagged week"])
    ax.set_ylabel("robust gain vs deterministic (%)")
    ax.set_title("Forecast model sensitivity (mean ± one s.d.)", color=NAVY)
    ax.legend(frameon=False)
    _save(fig, "part4_forecasts")


def plot_kappa() -> None:
    data = pd.read_csv(SNAP / "part5_kappa_2026-06-15.csv")
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for grid, group in data.groupby("grid", sort=False):
        group = group.sort_values("kappa")
        ax.plot(
            group["kappa"],
            group["gap_pct"],
            "-o",
            color=COLORS[grid],
            linewidth=1.8,
            markersize=4,
            label=LABELS[grid],
        )
    ax.axhline(0, color="#444", linewidth=1)
    ax.set_xlabel("mean-flattening κ (1 = observed grid; 0 = mean-ablated)")
    ax.set_ylabel("spatial dependence gap (%)")
    ax.set_title("Dependence value emerges as mean differences flatten", color=NAVY)
    ax.legend(frameon=False)
    _save(fig, "part5_kappa")


def main() -> None:
    FIG.mkdir(exist_ok=True)
    _style()
    plot_real_emergency()
    plot_forecasts()
    plot_kappa()
    print("wrote part3_real_emergency, part4_forecasts, and part5_kappa figures")


if __name__ == "__main__":
    main()
