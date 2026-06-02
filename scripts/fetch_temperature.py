"""Fetch + cache hourly 2 m temperature for the four zone load-centers.

Pulls from the Open-Meteo historical archive API (ERA5 reanalysis), 2021-2025,
on the UTC hourly grid, and caches one CSV per zone under
``data/raw/temperature/`` so re-runs never re-hit the API.

Usage
-----
    python -m scripts.fetch_temperature              # fetch (uses cache if present)
    python -m scripts.fetch_temperature --force      # force re-pull
    python -m scripts.fetch_temperature --verify     # also run Verification Gate 1

Verification Gate 1 (--verify) confirms:
  * timezone: a hot LA July afternoon (local 15:00) lands on the correct UTC
    hour with a high temperature; a pre-dawn local hour is cool;
  * shape: the aligned temperature panel matches the carbon panel exactly
    (same N, R, T; same dates; same REGION_ORDER);
  * per-zone summary stats (min/mean/max, % missing) for sanity.

Open-Meteo endpoint + limits (confirmed at build time, 2026-06):
    https://archive-api.open-meteo.com/v1/archive
    Free, no API key required for academic volumes; generous daily request
    cap (well above the 4 requests this script makes). timezone=UTC returns
    times on the UTC grid; units are degrees Celsius.
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from src.data.electricitymaps import load_all_zones, to_wide
from src.data.temperature import (
    DEFAULT_END,
    DEFAULT_START,
    DEFAULT_TEMP_DIR,
    STATION_COORDS,
    align_temperature_to_panel,
    fetch_all_zones,
    load_temperature_wide,
    temperature_summary,
)
from src.models.covariance import REGION_ORDER, build_daily_panel


def _verify(temp_wide: pd.DataFrame) -> int:
    """Verification Gate 1. Returns 0 on success, non-zero on failure."""
    print("\n" + "=" * 78)
    print("VERIFICATION GATE 1")
    print("=" * 78)

    ok = True

    # ---- (a) Timezone spot-check on RAW UTC series (LA / LDWP) --------------
    # LA is UTC-7 in July (PDT). Local 15:00 == 22:00 UTC; local 05:00 == 12:00 UTC.
    la = temp_wide["US-CAL-LDWP"]
    hot_utc = pd.Timestamp("2024-07-15 22:00", tz="UTC")   # 15:00 PDT
    cool_utc = pd.Timestamp("2024-07-15 12:00", tz="UTC")  # 05:00 PDT
    hot_val = float(la.loc[hot_utc])
    cool_val = float(la.loc[cool_utc])
    print("\n[tz spot-check: Los Angeles, 2024-07-15]")
    print(f"  local 15:00 (22:00 UTC) temperature = {hot_val:5.1f} C  (expect HOT)")
    print(f"  local 05:00 (12:00 UTC) temperature = {cool_val:5.1f} C  (expect COOL)")
    if not (hot_val > cool_val and hot_val > 25.0):
        print("  FAIL: afternoon not hotter than pre-dawn (or not hot enough)")
        ok = False
    else:
        print("  PASS: afternoon hotter than pre-dawn, afternoon > 25 C")

    # ---- (b) Shape + date + region alignment vs carbon panel ---------------
    print("\n[shape alignment vs carbon panel]")
    carbon_long = load_all_zones(list(REGION_ORDER))
    carbon_wide = to_wide(carbon_long)
    carbon_panel, carbon_dates = build_daily_panel(carbon_wide)
    temp_panel, temp_dates = align_temperature_to_panel(temp_wide, carbon_wide)
    print(f"  carbon panel shape      : {carbon_panel.shape}")
    print(f"  temperature panel shape : {temp_panel.shape}")
    same_shape = carbon_panel.shape == temp_panel.shape
    same_dates = carbon_dates.equals(temp_dates)
    print(f"  shapes match            : {same_shape}")
    print(f"  dates match exactly     : {same_dates}")
    if not (same_shape and same_dates):
        print("  FAIL: temperature panel does not match carbon panel grid")
        ok = False
    else:
        print("  PASS: identical (N, R, T), identical dates, REGION_ORDER preserved")

    # ---- (c) Panel-level tz confirmation -----------------------------------
    # In the LA-local panel, hour index t == local hour. Average across all
    # summer days: local mid-afternoon (t=15) must exceed pre-dawn (t=5).
    r_la = list(REGION_ORDER).index("US-CAL-LDWP")
    months = np.array([d.month for d in temp_dates])
    summer = np.isin(months, [6, 7, 8])
    afternoon = temp_panel[summer, r_la, 15].mean()
    predawn = temp_panel[summer, r_la, 5].mean()
    print("\n[panel-level tz: LA summer mean by local hour]")
    print(f"  t=15 (local 15:00) mean = {afternoon:5.1f} C")
    print(f"  t=05 (local 05:00) mean = {predawn:5.1f} C")
    if not (afternoon > predawn):
        print("  FAIL: panel hour indexing not LA-local")
        ok = False
    else:
        print("  PASS: panel hour axis is LA-local (afternoon > pre-dawn)")

    # ---- (d) Per-zone summary stats ----------------------------------------
    print("\n[per-zone temperature summary]")
    summ = temperature_summary(temp_panel, temp_wide, carbon_wide)
    print(summ.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print("\n" + "=" * 78)
    print("GATE 1 RESULT:", "PASS" if ok else "FAIL")
    print("=" * 78)
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="Re-pull even if cached.")
    ap.add_argument("--verify", action="store_true", help="Run Verification Gate 1.")
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    ap.add_argument("--cache-dir", default=str(DEFAULT_TEMP_DIR))
    args = ap.parse_args()

    print("Fetching 2 m temperature from Open-Meteo archive (UTC grid) ...")
    for z, (lat, lon, label) in STATION_COORDS.items():
        print(f"  {z:12s} -> {label:24s} ({lat:.4f}, {lon:.4f})")
    fetch_all_zones(REGION_ORDER, args.start, args.end, args.cache_dir, args.force)
    print(f"Cached under {args.cache_dir}")

    if args.verify:
        temp_wide = load_temperature_wide(
            REGION_ORDER, args.start, args.end, args.cache_dir
        )
        return _verify(temp_wide)
    return 0


if __name__ == "__main__":
    sys.exit(main())
