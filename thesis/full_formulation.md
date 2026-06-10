# Full formulation — revised feasible set (Task A) + two-region study (Task B)

*Supersedes the v11/v12 formulation. The DRO method (Algorithm 2b,
Mahalanobis–Wasserstein SOCP) is **unchanged**; only the feasible set X is
revised: the aggregate power cap is dropped, and two constraints are added
(windowed-demand deadline and temperature-coupled thermal/PUE).*

> **Two region sets (R is parameterized).** The same formulation is applied to
> two independent grids: **California/Nevada** (Task A, R=4: US-CAL-CISO,
> US-CAL-BANC, US-CAL-LDWP, US-NW-NEVP, clock America/Los_Angeles) and
> **Iberia + France** (Task B, R=3: ES, PT, FR, clock Europe/Madrid). Everything
> below is written for general R; D = R·T (96 for CA, 72 for Iberia). The
> region set, the common reference clock, and the climate-dependent constraint
> parameters (notably the thermal economizer set-point t_set) are the only
> differences. Both yield a **replicated null** (see `docs/progress_note_v13.md`,
> `docs/progress_note_v14.md`). For Iberia, PT is WET (one hour behind the
> Madrid common clock) — a stated common-reference-clock choice.

## Notation

| symbol | meaning | units |
|---|---|---|
| $r \in \{1,\dots,R\}$ | region (balancing-authority sub-zone), $R=4$ | — |
| $t \in \{0,\dots,T-1\}$ | hour of the local scheduling day, $T=24$ | — |
| $x_{r,t} \ge 0$ | compute power scheduled in region $r$, hour $t$ | MW |
| $\bar\rho_{r,t}$ | empirical mean carbon intensity (training) | gCO₂eq/kWh |
| $\hat\Sigma \in \mathbb{R}^{RT\times RT}$ | empirical covariance of the daily carbon field | — |
| $L$ | factor with $LL^\top=\hat\Sigma$ (Cholesky) | — |
| $\varepsilon \ge 0$ | Wasserstein radius | — |
| $\bar x_{r,t}$ | per-cell ceiling | MW |
| $W_r$ | per-region daily work requirement | MWh |
| $\alpha_r \in [0,1]$ | inflexible fraction of $W_r$ | — |
| $p_{r,t}$ | intraday shape of the inflexible base ($\sum_t p_{r,t}=1$) | — |
| $\Delta_r$ | per-region ramp limit | MW/h |
| $[\tau_1,\tau_2],\gamma$ | deadline window and required fraction | — |
| $T^{\mathrm{air}}_{r,t}$ | representative air temperature (training mean) | °C |
| $\mathrm{PUE}_0,\kappa,T_{\mathrm{set}}$ | PUE floor, slope, economizer set-point | —, /°C, °C |
| $\bar P$ | per-cell effective-power ceiling | MW |

The flattening convention is row-major: $\mathrm{vec}(x)[rT+t]=x_{r,t}$ (region
outer, hour inner), pinned in `src/models/covariance.py`.

## Objective (unchanged)

$$
\min_{x \in \mathcal{X}}\quad \langle \bar\rho, x\rangle \;+\; \varepsilon\,\sqrt{x^\top \hat\Sigma\, x}
\;=\;
\min_{x\in\mathcal X}\ \sum_{r,t}\bar\rho_{r,t}\,x_{r,t} \;+\; \varepsilon\,\big\| L^\top \mathrm{vec}(x)\big\|_2 .
$$

The Mahalanobis penalty $\sqrt{x^\top\hat\Sigma x}=\lVert L^\top\mathrm{vec}(x)\rVert_2$
makes the program a second-order cone program (SOCP). Off-diagonal blocks of
$\hat\Sigma$ couple regions: this is the channel through which spatial
correlation enters the optimizer. At $\varepsilon=0$ the program reduces to the
deterministic LP on $\bar\rho$ over $\mathcal X$.

