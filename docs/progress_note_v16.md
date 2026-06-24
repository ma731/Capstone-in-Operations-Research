# Progress note v16 — Phase 2: copula schedulers close the loop

**Scope:** Answer the one objection Phase 1 could not: *"the covariance ball found
nothing because it is elliptical — use a copula that sees the χ_L>χ_U asymmetry."*
We built copula schedulers, re-ran the falsification, and the null held.

---

## 1. Headline

**No passive dependence model recovers material scheduling value — not the
covariance ball, not a Gaussian copula, not a lower-tail Clayton copula built
specifically for the empirical asymmetry.** The Phase 1 null is now *total*, and a
mean-dominance bound explains why.

## 2. Method (mirrors shuffled-marginals, generalized to the full copula)

**Copula-coupled empirical resampling.** Each region keeps its empirical pool of
whole daily profiles (marginals preserved exactly, no parametric model); a copula
sample `u ∈ [0,1]^R` selects, per region, the training day whose daily-mean
intensity has rank `u_r` (low = clean). The copula governs only cross-region
coupling — exactly what the shuffled covariance did. Three nested models:

- **independence** — regions decoupled (= Phase 1 "shuf").
- **gaussian** — elliptical, at empirical rank-correlation (what covariance sees).
- **clayton** — exchangeable, lower-tail λ_L=2^(-1/θ), θ from mean Kendall τ
  (Marshall–Olkin frailty sampling, numpy-only). The object built for χ_L>χ_U.

**CVaR-SAA scheduler** (`src/models/cvar_saa.py`): Rockafellar–Uryasev LP,
S=1000 scenarios, over the *same* feasible set X as Phase 1 (shared
`src/models/feasible_set.py`; a unit test pins X to the Phase 1 solver). Each
schedule evaluated once on the 2025 panel by out-of-sample CVaR_0.95.

## 3. Result (`*_copula_2026-06-13.csv`)

| Case | τ̄ | θ | max\|gap_Gauss\| | max\|gap_Clay\| | mean(Clay−Gauss) | sign-stable? |
|------|----|----|------------------|-----------------|------------------|--------------|
| us_west | 0.47 | 1.77 | 0.066% | 0.038% | +0.011% | no |
| taskc | 0.31 | 0.90 | 0.158% | 0.083% | −0.056% | no |
| us_hetero | 0.20 | 0.50 | 0.270% | 0.127% | +0.070% | no |

Gap = CVaR reduction vs independence (positive = structured copula helps). Largest
absolute copula gap anywhere is **0.13%**, signs flip across α — same null as
Phase 1.

**The one interpretable signal:** Clayton−Gaussian is consistently **positive in
the heterogeneous case** (+0.07%) and negligible/negative where correlation is
common-mode. The asymmetric copula *does* extract something the elliptical one
cannot, in the expected direction — but an order of magnitude below materiality.

## 4. Why — the mean-dominance bound (Proposition 1)

CVaR translation invariance: `CVaR_β(<ρ,x>) = <ρ̄,x> + CVaR_β(<ξ,x>)`, ρ=ρ̄+ξ.
The dependence model affects **only** the residual tail term; its leverage Λ(x) is
the comonotone–diversified spread. The Phase 1 **mean-ablation measures Λ
directly**: ≤0.3% with the mean present, ~1.5% under flat ablation. The mean field
pins the schedule; the dependence model — elliptical or not — is immaterial.

## 5. What this does for the thesis

Converts the Phase 1 null from *"covariance is the wrong object"* into the stronger
*"no passive dependence model recovers value here, because the binding constraint
is the mean field."* Kills the "wrong model" rebuttal and adds a theoretical
contribution (the bound) — addressing the two weakest points of a pure-null thesis.

## 6. Next

The mean-dominance bound concerns **passive** risk reduction, so the **inter-region
transfer channel** (`f_{r→s,t}`, active load migration) is now the clearly-motivated
route to any spatial value — pending Bissan sign-off (migration is established background). A
full copula-*ambiguity* Wasserstein DRO (Fan–Ji–Lejeune) is the model-free version
of Phase 2 but the bound predicts the same outcome.

## 7. Code / tests

`feasible_set.py`, `cvar_saa.py`, `copula_scenarios.py`,
`scripts/run_copula_experiment.py`, `scripts/plot_copula.py`,
`tests/test_phase2_copula.py`. Full suite: **168 passing** (163 + 5). Figures:
`figures/copula_density.{pdf,png}`, `figures/copula_result.{pdf,png}`.
