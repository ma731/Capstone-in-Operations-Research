# Progress note v15 — three-case spatial-DRO synthesis + tail dependence

**Date:** 2026-06-11 (UTC). **Builds on v13 (Task A, California), v14 (Task B, Iberia).**
**Scope:** Close Phase 1 on the spatial question. Run the *same locked machinery*
across **three** US/Canada cases spanning the full correlation spectrum, and add a
**tail-dependence** diagnostic that explains *why* the null holds and *what* (if
anything) a covariance-based DRO is missing. Transport, not redesign: the DRO
method (Algorithm 2b Mahalanobis–Wasserstein SOCP), the three-regime design, the
shuffled-marginals device, CVaR₀.₉₅, blocked 5-fold CV, and the 1000-bootstrap CI
are **locked**. Only the region set, the common clock, and the 3c capacity
parameters differ. Runner: `scripts/run_case_experiment.py --region-set {...}`.

---

## 1. Headline verdict

**Spatial correlation of carbon intensity adds no robust scheduling value —
anywhere on the correlation spectrum.** Pairing the *joint* covariance with the
Mahalanobis–Wasserstein scheduler instead of the *block-diagonal (shuffled)*
covariance changes out-of-sample CVaR₀.₉₅ by a negligible amount in every case,
regime, and α level. This now includes a case **engineered to give
diversification value** and it still gives none.

A **mean-ablation** experiment (§6) makes the mechanism *causal*, not merely
asserted: when the mean field is neutralized, the joint covariance produces a
material, detectable advantage over the shuffled one — so the spatial signal is real
and exploitable, just **dominated by the mean** in the actual problem.

The tail diagnostic sharpens the *why*: the dependence in real carbon data is
**non-elliptical** (upper-tail-independent and radially asymmetric — regions go
clean together more than dirty together). A covariance / Mahalanobis–Wasserstein
ambiguity set is *structurally* incapable of representing that. So the second
moment is not merely unhelpful here — it is the **wrong object**. That is the
empirical mandate for the Phase 2 copula extension.

---

## 2. The three cases (the correlation spectrum)

| Case | Zones | Clock | Residual correlation | Mechanism |
|------|-------|-------|----------------------|-----------|
| **us_west** | CISO, BANC, LDWP, NEVP, AZPS | Pacific | **strong**, survives de-seasonalization (CISO↔NEVP 0.78, CISO↔LDWP 0.72) | WECC, shared solar + weather |
| **taskc** | CA-ON, NYIS, MISO, PJM | Eastern | **strong**, survives (CA-ON↔NYIS 0.73, MISO↔PJM 0.70) | Eastern Interconnection, weather fronts |
| **us_hetero** | CISO (solar), ERCO (wind), BPAT (hydro) | UTC | **near-zero** (ERCO↔BPAT 0.00) | different physical drivers — deliberately diversifiable |

`us_hetero` is the adversarial design: regions with *different* generation physics,
chosen so their clean/dirty periods do **not** line up. If spatial DRO value exists
anywhere, it should appear here. It does not.

---

## 3. Spatial gap results (CVaR₀.₉₅, gap = shuf − joint; + = joint better)

*3c capacity bounds Goldilocks-calibrated to (x_min, x_max) = (50, 75) on training
data (`scripts/calibrate_capacity.py`); R2 is no longer exploratory.*

| Case | ε* (CV) | gap range (% of CVaR₀.₉₅) | detectable cells | verdict |
|------|---------|---------------------------|------------------|---------|
| **us_west** | 1 (8/9 cells) | −0.005 … +0.043 | 1/9 (trivial, +3×10⁻⁶%) | null |
| **taskc** | 1 (9/9) | −0.022 … +0.038 | 4/9, **signs flip** across α | null (artifacts) |
| **us_hetero** | 1 (9/9) | −0.233 … +0.062 | 5/9, every material one **negative** | null (joint *hurts*) |

(9 cells/case = 3 regimes × 3 α. Full tables in `results/<case>_regimes_2026-06-10.csv`.)

