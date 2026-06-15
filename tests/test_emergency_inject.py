"""Tests for the Part 3 emergency-injection helper used in the stability experiment."""
import numpy as np

from scripts.run_parts34_stability import inject


def test_inject_zero_probability_is_identity():
    rng = np.random.default_rng(0)
    panel = np.ones((10, 3, 6)) * 2.0
    out = inject(panel, M=4.0, rng=rng, p=0.0)
    assert np.allclose(out, panel)             # no day perturbed


def test_inject_full_probability_scales_one_region_per_day():
    rng = np.random.default_rng(1)
    panel = np.ones((8, 3, 6))
    out = inject(panel, M=3.0, rng=rng, p=1.0)
    for day in out:
        scaled = np.isclose(day, 3.0).all(axis=1)   # which regions were multiplied
        assert scaled.sum() == 1                     # exactly one region per day
        untouched = np.isclose(day, 1.0).all(axis=1)
        assert untouched.sum() == 2


def test_inject_preserves_shape_and_does_not_mutate_input():
    rng = np.random.default_rng(2)
    panel = np.full((5, 4, 6), 2.0)
    ref = panel.copy()
    out = inject(panel, M=2.0, rng=rng, p=0.5)
    assert out.shape == panel.shape
    assert np.allclose(panel, ref)             # original untouched (copy semantics)
