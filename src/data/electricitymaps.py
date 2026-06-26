"""Loader for Electricity Maps academic-access CSV exports.

Files are named like:
    snapshots_2026-02-10_US-CAL-CISO-2024-hourly.csv

Each file has 11 columns:
    Datetime (UTC), Country, Zone name, Zone id,
    Carbon intensity gCO₂eq/kWh (direct),
    Carbon intensity gCO₂eq/kWh (Life cycle),
    Carbon-free energy percentage (CFE%),
    Renewable energy percentage (RE%),
    Data source, Data estimated, Data estimation method

We normalize column names and return a tidy DataFrame.
"""

from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

# Default location for raw Electricity Maps CSVs.
# Resolved relative to the project root so it works regardless of cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "electricitymaps"

# Mapping from the verbose original column names to clean snake_case.
# Note: the original headers contain Unicode subscript ₂ — we use the
# unicode escape \u2082 to make this file ASCII-safe.
COLUMN_RENAME = {
    "Datetime (UTC)": "timestamp_utc",
    "Country": "country",
    "Zone name": "zone_name",
    "Zone id": "zone_id",
    "Carbon intensity gCO\u2082eq/kWh (direct)": "ci_direct",
    "Carbon intensity gCO\u2082eq/kWh (Life cycle)": "ci_lifecycle",
    "Carbon-free energy percentage (CFE%)": "cfe_pct",
    "Renewable energy percentage (RE%)": "re_pct",
    "Data source": "data_source",
    "Data estimated": "data_estimated",
    "Data estimation method": "data_estimation_method",
}


def load_csv(path: Path) -> pd.DataFrame:
    """Load a single Electricity Maps CSV and return a tidy DataFrame.

    Args:
        path: Path to the CSV file.

    Returns:
        DataFrame with snake_case columns, UTC timestamps parsed,
        and numeric columns coerced to float.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    df = pd.read_csv(path, encoding="utf-8")

    # Rename verbose columns to snake_case
    df = df.rename(columns=COLUMN_RENAME)

    # Verify the rename actually landed. The source headers contain a Unicode
    # subscript-two (the "2" in gCO2eq); a header mismatch would otherwise
    # leave the original column names in place and surface as a cryptic
    # KeyError far downstream. Fail loudly here instead.
    required = {"timestamp_utc", "ci_direct", "ci_lifecycle", "cfe_pct"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{path.name}: expected columns missing after rename: {sorted(missing)}. "
            f"Got {list(df.columns)}. Check the CSV header (esp. the Unicode "
            f"subscript in 'gCO₂eq/kWh')."
        )

    # Parse timestamps to proper UTC datetime
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)

    # Coerce numeric columns (some rows may have NaN if data was unavailable)
    numeric_cols = ["ci_direct", "ci_lifecycle", "cfe_pct", "re_pct"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Boolean for the estimation flag
    df["data_estimated"] = df["data_estimated"].astype(str).str.lower() == "true"

    return df


def load_zone(
    zone: str,
    years: Optional[Iterable[int]] = None,
    raw_dir: Path = DEFAULT_RAW_DIR,
    granularity: str = "hourly",
) -> pd.DataFrame:
    """Load all (or a subset of) yearly CSVs for one zone and concatenate.

    Args:
        zone: Electricity Maps zone id, e.g., 'US-CAL-CISO'.
        years: Iterable of years to load. If None, loads all matching files.
        raw_dir: Directory containing the snapshot CSVs.
        granularity: 'hourly' (default), '15-minute', etc.

    Returns:
        Single DataFrame sorted by timestamp, deduplicated on timestamp.
    """
    raw_dir = Path(raw_dir)
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw data dir not found: {raw_dir}")

    pattern = f"snapshots_*_{zone}-*-{granularity}.csv"
    files = sorted(raw_dir.glob(pattern))

    if years is not None:
        years_set = set(years)
        # Match the data-year token specifically (the year sits right before the
        # granularity suffix, e.g. "...US-CAL-CISO-2024-hourly.csv"). The older
        # `f"-{y}-" in name` test could in principle also hit the snapshot date
        # in the filename prefix; anchoring on the suffix avoids that.
        files = [
            f
            for f in files
            if any(f.name.endswith(f"-{y}-{granularity}.csv") for y in years_set)
        ]

    if not files:
        raise FileNotFoundError(
            f"No CSVs matched zone={zone}, granularity={granularity}, "
            f"years={years} in {raw_dir}"
        )

    frames = [load_csv(f) for f in files]
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values("timestamp_utc").drop_duplicates("timestamp_utc")
    out = out.reset_index(drop=True)
    return out


def load_all_zones(
    zones: Iterable[str],
    years: Optional[Iterable[int]] = None,
    raw_dir: Path = DEFAULT_RAW_DIR,
    granularity: str = "hourly",
) -> pd.DataFrame:
    """Load multiple zones and stack them into a long-format DataFrame.

    Useful for cross-zone analysis (correlations etc.).

    Returns:
        Long-format DataFrame with all zones stacked. Includes a 'zone_id'
        column to distinguish rows.
    """
    frames = [
        load_zone(z, years=years, raw_dir=raw_dir, granularity=granularity)
        for z in zones
    ]
    return pd.concat(frames, ignore_index=True)


def to_wide(
    long_df: pd.DataFrame, value_col: str = "ci_lifecycle"
) -> pd.DataFrame:
    """Pivot the long-format DataFrame to wide: one column per zone.

    Args:
        long_df: Output of load_all_zones (long format).
        value_col: Which column to spread (default: 'ci_lifecycle' for
                   life-cycle carbon intensity).

    Returns:
        DataFrame indexed by timestamp, one column per zone, values = value_col.
        This is the natural input for correlation analysis.
    """
    wide = long_df.pivot(
        index="timestamp_utc", columns="zone_id", values=value_col
    )
    return wide


def _demo():
    """Quick smoke test: load CISO 2024, print summary stats."""
    df = load_zone("US-CAL-CISO", years=[2024])
    print(f"Loaded {len(df):,} rows for US-CAL-CISO 2024")
    print(f"Date range: {df['timestamp_utc'].min()} to {df['timestamp_utc'].max()}")
    print("\nLife-cycle carbon intensity (gCO₂eq/kWh):")
    print(df["ci_lifecycle"].describe().round(1))
    print(f"\nRenewable energy %: mean={df['re_pct'].mean():.1f}, "
          f"max={df['re_pct'].max():.1f}")
    print(f"Carbon-free energy %: mean={df['cfe_pct'].mean():.1f}, "
          f"max={df['cfe_pct'].max():.1f}")


if __name__ == "__main__":
    _demo()