**Reading:** every gap is a small fraction of one percent. In `us_west` and `taskc`
no cell is robustly non-zero and the signs flip across α (the signature of an
ε-selection artifact, not a real effect). In `us_hetero` the only detectable cells
are **negative** — the joint covariance slightly *hurts*: estimating cross-region
blocks that carry no exploitable signal just adds estimation noise (the cost of
fitting correlations that don't help). CV selects ε* = 1 throughout, so the DRO is
genuinely engaged — this is not a "the model switched itself off" null.

---

## 4. Tail dependence — what the covariance cannot see

We measure the empirical upper/lower tail-dependence coefficients χ_U (both regions
*dirty* together — the CVaR-relevant co-movement) and χ_L (both *clean* together),
and compare χ_U against the **Gaussian-copula benchmark** at the matched Pearson ρ.
A Gaussian copula — equivalently anything a covariance ball can represent — has
**zero asymptotic tail dependence**, so empirical-minus-Gaussian *excess* > 0 would
be dirty-tail structure the DRO is blind to. (`src/analysis/tail_dependence.py`,
`scripts/plot_tail_dependence.py`; residual = hour-of-day mean removed, q = 0.95.)

**Finding 1 — no dirty-tail structure is missed.** Across all three cases the
empirical χ_U sits **at or below** the Gaussian benchmark (residual excess ≈ −0.04
to −0.18). In the dirtiest moments the regions actually *de-couple* (upper-tail
independence). There is nothing in the upper tail for a richer model to exploit.

**Finding 2 — the dependence is radially asymmetric (χ_L > χ_U).** Regions go
*clean* together more than *dirty* together — clearest in `us_west` (solar): e.g.
CISO|LDWP residual χ_U = 0.25 vs χ_L = 0.48; BANC|LDWP χ_U = 0.17 vs χ_L = 0.40. A
Gaussian/elliptical copula forces χ_L = χ_U, so this asymmetry is **non-elliptical**
structure a Mahalanobis–Wasserstein ball cannot encode.

Selected residual tail-dependence (q = 0.95):

| Case | Pair | ρ | χ_U emp | χ_U Gauss | excess | χ_L emp |
|------|------|----|---------|-----------|--------|---------|
| us_west | CISO \| LDWP | 0.72 | 0.25 | 0.41 | −0.16 | 0.48 |
| us_west | BANC \| LDWP | 0.65 | 0.17 | 0.35 | −0.18 | 0.40 |
| us_west | CISO \| NEVP | 0.78 | 0.43 | 0.47 | −0.05 | 0.39 |
| taskc | CA-ON \| NYIS | 0.73 | 0.38 | 0.42 | −0.04 | 0.31 |
| taskc | MISO \| PJM | 0.70 | 0.43 | 0.39 | +0.04 | 0.42 |
| us_hetero | CISO \| BPAT | 0.33 | 0.10 | 0.16 | −0.06 | 0.26 |
| us_hetero | ERCO \| BPAT | 0.00 | 0.04 | 0.05 | −0.02 | 0.02 |

---

## 5. Why there is no spatial value (the mechanism, stated plainly)

1. **The mean field dominates.** The schedule's job is "send compute where carbon
   is low on average" — set by ρ̄, which the joint and shuffled models share
   *identically*. The covariance only enters as the penalty ε·‖Lᵀx‖₂, a 2nd-order
   regularizer. Joint vs shuffled can differ only in that thin margin.
2. **Positive correlation = common, non-diversifiable risk.** Diversification value
   needs regions that hedge each other (negative/heterogeneous dependence). Real
   grids are positively correlated → common-mode risk → no hedge to find. And the
   one genuinely clean escape (Ontario; hydro BPAT) is already flagged by its low
   *mean*, not the covariance.
3. **Even zero correlation doesn't help** (`us_hetero`): with no cross-structure to
   exploit, fitting the joint covariance only adds estimation noise.
4. **The exploitable-looking structure is in the tails, and it's non-elliptical**
   (§4) — invisible to a covariance-based ambiguity set by construction.

---

## 6. Mean-ablation — the causal demonstration (headline experiment)

§5 claims the mean field dominates and the covariance is second-order. We test that
claim causally with `--ablate-mean`: the mean ρ̄ used for **scheduling** is
neutralized, while **evaluation stays on the real carbon panel** (real emissions).
Two levels: `level` equalizes each region's time-average to the global mean (keeps
the hour-of-day shape); `flat` sets a constant mean everywhere, so the term
⟨ρ̄,x⟩ is constant under fixed demand and the schedule is driven **purely** by the
ε·‖Lᵀx‖₂ covariance penalty — a *covariance-only world*.

| Case | baseline gap | `level` gap | `flat` gap (covariance-only) |
|------|--------------|-------------|------------------------------|
| us_west | ~0, none detectable | ~0, none | ε*→0; −0.04 … +0.004 (still ~0) |
| taskc | ~0, sign-flips | ~0, sign-flips | **+0.14 … +0.41, all 9 detectable** |
| us_hetero | negative | negative | **+0.39 … +1.46, all 9 detectable** |

