# Thesis change map — what to keep, recast, and drop

Argued from Bissan's four signals, mapped to the evidence we now have.

**Bissan's signals:** (1) the null is boring, no contribution → lead with something useful;
(2) not convinced about the DRO quality; (3) predict carbon **daily** (day-ahead), not
yearly; (4) doesn't get where the copula came from.

| Component (current thesis) | Verdict | Argument (tied to the signal) |
|---|---|---|
| **Abstract** | **Recast** | Opens on the falsification/null — Bissan #1's "boring" frame. Re-lead with the artifact (day-ahead migration scheduler) + the savings, then the screening rule, then the crossover. The null shrinks to one clause. |
| **Intro / research questions** | **Recast** | RQs are null-shaped ("is correlation valid / does it help"). New RQs: *how much can a day-ahead carbon-aware migration scheduler cut emissions, and which lever drives it?* and *when is richer modeling complexity worth it?* Answers #1 and turns the null into a "when does it pay" question. |
| **Literature review** | **Keep (light recast)** | Add the "how much modeling is worth it" gap; **credit the deterministic-transfer literature explicitly** (`radovanovic2022,wiesner2021`, established background). Drop the "spatial DRO is untested" framing. |
| **DRO formulation (Mahalanobis–Wasserstein)** | **Recast — the pivotal change** | Today it hedges a *static annual covariance* and barely moves it (~0.18%) — exactly why Bissan (#2) isn't convinced. Re-point it as the robust layer over **day-ahead forecast error** (a standard data-driven Wasserstein/CVaR set on residuals), with a precise, honest domain of value (the crossover M*). This single change answers **both #2** (the DRO gets a defensible job + characterized value) **and #3** (daily, not yearly). |
| **Shuffled-marginals falsification test** | **Keep, demote** | Good method, stays — but as the *evidence* for the screening rule, not the spine (#1: the null can't headline). |
| **Mean-ablation + mean-dominance bound (Prop. 1)** | **Keep, promote** | This is the "so what": the a-priori rule for when passive dependence modeling cannot help. Turns the null into a *tool*. Keep the theorem. |
| **Tail-dependence diagnostic** | **Demote to appendix paragraph** | It existed to motivate the copula; with the copula demoted it's supporting detail. |
| **Copula chapter (Phase 2)** | **Drop to appendix** | Bissan #4, explicit. One paragraph: "richer passive dependence (Gaussian/Clayton) also adds nothing — corroborates the screening rule." Removes the unmotivated piece, costs ~0 pages. |
| **RQ1 correlation validation** | **Keep, brief** | A premise check (the data has structure), one figure. |
| **Robustness battery (BH, walk-forward, shrinkage, MDE power)** | **Keep** | Now validates the *savings* + the *screening rule*, not the null. High rigor, transfers directly. |
| **§4.1 day-ahead scheduler + savings** | **ADD (the artifact)** | #1: the useful result. Savings over the **honest per-region-greedy baseline**; the transfer-value curve (transfer is the dominant lever, 4.0–9.9% CVaR reduction over Φ=0). |
| **§4.4 the tail-severity crossover** | **ADD (the OR money shot)** | #2: the one place robustness unambiguously earns its keep — robustness pays only past M*≈3, framed as a **decision rule**, with the honest bound that real grids stay below it. |
| **Discussion / practical recommendation** | **Recast** | Around the unified decision rule: deploy deterministic migration; robustify only above M*; skip joint/copula modeling. |
| **Conclusions** | **Recast** | From "we found a null" to "we built a scheduler that saves X, and derived the rule for when each layer of complexity pays." |

## The through-line
Nothing rigorous is thrown away. The null is **re-aimed** from conclusion → decision rule.
The DRO is **re-pointed** from yearly-covariance (where it looks weak) to day-ahead forecast
error + the crossover (its honest domain). The copula **leaves the spotlight**. Every one of
Bissan's four signals maps to a specific change.

## The one honesty caution
Even recast, the DRO's domain of value (the crossover) **does not survive data-grounded
emergencies** — real grids sit below M*. So the honest claim is "robustness has a *characterized,
bounded* domain of value," not "the DRO works." Present it as a decision rule (when to invest in
robustness), with the real-world verdict attached. That is *more* defensible than overclaiming,
and it directly, honestly answers Bissan #2 — without pretending the DRO is a hero it isn't.
