# Proposal — Inter-region transfer channel for the spatial DRO

**Author:** Marco (DRO/spatial). **For:** Prof. Bissan Ghaddar. **Date:** 2026-06-11.
**Status:** proposal — needs sign-off (scope overlaps a teammate; see §5).

---

## 1. One-paragraph summary

Phase 1 found a **replicated null**: across three US/Canada cases spanning the
full correlation spectrum (strong → near-zero), the spatial covariance of carbon
intensity adds no robust CVaR scheduling value. This note argues the null may be a
property of the current **decision structure**, not of the data: in the present
model each region serves *its own* workload, so there is **no decision that moves
load toward whichever region is clean**. The covariance can therefore only act
through the second-order risk penalty. Adding an **inter-region transfer channel**
(load can be shifted between regions, at a cost / within limits) makes the decision
itself spatial — and is the single most likely change to make spatial structure
*pay off*. The result is informative either way, and it is publishable.

---

## 2. Why the null might be structural, not data-driven

The Algorithm 2b program is, per region, almost separable:

```
min_x  <rho_bar, x> + eps * || L^T x ||_2
s.t.   sum_t x_{r,t} = W_r        (each region serves its OWN demand)
       0 <= x_{r,t} <= x_bar_{r,t}, ramp, split, deadline, ...
```

The only thing linking regions is the cross-region block of `Sigma` inside the
penalty term. The **mean term `<rho_bar, x>` is fully separable across regions** and
dominates the solution (Phase 1 §5). So the optimizer never asks "*where* should
this workload run?" — only "*when*, within its own region". Spatial co-movement of
carbon is irrelevant to a decision that cannot relocate load.

**Hypothesis.** Give the optimizer the ability to relocate load across regions and
the *joint* distribution of where/when carbon is low becomes decision-relevant — so
the joint covariance (and, in Phase 2, the copula) can finally beat the shuffled /
independent baseline.

---

## 3. Model change (minimal, stays a convex SOCP)

Introduce transfer variables `f_{r->s,t} >= 0` (MWh of flexible workload moved from
region `r` to region `s` in hour `t`) on an allowed link set `E` (e.g. same
interconnect, or all pairs). The per-region served load becomes

```
y_{r,t} = x_{r,t} + sum_{s:(s,r) in E} f_{s->r,t} - sum_{s:(r,s) in E} f_{r->s,t}
```

and we evaluate emissions on `y` (what actually runs in region `r`) rather than `x`:

- **Demand (per region, over the day):** `sum_t x_{r,t} = W_r` still holds for the
  *origin* of work; transfers move *where* it executes, not *whether* it is served.
- **Capacity:** `0 <= y_{r,t} <= x_bar_{r,t}` (ceiling now applies to executed load).
- **Transfer budget / cost:** `sum_{t} sum_{(r,s)} f_{r->s,t} <= Phi` (a transfer
  cap), or a linear transfer penalty `+ lambda * sum f` in the objective
  (network/migration cost). Either keeps the problem a convex SOCP / LP-with-cone.
- **Conservation & non-negativity:** `f >= 0`, flows balance into `y`.

The objective becomes `min <rho_bar, y> + eps * || L^T y ||_2 (+ lambda * sum f)`.
Everything is linear in `(x, f, y)` except the unchanged Euclidean-norm penalty, so
**the program remains the same SOCP class** and still solves with CLARABEL/ECOS/SCS.
Carbon intensity stays the only stochastic object (scope unchanged).

---

## 4. Experiment (drops into the existing harness)

Re-run the **same** shuffled-marginals protocol (joint vs block-diagonal `Sigma`,
blocked 5-fold CV for `eps*`, 1000-bootstrap CVaR_0.95 gap) on all three cases, for
a few transfer budgets `Phi in {0, small, medium, unbounded}`:

- `Phi = 0` reproduces the Phase 1 null (sanity check).
- As `Phi` grows, **does the joint-minus-shuffled gap open up?** A widening,
  sign-stable, robustness-surviving gap = the first genuine spatial value — and a
  clean headline: *"spatial carbon structure matters once the scheduler can act on
  it spatially."*
- If the gap stays at zero even with free transfer, the null is deeper still
  (the mean field, now over a larger feasible set, still dominates) — also a clean,
  defensible result.

Expected cost: ~the current battery (a dozen runs); no new data.

---

## 5. Scope / coordination (the one thing to clear)

Inter-region **transfer** overlaps the deterministic-LP teammate's remit (Yaxin:
transfer + fairness). The distinction to preserve: hers is a *deterministic* model
of transfer + fairness; this is **transfer under distributional robustness** — the
*combination* "DRO + spatial transfer" is the novel contribution and the reason the
spatial covariance/copula could finally matter. Proposed boundary: Yaxin owns the
deterministic transfer model and fairness; Marco owns the robust (DRO) transfer
experiment and the spatial-value question. **Needs Bissan's explicit OK** before
building, to avoid duplicated work.

---

## 6. Recommendation

Run the **mean-ablation experiment first** (cheap, no scope conflict — it proves the
mean-dominance mechanism by equalizing regional means and checking whether the
covariance effect then appears). If ablation confirms "the mean masks the
covariance," that is the precise motivation for the transfer channel: remove the
mean's separable dominance *by giving the decision a spatial degree of freedom*.
Then build the transfer channel subject to §5 sign-off.
