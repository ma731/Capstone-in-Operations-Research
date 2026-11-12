"""Illustrative enterprise value case for the migration lever (RQ1).

What is measured: on the three studied grids, letting flexible compute move between
regions cut WORST-DAY emissions (CVaR at 95%, the average of the worst 5% of days) by the
percentages in docs/results_snapshots/part3_transfer_value_2026-06-15.csv.

What is NOT measured, and therefore not claimed here: the change in average-day emissions.
So this case only values the worst ~18 days a year. Every other number below is an
assumption you can change. Run from the repo root:

    python scripts/value_case.py
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "docs" / "results_snapshots" / "part3_transfer_value_2026-06-15.csv"

WORST_DAYS_PER_YEAR = round(0.05 * 365)    # CVaR 95% = the worst 5% of days
CARBON_PRICE_EUR_PER_T = 70                # assumption: an EU-ETS-like price; check the current one
WORST_DAY_INTENSITY_G_PER_KWH = 400        # assumption: carbon intensity of the grid mix on a bad day

# Illustrative fleets of FLEXIBLE AI compute (training and batch jobs that can wait or move),
# as an average power draw. Inference that must answer users now is not flexible.
PROFILES = [("Enterprise AI team", 5), ("Large AI programme", 25), ("AI training campus", 100)]


def measured_range():
    with open(SNAP, newline="") as f:
        cuts = [float(r["reduction_pct"]) / 100 for r in csv.DictReader(f)]
    return min(cuts), max(cuts)


def case(mw: float, lo: float, hi: float):
    worst_day_t = mw * 24 * WORST_DAY_INTENSITY_G_PER_KWH / 1000     # MWh x g/kWh = kg; /1000 = t
    yearly_exposure_t = worst_day_t * WORST_DAYS_PER_YEAR
    return worst_day_t, yearly_exposure_t * lo, yearly_exposure_t * hi


def main():
    lo, hi = measured_range()
    print(f"Measured worst-day cut: {lo:.1%} to {hi:.1%} | {WORST_DAYS_PER_YEAR} worst days a year | "
          f"{WORST_DAY_INTENSITY_G_PER_KWH} g/kWh on a bad day | carbon at EUR {CARBON_PRICE_EUR_PER_T}/t\n")
    print("| Flexible AI compute | Worst-day emissions | CO2 avoided on worst days, per year | At the carbon price |")
    print("|---|---|---|---|")
    for name, mw in PROFILES:
        day, a, b = case(mw, lo, hi)
        print(f"| {name}: {mw} MW | {day:,.0f} t/day | {a:,.0f} to {b:,.0f} t | "
              f"EUR {a * CARBON_PRICE_EUR_PER_T:,.0f} to {b * CARBON_PRICE_EUR_PER_T:,.0f} |")


if __name__ == "__main__":
    main()