## Feasible set $\mathcal{X}$ (revised)

**Per-cell ceiling (kept).**
$$0 \le x_{r,t} \le \bar x_{r,t}. \tag{C0}$$

**Flexible / inflexible split (C2, kept).** With $\alpha$ active, the inflexible
base $b_{r,t}=\alpha_r W_r\,p_{r,t}$ is pinned and the flexible part is a free
nonnegative variable:
$$x_{r,t}=b_{r,t}+x^{\mathrm{flex}}_{r,t},\qquad x^{\mathrm{flex}}_{r,t}\ge 0,\qquad \sum_t x^{\mathrm{flex}}_{r,t}=(1-\alpha_r)W_r. \tag{C2}$$
When $\alpha$ is inactive this collapses to the plain work equality
$\sum_t x_{r,t}=W_r$.

**Ramp (C3, kept).**
$$|x_{r,t}-x_{r,t-1}| \le \Delta_r,\qquad t=1,\dots,T-1. \tag{C3}$$

**Aggregate power cap (C1) — DROPPED.** The constraint
$\sum_r x_{r,t}\le P_{\max}$ is **removed** ($P_{\max}=\texttt{None}$). The
$\texttt{p\_max=None}$ path in both `schedule_deterministic_coupled` and
`solve_mahalanobis_dro` adds no aggregate constraint; this was verified, not
re-coded.

**Windowed-demand / deferral-deadline (3a, NEW).** For each region $r$ and each
window $(\tau_1,\tau_2,\gamma)$, a fraction $\gamma$ of the region's *flexible*
work must be served within the window:
$$\sum_{t=\tau_1}^{\tau_2} x^{\mathrm{flex}}_{r,t} \;\ge\; \gamma\,(1-\alpha_r)\,W_r. \tag{3a}$$
This is explicitly an **aggregate** deferral bound (a deadline on the flexible
slice), **not** a per-job SLA. It is only well-defined under the C2 split, so
$\alpha$ must be active.

**Temperature-coupled thermal / PUE (3b, NEW).** Effective (wall-plug) power is
IT power inflated by a temperature-dependent PUE:
$$\mathrm{PUE}(T^{\mathrm{air}}_{r,t}) = \mathrm{PUE}_0 + \kappa\,\max\!\big(T^{\mathrm{air}}_{r,t}-T_{\mathrm{set}},\,0\big),$$
$$\mathrm{PUE}(T^{\mathrm{air}}_{r,t})\, x_{r,t} \;\le\; \bar P. \tag{3b}$$
Because $T^{\mathrm{air}}$ is data, $\mathrm{PUE}(\cdot)$ is a constant matrix and
(3b) is **linear** — it tightens the effective ceiling in hot hours,
$x_{r,t}\le \bar P/\mathrm{PUE}(T^{\mathrm{air}}_{r,t})$ — so the program stays an
SOCP. The thermal field $T^{\mathrm{air}}$ is the per-cell **training-period
mean** temperature (a fixed feasible-set parameter, like the ceiling; never
re-estimated per CV fold and never read from the test set).

## Constraint regimes (Phase 4 experiment)

The joint-vs-shuffled spatial comparison is run across three nested regimes so
the marginal value of spatial correlation is reported as a function of
operational tightness:

| regime | constraints active | role |
|---|---|---|
| **R3 (reference)** | C0 + C2 + C3 | post-cap baseline (anchor) |
| **R1 (lean)** | R3 + 3a | headline candidate (no thermal) |
| **R2 (full)** | R1 + 3b | tightest realistic regime |

## Calibration (chosen on training data only)