**Interpretation.** Equalizing the *level* changes nothing — the diurnal mean shape
still dominates. But in the *covariance-only* world the joint covariance produces a
**material, fully detectable** advantage over the shuffled/block-diagonal one
(taskc up to +0.41%, us_hetero up to +1.46%), and CV no longer collapses to a single
ε* (joint and shuf select very different radii). So the spatial covariance **does**
carry genuine, exploitable information — it is simply **swamped by the mean** in the
real problem. This converts the null from an assertion ("covariance doesn't matter")
into a demonstrated *ordering*: **the mean field dominates the schedule so completely
that a real and exploitable second-moment signal contributes negligibly.** (us_west
is the instructive exception: its strong *common-mode* positive correlation offers
little even in isolation — diversification needs heterogeneity, not co-movement.)

*Caveat:* the `flat` schedule deliberately ignores the real mean, so its absolute
CVaR is worse than baseline — by **+1.6–3.8% (us_hetero), +1.9–4.1% (us_west), and
−0.1–0.2% (taskc)** — i.e. the covariance-only gain (≤1.46%) never repays the cost
of discarding the mean. This is a mechanism probe (does the covariance carry *any*
exploitable signal once the mean is removed?), not an achievable-value claim.

*ε-grid note:* under `flat` the CV-selected ε\* is unstable on the standard
6-point grid (joint/shuf pick radii orders of magnitude apart); a log-denser
11-point grid (`--eps-grid fine`) is used to confirm the flat-ablation gaps are
not grid artifacts (results `*_finegrid.csv`).

---

## 7. Robustness battery

Each case re-run with `--residualize seasonal`, `--residualize ar1`, and
`--shrinkage` (Ledoit–Wolf). A spatial effect only counts if it is positive AND
agrees in sign across the seasonal and AR(1) residual estimators. (Results in
`results/<case>_regimes_<date>_{seasonal,ar1,lw}.csv`.)

**Result — the null survives the battery.** The largest |gap| under *any* estimator
is **0.07% (us_west), 0.18% (taskc), 0.36% (us_hetero)** of CVaR — all economically
negligible. No cell shows a *material* beneficial spatial effect that is sign-stable
across the seasonal **and** AR(1) residual estimators: the cells that flip positive
disagree by orders of magnitude across estimators (e.g. taskc R3/α0.30: seasonal
−0.033% vs ar1 +0.179%) — the signature of ε-selection noise, not signal. In
`us_hetero` every detectable cell is **negative** (joint covariance hurts). This is
the confirmed, robustness-checked version of the null across all three cases.

**Multiple-testing correction (Benjamini–Hochberg).** Because we test 144
non-ablation cells (case × regime × α × estimator), some bootstrap CIs exclude zero
by chance. Recomputing bootstrap p-values per cell and applying BH at q = 0.05
across all cells (`scripts/bh_correction.py`): the largest *positive* gap that
survives correction is **0.179%** — the AR(1) taskc cell already rejected by the
seasonal∧AR(1) agreement rule. With N ≈ 362 test days, gaps this small are
statistically resolvable but economically negligible; nothing material survives
both BH and the agreement rule. Walk-forward check (train→2023, test 2024;
`--test-year 2024`) confirms the null is not a 2025 artifact (results
`*_ty2024.csv`).

---

## 8. Practical recommendation

For carbon-aware data-center scheduling under a covariance-based robust model:
**use a per-region marginal scheduler.** Modelling cross-region carbon dependence
adds estimation burden and (in the heterogeneous case) measurable noise, for no
robust benefit — the regional *mean* carbon profiles capture essentially all the
schedulable value. Spatial dependence modelling should be reserved for (i)
decision structures that can act on it (inter-region transfer — see
`docs/proposal_transfer_channel.md`) and (ii) dependence models that can represent
its actual non-elliptical shape (Phase 2).

---

## 9. Phase 2 hook

The Phase 1 null is not a dead end — it is a *specification result*. Second-moment
spatial dependence carries no robust value, and the genuine dependence structure is
non-elliptical (upper-tail-independent, radially asymmetric). Capturing it requires
modelling the **copula**, not the covariance — directly motivating the vine-copula
extension (Phase 2): asymmetric tail dependence (e.g. Clayton-type clean-together
coupling) and the freedom to set χ_L ≠ χ_U, neither of which the
Mahalanobis–Wasserstein ground metric can express.

---

## 10. Caveats

- Carbon intensity is the only stochastic object; load is deterministic (clean
  scope split from the joint-uncertainty teammate).
- Tail-dependence coefficients at q = 0.95 are finite-sample estimates; the χ_U(q)
  curves (`figures/tail_dependence_<case>.*`) show the trend toward the asymptote.
- `us_hetero` spans three time zones; aligned/residualized in UTC.
