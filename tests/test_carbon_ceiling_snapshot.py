"""Snapshot-binding test for the RQ3 carbon-ceiling severities.

Pins the data-grounded emergency severities the thesis reports (Section
res-crossover: real grids reach only M~1.3-1.9, well below the M*~3 crossover)
to their archived, license-safe snapshot, so a code change cannot silently
drift the RQ3 numbers. This is the RQ3 counterpart of the RQ1 transfer-headline
guard in tests/test_transfer_dro.py. Source of truth:
docs/results_snapshots/carbon_ceiling_2026-06-24.csv, from scripts/run_carbon_ceiling.py.
"""
import csv
from pathlib import Path


def _load_severities():
    snap = (Path(__file__).resolve().parents[1] / "docs" / "results_snapshots"
            / "carbon_ceiling_2026-06-24.csv")
    rows = list(csv.DictReader(snap.open()))
    return {(r["kind"], r["key"]): float(r["severity"]) for r in rows}


def test_carbon_ceiling_matches_thesis():
    sev = _load_severities()

    # Joint (portfolio) per-grid severities reported in the body, to 2 dp.
    assert round(sev[("joint", "us_west")], 2) == 1.34
    assert round(sev[("joint", "taskc")], 2) == 1.29
    assert round(sev[("joint", "us_hetero")], 2) == 1.89

    # The decisive RQ3 claim: no grid's joint severity reaches the M*~3 crossover.
    joint_max = max(v for (kind, _), v in sev.items() if kind == "joint")
    assert joint_max < 3.0, f"a joint severity reached the M*~3 crossover: {joint_max}"

    # Per-region extremes on near-zero-carbon bases (1 dp) and Winter Storm Uri.
    assert round(sev[("region", "US-NW-BPAT")], 1) == 5.1
    assert round(sev[("region", "CA-ON")], 1) == 2.6
    assert round(sev[("event", "US-TEX-ERCO__Uri2021")], 1) == 1.3