$T=24$, $R=4$, ceiling $\bar x=50$ MW, utilization $0.80$
($W_r=0.80\cdot 50\cdot 24=960$ MWh), $\alpha\in\{0.30,0.50,0.75\}$, ramp
$\Delta=15$ MW/h. Deadline window $[\tau_1,\tau_2]=[0,7]$ (morning, off the
cheap solar trough at hours 8–15), $\gamma=0.20$. Thermal $\mathrm{PUE}_0=1.10$,
$\kappa=0.015\,/°\mathrm{C}$, $T_{\mathrm{set}}=20°\mathrm{C}$, $\bar P=57$ MW.
These bind **loosely** (active in some hours, not dominant): on the training
panel the deadline binds for most regions, thermal binds ≈25 % of cells, and the
DRO still reallocates ≈25–30 % of total work as $\varepsilon$ grows — i.e. the
set is not frozen. See `scripts/calibrate_taskA_regimes.py`.

## Mapping to code

| object | code |
|---|---|
| objective + penalty + all constraints | `src/models/algorithm_2b_mahalanobis.py::solve_mahalanobis_dro` |
| deterministic counterpart ($\varepsilon=0$) | `src/models/algorithm_1.py::schedule_deterministic_coupled` |
| PUE hockey-stick | `src/data/temperature.py::pue_from_temperature` |
| thermal field $T^{\mathrm{air}}$ | `src/data/temperature.py::temperature_field` |
| regimes + locked config | `scripts/run_shuffled_marginals_taskA_experiment.py` |

## Task C additions (Ontario + Eastern-Interconnection belt)

Task C is a THIRD region set (`CA-ON, US-NY-NYIS, US-MIDW-MISO, US-MIDA-PJM`;
clock `America/Toronto`), chosen for high *residual* (weather-front-driven)
cross-correlation — the structure Tasks A/B lacked. It AUGMENTS the feasible set
$\mathcal X$ with two constraints adapted from Wijayawardana & Chien (SoCC '25),
"Scheduling Cloud VMs on Variable Capacity Datacenters." Tasks A/B and their
replicated null are on the UNAUGMENTED $\mathcal X$ above and are untouched.

**Variable carbon-coupled capacity (3c, NEW).** The flat ceiling $\bar x$ is
replaced by a CFE-driven one:
$$\bar x_{r,t} = x_{\min} + (x_{\max}-x_{\min})\cdot \frac{\mathrm{CFE}_{r,t}}{100},$$
where $\mathrm{CFE}_{r,t}$ is the **training-mean carbon-free-energy fraction**
(Electricity Maps `cfe_pct`). CFE is data — a fixed feasible-set parameter, like
the 3b thermal field, never re-estimated per fold and never read from the test
set — so $\bar x$ is a constant matrix and the per-cell ceiling (C0) stays linear.
Mechanistic point: CFE is spatially correlated through shared weather, so the
ceiling **co-varies across regions** — a SECOND spatial channel on top of the
carbon-cost coupling that enters through the off-diagonal blocks of $\hat\Sigma$.

**Carbon budget (3d, NEW).** An optional cap on nominal carbon:
$$\sum_{r,t} \bar\rho_{r,t}\,x_{r,t} \;\le\; B. \tag{3d}$$
$\bar\rho$ is data, so (3d) is a single linear constraint and the program stays an
SOCP. It is slack-or-infeasible in the pure-min baseline (the objective already
minimizes carbon); it binds only in the DRO, where the robustness term can push
nominal carbon above the deterministic minimum.

Both are additive (default off) and leave the A2b SOCP structure intact. Capacity
is treated as DATA, never as a second stochastic vector (preserves the
carbon-only ambiguity-set scope, Decision 2). Calibration of $(x_{\min}, x_{\max},
B)$ to the loosely-binding "Goldilocks" regime is pending (see `docs/decisions.md`
Decisions 8–9).

| object | code |
|---|---|
| CFE field + panel | `src/data/capacity.py::{build_cfe_panel, cfe_field}` |
| CFE → ceiling mapping (3c) | `src/data/capacity.py::capacity_from_cfe` |
| carbon budget (3d) | `carbon_budget=` kwarg in `algorithm_1` / `algorithm_2b` |
