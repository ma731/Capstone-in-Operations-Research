"""Tests for the CFE-driven variable-capacity field (Task C, constraint 3c).

Pure unit tests on capacity_from_cfe (the deterministic CFE -> ceiling mapping)
and cfe_field (training-mean field selection). No real data required.
"""

import numpy as np
import pandas as pd
import pytest

from src.data.capacity import capacity_from_cfe, cfe_field


class TestCapacityFromCFE:
    def test_endpoints(self):
        # CFE=0 -> x_min, CFE=100 -> x_max, CFE=50 -> midpoint.
        assert np.isclose(capacity_from_cfe(np.array([0.0]), 30, 60)[0], 30.0)
        assert np.isclose(capacity_from_cfe(np.array([100.0]), 30, 60)[0], 60.0)
        assert np.isclose(capacity_from_cfe(np.array([50.0]), 30, 60)[0], 45.0)

    def test_clips_out_of_range_cfe(self):
        # Noisy CFE outside [0,100] is clipped, never escaping [x_min, x_max].
        assert np.isclose(capacity_from_cfe(np.array([-10.0]), 30, 60)[0], 30.0)
        assert np.isclose(capacity_from_cfe(np.array([150.0]), 30, 60)[0], 60.0)

    def test_monotone_increasing_and_bounded(self):
        cfe = np.array([[0.0, 25.0, 50.0, 75.0, 100.0]])
        cap = capacity_from_cfe(cfe, 40, 60)
        assert cap.shape == cfe.shape
        assert np.all(np.diff(cap[0]) > 0)          # more clean power -> more capacity
        assert cap.min() >= 40.0 and cap.max() <= 60.0

    def test_validation(self):
        with pytest.raises(ValueError):
            capacity_from_cfe(np.array([50.0]), -1, 60)   # x_min < 0
        with pytest.raises(ValueError):
            capacity_from_cfe(np.array([50.0]), 60, 40)   # x_max < x_min


class TestCFEField:
    def test_mean_over_all_days(self):
        panel = np.stack([
            np.full((2, 4), 10.0),
            np.full((2, 4), 20.0),
            np.full((2, 4), 30.0),
        ])
        dates = pd.DatetimeIndex(["2021-01-01", "2021-01-02", "2022-01-01"])
        assert np.allclose(cfe_field(panel, dates), 20.0)

    def test_year_selection(self):
        panel = np.stack([
            np.full((2, 4), 10.0),
            np.full((2, 4), 20.0),
            np.full((2, 4), 30.0),
        ])
        dates = pd.DatetimeIndex(["2021-01-01", "2021-01-02", "2022-01-01"])
        # 2021 mean = (10 + 20) / 2 = 15; keeps the 2022 day out.
        assert np.allclose(cfe_field(panel, dates, years=[2021]), 15.0)

    def test_empty_year_raises(self):
        panel = np.full((1, 2, 4), 10.0)
        dates = pd.DatetimeIndex(["2021-01-01"])
        with pytest.raises(ValueError):
            cfe_field(panel, dates, years=[1999])
