"""Phase 3 (Task A): re-validate non-triviality on the REVISED feasible set.

The revised set X drops the aggregate power cap and keeps:
    per-cell ceiling + flex/inflexible split (C2) + ramp (C3)
and ADDS:
    windowed-demand / deferral-deadline (3a) + temperature-coupled thermal (3b).

This script proves, on a small hand-controllable instance, that:
  (1) the per-region GREEDY sort (cheapest-hours-first) is INFEASIBLE on the
      new set -- it violates ramp, the deadline window, and/or the thermal cap;
  (2) a SOLVER is required: the optimal objective differs from the (infeasible)
      greedy objective, and the coupled-A1 optimum equals A2b at epsilon=0;
  (3) which constraints BIND, with their binding margins;
  (4) GOLDILOCKS: whether the feasible set still has wiggle room (the DRO
      reallocates as epsilon grows) or has frozen (over-constrained).

Uses the REAL repo functions (schedule_deterministic_coupled,
greedy_sort_schedule_multiregion, solve_mahalanobis_dro). Self-contained:
synthetic carbon + temperature fields, no data download.
"""
from __future__ import annotations

import numpy as np

from src.data.temperature import pue_from_temperature
from src.models.algorithm_1 import (
    greedy_sort_schedule_multiregion,
    schedule_deterministic_coupled,
)
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro

np.set_printoptions(precision=2, suppress=True, linewidth=140)

# ----------------------------------------------------------------------
# Toy instance: R=3 regions, T=12 hours. Hand-built so each new constraint
# is calibrated to bind LOOSELY (active but not dominant), per the brief.
# ----------------------------------------------------------------------
R, T = 3, 12
RO = ("R0", "R1", "R2")

# Carbon: a smooth diurnal trough mid-day (hours 4-7 cheap, dawn/dusk dear),
# with small per-region phase offsets so regions are not identical.
hours = np.arange(T)
base = 300 + 120 * np.cos((hours - 6) * np.pi / 6)   # min near hour 6
RHO = np.vstack([
    base,
    np.roll(base, 1) + 8.0,
    np.roll(base, -1) - 5.0,
]).astype(float)
RHO = np.clip(RHO, 60.0, None)

CEIL = np.full((R, T), 10.0)               # per-cell ceiling, MW
# Utilization ~0.55 of fleet ceiling-hours: leaves genuine scheduling freedom.
W = np.full(R, 0.55 * 10.0 * T)            # MWh/region
ALPHA = np.array([0.50, 0.50, 0.50])       # half the work is flexible
RAMP = np.array([3.0, 3.0, 3.0])           # MW/h ramp limit (loose-ish)

# Deferral deadline: 30% of flexible work must be served in the morning
# window hours [1,4] (which straddles the dear-ish dawn and the cheap trough
# edge) -- active but leaves the bulk of flex free.
DEFERRAL = [(1, 4, 0.30)]

# Temperature: hot afternoon bump peaking ~hour 8 (post-solar), so PUE rises
# where some cheap hours sit; bar_P chosen to throttle but not forbid.
TEMP = 18.0 + 16.0 * np.clip(np.cos((hours - 8) * np.pi / 7), 0, None)  # up to 34 C
TEMP = np.vstack([TEMP, TEMP + 2.0, TEMP - 1.0])
PUE0, KAPPA, T_SET = 1.10, 0.015, 20.0
# nominal effective ceiling at floor PUE is 10*1.10 = 11.0; set bar_P just
# below it so the cap bites (binds) in the hottest hours but is not dominant.
BAR_P = 11.0

L_ID = np.linalg.cholesky(np.eye(R * T) * 100.0)


