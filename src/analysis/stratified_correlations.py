"""Stratified correlation analysis for carbon intensity vectors.

Computes pairwise correlations of regional carbon intensity conditional on:
  - hour-of-day (in local Pacific time)
  - meteorological season (DJF, MAM, JJA, SON)
  - weekday vs weekend

All time-based stratification uses LOCAL time (America/Los_Angeles by default),
not UTC, since the operational relevance is to local grid dynamics (solar
cycle, dispatch patterns, business hours).

Output format: tidy long DataFrame with columns
  stratum_type, stratum, pair, correlation, n_samples
This format is convenient for downstream pivoting, plotting, and reporting.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_TZ = "America/Los_Angeles"

SEASON_MAP = {
    12: "DJF", 1: "DJF", 2: "DJF",
    3: "MAM", 4: "MAM", 5: "MAM",
    6: "JJA", 7: "JJA", 8: "JJA",
    9: "SON", 10: "SON", 11: "SON",
}


def to_local(wide_df: pd.DataFrame, tz: str = DEFAULT_TZ) -> pd.DataFrame:
    """Return a copy of wide_df with its index converted to local time.

    If the input index is timezone-naive it is assumed to be UTC, which
    matches the Electricity Maps loader convention.
    """
    df = wide_df.copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(tz)
    return df


def _pairs_long(
    corr_matrix: pd.DataFrame,
    n_samples: int,
    stratum_type: str,
    stratum,
) -> pd.DataFrame:
    """Flatten the upper triangle of a correlation matrix into long format."""
    cols = list(corr_matrix.columns)
    rows = []
    for i, c1 in enumerate(cols):
        for j, c2 in enumerate(cols):
            if i < j:
                rows.append({
                    "stratum_type": stratum_type,
                    "stratum": stratum,
                    "pair": f"{c1}-{c2}",
                    "correlation": float(corr_matrix.iloc[i, j]),
                    "n_samples": int(n_samples),
                })
    return pd.DataFrame(rows)


def correlations_by_hour(wide_df: pd.DataFrame, tz: str = DEFAULT_TZ) -> pd.DataFrame:
    """Pairwise correlations conditional on hour-of-day in local time."""
    local = to_local(wide_df, tz)
    parts = []
    for h, g in local.groupby(local.index.hour):
        parts.append(_pairs_long(g.corr(), len(g), "hour", int(h)))
    return pd.concat(parts, ignore_index=True)


def correlations_by_season(wide_df: pd.DataFrame, tz: str = DEFAULT_TZ) -> pd.DataFrame:
    """Pairwise correlations conditional on meteorological season."""
    local = to_local(wide_df, tz)
    season_labels = local.index.month.map(SEASON_MAP)
    parts = []
    for s, g in local.groupby(season_labels):
        parts.append(_pairs_long(g.corr(), len(g), "season", s))
    return pd.concat(parts, ignore_index=True)


def correlations_by_weekday(wide_df: pd.DataFrame, tz: str = DEFAULT_TZ) -> pd.DataFrame:
    """Pairwise correlations conditional on weekday vs weekend."""
    local = to_local(wide_df, tz)
    is_weekend = local.index.dayofweek >= 5
    parts = [
        _pairs_long(local[~is_weekend].corr(), int((~is_weekend).sum()), "daytype", "weekday"),
        _pairs_long(local[is_weekend].corr(), int(is_weekend.sum()), "daytype", "weekend"),
    ]
    return pd.concat(parts, ignore_index=True)


def summarize_all(wide_df: pd.DataFrame, tz: str = DEFAULT_TZ) -> pd.DataFrame:
    """Run all three stratifications and return a concatenated long DataFrame."""
    return pd.concat(
        [
            correlations_by_hour(wide_df, tz),
            correlations_by_season(wide_df, tz),
            correlations_by_weekday(wide_df, tz),
        ],
        ignore_index=True,
    )


def _pivot_for_display(long_df: pd.DataFrame, strip_prefix: str = "US-CAL-") -> pd.DataFrame:
    """Pivot long-format output to strata x pairs for compact terminal display."""
    df = long_df.copy()
    df["pair"] = df["pair"].str.replace(strip_prefix, "", regex=False)
    pivot = df.pivot_table(index="stratum", columns="pair", values="correlation")
    n = df.groupby("stratum")["n_samples"].first()
    pivot["n"] = n.astype(int)
    return pivot


if __name__ == "__main__":
    # CLI: load the standard CA panel and print all three stratifications.
    from src.data.electricitymaps import load_all_zones, to_wide

    zones = ["US-CAL-CISO", "US-CAL-BANC", "US-CAL-LDWP"]
    long_df = load_all_zones(zones)
    wide = to_wide(long_df)

    print(f"Wide panel: {len(wide):,} hourly observations across {wide.shape[1]} zones")
    print(f"Time range: {wide.index.min()} to {wide.index.max()} (UTC)\n")

    print("=" * 72)
    print("CORRELATIONS BY HOUR OF DAY (local Pacific time)")
    print("=" * 72)
    h = _pivot_for_display(correlations_by_hour(wide))
    print(h.round(3))

    print()
    print("=" * 72)
    print("CORRELATIONS BY SEASON  (DJF/MAM/JJA/SON = winter/spring/summer/fall)")
    print("=" * 72)
    s = _pivot_for_display(correlations_by_season(wide))
    print(s.reindex(["DJF", "MAM", "JJA", "SON"]).round(3))

    print()
    print("=" * 72)
    print("CORRELATIONS BY DAY TYPE")
    print("=" * 72)
    w = _pivot_for_display(correlations_by_weekday(wide))
    print(w.reindex(["weekday", "weekend"]).round(3))
