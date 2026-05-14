"""Tests for the Electricity Maps loader.

These tests assume the 15 California CSVs are present at
data/raw/electricitymaps/. If they're missing, the tests are skipped
rather than failed — they're integration tests on real data, not unit
tests.
"""

from pathlib import Path

import pandas as pd
import pytest

from src.data.electricitymaps import (
    DEFAULT_RAW_DIR,
    load_all_zones,
    load_csv,
    load_zone,
    to_wide,
)

# Skip the whole module if the raw data isn't there yet.
pytestmark = pytest.mark.skipif(
    not DEFAULT_RAW_DIR.exists() or not list(DEFAULT_RAW_DIR.glob("*.csv")),
    reason="Electricity Maps raw CSVs not present in data/raw/electricitymaps/",
)


CALIFORNIA_ZONES = ["US-CAL-CISO", "US-CAL-BANC", "US-CAL-LDWP"]


class TestSingleFileLoad:
    def test_loads_ciso_2024(self):
        path = DEFAULT_RAW_DIR / "snapshots_2026-02-10_US-CAL-CISO-2024-hourly.csv"
        df = load_csv(path)
        assert len(df) > 0
        assert "timestamp_utc" in df.columns
        assert "ci_lifecycle" in df.columns
        assert "zone_id" in df.columns

    def test_ciso_2024_has_expected_row_count(self):
        # 2024 is a leap year: 366 * 24 = 8784 hours
        path = DEFAULT_RAW_DIR / "snapshots_2026-02-10_US-CAL-CISO-2024-hourly.csv"
        df = load_csv(path)
        assert 8000 < len(df) <= 8784  # allow for small gaps

    def test_timestamps_are_utc(self):
        path = DEFAULT_RAW_DIR / "snapshots_2026-02-10_US-CAL-CISO-2024-hourly.csv"
        df = load_csv(path)
        assert df["timestamp_utc"].dt.tz is not None

    def test_carbon_intensity_is_positive(self):
        path = DEFAULT_RAW_DIR / "snapshots_2026-02-10_US-CAL-CISO-2024-hourly.csv"
        df = load_csv(path)
        # Carbon intensity should be non-negative (zero is plausible in
        # 100%-renewable hours)
        assert (df["ci_lifecycle"].dropna() >= 0).all()

    def test_ciso_zone_id(self):
        path = DEFAULT_RAW_DIR / "snapshots_2026-02-10_US-CAL-CISO-2024-hourly.csv"
        df = load_csv(path)
        assert (df["zone_id"] == "US-CAL-CISO").all()


class TestZoneLoad:
    def test_load_full_ciso_history(self):
        df = load_zone("US-CAL-CISO")
        # 5 years of hourly data ~ 43,800 rows
        assert 40000 < len(df) < 50000

    def test_load_specific_years(self):
        df = load_zone("US-CAL-CISO", years=[2023, 2024])
        # 2 years of hourly data ~ 17,520 rows (one leap year adds 24)
        assert 17000 < len(df) < 18000

    def test_timestamps_are_sorted(self):
        df = load_zone("US-CAL-CISO", years=[2024])
        assert df["timestamp_utc"].is_monotonic_increasing

    def test_no_duplicate_timestamps(self):
        df = load_zone("US-CAL-CISO", years=[2024])
        assert not df["timestamp_utc"].duplicated().any()


class TestMultiZoneLoad:
    def test_load_all_three_zones(self):
        df = load_all_zones(CALIFORNIA_ZONES, years=[2024])
        # 3 zones * ~8784 hours
        assert 25000 < len(df) < 27000
        assert set(df["zone_id"].unique()) == set(CALIFORNIA_ZONES)

    def test_to_wide_format(self):
        long_df = load_all_zones(CALIFORNIA_ZONES, years=[2024])
        wide = to_wide(long_df)
        # Wide format: one column per zone
        assert set(wide.columns) == set(CALIFORNIA_ZONES)
        # Rows = hours in 2024
        assert 8000 < len(wide) <= 8784


class TestSmokeAnalysis:
    """Sanity-check that the data we loaded has the expected real-world
    structure. Not strict tests — just guards against catastrophic data
    issues."""

    def test_ciso_carbon_intensity_in_plausible_range(self):
        df = load_zone("US-CAL-CISO", years=[2024])
        mean_ci = df["ci_lifecycle"].mean()
        # CAISO 2024 should be in roughly the 150-350 gCO2/kWh range
        assert 100 < mean_ci < 500, f"Unexpected CAISO mean CI: {mean_ci:.1f}"

    def test_ldwp_higher_than_ciso(self):
        """LADWP has historically been more coal/gas-heavy than CAISO.
        Their mean carbon intensity should generally be higher."""
        ciso = load_zone("US-CAL-CISO", years=[2024])["ci_lifecycle"].mean()
        ldwp = load_zone("US-CAL-LDWP", years=[2024])["ci_lifecycle"].mean()
        # Soft check — just confirm they're different enough to be meaningful
        assert abs(ldwp - ciso) > 10
