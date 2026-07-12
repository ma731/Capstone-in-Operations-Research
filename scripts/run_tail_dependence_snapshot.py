"""Archive the tail-dependence table as a license-safe summary CSV.

WHY THIS EXISTS
---------------
The defense deck and the thesis quote the upper/lower tail-dependence asymmetry
(``chi_L > chi_U``: regions go clean together more than dirty together, e.g.
CISO | LDWP clean 0.48 vs dirty 0.25). ``scripts.plot_tail_dependence`` computes
those numbers but only *prints* them, so they were the one figure whose numbers
did not trace to an archived file. This script writes them to
``docs/results_snapshots/`` alongside every other reported number, so the claim
"every number traces to an archived snapshot" holds for the tail-dependence
figure too.

The output contains only derived aggregate statistics (rank-based tail
coefficients and Pearson rho), never the licensed Electricity Maps intensities,
so the non-redistribution academic licence does not apply -- same policy as the
other snapshots under ``docs/results_snapshots/``.

Run:
    .venv\\Scripts\\python -m scripts.run_tail_dependence_snapshot
    .venv\\Scripts\\python -m scripts.run_tail_dependence_snapshot --date 2026-07-05
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.analysis.stratified_correlations import DISPLAY_NAME, REGION_SETS
from src.analysis.tail_dependence import (
    residualize_hour_of_day,
    tail_dependence_table,
)
from src.data.electricitymaps import load_all_zones, to_wide

SNAP_DIR = Path("docs/results_snapshots")

# The three headline grids the deck/thesis report; the tail-dependence figure and
# the chi_L > chi_U asymmetry are drawn from these.
GRIDS = ("us_west", "taskc", "us_hetero")


def build_table(region_set: str, q: float) -> pd.DataFrame:
    """Raw + hour-of-day-residual tail-dependence table for one region set."""
    cfg = REGION_SETS[region_set]
    zones, tz = cfg["zones"], cfg["tz"]
    wide = to_wide(load_all_zones(zones))[zones]
    resid = residualize_hour_of_day(wide, tz)

    frames = []
    for series_name, frame in (("raw", wide), ("residual", resid)):
        tbl = tail_dependence_table(frame, q=q)
        tbl.insert(0, "grid", region_set)
        tbl.insert(1, "display", DISPLAY_NAME.get(region_set, region_set))
        tbl.insert(2, "series", series_name)
        tbl.insert(3, "n_obs", len(frame))
        frames.append(tbl)
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--q", type=float, default=0.95,
                    help="Tail quantile for chi_U(q); chi_L uses p = 1 - q. Default 0.95.")
    ap.add_argument("--date", default="2026-07-05",
                    help="Date stamp for the snapshot filename (YYYY-MM-DD).")
    ap.add_argument("--grids", nargs="+", default=list(GRIDS), choices=list(REGION_SETS),
                    help="Region sets to include (default: the three headline grids).")
    args = ap.parse_args()

    tables = [build_table(g, args.q) for g in args.grids]
    out = pd.concat(tables, ignore_index=True)

    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAP_DIR / f"tail_dependence_{args.date}.csv"
    out.to_csv(path, index=False)

    print(f"wrote {path}  ({len(out)} rows, q={args.q})")
    # Echo the clean-vs-dirty asymmetry the deck cites (residual series).
    res = out[out["series"] == "residual"]
    show = res[["grid", "pair", "chi_L_emp", "chi_U_emp", "chi_U_excess"]]
    print(show.to_string(index=False, float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
