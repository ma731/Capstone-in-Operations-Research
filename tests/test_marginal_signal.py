"""Tests for src.data.marginal_signal (roadmap D1 scaffold)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.data.marginal_signal import (
    LBS_PER_MWH_TO_G_PER_KWH,
    coverage_report,
    load_all_marginal_zones,
    load_marginal_zone,
    to_wide_marginal,
)


def _write_canonical(dirpath, zone, hours=48, start="2024-01-01"):
    ts = pd.date_range(start, periods=hours, freq="h", tz="UTC")
    df = pd.DataFrame({"timestamp_utc": ts, "marginal_ci": np.arange(hours) + 100.0})
    df.to_csv(dirpath / f"{zone}.csv", index=False)
    return df


def _write_watttime(dirpath, zone, hours=24, start="2024-01-01"):
    ts = pd.date_range(start, periods=hours, freq="h", tz="UTC")
    df = pd.DataFrame({"point_time": ts, "value": np.full(hours, 1000.0),
                       "frequency": 300, "market": "RTM"})
    df.to_csv(dirpath / f"{zone}.csv", index=False)
    return df


def test_load_canonical_schema(tmp_path):
    _write_canonical(tmp_path, "US-CAL-CISO")
    df = load_marginal_zone("US-CAL-CISO", raw_dir=tmp_path)
    assert list(df.columns) == ["timestamp_utc", "zone_id", "marginal_ci"]
    assert df.zone_id.unique().tolist() == ["US-CAL-CISO"]
    assert df.timestamp_utc.dt.tz is not None
    assert len(df) == 48
    assert df.marginal_ci.iloc[0] == 100.0


def test_load_watttime_schema_converts_units(tmp_path):
    _write_watttime(tmp_path, "US-CAL-CISO")
    df = load_marginal_zone("US-CAL-CISO", raw_dir=tmp_path)
    # 1000 lbs/MWh -> 453.59237 g/kWh
    assert df.marginal_ci.iloc[0] == pytest.approx(1000 * LBS_PER_MWH_TO_G_PER_KWH)
    assert df.marginal_ci.iloc[0] == pytest.approx(453.59237)


def test_missing_file_explains_data_access(tmp_path):
    with pytest.raises(FileNotFoundError, match="WattTime|licence|premium"):
        load_marginal_zone("US-NW-NEVP", raw_dir=tmp_path)


def test_unknown_schema_rejected(tmp_path):
    pd.DataFrame({"time": [1], "co2": [2]}).to_csv(tmp_path / "X.csv", index=False)
    with pytest.raises(ValueError, match="no known schema"):
        load_marginal_zone("X", raw_dir=tmp_path)


def test_stack_and_pivot_mirror_electricitymaps_shapes(tmp_path):
    _write_canonical(tmp_path, "ES")
    _write_canonical(tmp_path, "PT")
    long_df = load_all_marginal_zones(["ES", "PT"], raw_dir=tmp_path)
    wide = to_wide_marginal(long_df)
    assert set(wide.columns) == {"ES", "PT"}
    assert wide.shape == (48, 2)
    assert wide.index.name == "timestamp_utc"


def test_coverage_report_flags_gaps_and_missing_zones(tmp_path):
    _write_canonical(tmp_path, "ES", hours=48)
    _write_canonical(tmp_path, "PT", hours=24)  # covers only half the grid
    long_df = load_all_marginal_zones(["ES", "PT"], raw_dir=tmp_path)
    wide = to_wide_marginal(long_df)

    ts = pd.date_range("2024-01-01", periods=48, freq="h", tz="UTC")
    carbon_wide = pd.DataFrame(
        {"ES": 1.0, "PT": 1.0, "FR": 1.0}, index=ts)

    rep = coverage_report(wide, carbon_wide)
    assert rep.loc["ES", "coverage"] == pytest.approx(1.0)
    assert rep.loc["PT", "coverage"] == pytest.approx(0.5)
    assert rep.loc["FR", "coverage"] == 0.0
    assert rep.loc["FR", "hours_present"] == 0
