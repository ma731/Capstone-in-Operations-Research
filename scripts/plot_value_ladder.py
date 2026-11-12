"""The one-glance figure for the README: what each layer of sophistication buys.

Every number is read from an archived snapshot in docs/results_snapshots/, so the
figure cannot drift from the results. Run from the repo root:

    python scripts/plot_value_ladder.py
"""
import csv
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "docs" / "results_snapshots"
OUT = ROOT / "figures"

GRIDS = [("us_west", "Western US"), ("taskc", "Eastern US-Canada"), ("us_hetero", "Diversified")]


def rows(name):
    with open(SNAP / name, newline="") as f:
        return list(csv.DictReader(f))


def main():
    rq1 = {r["grid"]: float(r["reduction_pct"]) for r in rows("part3_transfer_value_2026-06-15.csv")}
    rq2 = {g: max(abs(float(r["gap_pct"])) for r in rows(f"{g}_regimes_2026-06-10.csv") if r["gap_pct"])
           for g, _ in GRIDS}
    sev = [float(r["severity"]) for r in rows("carbon_ceiling_2026-06-24.csv") if r["kind"] == "joint"]

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2), gridspec_kw={"width_ratios": [1, 1, 1.05]})
    green, grey, amber = "#2f6b3c", "#9a948a", "#b5651d"
    labels = [n for _, n in GRIDS]

    ax = axes[0]
    vals = [rq1[g] for g, _ in GRIDS]
    ax.barh(labels, vals, color=green)
    for i, v in enumerate(vals):
        ax.text(v + 0.2, i, f"{v:.1f}%", va="center", fontsize=11, fontweight="bold", color=green)
    ax.set_xlim(0, 12)
    ax.set_title("1. Move jobs between regions\nPAYS", loc="left", fontsize=12, fontweight="bold", color=green)
    ax.set_xlabel("cut in worst-day emissions (CVaR 95%)")

    ax = axes[1]
    vals = [rq2[g] for g, _ in GRIDS]
    ax.barh(labels, vals, color=grey)
    ax.axvline(0.4, color="#58544b", ls="--", lw=1)
    ax.text(0.42, -0.62, "0.4% materiality margin", fontsize=8.5, color="#58544b", va="center")
    for i, v in enumerate(vals):
        ax.text(max(v, 0.4) + 0.03, i, f"{v:.2f}%", va="center", fontsize=11, color="#58544b")
    ax.set_xlim(0, 1.2)
    ax.set_ylim(-0.85, 2.5)
    ax.set_yticklabels([])
    ax.set_title("2. Model regional co-movement\nABOUT ZERO", loc="left", fontsize=12, fontweight="bold", color="#58544b")
    ax.set_xlabel("largest gap vs. ignoring co-movement")

    ax = axes[2]
    lo, hi = min(sev), max(sev)
    ax.axvspan(lo, hi, color=amber, alpha=0.25)
    ax.text((lo + hi) / 2, 0.82, f"real joint grids\n{lo:.2f}x to {hi:.2f}x", ha="center", fontsize=9.5, color=amber)
    ax.axvline(3.0, color=amber, lw=2)
    ax.text(3.05, 0.35, "robustness starts\nto pay (~3x)", fontsize=9.5, color=amber)
    ax.set_xlim(1, 4)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_title("3. Hedge with robust optimisation\nONLY IN EXTREME EMERGENCIES", loc="left", fontsize=12, fontweight="bold", color=amber)
    ax.set_xlabel("grid-emergency severity (carbon spike multiple)")

    for ax in axes:
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    fig.suptitle("The price of sophistication: one layer pays, two mostly do not",
                 x=0.01, ha="left", fontsize=14, fontweight="bold")
    fig.subplots_adjust(left=0.11, right=0.98, top=0.74, bottom=0.17, wspace=0.3)
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / "value_ladder.svg")
    fig.savefig(OUT / "value_ladder.png", dpi=180)
    print(f"RQ1 {rq1} | RQ2 max |gap| {rq2} | RQ3 joint severity {lo:.2f}-{hi:.2f}")


if __name__ == "__main__":
    main()
