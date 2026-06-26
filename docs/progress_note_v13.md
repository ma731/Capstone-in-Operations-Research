# Progress note v13 — revised feasible set + re-run (Task A)

**Date:** 2026-06-02 (UTC). **Supersedes v12.**
**Scope:** Revise the feasible set X (drop the aggregate power cap; add a
windowed-demand deadline and a temperature-coupled thermal/PUE constraint),
re-validate non-triviality, and re-run the four-zone joint-vs-shuffled DRO
experiment + robustness lines on the new set. **The DRO method (Algorithm 2b,
Mahalanobis–Wasserstein SOCP) is unchanged; only X changed.**

---

## 1. Headline

**The null survives on the revised feasible set, and it is substantive — not a
mechanical artifact of an over-tight set.** Across all three constraint regimes
and all three alpha levels, pairing the *joint* covariance with the
Mahalanobis–Wasserstein scheduler instead of the *block-diagonal (shuffled)*
covariance changes out-of-sample tail emissions (CVaR₀.₉₅ on held-out 2025) by
**at most 0.06 %**, and in most cells by under 0.03 %. This is the same order as
the prior P_max=180 null (≈0.01–0.05 %). The binding-margin audit shows every
regime retains 24–32 % schedule-reallocation room (verdict *loose-OK*, none
frozen), so the null reflects genuine absence of exploitable spatial structure,
not a collapsed feasible set.

This re-confirms, on a cleaner and more physically defensible feasible set, the
v10–v12 finding: **spatial correlation of California carbon intensity adds
negligible robust value to the schedule.**

---

## 2. What changed in the feasible set

| constraint | status | form |
|---|---|---|
| per-cell ceiling (C0) | kept | `0 ≤ x ≤ x̄` |
| flex/inflexible split (C2) | kept | `x = αW·p + x_flex`, `Σ_t x_flex = (1−α)W` |
| ramp (C3) | kept | `|x_{r,t} − x_{r,t−1}| ≤ Δ_r` |
| **aggregate cap (C1)** | **DROPPED** | `p_max=None` (verified bypass, not re-coded) |
| **windowed-demand / deadline (3a)** | **ADDED** | `Σ_{t∈[τ1,τ2]} x_flex ≥ γ(1−α)W` (aggregate, not per-job SLA) |
| **thermal / PUE (3b)** | **ADDED** | `PUE(T)·x ≤ P̄`, `PUE(T)=pue0+κ·max(T−T_set,0)` |

All new kwargs default OFF; existing behavior unbroken (full suite 141 passed,
0 regressions; 13 new tests in `tests/test_constraints_taskA.py`).

Math docs: `thesis/full_formulation.md`, `thesis/constraints_explained.md`.

---

## 3. Temperature data (new external source)

Open-Meteo historical archive API (ERA5 reanalysis), hourly 2 m air temperature,
2021-01-01 → 2025-12-31, UTC grid, cached under `data/raw/temperature/` (one CSV
per zone; re-runs hit the cache). One representative load-center point per zone:

| zone | point | coord |
|---|---|---|
| US-CAL-CISO | Fresno / Central Valley (warm inland, not coastal SF; distinct from LDWP) | 36.738, −119.787 |
| US-CAL-BANC | Sacramento | 38.582, −121.494 |
| US-CAL-LDWP | Los Angeles | 34.052, −118.244 |
| US-NW-NEVP | Las Vegas | 36.172, −115.139 |

**Verification Gate 1 — PASS.** Temperature is aligned through the *same*
`build_daily_panel` as carbon → an identical (1815, 4, 24) panel, date-for-date,
REGION_ORDER preserved. Timezone confirmed: a hot LA July afternoon (local 15:00
= 22:00 UTC) reads 28.8 °C; pre-dawn (local 05:00) reads 17.1 °C; panel hour axis
is LA-local (summer t=15 mean 29.5 °C ≫ t=05 mean 17.1 °C). Per-zone stats (% NaN
= 0, ERA5 is gap-free):

| zone | min | mean | max (°C) |
|---|---|---|---|
| CISO (Fresno) | −1.6 | 19.0 | 47.7 |
| BANC (Sacramento) | −3.0 | 17.0 | 47.4 |
| LDWP (Los Angeles) | 0.9 | 17.7 | 45.7 |
| NEVP (Las Vegas) | −4.4 | 21.5 | 47.4 |

**Note (carried subtlety):** the carbon panel's hour index is *LA-local*, not raw
UTC — `build_daily_panel` converts UTC→America/Los_Angeles before day-grouping.
The brief assumed pure UTC; alignment is to the carbon panel exactly (the robust
choice), so this is handled, not a discrepancy in results.

