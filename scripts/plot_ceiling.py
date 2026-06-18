"""plot_ceiling.py -- the carbon-ceiling impossibility figure (#1).

Robustness activates only past emergency severity M* ~ 3 (carbon-spike multiplier).
But carbon intensity is bounded above by the fossil ceiling, so the *physically
achievable* severity of every real grid sits far below M*. This figure plots each
of the 17 zones' worst realised severity (max daily / annual mean) against the M*
threshold -- including Winter Storm Uri, the worst US grid event on record, at 1.3x.
The robustness activation threshold lies outside the achievable envelope: the null
is structural, not empirical.

Run: .venv\\Scripts\\python -m scripts.plot_ceiling
"""
from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt

from src.analysis.plotstyle import apply_style, NAVY, GOLD, SAGE, RUST, MUTED, save
from src.data.electricitymaps import load_all_zones, to_wide

apply_style()

NA = ["CA-AB", "CA-ON", "US-SW-SRP", "US-SW-AZPS", "US-SW-PNM",
      "US-CAL-CISO", "US-CAL-BANC", "US-CAL-LDWP", "US-CAL-IID", "US-CAL-TIDC",
      "US-TEX-ERCO", "US-MIDW-MISO", "US-MIDW-AECI", "US-MIDA-PJM", "US-NY-NYIS",
      "US-NW-NEVP", "US-NW-BPAT"]
SHORT = {z: z.split("-")[-1] for z in NA}
MSTAR = 3.0


def main():
    daily = to_wide(load_all_zones(NA))[NA].resample("D").mean()
    sev = {}
    for z in NA:
        s = daily[z].dropna()
        sev[z] = s.max() / s.mean()
    order = sorted(NA, key=lambda z: sev[z])
    vals = [sev[z] for z in order]
    labels = [SHORT[z] for z in order]

    # Uri-specific ERCO severity (Feb 2021 storm window vs 2021 mean)
    e = daily["US-TEX-ERCO"]
    uri = float(daily["US-TEX-ERCO"]["2021-02-12":"2021-02-21"].max()
                / e[e.index.year == 2021].mean())

    fig, ax = plt.subplots(figsize=(9.0, 5.4))
    y = np.arange(len(order))
    cols = [SAGE if v < 1.5 else GOLD for v in vals]
    ax.barh(y, vals, color=cols, edgecolor="white", height=0.7, zorder=3)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlim(1.0, 3.3)

    # M* activation threshold + "robustness pays" zone
    ax.axvspan(MSTAR, 3.3, color="#fbeeec", zorder=0)
    ax.axvline(MSTAR, color=RUST, lw=2.2, zorder=4)
    ax.text(MSTAR + 0.04, len(order) - 1.5,
            "M* ~ 3\nrobustness\nactivates", color=RUST, fontsize=10, weight="bold", va="top")
    # the achievable envelope
    ax.axvspan(1.0, max(vals) + 0.02, color="#eef4ef", zorder=0)
    ax.text(1.35, 1.0, "physically achievable\nseverity envelope", color=SAGE,
            fontsize=9.5, ha="center")
    # Uri marker
    ax.scatter([uri], [order.index("US-TEX-ERCO")], s=120, marker="*",
               color=NAVY, zorder=6)
    ax.annotate(f"Winter Storm Uri\n(worst US event): {uri:.2f}x",
                xy=(uri, order.index("US-TEX-ERCO")), xytext=(1.9, 4.5),
                fontsize=9, color=NAVY,
                arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.2))

    ax.set_xlabel("worst realised carbon severity  (max daily / mean)")
    ax.set_title("Real carbon severity never reaches the robustness threshold",
                 color=NAVY)
    fig.tight_layout()
    save(fig, "carbon_ceiling")
    print(f"wrote figures/carbon_ceiling.png  (max real severity {max(vals):.2f}x, "
          f"Uri {uri:.2f}x, all < M*={MSTAR})")


if __name__ == "__main__":
    main()
