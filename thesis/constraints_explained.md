# Constraints explained — revised feasible set (Task A)

Plain-language companion to `full_formulation.md`. One section per constraint:
what it represents, why it is shaped the way it is, and how it behaves in the
optimizer. The DRO method is unchanged throughout — these notes are entirely
about the feasible set $\mathcal X$.

---

## Why the set was revised

The earlier feasible set leaned on an **aggregate per-hour power cap**
($\sum_r x_{r,t}\le P_{\max}$, with $P_{\max}=180$). That cap was the main thing
coupling regions in the *deterministic* problem, and it made the operating
point sit on a flat face of the polytope where the schedule barely moved. The
revision **drops the cap** and replaces its operational role with two
constraints that are both more physically defensible and more local:

- a **deadline** on deferrable work (jobs cannot be pushed arbitrarily late), and
- a **thermal/PUE** limit that ties usable compute to cooling effort, which
  rises with outdoor temperature.

This keeps the operation realistically constrained without the single global
knob ($P_{\max}$) that previously dominated the geometry.

---

## C0 — Per-cell ceiling (kept)

$0 \le x_{r,t}\le \bar x_{r,t}$. A site cannot draw more than its installed
capacity in any hour. Trivial but essential: it bounds the polytope.

## C2 — Flexible / inflexible split (kept)

A fraction $\alpha_r$ of each region's daily work is **inflexible** — it runs on
a fixed intraday shape $p_{r,t}$ no matter what (interactive load, must-run
services). The remaining $(1-\alpha_r)$ is **flexible** and is what the
scheduler actually moves. $\alpha$ is the **master dial**: it fixes how much
work is movable *before any other constraint acts*. Lower $\alpha$ ⇒ more
flexible work ⇒ more room for the spatial effect to show.

In code the inflexible base $b_{r,t}=\alpha_r W_r p_{r,t}$ is pinned and
$x^{\mathrm{flex}}_{r,t}\ge 0$ is a separate variable summing to $(1-\alpha_r)W_r$.

## C3 — Ramp (kept)

$|x_{r,t}-x_{r,t-1}|\le\Delta_r$. Power cannot jump hour-to-hour beyond
$\Delta_r$ (thermal inertia, contractual ramp limits, orderly job admission).
This is what makes the greedy "fill the cheapest hours first" schedule
**infeasible** — greedy slams from 0 to ceiling between adjacent hours.

## C1 — Aggregate power cap (DROPPED)

Removed. `p_max=None` adds no aggregate constraint. Verified, not re-coded. The
null result must be re-confirmed on this new set precisely because the old null
was measured *with* this cap.

---

## 3a — Windowed-demand / deferral-deadline (NEW)

**What it says.** For a window $[\tau_1,\tau_2]$ and fraction $\gamma$, at least
$\gamma\,(1-\alpha_r)W_r$ of the region's *flexible* work must be completed
within the window:
$$\sum_{t=\tau_1}^{\tau_2} x^{\mathrm{flex}}_{r,t}\ \ge\ \gamma\,(1-\alpha_r)\,W_r.$$

**Why this shape.** Deferrable compute is not infinitely deferrable: training
jobs, batch ETL, and nightly pipelines have deadlines. Rather than track every
job's SLA (out of scope, and not what an aggregate carbon-scheduling model
should claim), we impose an **aggregate** deadline — a floor on how much
flexible work has cleared by the end of the window. It is deliberately *not* a
per-job SLA; it is the coarse, model-appropriate version of "don't defer
everything to the cheapest hour."

**Why it requires the split.** "Flexible work" is only defined once C2 is
active, so 3a raises an error if $\alpha$ is off — it bounds $x^{\mathrm{flex}}$,
not $x$.

**Behavior.** With the window on the morning hours $[0,7]$ — *off* the cheap
midday solar trough — it forces a slice of flexible work out of the cheapest
hours into pricier morning hours. It binds for most regions but moves only
$\gamma=20\%$ of flexible work, leaving the bulk free: active, not dominant.

## 3b — Temperature-coupled thermal / PUE (NEW)

**What it says.** Usable IT power is limited by *effective* (wall-plug) power,
which is IT power times the facility PUE:
$$\mathrm{PUE}(T)=\mathrm{PUE}_0+\kappa\max(T-T_{\mathrm{set}},0),\qquad
\mathrm{PUE}(T^{\mathrm{air}}_{r,t})\,x_{r,t}\le\bar P.$$

**Why this shape.** PUE (power usage effectiveness) is the ratio of total
facility power to IT power; cooling is the dominant overhead. Below an
economizer set-point $T_{\mathrm{set}}$ the site free-cools at a floor PUE
$\mathrm{PUE}_0$; above it, mechanical cooling kicks in and PUE rises roughly
linearly — the "hockey-stick" $\max(T-T_{\mathrm{set}},0)$. So in hot hours a
fixed wall-plug budget $\bar P$ buys **less** usable compute. This couples the
schedule to **weather**, which is the physical reason temperature data enters
the project at all. Defaults sit in typical industry ranges
($\mathrm{PUE}_0\approx1.1$, $\kappa\approx0.015/°\mathrm{C}$,
$T_{\mathrm{set}}\approx20°\mathrm{C}$) and are exposed for sensitivity.

**Why it stays an SOCP.** $T^{\mathrm{air}}$ is data, so $\mathrm{PUE}(\cdot)$ is
a constant per-cell number. The constraint is linear — it simply tightens the
ceiling to $\bar P/\mathrm{PUE}(T^{\mathrm{air}}_{r,t})$ in hot hours. The
Mahalanobis cone is untouched.

**Which temperature.** A single representative point per zone (load-weighted
load-center), and the per-cell **training-mean** temperature as the fixed field
$T^{\mathrm{air}}$ — the analogue of a fixed ceiling. It is never re-estimated
per CV fold and never read from the test set, so the feasible set carries no
look-ahead. Multi-station spatial averaging is a noted refinement, not
implemented.

---

## Regimes and the point of the sensitivity table

Because 3b is the tightest and most assumption-laden constraint, the experiment
reports the spatial gap across three nested regimes:

- **R3 (reference)** — ceiling + split + ramp. The post-cap anchor.
- **R1 (lean)** — R3 + deadline. The likely headline (physically clean, no
  weather assumptions).
- **R2 (full)** — R1 + thermal. The tightest realistic regime.

If the Goldilocks margins show R2 freezing the optimizer, R1 becomes the
headline and R2 is read as "under the tightest realistic regime the spatial
value declines further" — a richer finding, not a failure. The expected clean
pattern is a **monotone shrink** of the spatial gap R3 → R1 → R2: the more
constrained the operation, the less room spatial correlation has to help. Any
departure from that ordering is reported honestly rather than smoothed over.