---

## 4. Non-triviality + Goldilocks (Phase 3)

`scripts/toy_validation_taskA.py` (R=3, T=12, util 0.55, no cap): the per-region
greedy sort is **INFEASIBLE** (violates ramp +7 MW and thermal +1.45), a solver
is **required** (optimum 51,073 vs infeasible greedy 46,163; A1 == A2b at ε=0),
constraints bind loosely (ramp 7/33, thermal 8/36, deadline 1/3) and the DRO
still reallocates ~20 % of work as ε grows → **APPROPRIATELY CONSTRAINED**.

Calibration of the real config was chosen on **training data only**
(`scripts/calibrate_taskA_regimes.py`): deadline window [0,7] (morning, off the
cheap solar trough at hours 8–15), γ=0.20; thermal pue0=1.10, κ=0.015/°C,
T_set=20 °C, P̄=57 MW (floor effective load pue0·ceiling = 55). Both bind loosely.

**Binding-margin audit on real data (`scripts/report_binding_margins_taskA.py`):**

| regime | α | ramp tight /92 | thermal tight /96 | deadline tight | DRO move (% work) | verdict |
|---|---|---|---|---|---|---|
| R3_reference | 0.30 | 15 | – | – | 27.6 | loose-OK |
| R3_reference | 0.50 | 19 | – | – | 27.3 | loose-OK |
| R3_reference | 0.75 | 10 | – | – | 24.2 | loose-OK |
| R1_lean | 0.30 | 19 | – | 3/4 | 31.5 | loose-OK |
| R1_lean | 0.50 | 18 | – | 4/4 | 31.1 | loose-OK |
| R1_lean | 0.75 | 4 | – | 4/4 | 25.5 | loose-OK |
| R2_full | 0.30 | 21 | 27 | 3/4 | 30.2 | loose-OK |
| R2_full | 0.50 | 18 | 26 | 4/4 | 29.9 | loose-OK |
| R2_full | 0.75 | 6 | 22 | 4/4 | 25.2 | loose-OK |

Every cell is *loose-OK*: constraints active but the optimizer keeps 24–32 %
reallocation room. **The set is not frozen in any regime — the null is
substantive (correlation genuinely adds nothing), not mechanical.**

---

## 5. Main re-run (Phase 4) — spatial gap by regime × alpha

Regimes: **R3** = ceiling+split+ramp (post-cap baseline); **R1** = R3+deadline;
**R2** = R1+thermal. Blocked 5-fold CV for ε on 2021–24, held-out 2025 test,
1000-bootstrap CI on the CVaR₀.₉₅ gap (shuf − joint; positive = joint better).
Util fixed 0.80, ceiling 50 MW, ramp 15 MW/h, ε-grid {0,0.1,1,10,100,1000}.
Every CV selected ε*=1.0 (interior, no boundary). `results/taskA_regimes_2026-06-02.csv`.

| regime | α | joint CVaR | shuf CVaR | gap_abs | gap_% | 95 % CI | detectable |
|---|---|---|---|---|---|---|---|
| R3 | 0.30 | 1,591,553 | 1,592,482 | +928.6 | +0.0583 | [211, 1942] | yes |
| R3 | 0.50 | 1,592,885 | 1,593,454 | +569.4 | +0.0357 | [−532, 2177] | no |
| R3 | 0.75 | 1,597,017 | 1,596,823 | −194.4 | −0.0122 | [−581, 488] | no |
| R1 | 0.30 | 1,592,284 | 1,592,545 | +261.2 | +0.0164 | [−118, 831] | no |
| R1 | 0.50 | 1,593,895 | 1,594,327 | +431.8 | +0.0271 | [−359, 1577] | no |
| R1 | 0.75 | 1,597,645 | 1,597,671 | +26.7 | +0.0017 | [13, 41] | yes* |
| R2 | 0.30 | 1,594,451 | 1,594,746 | +294.3 | +0.0185 | [34, 693] | yes |
| R2 | 0.50 | 1,595,870 | 1,596,288 | +418.5 | +0.0262 | [−267, 1366] | no |
| R2 | 0.75 | 1,599,268 | 1,599,294 | +26.7 | +0.0017 | [13, 41] | yes* |

`*` "detectable" but economically meaningless: the gap is 0.0017 % of CVaR; the
bootstrap CI is tight only because the two schedules are nearly identical (a
near-deterministic 27 gCO₂ separation on a 1.6 M baseline).

