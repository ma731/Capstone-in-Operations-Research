"""Data for the grid room page (site/index.html).

Writes site/grid_room_data.js: per zone, the 2025 average carbon intensity for each hour
of the day, the hourly correlation between zones, and the measured results read from the
archived snapshots. Only yearly averages and correlations leave the machine, never the
licensed hourly series. Run from the repo root:

    python scripts/build_grid_room.py [path/to/data/raw/electricitymaps]
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "docs" / "results_snapshots"
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "raw" / "electricitymaps"
YEAR = 2025  # the held-out test year

# plain names and rough locations (balancing-area centres, for the map only)
ZONES = {
    "US-CAL-CISO": ("California grid", "Folsom, CA", 36.8, -119.8),
    "US-CAL-BANC": ("Sacramento", "Sacramento, CA", 38.6, -121.5),
    "US-CAL-LDWP": ("Los Angeles", "Los Angeles, CA", 34.05, -118.25),
    "US-NW-NEVP": ("Nevada", "Las Vegas, NV", 36.2, -115.1),
    "US-SW-AZPS": ("Arizona", "Phoenix, AZ", 33.45, -112.07),
    "CA-ON": ("Ontario", "Toronto, ON", 43.7, -79.4),
    "US-NY-NYIS": ("New York", "Albany, NY", 42.7, -74.5),
    "US-MIDW-MISO": ("Midwest (MISO)", "Carmel, IN", 41.5, -89.5),
    "US-MIDA-PJM": ("Mid-Atlantic (PJM)", "Valley Forge, PA", 39.6, -78.6),
    "US-TEX-ERCO": ("Texas", "Austin, TX", 31.0, -97.7),
    "US-NW-BPAT": ("Pacific Northwest", "Portland, OR", 45.6, -121.0),
}

GRIDS = [
    ("us_west", "Western US", ["US-CAL-CISO", "US-CAL-BANC", "US-CAL-LDWP", "US-NW-NEVP", "US-SW-AZPS"],
     -8, "Pacific time", "One interconnected grid. Solar floods all of it at midday, so the zones rise and fall together."),
    ("taskc", "Eastern US and Canada", ["CA-ON", "US-NY-NYIS", "US-MIDW-MISO", "US-MIDA-PJM"],
     -5, "Eastern time", "Ontario runs on hydro and nuclear; the US Midwest still burns coal and gas. Big gaps, steady all day."),
    ("us_hetero", "Diversified", ["US-CAL-CISO", "US-TEX-ERCO", "US-NW-BPAT"],
     -6, "Central time", "Picked to disagree: California solar, Texas wind, Northwest hydro. The best case for modelling co-movement."),
]


def rows(name):
    with open(SNAP / name, newline="") as f:
        return list(csv.DictReader(f))


def load(zone):
    files = sorted(RAW.glob(f"snapshots_*_{zone}-{YEAR}-hourly.csv"))
    if not files:
        raise SystemExit(f"no {YEAR} file for {zone} in {RAW}")
    df = pd.read_csv(files[-1])
    s = pd.Series(df["Carbon intensity gCO₂eq/kWh (Life cycle)"].to_numpy(dtype=float),
                  index=pd.to_datetime(df["Datetime (UTC)"]))
    return s[~s.index.duplicated()]


def main():
    series = {z: load(z) for z in ZONES}
    zones = {}
    for z, (name, city, lat, lon) in ZONES.items():
        s = series[z]
        prof = s.groupby(s.index.hour).mean()
        zones[z] = {"name": name, "city": city, "lat": lat, "lon": lon,
                    "hourly_utc": [round(float(prof[h]), 1) for h in range(24)],
                    "mean": round(float(s.mean()), 1)}

    rq1 = {r["grid"]: float(r["reduction_pct"]) for r in rows("part3_transfer_value_2026-06-15.csv")}
    rq2 = {g: max(abs(float(r["gap_pct"])) for r in rows(f"{g}_regimes_2026-06-10.csv") if r["gap_pct"])
           for g, *_ in GRIDS}
    sev = {r["key"]: float(r["severity"]) for r in rows("carbon_ceiling_2026-06-24.csv") if r["kind"] == "joint"}
    emer = {}
    for r in rows("part3_emergency_2026-06-15.csv"):
        emer.setdefault(r["grid"], []).append({"M": float(r["M"]), "gain": round(float(r["gain_pct"]), 2),
                                              "lo": round(float(r["ci_lo"]), 2), "hi": round(float(r["ci_hi"]), 2),
                                              "sig": r["significant"] == "True"})

    grids = []
    for key, display, zs, tz, clock, blurb in GRIDS:
        wide = pd.concat([series[z] for z in zs], axis=1, keys=zs).dropna()
        c = wide.corr().to_numpy()
        pairs = [{"a": zs[i], "b": zs[j], "r": round(float(c[i, j]), 2)}
                 for i in range(len(zs)) for j in range(i + 1, len(zs))]
        off = np.triu(c, 1)[np.triu_indices(len(zs), 1)]
        grids.append({"key": key, "name": display, "zones": zs, "tz": tz, "clock": clock, "blurb": blurb,
                      "move_pct": round(rq1[key], 1), "comove_pct": round(rq2[key], 2),
                      "mean_corr": round(float(off.mean()), 2), "pairs": pairs,
                      "real_severity": round(sev[key], 2), "emergency": emer[key]})

    out = {"year": YEAR, "zones": zones, "grids": grids, "crossover": 3.0, "materiality_pct": 0.4}
    dest = ROOT / "site" / "grid_room_data.js"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text("// built by scripts/build_grid_room.py; yearly averages and snapshot results only\n"
                    "window.GRID_ROOM = " + json.dumps(out, indent=1) + ";\n", encoding="utf-8")
    for g in grids:
        print(g["key"], g["move_pct"], g["comove_pct"], g["mean_corr"], g["real_severity"])
    for z, v in zones.items():
        print(f"{z:14s} mean {v['mean']:6.1f}  min {min(v['hourly_utc']):6.1f}  max {max(v['hourly_utc']):6.1f}")


if __name__ == "__main__":
    main()
