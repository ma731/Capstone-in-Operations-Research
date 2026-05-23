"""Algorithm 2a degeneracy demonstration on the 4-zone panel.

Run from project root:
    python scripts/run_algorithm2a_degeneracy_demo.py

Demonstrates the Phase 1 finding documented in progress_note_v8_3.tex
Section 2 ("The ell_infinity baseline and its degeneracy"):

    Under the natural ell_infinity Wasserstein lift to R^{R x T} with
    linear loss, non-negative compute, and binding work constraints, the
    optimal schedule is identical to the deterministic Algorithm 1
    schedule on the empirical mean field rho_bar -- for every epsilon and
    for every mean-preserving sample shuffle.

The script reports:
  1. Schedules under epsilon in {0, 1, 100, 10000} - identical to numerical
     precision.
  2. Joint vs per-region-shuffled panel - identical schedules and identical
     closed-form robust values.
  3. Closed-form decomposition: <rho_bar, x*> + epsilon * sum_r W_r.

Writes a markdown summary to docs/snippets/algorithm_2a_degeneracy.md for
direct citation in v8.3 Section 3 or in the thesis empirical chapter.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.data.electricitymaps import load_all_zones, to_wide
from src.models.algorithm_2a_linf import solve_linf_dro_baseline
from src.models.covariance import (
    REGION_ORDER,
    T_HOURS,
    build_daily_panel,
    per_region_temporal_shuffle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNIPPETS_DIR = PROJECT_ROOT / "docs" / "snippets"
SNIPPETS_DIR.mkdir(parents=True, exist_ok=True)


def short(zone: str) -> str:
    """US-CAL-BANC -> BANC, US-NW-NEVP -> NEVP."""
    return zone.rsplit("-", 1)[-1]


def main() -> None:
    print("=" * 72)
    print("Algorithm 2a degeneracy demonstration -- 4-zone panel")
    print("=" * 72)

    # ---- Load 4-zone panel ----
    long_df = load_all_zones(list(REGION_ORDER))
    wide = to_wide(long_df)
    panel, dates = build_daily_panel(wide)
    N, R, T = panel.shape
    print(f"\nLoaded panel: N={N} daily samples, R={R} zones, T={T} hours")
    print(f"  Zones (row-major): {[short(z) for z in REGION_ORDER]}")
    print(f"  Date range: {dates.min().date()} to {dates.max().date()}")

    # ---- Operator parameters ----
    # Workloads: 600 MWh per region (25 MW average over 24 hours). Ceiling:
    # flat 50 MW per hour per region. These are illustrative; the
    # degeneracy result is invariant to the specific values.
    workloads = np.full(R, 600.0)
    ceiling = np.full((R, T), 50.0)
    print(f"\nWorkloads: {workloads[0]:.0f} MWh per region; "
          f"sum_r W_r = {workloads.sum():.0f} MWh")
    print(f"Ceiling: flat {ceiling[0, 0]:.0f} MW per hour")

    # ---- 1. Epsilon invariance ----
    print("\n" + "-" * 72)
    print("1. Schedule invariance with respect to epsilon")
    print("-" * 72)
    epsilons = [0.0, 1.0, 100.0, 10_000.0]
    eps_results = [
        solve_linf_dro_baseline(panel, workloads, ceiling, epsilon=e)
        for e in epsilons
    ]
    baseline = eps_results[0].schedule
    max_dev = 0.0
    print(f"{'epsilon':>12} | {'robust_value (gCO2)':>22} | {'max |schedule - baseline|':>28}")
    for r, e in zip(eps_results, epsilons):
        dev = float(np.max(np.abs(r.schedule - baseline)))
        max_dev = max(max_dev, dev)
        print(f"{e:>12.1f} | {r.robust_value:>22,.0f} | {dev:>28.2e}")
    print(f"\nMax schedule deviation across epsilon: {max_dev:.2e} "
          f"({'PASS' if max_dev < 1e-3 else 'FAIL'} threshold 1e-3)")

    # ---- 2. Joint vs per-region-shuffled invariance ----
    print("\n" + "-" * 72)
    print("2. Joint vs per-region-shuffled invariance (epsilon = 100)")
    print("-" * 72)
    shuf = per_region_temporal_shuffle(panel, rng=np.random.default_rng(0))
    eps_for_shuffle = 100.0

    a2a_joint = solve_linf_dro_baseline(panel, workloads, ceiling, epsilon=eps_for_shuffle)
    a2a_shuf = solve_linf_dro_baseline(shuf, workloads, ceiling, epsilon=eps_for_shuffle)

    rho_bar_dev = float(np.max(np.abs(a2a_joint.rho_bar - a2a_shuf.rho_bar)))
    sched_dev = float(np.max(np.abs(a2a_joint.schedule - a2a_shuf.schedule)))
    rv_dev = abs(a2a_joint.robust_value - a2a_shuf.robust_value)

    print(f"  Per-coordinate rho_bar deviation:        {rho_bar_dev:.2e}")
    print(f"  Schedule max-element deviation:          {sched_dev:.2e}")
    print(f"  Robust value deviation (gCO2):           {rv_dev:.2e}")
    print(f"  Joint robust value: {a2a_joint.robust_value:>16,.0f} gCO2")
    print(f"  Shuf  robust value: {a2a_shuf.robust_value:>16,.0f} gCO2")

    # ---- 3. Closed-form decomposition ----
    print("\n" + "-" * 72)
    print("3. Closed-form decomposition at epsilon = 100")
    print("-" * 72)
    mcv = a2a_joint.mean_carbon_value
    pen = a2a_joint.penalty
    print(f"  <rho_bar, x*>           = {mcv:>16,.0f}  (empirical mean cost)")
    print(f"  epsilon * sum_r W_r     = {pen:>16,.0f}  (constant ell_1 penalty)")
    print(f"  robust_value (closed)   = {mcv + pen:>16,.0f}")
    print(f"  robust_value (reported) = {a2a_joint.robust_value:>16,.0f}")
    print(f"  decomposition residual  = {abs(a2a_joint.robust_value - mcv - pen):.2e}")

    # ---- 4. Per-region schedule summary ----
    print("\n" + "-" * 72)
    print("4. Optimal schedule summary, per region (epsilon = 0)")
    print("-" * 72)
    r0 = eps_results[0]
    print(f"{'zone':>6} | {'sum schedule (MWh)':>20} | {'mean schedule (MW)':>20} | "
          f"{'mean rho_bar (gCO2/kWh)':>26}")
    for r, zone in enumerate(REGION_ORDER):
        sch_sum = float(r0.schedule[r].sum())
        sch_mean = float(r0.schedule[r].mean())
        rho_mean = float(r0.rho_bar[r].mean())
        print(f"{short(zone):>6} | {sch_sum:>20.1f} | {sch_mean:>20.2f} | {rho_mean:>26.1f}")

    # ---- Write markdown snippet ----
    snippet_path = SNIPPETS_DIR / "algorithm_2a_degeneracy.md"
    snippet = f"""# Algorithm 2a empirical degeneracy summary

