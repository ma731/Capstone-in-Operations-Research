# Proposal — Part 3: Spatially-coupled transfer DRO (the new algorithm)

**Author:** Marco (DRO/spatial). **For:** Prof. Bissan Ghaddar.
**Date:** 2026-06-11, **updated 2026-06-14 (post-Phase-2).**
**Status:** proposal — needs sign-off (scope overlaps a teammate; see §5).

> **Where this sits.** Part 1 (covariance) and Part 2 (copulas) are *done* and live
> in the capstone: both are nulls, and the mean-dominance bound explains why no
> *passive* dependence model can help. This proposal is **Part 3** — the genuinely
> novel **algorithm** (active inter-region transfer under DRO) and the natural
> publication follow-on. The capstone itself is **Paper 1** (a negative/measurement
> result: HotCarbon / e-Energy / SIGEnergy workshop); this is **Paper 2**.

---

## 1. One-paragraph summary

The capstone established a **total null**: across three US/Canada grids spanning the
full correlation spectrum, *neither* the spatial covariance *nor* a Gaussian/Clayton/
comonotone copula adds robust CVaR scheduling value, and a mean-dominance bound
proves no *passive* dependence model can. The null is a property of the **decision
structure**, not the data: in the present model each region serves *its own*
workload, so there is **no decision that moves load toward whichever region is
clean**. The mean field dominates — and it dominates *spatially* too (at each hour
one region is cleanest on average), a first-order signal the passive ambiguity set
cannot act on. An **inter-region transfer channel** (load can shift between regions,
at a cost / within limits) makes the decision itself spatial and is the one route
left to extracting spatial value. The novel contribution is the *combination*
**DRO + active transfer**; the result is informative and publishable either way.

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

**Hypothesis (refined post-Phase-2).** Give the optimizer the ability to relocate
load across regions and the *spatial* structure of carbon becomes decision-relevant.
Note the subtlety the capstone exposed: transfer will help **because it is
mean-exploiting** (move work to the region with the lowest *mean* carbon right now),
not because it suddenly makes the *covariance* pay. So the honest research question
for Part 3 is **not** "does transfer help" (it must) but:

> **Does *robustifying* the transfer (DRO) beat plain *deterministic* transfer?**

The same mean-dominance logic that killed the passive covariance suggests the
robustness layer may again be second-order — so the interesting, non-obvious result
is characterizing *when* robust transfer wins: under forecast error, distribution
shift, or for tail-risk-averse operators. That is the publishable methods question.

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

Two questions, two comparisons, all on the locked pre-registration discipline.

**(a) Does transfer unlock spatial value?** Re-run the shuffled-marginals protocol
(joint vs block-diagonal `Sigma`, blocked 5-fold CV for `eps*`, 1000-bootstrap
CVaR_0.95 gap) on all three grids for transfer budgets `Phi in {0, small, medium,
unbounded}`. `Phi=0` reproduces the null (sanity check); as `Phi` grows, watch
whether the joint-minus-shuffled gap opens up. Expect it to — but via the mean, not
the covariance, which (b) disentangles.

**(b) The real methods question — robust vs deterministic transfer.** Head-to-head,
out-of-sample on 2025:
- **Deterministic transfer** (`eps=0`): schedule + transfer on the mean field only.
- **Robust transfer** (`eps*` by CV): same, with the Wasserstein penalty.
- Stress both under **forecast error** (perturb/replace `rho_bar` with a lagged or
  noisy forecast) and report the CVaR_0.95 of *realized* emissions.

A robust-transfer advantage that **grows with forecast error / tail aversion** is
the headline positive result: *"robustness is worthless for passive spatial
hedging, but valuable once spatial transfer is an active decision under
uncertainty."* If robust ≈ deterministic everywhere, that extends the
mean-dominance story one level further (also clean, also publishable).

Expected cost: ~the current battery scale; no new data (the transfer is a model
change, carbon intensity stays the only stochastic object).

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

## 6. Recommendation & status

The mean-ablation (the cheap mechanism check this doc originally recommended first)
is **done** and confirmed the mean masks the covariance; Phase 2 then showed even
copulas cannot recover it. The motivation for the transfer channel is therefore
established, not hypothetical: passive spatial structure is provably worthless, so
the decision must be made spatial.

**Next steps:** (1) get Bissan's explicit OK on the §5 boundary with Yaxin's
deterministic-transfer work; (2) build the transfer variables into `algorithm_2b`
(a small, SOCP-preserving change — `f >= 0`, the `y = x + inflow - outflow`
substitution, and a transfer budget/penalty); (3) run experiment (b) — robust vs
deterministic transfer under forecast error — as the core of Paper 2.

**Publication trajectory.** Paper 1 = the capstone negative result (ready now,
HotCarbon / e-Energy / SIGEnergy workshop). Paper 2 = this transfer DRO (the novel
algorithm + the robust-vs-deterministic result), a stronger venue once results land.
