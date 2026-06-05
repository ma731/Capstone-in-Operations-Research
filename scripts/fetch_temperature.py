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
from src.models.covariance import (
    DEFAULT_TZ,
    DEFAULT_TZ_ES_PT_FR,
    REGION_ORDER,
    REGION_ORDER_ES_PT_FR,
    build_daily_panel,
)

# Region sets. Each: zones, common clock, and a tz spot-check spec (a zone +
# the UTC hours that map to local 15:00 / 05:00 on a hot summer day). The US
# set reproduces Task A's Verification Gate 1; the Iberian set is Gate B2.
REGION_SETS = {
    "us": {
        "zones": REGION_ORDER,
        "tz": DEFAULT_TZ,
        "spot_zone": "US-CAL-LDWP",
        "spot_label": "Los Angeles",
        # LA in July = PDT (UTC-7): local 15:00 = 22:00 UTC, 05:00 = 12:00 UTC.
        "hot_utc": "2024-07-15 22:00",
        "cool_utc": "2024-07-15 12:00",
        "gate": "1",
    },
    "es_pt_fr": {
        "zones": REGION_ORDER_ES_PT_FR,
        "tz": DEFAULT_TZ_ES_PT_FR,
        "spot_zone": "ES",
        "spot_label": "Madrid",
        # Madrid in July = CEST (UTC+2): local 15:00 = 13:00 UTC, 05:00 = 03:00 UTC.
        # (Spot-check ES, where the Madrid common clock is exact. PT is WET, one
        # hour behind, so PT's panel hours are offset +1h -- documented, not a bug.)
        "hot_utc": "2024-07-15 13:00",
        "cool_utc": "2024-07-15 03:00",
        "gate": "B2",
    },
}


def _verify(temp_wide: pd.DataFrame, rs: dict) -> int:
    """Verification Gate (US Gate 1 / Iberia Gate B2). Returns 0 on success."""
    zones = list(rs["zones"])
    tz = rs["tz"]
    print("\n" + "=" * 78)
    print(f"VERIFICATION GATE {rs['gate']}  (region set tz = {tz})")
    print("=" * 78)

    ok = True

    # ---- (a) Timezone spot-check on RAW UTC series -------------------------
    zname = rs["spot_zone"]
    series = temp_wide[zname]
    hot_utc = pd.Timestamp(rs["hot_utc"], tz="UTC")
    cool_utc = pd.Timestamp(rs["cool_utc"], tz="UTC")
    hot_val = float(series.loc[hot_utc])
    cool_val = float(series.loc[cool_utc])
    print(f"\n[tz spot-check: {rs['spot_label']}, 2024-07-15]")
    print(f"  local 15:00 ({hot_utc:%H:%M} UTC) temperature = {hot_val:5.1f} C  (expect HOT)")
    print(f"  local 05:00 ({cool_utc:%H:%M} UTC) temperature = {cool_val:5.1f} C  (expect COOL)")
    if not (hot_val > cool_val and hot_val > 25.0):
        print("  FAIL: afternoon not hotter than pre-dawn (or not hot enough)")
        ok = False
    else:
        print("  PASS: afternoon hotter than pre-dawn, afternoon > 25 C")

    # ---- (b) Shape + date + region alignment vs carbon panel ---------------
    print("\n[shape alignment vs carbon panel]")
    carbon_wide = to_wide(load_all_zones(zones))
    carbon_panel, carbon_dates = build_daily_panel(carbon_wide, region_order=zones, tz=tz)
    temp_panel, temp_dates = align_temperature_to_panel(
        temp_wide, carbon_wide, region_order=zones, tz=tz
    )
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
        print("  PASS: identical (N, R, T), identical dates, region order preserved")

    # ---- (c) Panel-level tz confirmation -----------------------------------
    r_spot = zones.index(zname)
    months = np.array([d.month for d in temp_dates])
    summer = np.isin(months, [6, 7, 8])
    afternoon = temp_panel[summer, r_spot, 15].mean()
    predawn = temp_panel[summer, r_spot, 5].mean()
    print(f"\n[panel-level tz: {rs['spot_label']} summer mean by local hour]")
    print(f"  t=15 (local 15:00) mean = {afternoon:5.1f} C")
    print(f"  t=05 (local 05:00) mean = {predawn:5.1f} C")
    if not (afternoon > predawn):
        print("  FAIL: panel hour indexing not local")
        ok = False
    else:
        print("  PASS: panel hour axis is local (afternoon > pre-dawn)")

    # ---- (d) Per-zone summary stats ----------------------------------------
    print("\n[per-zone temperature summary]")
    summ = temperature_summary(temp_panel, temp_wide, carbon_wide, region_order=zones)
    print(summ.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    print("\n" + "=" * 78)
    print(f"GATE {rs['gate']} RESULT:", "PASS" if ok else "FAIL")
    print("=" * 78)
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region-set", choices=("us", "es_pt_fr"), default="us",
                    help="Which zone set to fetch (default us = Task A).")
    ap.add_argument("--force", action="store_true", help="Re-pull even if cached.")
    ap.add_argument("--verify", action="store_true", help="Run the verification gate.")
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    ap.add_argument("--cache-dir", default=str(DEFAULT_TEMP_DIR))
    args = ap.parse_args()
    rs = REGION_SETS[args.region_set]
    zones = list(rs["zones"])

    print(f"Fetching 2 m temperature from Open-Meteo archive (UTC grid) "
          f"-- region set '{args.region_set}' ...")
    for z in zones:
        lat, lon, label = STATION_COORDS[z]
        print(f"  {z:12s} -> {label:24s} ({lat:.4f}, {lon:.4f})")
    fetch_all_zones(zones, args.start, args.end, args.cache_dir, args.force)
    print(f"Cached under {args.cache_dir}")

    if args.verify:
        temp_wide = load_temperature_wide(zones, args.start, args.end, args.cache_dir)
        return _verify(temp_wide, rs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
