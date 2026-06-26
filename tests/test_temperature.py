"""Synthetic tests for temperature panel alignment and summary.

These exercise the load-bearing plumbing (align_temperature_to_panel,
temperature_summary) on in-memory frames, so they run offline (no Open-Meteo
fetch) and pin behavior that was previously only touched by a network-gated
script: shape/date agreement with the carbon panel, short- and long-gap
filling, and that `pct_missing_raw` is computed BEFORE interpolation.
"""
import numpy as np
import pandas as pd

from src.data.temperature import align_temperature_to_panel, temperature_summary
from src.models.covariance import build_daily_panel

# Two zones that exist in STATION_COORDS (temperature_summary needs the coords).
ZONES = ["US-CAL-CISO", "US-CAL-BANC"]
TZ = "America/Los_Angeles"


def _wide(n_days=4):
    """A carbon-like wide frame: tz-aware UTC index spanning `n_days` complete
    LA-local days (June, so no DST transition), one column per zone."""
    local = pd.date_range("2021-06-01 00:00", periods=24 * n_days, freq="h", tz=TZ)
    idx = local.tz_convert("UTC")
    data = {z: np.linspace(10.0, 30.0, len(idx)) + i * 5.0 for i, z in enumerate(ZONES)}
    return pd.DataFrame(data, index=idx)


def test_align_shape_and_dates_match_carbon():
    carbon = _wide(4)
    temp = _wide(4)
    _, c_dates = build_daily_panel(carbon, region_order=ZONES, tz=TZ)
    t_panel, t_dates = align_temperature_to_panel(temp, carbon, region_order=ZONES, tz=TZ)
    assert t_panel.shape == (4, len(ZONES), 24)
    assert list(t_dates) == list(c_dates)   # same kept-day set as the carbon panel
    assert np.isfinite(t_panel).all()


def test_align_fills_short_and_long_gaps_keeping_all_days():
    carbon = _wide(4)
    temp = _wide(4)
    ci = temp.columns.get_loc("US-CAL-CISO")
    ba = temp.columns.get_loc("US-CAL-BANC")
    temp.iloc[5:8, ci] = np.nan      # short 3 h gap (within the 6 h interp limit)
    temp.iloc[40:70, ba] = np.nan    # long 30 h gap spanning a day boundary
    t_panel, _ = align_temperature_to_panel(temp, carbon, region_order=ZONES, tz=TZ)
    # No day is dropped and no residual NaN survives (ffill/bfill backstops interp).
    assert t_panel.shape == (4, len(ZONES), 24)
    assert np.isfinite(t_panel).all()


def test_summary_pct_missing_is_pre_interpolation():
    carbon = _wide(4)
    temp = _wide(4)
    n_missing = 12
    temp.iloc[0:n_missing, temp.columns.get_loc("US-CAL-CISO")] = np.nan
    t_panel, _ = align_temperature_to_panel(temp, carbon, region_order=ZONES, tz=TZ)
    summ = temperature_summary(t_panel, temp, carbon, region_order=ZONES).set_index("zone")
    total = len(carbon)  # 96 hourly rows
    # pct_missing_raw reflects the RAW NaNs, before align's interpolation.
    assert abs(summ.loc["US-CAL-CISO", "pct_missing_raw"] - 100.0 * n_missing / total) < 1e-9
    assert summ.loc["US-CAL-BANC", "pct_missing_raw"] == 0.0
    # ...yet the aligned panel is gap-free, proving the fill happened downstream.
    assert np.isfinite(t_panel).all()