**Reading.** Largest spatial benefit anywhere is **+0.058 %** (R3, α=0.30). No
cell exceeds ~0.06 %. The handful of "detectable" cells are economically
negligible. **Ordering:** at α=0.30 and 0.50 the gap weakly shrinks R3→R1→R2
(0.058→0.016→0.018 %; 0.036→0.027→0.026 %), i.e. *directionally* consistent with
"spatial value declines as the operating regime tightens." But R1→R2 is flat and
all magnitudes sit within bootstrap noise of zero, so this ordering is a faint
tendency, not a clean monotone law. At α=0.75 every regime is ≈0. Reported as-is.

---

## 6. Robustness lines

Run on R1 (lean, the headline candidate) and R2 (full, tightest). 

**Residual-space (covariance estimated from forecast residuals; ρ̄ and scored
emissions stay raw). Agreement rule: effect counts only if seasonal AND AR(1)
agree in sign.**

| regime | α | seasonal gap_% | AR(1) gap_% | agree? |
|---|---|---|---|---|
| R1 | 0.30 | +0.0631 | −0.0073 | no (sign flip) |
| R1 | 0.50 | +0.0014 | −0.0000003 | no |
| R1 | 0.75 | +0.0001 | −0.00000001 | no |
| R2 | 0.30 | +0.0577 | −0.0000417 | no (sign flip) |
| R2 | 0.50 | +0.0005 | +0.0000046 | yes but ≈0 |
| R2 | 0.75 | +0.0001 | −0.0000022 | no |

AR(1) residualization drives CV to select ε*=0 (DRO penalty off) for most cells,
so joint ≡ shuf and the "gaps" are machine noise (the spuriously-tight CIs around
±1e-6 % reflect identical schedules). Seasonal and AR(1) **disagree in sign**, so
the agreement rule yields **no residual-space effect**. The null holds in
residual space.

**Ledoit–Wolf shrinkage covariance (CV)** (scikit-learn 1.9.0 added to the env —
`src/models/covariance.py` already imported it). All CV selected ε*=1.0.

| regime | α | shrinkage gap_% | 95 % CI (abs) | detectable | sample+ridge gap_% |
|---|---|---|---|---|---|
| R1 | 0.30 | +0.0164 | [−118, 831] | no | +0.0164 |
| R1 | 0.50 | +0.0271 | [−359, 1577] | no | +0.0271 |
| R1 | 0.75 | +0.0017 | [13, 41] | yes* | +0.0017 |
| R2 | 0.30 | +0.0185 | [34, 693] | yes | +0.0185 |
| R2 | 0.50 | +0.0262 | [−267, 1366] | no | +0.0262 |
| R2 | 0.75 | +0.0017 | [13, 41] | yes* | +0.0017 |

Shrinkage reproduces the sample+ridge gaps to ~4 significant figures: it does
**not** widen the joint-vs-shuffled separation. The null is robust to the
covariance estimator.

---

## 7. Repo state

- Branch `taskA-revised-feasible-set`. Config commit-locked at `9347c46` *before*
  the test set was touched (pre-registration); dry-run gate passed first.
- New code: `src/data/temperature.py`, constraint kwargs in
  `src/models/algorithm_1.py` & `algorithm_2b_mahalanobis.py`.
- New scripts: `fetch_temperature.py`, `toy_validation_taskA.py`,
  `calibrate_taskA_regimes.py`, `report_binding_margins_taskA.py`,
  `run_shuffled_marginals_taskA_experiment.py`.
- New tests: `tests/test_constraints_taskA.py` (13). Suite: 141 passed.
- Results: `results/taskA_regimes_2026-06-02*.csv/.pkl` (main + 4 robustness
  variants × {R1,R2}). Cached temperature: `data/raw/temperature/*.csv`.
- Docs: `thesis/full_formulation.md`, `thesis/constraints_explained.md`, this note.

---

## 8. Planning hand-back

1. **Null tables** (§5) and **robustness tables** (§6): the spatial gap is ≤0.06 %
   everywhere, not robustly detectable, and disagrees in sign across residual
   baselines. Frame the thesis against THIS re-run, not the old P_max=180 result.
2. **Binding-margin report** (§4): every regime is *loose-OK* (24–32 % move room).
   The null is **substantive**, not a frozen-set artifact — the strongest version
   of the finding.
3. **Regime ordering**: a faint R3→R1→R2 shrink at low/mid α; flat at high α.
   Usable as "spatial value, already negligible, declines further as the
   operation tightens" — but do not over-claim a monotone law.
