"""Tests for src.analysis.stratified_correlations."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analysis.stratified_correlations import (
    SEASON_MAP,
    correlations_by_hour,
    correlations_by_season,
    correlations_by_weekday,
    summarize_all,
    to_local,
)


@pytest.fixture
def synthetic_panel() -> pd.DataFrame:
    """21 days of synthetic 3-zone hourly data, UTC-indexed.

    Construction: shared base signal + independent zone-specific noise,
    producing realistic moderate-to-strong correlations.
    """
    n = 24 * 21
    idx = pd.date_range("2024-03-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(42)
    base = rng.normal(100.0, 30.0, n)
    return pd.DataFrame(
        {
            "US-CAL-CISO": base + rng.normal(0.0, 5.0, n),
            "US-CAL-BANC": base + rng.normal(0.0, 15.0, n),
            "US-CAL-LDWP": base * 1.5 + rng.normal(0.0, 8.0, n),
        },
        index=idx,
    )


def test_to_local_converts_utc_to_pacific(synthetic_panel):
    local = to_local(synthetic_panel)
    assert local.index.tz is not None
    assert "Los_Angeles" in str(local.index.tz)


def test_to_local_assumes_utc_for_naive_index():
    idx = pd.date_range("2024-06-01", periods=48, freq="h")  # naive
    df = pd.DataFrame({"A": range(48), "B": range(48)}, index=idx)
    local = to_local(df)
    assert local.index.tz is not None
    assert "Los_Angeles" in str(local.index.tz)


def test_season_map_covers_all_months():
    assert set(SEASON_MAP.keys()) == set(range(1, 13))
    assert set(SEASON_MAP.values()) == {"DJF", "MAM", "JJA", "SON"}


def test_correlations_by_hour_returns_long_format(synthetic_panel):
    out = correlations_by_hour(synthetic_panel)
    assert {"stratum_type", "stratum", "pair", "correlation", "n_samples"} <= set(out.columns)
    assert (out["stratum_type"] == "hour").all()


def test_correlations_by_hour_covers_all_24_hours(synthetic_panel):
    out = correlations_by_hour(synthetic_panel)
    # 3 zones → 3 unique pairs (upper triangle); 24 hours → 72 rows
    assert len(out) == 24 * 3
    assert set(out["stratum"].unique()) == set(range(24))


def test_correlations_by_season_returns_subset_of_four(synthetic_panel):
    out = correlations_by_season(synthetic_panel)
    seasons_present = set(out["stratum"].unique())
    assert seasons_present <= {"DJF", "MAM", "JJA", "SON"}
    # March data, converted to Pacific time, will include MAM
    assert "MAM" in seasons_present


def test_correlations_by_weekday_returns_both_categories(synthetic_panel):
    out = correlations_by_weekday(synthetic_panel)
    assert set(out["stratum"].unique()) == {"weekday", "weekend"}


def test_correlations_are_bounded(synthetic_panel):
    """Pearson correlation is always in [-1, 1]."""
    for fn in (correlations_by_hour, correlations_by_season, correlations_by_weekday):
        out = fn(synthetic_panel)
        assert (out["correlation"] >= -1.0 - 1e-9).all()
        assert (out["correlation"] <= 1.0 + 1e-9).all()


def test_summarize_all_includes_three_stratum_types(synthetic_panel):
    out = summarize_all(synthetic_panel)
    assert set(out["stratum_type"].unique()) == {"hour", "season", "daytype"}


def test_n_samples_is_positive_integer(synthetic_panel):
    out = summarize_all(synthetic_panel)
    assert (out["n_samples"] > 0).all()
    assert pd.api.types.is_integer_dtype(out["n_samples"])
