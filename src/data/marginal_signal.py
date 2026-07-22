"""Marginal-emissions signal ingestion (roadmap D1, pre-data scaffold).

The whole study optimizes *average* carbon intensity (Electricity Maps
life-cycle CI). The field is split on average vs. marginal signals, and the
two produce conflicting schedules (e-Energy'24), so D1 asks: does the
dependence null survive when the scheduler optimizes a marginal signal?

This module is the data seam for that experiment. It loads per-zone marginal
carbon-intensity CSVs into the exact long/wide shapes produced by
src.data.electricitymaps, so the entire locked Phase 1 pipeline runs
unchanged with `to_wide_marginal(...)` in place of `to_wide(...)`.

Status: NO marginal data ships with the repo. The average-CI academic licence
does not cover marginal streams. Supported sources once access lands:

  - WattTime v3 MOER exports (columns: point_time, value; value in
    lbs CO2/MWh, converted here to gCO2/kWh), academic access program.
  - Electricity Maps premium marginal stream exported to the canonical
    schema below.

Canonical schema (one CSV per zone under data/raw/marginal/):

    <zone>.csv with columns: timestamp_utc, marginal_ci   [gCO2eq/kWh]

Files under data/raw/marginal/ are licensed like the average-CI data:
gitignored, never committed. See docs/protocols/marginal_signal_protocol.md
for the pre-registered experimental design this module feeds.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

DEFAULT_MARGINAL_DIR = Path("data/raw/marginal")

# 1 lb/MWh = 453.59237 g / 1000 kWh
LBS_PER_MWH_TO_G_PER_KWH = 453.59237 / 1000.0


def load_marginal_zone(
    zone: str,
    raw_dir: Path = DEFAULT_MARGINAL_DIR,
) -> pd.DataFrame:
    """Load one zone's marginal-CI series into the canonical long format.

    Accepts either the canonical schema (timestamp_utc, marginal_ci in
    gCO2eq/kWh) or a WattTime v3 MOER export (point_time, value in
    lbs CO2/MWh, converted on load).

    Args:
        zone: zone id; the file is expected at raw_dir/<zone>.csv.
        raw_dir: directory of per-zone marginal CSVs.

    Returns:
        DataFrame with columns [timestamp_utc (tz-aware UTC), zone_id,
        marginal_ci] sorted by timestamp.

    Raises:
        FileNotFoundError: with a data-access explanation if the file is
            missing (the expected state until D1's data lands).
        ValueError: if the CSV matches neither known schema.
    """
    path = Path(raw_dir) / f"{zone}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"No marginal-CI file at {path}. Marginal data is not part of "
            f"the average-CI academic licence; obtain it via WattTime "
            f"academic access or an Electricity Maps premium export, then "
            f"place per-zone CSVs under {raw_dir}/ (gitignored). See "
            f"docs/protocols/marginal_signal_protocol.md."
        )
    df = pd.read_csv(path)
    cols = set(df.columns)
    if {"timestamp_utc", "marginal_ci"} <= cols:
        out = df[["timestamp_utc", "marginal_ci"]].copy()
    elif {"point_time", "value"} <= cols:  # WattTime v3 MOER export
        out = pd.DataFrame({
            "timestamp_utc": df["point_time"],
            "marginal_ci": df["value"] * LBS_PER_MWH_TO_G_PER_KWH,
        })
    else:
        raise ValueError(
            f"{path} matches no known schema. Expected columns "
            f"(timestamp_utc, marginal_ci) or WattTime (point_time, value); "
            f"got {sorted(cols)}."
        )
    out["timestamp_utc"] = pd.to_datetime(out["timestamp_utc"], utc=True)
    out["zone_id"] = zone
    out = out[["timestamp_utc", "zone_id", "marginal_ci"]]
    return out.sort_values("timestamp_utc").reset_index(drop=True)


def load_all_marginal_zones(
    zones: Iterable[str],
    raw_dir: Path = DEFAULT_MARGINAL_DIR,
) -> pd.DataFrame:
    """Load and stack multiple zones (mirrors electricitymaps.load_all_zones).

    Returns:
        Long-format DataFrame [timestamp_utc, zone_id, marginal_ci].
    """
    frames = [load_marginal_zone(z, raw_dir=raw_dir) for z in zones]
    return pd.concat(frames, ignore_index=True)


def to_wide_marginal(long_df: pd.DataFrame) -> pd.DataFrame:
    """Pivot to wide format: UTC index, one column per zone (mirrors
    electricitymaps.to_wide, so build_daily_panel consumes it unchanged).
    """
    wide = long_df.pivot(
        index="timestamp_utc", columns="zone_id", values="marginal_ci"
    )
    return wide


def coverage_report(
    marginal_wide: pd.DataFrame,
    carbon_wide: pd.DataFrame,
) -> pd.DataFrame:
    """Per-zone overlap between a marginal panel and the average-CI panel.

    The locked D1 design requires the marginal panel to cover the same
    train/test hours as the average panel; this is the dry-run gate metric.

    Args:
        marginal_wide: to_wide_marginal output.
        carbon_wide: electricitymaps.to_wide output (defines the hour grid).

    Returns:
        DataFrame indexed by zone with columns [hours_expected, hours_present,
        coverage] where coverage = present/expected on the carbon hour grid.
        Zones absent from marginal_wide get coverage 0.0.
    """
    rows = {}
    for zone in carbon_wide.columns:
        expected = carbon_wide[zone].notna()
        n_expected = int(expected.sum())
        if zone in marginal_wide.columns:
            present = marginal_wide[zone].reindex(
                carbon_wide.index[expected]).notna()
            n_present = int(present.sum())
        else:
            n_present = 0
        rows[zone] = {
            "hours_expected": n_expected,
            "hours_present": n_present,
            "coverage": (n_present / n_expected) if n_expected else 0.0,
        }
    out = pd.DataFrame.from_dict(rows, orient="index")
    out.index.name = "zone_id"
    return out
