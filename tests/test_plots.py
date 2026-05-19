"""Tests for src.analysis.plots.

These are smoke tests: plotting code is primarily visual, so the tests
confirm that each function runs without error and writes non-empty
PDF and PNG files to the requested directory.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analysis.plots import (
    plot_correlation_by_hour,
    plot_correlation_by_season,
)


@pytest.fixture
def synthetic_panel() -> pd.DataFrame:
    """One full year of synthetic 3-zone hourly data (covers all 4 seasons)."""
    n = 24 * 365
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(0)
    base = rng.normal(100.0, 30.0, n)
    return pd.DataFrame(
        {
            "US-CAL-CISO": base + rng.normal(0.0, 12.0, n),
            "US-CAL-BANC": 0.6 * base + rng.normal(0.0, 28.0, n),
            "US-CAL-LDWP": base + rng.normal(0.0, 16.0, n),
        },
        index=idx,
    )


def test_plot_by_hour_writes_pdf_and_png(synthetic_panel, tmp_path):
    paths = plot_correlation_by_hour(synthetic_panel, save_dir=tmp_path)
    assert len(paths) == 2
    assert {p.suffix for p in paths} == {".pdf", ".png"}
    for p in paths:
        assert p.exists()
        assert p.stat().st_size > 0


def test_plot_by_season_writes_pdf_and_png(synthetic_panel, tmp_path):
    paths = plot_correlation_by_season(synthetic_panel, save_dir=tmp_path)
    assert len(paths) == 2
    assert {p.suffix for p in paths} == {".pdf", ".png"}
    for p in paths:
        assert p.exists()
        assert p.stat().st_size > 0


def test_plot_creates_missing_output_directory(synthetic_panel, tmp_path):
    target = tmp_path / "nested" / "figures"
    assert not target.exists()
    paths = plot_correlation_by_hour(synthetic_panel, save_dir=target)
    assert target.exists()
    assert all(p.exists() for p in paths)


def test_plot_by_hour_is_repeatable(synthetic_panel, tmp_path):
    """Running twice overwrites cleanly and does not error."""
    first = plot_correlation_by_hour(synthetic_panel, save_dir=tmp_path)
    second = plot_correlation_by_hour(synthetic_panel, save_dir=tmp_path)
    assert [p.name for p in first] == [p.name for p in second]
    for p in second:
        assert p.stat().st_size > 0
