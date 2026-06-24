# Research roadmap — where spatial structure creates value in robust carbon scheduling

One question runs through the whole line: **when does the *spatial/dependence*
structure of carbon intensity actually create value in robust data-center
scheduling, and when is it a distraction?** Each part answers a sharper version. The
program is a finished five-part arc — knowing where it *ends* is part of the design.

| Part | Question | Answer | Contribution | Status |
|------|----------|--------|--------------|--------|
| **1** | Does the spatial **covariance** help? | No (replicated null) | falsification protocol + empirical null | **done** (capstone) |
| **2** | Does a richer **copula** help? | No — the null is total | mean-dominance bound; copula schedulers | **done** (capstone) |
| **3** | Does making the decision **spatial** (active transfer) help? | likely yes (mean-exploiting); open: does *robustifying* it beat deterministic? | DRO + active transfer (new algorithm) | proposed (`proposal_transfer_channel.md`) |
| **4** | Does it survive the **realistic operational** setting? | TBD | online multistage robust transfer with a learned ambiguity set | future |
| **5** | Is there a **general principle**? | TBD | a problem-class condition for when cross-coordinate dependence can ever help a robust allocation | future |

Parts 1–2 are the capstone (**Paper 1**, a negative/measurement result). Part 3 is
the novel algorithm (**Paper 2**). Parts 4–5 are the program's expansion: deploy it,
then generalize it. The line then closes.

---

## Part 3 — Spatially-coupled transfer DRO (the new algorithm)

Detailed in `proposal_transfer_channel.md`. In one line: introduce inter-region load
flows `f_{r→s,t}` so the schedule can migrate work toward whichever region is
cleanest, and ask not "does transfer help" (it must — it is mean-exploiting) but
**"does robustifying transfer beat plain deterministic transfer?"** The combination
DRO + active transfer is novel; the deterministic baseline is the teammate's model
(`ε=0`), so the pieces compose rather than compete.

## Part 4 — Online, learning-augmented robust transfer (deploy it)

Parts 1–3 all live in a **static, one-day-ahead, carbon-only, perfect-mean** world.
Part 4 removes those idealizations and asks whether the conclusions survive.

- **Sequential decisions.** Forecasts arrive over time; the operator commits load and
  transfers, then adapts. Static one-shot DRO becomes **multistage DRO** (or a robust
  model-predictive / rolling-horizon controller) over the Part 3 transfer model.
- **Joint uncertainty.** Carbon intensity is no longer the only stochastic object —
  demand, renewable availability and transmission limits are uncertain too. This
  tests whether mean-dominance survives when the *mean itself* is uncertain (if it
  breaks under sequential forecast error, that is itself a finding).
- **Learned ambiguity set.** Centre the Wasserstein ball on a **learned forecast**
  (the team's CNN/ANN carbon forecaster) and size `ε` by its out-of-sample error —
  "learning-augmented DRO," where forecasting meets optimization.
- **Closed-loop evaluation.** Roll the controller over a full year of real traces and
  report *realized* CVaR and carbon — deployed performance, not one-day-ahead
  optimality.

This is where the modelling pieces compose (Nicolás's forecasts, the deterministic
transfer baseline as established background, Marco's robust layer) and is the natural home for a
strong systems venue. It depends on Part 3 landing first.

## Part 5 — When does coupling matter? (the general principle)

The mean-dominance bound (capstone Proposition 1) is stated for this specific SOCP,
but the *phenomenon* is general: **any robust resource-allocation problem with a
dominant separable mean plus a correlated residual will be insensitive to the
residual's dependence structure.** Part 5 turns the bound into a problem-class
characterization:

> An *a-priori* condition — in terms of the mean's separable gradient, the residual
> covariance norm, and the feasible-set geometry — for **when modelling
> cross-coordinate dependence can and cannot improve the robust objective.**

Carbon-aware data centers become *one instance*; the same lens applies to
energy-storage arbitrage, EV charging fleets, spatial supply chains and portfolio
selection — wherever practitioners reflexively model a full covariance/copula. The
deliverable is a short theory paper that tells a field *when not to bother* — exactly
the kind of negative-but-general result that gets cited. It is the program's
intellectual capstone, and it gets stronger the more application instances Parts 3–4
(and adjacent work) supply, so it is written last.

## Sequencing & scope

1. **Part 3** first — needs supervisor sign-off on the boundary with the teammate's
   deterministic-transfer work (see `proposal_transfer_channel.md` §5).
2. **Part 4** next — concrete, collaborative, deployable; stress-tests the static
   conclusions.
3. **Part 5** last — but keep a running theory notebook from Part 3 onward, since
   every new instance is a data point for the general condition.

**The line stops at Part 5.** Anything further is either a *new domain* (which is
really an instance feeding Part 5) or a *different question* (carbon-aware market
design, cooling/hardware co-scheduling, …) — a new line, not a Part 6. A crisp
five-part arc is more compelling than an open-ended list.

> **Reality check.** All of the above is downstream of work that does not exist yet:
> Part 3 needs sign-off; Parts 4–5 need Part 3 to land. What is *due* is the capstone
> (Parts 1–2), which is complete. This roadmap is the future-work story to gesture at
> in the defense, not a commitment.