def _violations(x, label):
    """Report how a candidate schedule x violates the revised set."""
    print(f"\n  [{label}] feasibility audit against the revised set:")
    # work / split
    work = x.sum(axis=1)
    print(f"    work per region        : {work}  (target {W})")
    # ramp
    ramp_viol = max(
        abs(x[r, t] - x[r, t - 1]) - RAMP[r]
        for r in range(R) for t in range(1, T)
    )
    print(f"    max ramp excess        : {ramp_viol:+.2f} MW   "
          f"({'VIOLATED' if ramp_viol > 1e-6 else 'ok'})")
    # deadline (greedy has no split; treat ALL of x as if schedulable -> still
    # check the window fraction of the flexible target)
    flex_target = (1 - ALPHA) * W
    for (t1, t2, g) in DEFERRAL:
        served = x[:, t1:t2 + 1].sum(axis=1)
        deficit = g * flex_target - served
        worst = deficit.max()
        print(f"    deadline win[{t1},{t2}] g={g}: served {served}, "
              f"need>={g*flex_target}  ({'VIOLATED' if worst > 1e-6 else 'ok'})")
    # thermal
    pue = pue_from_temperature(TEMP, PUE0, KAPPA, T_SET)
    eff = pue * x
    therm_excess = (eff - BAR_P).max()
    print(f"    max thermal excess     : {therm_excess:+.2f}    "
          f"({'VIOLATED' if therm_excess > 1e-6 else 'ok'})")
    return ramp_viol > 1e-6 or therm_excess > 1e-6


