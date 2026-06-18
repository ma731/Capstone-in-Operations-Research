"""data_audit.py -- full audit of the carbon-intensity archive.

Loads every North-American zone, checks completeness, characterizes each zone
(carbon level, day-to-day volatility, tail severity), computes the full
de-seasonalized dependence structure, and vets candidate region sets. Used to
decide whether the thesis's grids / testing / methodology need changes now that
the full archive (17 zones) is available.

Run: .venv\\Scripts\\python -m scripts.data_audit
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from src.analysis.plotstyle import apply_style, NAVY, save
from src.data.electricitymaps import load_all_zones, to_wide

apply_style()

NA = ["CA-AB", "CA-ON", "US-SW-SRP", "US-SW-AZPS", "US-SW-PNM",
      "US-CAL-CISO", "US-CAL-BANC", "US-CAL-LDWP", "US-CAL-IID", "US-CAL-TIDC",
      "US-TEX-ERCO", "US-MIDW-MISO", "US-MIDW-AECI", "US-MIDA-PJM", "US-NY-NYIS",
      "US-NW-NEVP", "US-NW-BPAT"]
SHORT = {z: z.split("-")[-1] for z in NA}


def deseasonalize(daily):
    doy = daily.index.dayofyear
    out = daily.copy()
    for c in daily.columns:
        out[c] = daily[c] - daily[c].groupby(doy).transform("mean").values
    return out


def main():
    wide = to_wide(load_all_zones(NA))[NA]
    daily = wide.resample("D").mean()

    print("=== per-zone: completeness, carbon level, volatility, tail severity ===")
    print(f"  {'zone':<6}{'days':>6}{'miss%':>7}{'mean':>7}{'CV':>6}{'p95/mn':>8}{'max/mn':>8}")
    rows = []
    for z in NA:
        s = daily[z].dropna()
        n = len(s); miss = 100 * daily[z].isna().mean()
        cv = s.std() / s.mean(); p95 = s.quantile(.95) / s.mean(); mx = s.max() / s.mean()
        rows.append((z, s.mean(), cv, p95, mx))
        print(f"  {SHORT[z]:<6}{n:>6}{miss:>6.1f}%{s.mean():>7.0f}{cv:>6.2f}{p95:>8.2f}{mx:>8.2f}")

    # full de-seasonalized correlation
    dd = deseasonalize(daily).dropna()
    res = dd.corr()

    print("\n=== dependence structure (de-seasonalized daily) ===")
    pairs = [(SHORT[a], SHORT[b], res.loc[a, b])
             for i, a in enumerate(NA) for b in NA[i + 1:]]
    pairs.sort(key=lambda p: p[2])
    print("  most ANTI-correlated (diversifiers):")
    for a, b, r in pairs[:6]:
        print(f"    {a:>5} x {b:<5} {r:+.2f}")
    print("  most CORRELATED (common-mode clusters):")
    for a, b, r in pairs[-6:][::-1]:
        print(f"    {a:>5} x {b:<5} {r:+.2f}")

    def setcorr(zs):
        sub = res.loc[zs, zs].values
        off = sub[np.triu_indices(len(zs), 1)]
        return off.min(), off.mean(), off.max()

    print("\n=== candidate region sets (de-seasonalized corr: min / mean / max) ===")
    cands = {
        "us_west (current)": ["US-CAL-CISO", "US-CAL-BANC", "US-CAL-LDWP", "US-NW-NEVP", "US-SW-AZPS"],
        "taskc (current)": ["CA-ON", "US-NY-NYIS", "US-MIDW-MISO", "US-MIDA-PJM"],
        "us_hetero (current)": ["US-CAL-CISO", "US-TEX-ERCO", "US-NW-BPAT"],
        "south-central NM+MO+TX": ["US-SW-PNM", "US-MIDW-AECI", "US-TEX-ERCO"],
        "Alberta+Ontario": ["CA-AB", "CA-ON"],
    }
    for name, zs in cands.items():
        lo, mn, hi = setcorr(zs)
        means = [daily[z].mean() for z in zs]
        print(f"  {name:<26} corr {lo:+.2f}/{mn:+.2f}/{hi:+.2f}   "
              f"carbon {min(means):.0f}-{max(means):.0f}")

    # heatmap of the full structure
    fig, ax = plt.subplots(figsize=(8.4, 7.0))
    im = ax.imshow(res.values, cmap="RdYlGn_r", vmin=-0.6, vmax=1.0)
    ax.set_xticks(range(len(NA))); ax.set_yticks(range(len(NA)))
    ax.set_xticklabels([SHORT[z] for z in NA], rotation=90, fontsize=8)
    ax.set_yticklabels([SHORT[z] for z in NA], fontsize=8)
    ax.set_title("De-seasonalized carbon-intensity correlation, 17 NA zones", color=NAVY)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Pearson r")
    fig.tight_layout()
    save(fig, "all_zones_correlation")
    print("\nwrote figures/all_zones_correlation.png")


if __name__ == "__main__":
    main()
