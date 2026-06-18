"""screen_zones.py -- quick correlation screen to vet candidate region sets.

Loads every North American zone on disk, computes the daily-mean carbon-intensity
correlation matrix (raw and de-seasonalized), and reports how Texas (ERCO) relates to
everything else, plus the most-correlated and most-diversified pairs. Used to decide
whether a Texas-anchored set (e.g. Texas + Mexico) is worth staging new data for.

Run: .venv\\Scripts\\python -m scripts.screen_zones
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.electricitymaps import load_all_zones, to_wide

NA = ["US-TEX-ERCO", "US-CAL-CISO", "US-CAL-BANC", "US-CAL-LDWP", "US-NW-NEVP",
      "US-SW-AZPS", "US-NW-BPAT", "US-MIDA-PJM", "US-MIDW-MISO", "US-NY-NYIS", "CA-ON"]
SHORT = {z: z.split("-")[-1] for z in NA}


def deseasonalize(daily: pd.DataFrame) -> pd.DataFrame:
    """Remove each zone's day-of-year climatology (a 15-day rolling seasonal mean)."""
    doy = daily.index.dayofyear
    out = daily.copy()
    for col in daily.columns:
        clim = daily[col].groupby(doy).transform("mean")
        out[col] = daily[col] - clim.values
    return out


def main():
    wide = to_wide(load_all_zones(NA))
    daily = wide[NA].resample("D").mean().dropna(how="all")
    raw = daily.corr()
    res = deseasonalize(daily).corr()

    print("=== Texas (ERCO) daily-mean carbon correlation with each zone ===")
    print(f"  {'zone':<8}{'raw':>8}{'de-seasonal':>14}")
    for z in NA:
        if z == "US-TEX-ERCO":
            continue
        print(f"  {SHORT[z]:<8}{raw.loc['US-TEX-ERCO', z]:>8.2f}{res.loc['US-TEX-ERCO', z]:>14.2f}")

    # most correlated / most diversified pairs (de-seasonalized)
    pairs = []
    for i, a in enumerate(NA):
        for b in NA[i + 1:]:
            pairs.append((SHORT[a], SHORT[b], res.loc[a, b]))
    pairs.sort(key=lambda p: p[2])
    print("\n=== most DIVERSIFIED pairs (lowest de-seasonalized corr) ===")
    for a, b, r in pairs[:5]:
        print(f"  {a:>6} x {b:<6}: {r:+.2f}")
    print("=== most CORRELATED pairs ===")
    for a, b, r in pairs[-5:][::-1]:
        print(f"  {a:>6} x {b:<6}: {r:+.2f}")

    erco = res.loc["US-TEX-ERCO"].drop("US-TEX-ERCO")
    print(f"\nERCO de-seasonalized corr: min {erco.min():+.2f} ({SHORT[erco.idxmin()]}), "
          f"max {erco.max():+.2f} ({SHORT[erco.idxmax()]}), mean {erco.mean():+.2f}")


if __name__ == "__main__":
    main()