def main() -> int:
    print("=" * 78)
    print("  PHASE 3 -- NON-TRIVIALITY ON THE REVISED FEASIBLE SET (NO CAP)")
    print("=" * 78)
    print(f"  R={R}, T={T}, util~0.55, alpha=0.50, ramp=3, deadline={DEFERRAL}, "
          f"bar_P={BAR_P}")

    # ---- (1) Greedy sort, and its infeasibility -------------------------
    g = greedy_sort_schedule_multiregion(RHO, W, CEIL)
    g_obj = float((RHO * g).sum())
    print(f"\n(1) Greedy sort objective (cheapest-hours-first): {g_obj:,.1f} gCO2")
    greedy_infeasible = _violations(g, "greedy")
    print(f"\n    => greedy is {'INFEASIBLE' if greedy_infeasible else 'FEASIBLE'} "
          f"on the revised set.")
    assert greedy_infeasible, "expected greedy to violate the revised set"

    # ---- (2) Solver required: coupled A1 == A2b(eps=0), objective != greedy
    a1 = schedule_deterministic_coupled(
        RHO, W, CEIL, p_max=None, alpha=ALPHA, ramp=RAMP,
        deferral_windows=DEFERRAL, temperature=TEMP, bar_P=BAR_P,
        pue0=PUE0, kappa=KAPPA, t_set=T_SET,
    )
    a2b0 = solve_mahalanobis_dro(
        RHO, L_ID, W, CEIL, 0.0, region_order=RO,
        p_max=None, alpha=ALPHA, ramp=RAMP,
        deferral_windows=DEFERRAL, temperature=TEMP, bar_P=BAR_P,
        pue0=PUE0, kappa=KAPPA, t_set=T_SET,
    )
    print(f"\n(2) Coupled-A1 optimum objective              : {a1.total_carbon:,.1f} gCO2")
    print(f"    A2b(eps=0) mean-carbon objective          : {a2b0.mean_carbon_value:,.1f} gCO2")
    print(f"    |A1 - A2b(eps=0)| schedule max-dev        : "
          f"{np.max(np.abs(a1.schedule - a2b0.schedule)):.2e}")
    print(f"    optimum - greedy (greedy is infeasible)   : "
          f"{a1.total_carbon - g_obj:+,.1f} gCO2")
    assert abs(a1.total_carbon - a2b0.mean_carbon_value) < 1e-1
    assert abs(a1.total_carbon - g_obj) > 1.0, "solver must differ from greedy"
    print("    => a SOLVER is required; the greedy closed form does not apply.")

    # ---- (3) Binding report + margins -----------------------------------
    b = a1.binding
    print("\n(3) Which constraints BIND on the revised set:")
    print(f"    aggregate cap          : ABSENT (dropped)  "
          f"[{'cap_tight_hours' not in b and 'confirmed off' or 'PRESENT?!'}]")
    print(f"    ramp tight transitions : {b.get('ramp_tight_transitions')}"
          f" / {R*(T-1)} transitions")
    print(f"    thermal tight cells    : {b.get('thermal_tight_cells')}"
          f" / {R*T} cells   (min slack {b.get('thermal_min_margin'):+.3f})")
    dm = b.get("deferral_margins", [])
    tightest = min((m for (_, _, _, m) in dm), default=float('nan'))
    print(f"    deadline tight windows : {b.get('deferral_tight_windows')}"
          f" / {len(dm)}   (tightest slack {tightest:+.3f} MWh)")
    # inflexible base pinned: schedule >= inflex base everywhere
    inflex = b["inflex_base"]
    print(f"    inflexible base pinned : min(x - base) = "
          f"{(a1.schedule - inflex).min():+.3f} (>=0 required)")

    # ---- (4) GOLDILOCKS: does the DRO still move? -----------------------
    print("\n(4) GOLDILOCKS -- degrees of freedom / can the DRO reallocate?")
    # Build a non-trivial joint covariance so the penalty has a gradient.
    rng = np.random.default_rng(0)
    A = rng.normal(size=(R * T, R * T))
    Sigma = A @ A.T + np.eye(R * T)             # SPD
    L = np.linalg.cholesky(Sigma)
    moves = []
    base_sched = a2b0.schedule
    for eps in (0.0, 1.0, 10.0, 100.0):
        res = solve_mahalanobis_dro(
            RHO, L, W, CEIL, eps, region_order=RO,
            p_max=None, alpha=ALPHA, ramp=RAMP,
            deferral_windows=DEFERRAL, temperature=TEMP, bar_P=BAR_P,
            pue0=PUE0, kappa=KAPPA, t_set=T_SET,
        )
        l1 = float(np.abs(res.schedule - base_sched).sum())
        moves.append((eps, l1, res.mean_carbon_value, res.penalty))
        print(f"    eps={eps:>7.1f}:  ||x_eps - x_0||_1 = {l1:8.3f} MWh   "
              f"mean={res.mean_carbon_value:,.0f}  penalty={res.penalty:,.1f}")

    total_work = float(W.sum())
    max_move = max(m[1] for m in moves)
    move_frac = max_move / total_work
    # crude DoF accounting: free cells = cells strictly interior to all bounds
    at_ceiling = np.isclose(base_sched, CEIL, atol=1e-3).sum()
    at_floor = np.isclose(base_sched, inflex, atol=1e-3).sum()
    thermal_tight = b.get("thermal_tight_cells", 0)
    pinned = at_ceiling + thermal_tight
    free_cells = R * T - pinned
    print(f"\n    total flexible work        : {total_work:.0f} MWh")
    print(f"    max DRO reallocation       : {max_move:.2f} MWh "
          f"({100*move_frac:.1f}% of total work)")
    print(f"    cells at ceiling           : {at_ceiling}/{R*T}")
    print(f"    cells thermal-capped       : {thermal_tight}/{R*T}")
    print(f"    cells at inflexible floor  : {at_floor}/{R*T}")
    print(f"    approx. free (interior) cells: {free_cells}/{R*T}")

    if move_frac < 0.005:
        verdict = ("OVER-CONSTRAINED: the DRO cannot move the schedule; the "
                   "feasible set has frozen. A spatial effect cannot show here.")
    elif move_frac > 0.30:
        verdict = ("UNDER-CONSTRAINED: the set is so loose the penalty drives "
                   "huge reallocation; constraints barely shape the optimum.")
    else:
        verdict = ("APPROPRIATELY CONSTRAINED: constraints bind but the DRO "
                   "retains room to reallocate -- a spatial effect CAN show.")
    print(f"\n    GOLDILOCKS VERDICT: {verdict}")

    print("\n" + "=" * 78)
    print("  PHASE 3 COMPLETE: greedy INFEASIBLE, solver required, margins above.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
