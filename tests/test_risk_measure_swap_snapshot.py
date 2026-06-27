"""Snapshot-binding test for the risk-measure-swap generality probe.

Pins the result the thesis robustness subsection reports (swapping the coherent
mean-std DRO for a non-coherent mean-variance objective does NOT make modelling
cross-region covariance pay out of sample, so the spatial null is not an artifact
of CVaR's translation invariance) to its archived, license-safe snapshot, so a code
change cannot silently drift the numbers. Source of truth:
docs/results_snapshots/risk_measure_swap_2026-06-27.csv, from
scripts/run_risk_measure_swap.py.
"""
import csv
from pathlib import Path


def _load_rows():
    snap = (Path(__file__).resolve().parents[1] / "docs" / "results_snapshots"
            / "risk_measure_swap_2026-06-27.csv")
    return list(csv.DictReader(snap.open()))


def _mv_balanced(rows, grid):
    """The mean-variance row at lam = 1x lam_ref (variance term balances the mean)."""
    for r in rows:
        if (r["grid"] == grid and r["objective"] == "mean_variance"
                and r["param_value"] == "1.0"):
            return r
    raise AssertionError(f"no balanced mean-variance row for {grid}")


def test_dro_reference_reproduces_the_null():
    """The coherent objective: joint-vs-shuffled CVaR gap stays tiny and flips sign."""
    rows = _load_rows()
    dro = [r for r in rows if r["objective"] == "mean_std_dro"]
    assert dro, "no DRO reference rows"
    assert max(abs(float(r["cvar_gap_pct"])) for r in dro) < 1.0


def test_meanvar_swap_does_not_rescue_covariance():
    """At the balanced weighting the bootstrap CI excludes zero on every grid, but
    covariance HURTS the tail on two of three grids and helps only trivially on the
    third: the swap indicts covariance rather than rescuing it."""
    rows = _load_rows()

    # us_hetero and us_west: modelling joint covariance significantly WORSENS OOS CVaR.
    for grid, gap, lo, hi in [("us_hetero", -0.84, -1.02, -0.63),
                              ("us_west", -1.50, -1.92, -1.18)]:
        r = _mv_balanced(rows, grid)
        assert round(float(r["boot_gap_pct"]), 2) == gap
        assert float(r["boot_hi_pct"]) < 0.0, f"{grid} CI should exclude 0 on the negative side"
        assert round(float(r["boot_lo_pct"]), 2) == lo
        assert round(float(r["boot_hi_pct"]), 2) == hi

    # taskc: detectable but economically trivial benefit (< 0.2% of CVaR).
    r = _mv_balanced(rows, "taskc")
    assert 0.0 < float(r["boot_gap_pct"]) < 0.2
    assert float(r["boot_lo_pct"]) > 0.0


def test_swap_moves_the_schedule():
    """Sanity check that the swap is non-trivial: covariance DOES enter the decision
    (schedules diverge by up to ~30%), so the small CVaR gap is not because the
    objective ignored the covariance."""
    rows = _load_rows()
    mv = [r for r in rows if r["objective"] == "mean_variance"]
    assert max(float(r["sched_diff_pct"]) for r in mv) > 20.0