Source: `scripts/run_algorithm2a_degeneracy_demo.py`, 4-zone panel
(N={N}, R={R}, T={T}), dates {dates.min().date()} to {dates.max().date()}.
Workloads {workloads[0]:.0f} MWh/region; flat {ceiling[0, 0]:.0f} MW ceiling.

## Epsilon invariance

| epsilon | robust_value (gCO2) | max schedule deviation |
|---------|---------------------|------------------------|
"""
    for r, e in zip(eps_results, epsilons):
        dev = float(np.max(np.abs(r.schedule - baseline)))
        snippet += f"| {e:.1f} | {r.robust_value:,.0f} | {dev:.2e} |\n"

    snippet += f"""
Max schedule deviation across the four epsilon values: **{max_dev:.2e}** -- 
within numerical tolerance of zero, empirically confirming the closed-form
result that the argmin is independent of epsilon.

## Joint vs shuffled invariance (epsilon = {eps_for_shuffle})

- Per-coordinate rho_bar deviation: **{rho_bar_dev:.2e}**
- Schedule max-element deviation: **{sched_dev:.2e}**
- Robust value deviation: **{rv_dev:.2e}** gCO2 on a base of {a2a_joint.robust_value:,.0f} gCO2

The per-region temporal shuffle preserves rho_bar exactly (the residual
is floating-point noise), and consequently the A2a schedule and robust
value are identical to numerical precision. This is the empirical
confirmation of the joint-vs-shuffled degeneracy under ell_infinity.

## Closed-form decomposition

`robust_value = <rho_bar, x*> + epsilon * sum_r W_r`

- Mean term `<rho_bar, x*>`: {mcv:,.0f} gCO2
- Penalty term `epsilon * sum_r W_r`: {pen:,.0f} gCO2
- Decomposition residual: {abs(a2a_joint.robust_value - mcv - pen):.2e} gCO2

## Conclusion

The natural Wasserstein lift to R^(R*T) under the ell_infinity ground
metric is schedule-degenerate on this panel: epsilon does not affect
the optimal schedule, and the joint and per-region-shuffled ambiguity
balls yield identical schedules and identical robust values. The
Mahalanobis-Wasserstein reformulation of Algorithm 2b is therefore the
first formulation in this work in which the joint covariance structure
can affect the optimizer.
"""

    snippet_path.write_text(snippet, encoding="utf-8")
    print(f"\nWrote summary to {snippet_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
