# Research roadmap — where spatial structure creates value in robust carbon scheduling

One question runs through the whole line: **when does the *spatial/dependence*
structure of carbon intensity actually create value in robust data-center
scheduling, and when is it a distraction?** Each part answers a sharper version.

| Part | Question | Answer | Contribution | Status |
|------|----------|--------|--------------|--------|
| **1** | Does the spatial **covariance** help? | No (replicated null) | falsification protocol + empirical null | **done** (capstone) |
| **2** | Does a richer **copula** help? | No — null is total | mean-dominance bound; copula schedulers | **done** (capstone) |
| **3** | Does making the decision **spatial** (active transfer) help? | likely yes (mean-exploiting); open: does *robustifying* it beat deterministic? | DRO + active transfer (new algorithm) | proposed (`proposal_transfer_channel.md`) |
| **4** | Does it survive the **realistic operational** setting — and is there a general principle? | TBD | online multistage robust transfer + a learned ambiguity set; *or* a general "when does coupling matter" theory | future |

Parts 1–2 are the capstone (Paper 1, a negative/measurement result). Part 3 is the
novel algorithm (Paper 2). Part 4 is the program's capstone — two complementary
tracks, below.

---

## Part 4 — Online, learning-augmented robust transfer (and the general principle)

Parts 1–3 all live in the same **static, one-day-ahead, carbon-only, perfect-mean**
world. Part 4 removes those four idealizations, in roughly increasing ambition.

### Track A (systems / deployable): online multistage robust transfer

The realistic operational problem is **sequential**: day-ahead and intra-day
forecasts arrive over time, the operator commits load and transfers, then adapts as
information is revealed. Static one-shot DRO is replaced by **multistage
distributionally robust optimization** (or a robust model-predictive / rolling-horizon
controller) over the transfer-augmented model of Part 3.

- **Multiple uncertainties, jointly.** Carbon intensity is no longer the only
  stochastic object: demand, renewable availability, and transmission limits are
  uncertain too. Part 4 robustifies against the joint uncertainty, testing whether
  the Part 1–3 conclusions (mean-dominance; transfer is the lever) survive when the
  *mean itself* is uncertain.
- **Learned ambiguity set.** Feed the team's CNN/ANN carbon forecaster
  (Nicolás's work) into the ambiguity set: centre the Wasserstein ball on the
  *learned forecast*, size $\varepsilon$ by the forecaster's out-of-sample error.
  This is "learning-augmented DRO" and is where forecasting and optimization meet.
- **Closed-loop evaluation.** Evaluate as a rolling-horizon controller on real
  operational traces (carbon + workload), reporting realized CVaR and carbon over a
  full year — i.e. *deployed* performance, not one-day-ahead optimality.

This turns the line from "what is optimal in principle" into "what is deployable,"
and is the natural home for a strong systems venue (e-Energy, SIGEnergy, or a
journal). It is also where the three teammates' pieces compose: Nicolás's forecasts,
Yaxin's deterministic transfer baseline, Marco's robust layer.

### Track B (theory / high-impact): when does coupling matter?

The mean-dominance bound (capstone Proposition 1) is stated for this specific SOCP,
but the *phenomenon* is general: any robust resource-allocation problem with a
**dominant separable mean** plus a **correlated residual** will be insensitive to
the residual's dependence structure. Track B generalizes the bound into a
problem-class characterization:

> Given a robust allocation problem, a clean *a-priori* condition (in terms of the
> mean's separable gradient, the residual covariance norm, and the feasible-set
> geometry) for **when modelling cross-coordinate dependence can and cannot improve
> the robust objective.**

Carbon-aware data centers become *one instance*; the same lens applies to
energy-storage arbitrage, EV charging fleets, spatial supply chains, and portfolio
selection — wherever practitioners reflexively model a full covariance/copula. The
deliverable is a short theory paper that tells a field *when not to bother*, which
is exactly the kind of negative-but-general result that gets cited. This is the
higher-risk, higher-reward track and the one that turns a set of experiments into a
**research program** rather than a sequence of papers.

### Recommended sequencing

Track A first (concrete, collaborative, deployable, and it stress-tests whether the
static conclusions hold). Track B can be developed in parallel as the unifying
theory and written once Tracks A / Part 3 supply the empirical instances. Both
depend on Part 3 landing first.
