# Thesis split: regular capstone vs. extended thesis

How the two write-ups divide the material, grounded in Bissan's four signals and the
30-page hard limit. Bissan's signals (from `docs/thesis_change_map.md`, `docs/pivot_plan.md`):
**(1)** the null is boring — lead with something useful; **(2)** not convinced of the DRO
quality; **(3)** forecast carbon **daily / day-ahead**, not yearly; **(4)** doesn't get
where the copula came from — cut it from the main story.

- **Regular capstone:** `thesis/capstone_thesis.tex` → 41 pp PDF, graded body ~29 pp.
  HARD LIMIT 30 pp excl. references + appendices. 12 pt Times, 1.5 spacing. Due **Mon 29 Jun 2026**.
- **Extended thesis:** `full_thesis/full_thesis.tex` → 57 pp. No page limit; develops
  Parts 3–5 (transfer, online/rolling-horizon, theory) in the body.

---

## B. The split principle (the one-line rule)

> **Capstone = the value-first, day-ahead scheduler story Bissan asked for, defensible in
> 30 pp (RQ1 savings lead, RQ2 screening rule, RQ3 crossover as a decision rule; copula
> DEMOTED to a one-paragraph appendix; null re-aimed as a tool, not a conclusion).
> Extended thesis = the rigor, the negative results in full, and the deeper OR theory —
> the spatially-coupled transfer DRO, online/rolling-horizon control, and the
> multistage/condition-number theory — that prove the capstone's claims.**

Operationally: if a section *raises the grade inside 30 pp and answers a Bissan signal*, it
is capstone body. If it is *depth, a secondary null, or OR theory that a committee rewards
but a 30-pp brief can only gesture at*, it lives in the extended thesis (and as a
one-paragraph capstone appendix pointer). The day-ahead framing leads both; the copula
trails both.

---

## A. The split table

One row per topic. "Body / appendix / cut" is for the **capstone**. Extended column says
where it lives in `full_thesis.tex`. Section numbers are from the two `.toc` files.

| Topic | Capstone | Extended thesis | Rationale (Bissan signal + 30 pp) |
|---|---|---|---|
| **Day-ahead migration scheduler + savings (RQ1)** | **Body** — §4.2 "The day-ahead scheduler and its savings" | Body §4.2 (mirrored) + §6 transfer DRO | Signal #1 (the useful result) and #3 (daily). This is the new spine — must lead Results. 4.0–9.9 % CVaR cut over Φ=0. |
| **Transfer-value curve / complexity–value frontier (RQ1)** | **Body** — §4.3 "Where the value comes from: the complexity–value frontier" | Body §4.3 + the active transfer model §6.1–6.2 | The "which lever" answer. Capstone shows the curve + frontier figure; extended develops the spatially-coupled transfer *model*. |
| **Screening rule: passive covariance adds nothing (RQ2)** | **Body** — §4.4 | Body §4.4 | Signal #1 re-aimed: the null becomes a *screening rule* ("don't bother modelling passive dependence"), not a dead end. Keep, brief. |
| **Covariance null + robustness battery (BH, walk-forward, shrinkage, MDE power, equivalence) (RQ2)** | **Body, condensed** — §4.5 + paras (tail-level, conditioning, power, equivalence) | Body §4.5 + dedicated validation §9.1–9.6 | High rigor, validates the screening rule. Capstone keeps the headline battery; extended carries the full per-test detail and the software test suite. |
| **Mean-dominance theorem (Prop. 1)** | **Body** — stated in §3.9 / §5.2 mechanism; keep as diagnostic | Body §8 "A Problem-Class Condition" (full treatment: §8.1 ratio, §8.2 validation) | "Keep, promote" (change map). It is the *so-what* that turns the null into a rule. Capstone states it + uses it; extended gives the problem-class condition + regime indicator. |
| **Copulas (Gaussian / Clayton / copula-CVaR scheduler)** | **Appendix B, one paragraph** — "richer passive dependence also adds ~0" | Appendix B (3 paras) + the design-justification one-liner | Signal #4, explicit: Bissan didn't get where the copula came from → **cut from main story**, demote to a one-line design justification + appendix corroboration. Costs ~0 pp. |
| **Tail-severity crossover / price of robustness (RQ3)** | **Body** — §4.9 "The price of robustness: when does the crossover pay?" + "real grids stay below" para | Body §6.3 (data-grounded emergency) + §4.9 | Signal #2: the one place robustness earns its keep. Frame as a **decision rule** (robustify only past M*≈3) with the honest bound (real grids reach only M≈1.4). The OR money shot. |
| **Online / rolling-horizon control (Part 4)** | **Appendix C pointer** ("Extended outlook: online and multistage robust transfer") | **Body §7** "Online Operation: Rolling-Horizon Control" (§7.1 controller, §7.2 second-order online, §7.3 forecast robustness) | Depth, not needed to defend RQ1–RQ3 in 30 pp. Extended develops it; capstone gestures in App. C. |
| **Multistage / condition-number theory (Part 5)** | **Appendix C pointer** (same outlook appendix) | **Body §8** (mean-dominance ratio) + Appendix C "Five-Part Research Programme" | OR theory that rewards a committee but overflows 30 pp. Extended body; capstone one-paragraph horizon note. |
| **Tail-dependence diagnostics (χ_L, χ_U)** | **Appendix paragraph** (demoted) — supports §4.7 | Body §4.7 "Tail dependence: the structure is non-elliptical" | Change map: "demote to appendix paragraph" — it existed to motivate the copula; with the copula gone it is supporting detail. Capstone keeps one line in §3.9 / §4.7, full diagnostic in extended. |
| **Reproducibility** | **Appendix A** (Reproducibility Details) | Appendix A + Body §9 (testing/validation/reproducibility chapter) | Standard appendix in capstone; extended elevates to a full §9 chapter ("what 'tested in many files' does and does not mean"). |
| **RQ1 correlation validation (premise check)** | **Body, one figure** — §4.1 | Body §4.1 | "Keep, brief": the data has structure. One figure, premise only. |
| **Falsification / shuffled-marginals test** | **Body, demoted** — §3.7 (method) feeding §4.4 | Body §3.7 + §9.2 protocol | Good method, stays as *evidence* for the screening rule, not the spine (#1: a null can't headline). |

---

## C. Page-budget check (target ≤ 30 pp body)

Current capstone body runs **§1 (p4) → end of §6 Conclusions (p31–32)**; appendices A–C +
Annex A then run p33–39. So the **graded body is ~29 pp and §6.3 spills onto p31** — it is
**over the 30-pp line by 1–2 pp** as rendered. Tighten before submission.

### Must move OUT (or compress) to land comfortably ≤ 30:

| Item | Where now | Action | Est. pp saved |
|---|---|---|---|
| Robustness-battery sub-paragraphs (tail-level, conditioning, power, equivalence) | §4.5, pp 20–23 | Keep the headline + equivalence; move per-test detail (conditioning artifact, MDE power table) to App. A | ~1.0 |
| §4.7 tail-dependence prose | pp 24–25 | Compress to 3–4 sentences + one figure; full χ_L/χ_U table to appendix | ~0.5 |
| §4.8 "richer dependence models confirm screening rule" | p 25 | Fold into the App. B one-paragraph copula note; leave a single cross-reference in body | ~0.7 |
| §3.10 "Phase 2: richer dependence models (summary)" + "Why second-order" + "Computational considerations" | pp 13–15 | Demote to App. B; keep one sentence in §3 | ~1.0 |
| §5.3 "Relation to prior work" | p 28 | Trim to a tight paragraph (lit-review already covers it) | ~0.3 |

Net: ~3.5 pp of slack → body lands at **~26–27 pp**, safely under 30.

### Could move IN if space allows (only after the above):
- A second **crossover figure** (synthetic-vs-real M side-by-side, N4 in pivot plan) — strengthens RQ3, the highest-value addition. ~0.7 pp.
- A one-row **decision-rule table** in §5.4 (deploy deterministic / robustify above M* / skip joint+copula) — cheap, high clarity. ~0.3 pp.
- The day-ahead **savings bar chart** (S1) as the opening Results figure if not already placed. ~0.5 pp.

---

## D. Prioritized "make it better" lists

Risk key: **safe-polish** (low risk) · **needs-care** (verify numbers/claims) · **restructure** (moves sections / re-runs).

### D1. Capstone — raise the grade within 30 pp, answer Bissan #2/#3

| # | Improvement | Why it raises the grade | Risk | Effort |
|---|---|---|---|---|
| 1 | **DONE (boundary, no attribution) — author decision 2026-06-18.** Chosen approach is *keep no-Yaxin, sharpen the boundary*: §2.1 now credits the deterministic-migration *literature* (`radovanovic2022,wiesner2021`) as established background and scopes the novelty to the modelling layers; contributions (i) states the migration mechanism follows established practice and the contribution is the honest $\Phi=0$-anchored measurement. The lever is framed as Marco's robust/stochastic + decision-rule work. No Yaxin attribution per standing decision ("we are not doing the same thing"). | Integrity — closes the "uncited headline overlap" attack by framing migration as known background and the contribution as the characterization. | done | done |
| 2 | **Make the DRO's day-ahead job airtight (Signal #2).** §3.3 already re-points the ball to day-ahead forecast-error residuals (good). Add 2–3 sentences naming the comparator forecasts and stating the residual-CVaR unit test (S4) result, so "convince me of DRO quality" has a concrete answer. | Directly answers #2; pre-empts the "your DRO barely moves anything" objection by showing it has a *characterized* job + a passing test. | needs-care | 2 h |
| 3 | **DONE 2026-06-18 — restored the 7 `es_pt_fr` derived snapshots** (and generator scripts) to `docs/results_snapshots/`, fixing the traceability gap that an over-aggressive Iberia cleanup had introduced. Iberia stays as honest low-correlation external validity; all cited Iberia numbers trace to a snapshot again. | Traceability restored without scrubbing Iberia from the theses. | done | done |
| 4 | **Lead Results with the savings bar chart + a one-line decision-rule box** (S1 + S3). | Signal #1: the useful result must be the first thing the reader sees; the decision rule is the "so what." | safe-polish | 2 h |
| 5 | **Compress §4.5–4.8 per the page budget (C).** Land body at ~26–27 pp; banks ~3.5 pp for the crossover figure + decision-rule table. | Keeps the value-first arc tight; avoids the 30-pp overflow currently at p31. | restructure | 3 h |
| 6 | **DONE 2026-06-18.** Added Limitation (vi): the day-ahead forecast is deliberately a transparent hour-of-day climatological mean updated daily, not a learned predictor, framed as a design choice that keeps the price-of-robustness result a property of hedging residual error (a learned forecaster would only shrink the already-immaterial premium). Directly answers Bissan #2. | Turns "your forecast is trivial" into a stated, defensible scope choice. | done | done |
| 7 | **State the copula demotion as one design-justification line** in §3 + the App. B paragraph, never in the spine. | Signal #4: closes the "where did the copula come from" gap cleanly. | safe-polish | 0.5 h |

### D2. Extended thesis — depth and rigor

| # | Improvement | Why it adds depth | Risk | Effort |
|---|---|---|---|---|
| 1 | **DONE 2026-06-18 — mirrored the capstone boundary edit (no Yaxin attribution).** Applied the same §2.1 lit-review boundary (`radovanovic2022,wiesner2021` as established migration background), the contributions-(i) "migration follows established practice; contribution is the honest $\Phi=0$-anchored measurement" clause, and the softened Annex A to `full_thesis.tex`. Recompiled clean (57 pp, refs resolve, 0 em-dashes, 0 Yaxin). | The two write-ups are now consistent; the overlap attack is closed the same way in both. | done | done |
| 2 | **Promote Prop. 1 to a proved problem-class condition** in §8 with the κ (condition-number) regime indicator and a worked bound, not just a ratio. | This is the extended thesis's strongest OR-theory contribution; a committee rewards a clean theorem + regime map. | needs-care | 4–6 h |
| 3 | **Develop the two-stage robust transfer with costly recourse** (§6.1–6.3) fully — the data-grounded emergency model and the M* crossover derivation, including why real grids sit below M*. | The genuine OR novelty (DRO + active transfer); the §6.3 "does the crossover survive a data-grounded emergency" is the make-or-break shot. | needs-care | 6–8 h |
| 4 | **Flesh out §7 rolling-horizon control** with the forecast-robustness sweep (§7.3) and the "robustness is second-order online too" result on real data. | Shows the null/screening result is not an artifact of the one-shot formulation — strengthens external validity. | needs-care | 4 h |
| 5 | **Build the synthetic-vs-real crossover side-by-side panel** (N4) and the full χ_L/χ_U tail-dependence diagnostic with all 17 zones. | Visual proof of the central RQ3 claim; the extended thesis has the page budget the capstone lacks. | safe-polish | 2 h |
| 6 | **Make §9 a real validation chapter** ("what 'tested in many files' does and does not mean") — tie each of the 194 tests to a claim. | Reviewer-grade reproducibility; differentiates the extended thesis from the brief. | safe-polish | 2 h |

---

## E. Risk flags (explicit checks)

### E-i. DELETED Iberia (es_pt_fr) snapshots vs. still-cited numbers — **CONFIRMED GAP**

There is **no `es_pt_fr` snapshot** in `docs/results_snapshots/` or in the live `results/`
directory (both fully listed — only `taskA`, `taskC`/`us_west`/`us_hetero`/`taskc`, copula,
and Part 3/4/5 files remain). The snapshots README still documents `es_pt_fr` as a valid
case, but the files are gone. **Both theses still cite Iberia–France numbers:**

| File | Lines citing Iberia / es_pt_fr |
|---|---|
| `thesis/capstone_thesis.tex` | 87, 553, 712, **829–838** (the ε* "flickers between 0,0.1,1,10" paragraph — a hard numeric claim), 1191, 1315, 1370, 1557 |
| `full_thesis/full_thesis.tex` | 92, 580, 752, **883–892**, 1257, 1382, 1951, 2168 |

The most exposed is the **§4.3 Iberia paragraph (capstone 829–838 / extended 883–892)**: it
makes specific ε* claims with no traceable snapshot. **Action:** either re-run `es_pt_fr` and
re-snapshot, or downgrade every site to qualitative ("a near-zero-correlation European panel
provides low-correlation external validity") and remove the specific ε* values. The "17 zones"
count (capstone 1191/1370, extended 1257/1951) also implicitly includes Iberia — verify the
count still holds without it.

### E-ii. "Day-ahead forecasting" overstatement — **MODERATE, attack surface exists**

The forecast is the **hour-of-day climatological mean on the training window, updated daily**
(`capstone_thesis.tex` §3.3, lines 293–296) — i.e. a persistence/seasonal mean, **not a learned
forecaster**. The thesis is mostly honest (it says "point forecast," "empirical mean field"),
but the abstract/intro language "day-ahead carbon forecasting" (lines 78, 96, 147) can be read
as a real forecasting model. **Attack vector:** a committee can argue "your DRO conclusion only
shows robustness doesn't help *a trivial forecast* — a good learned forecaster might change the
crossover." **Action (capstone D1-#6):** one sentence in §3.3 naming the forecast as
climatological-mean-by-design, and a Limitations line conceding a learned forecaster is future
work. The extended thesis's §7.3 forecast-robustness sweep partly answers this — cross-reference it.

### E-iii. Transfer-channel scope overlap with teammate (Yaxin) — **HIGH, currently unmitigated**

`docs/proposal_transfer_channel.md` §5 and `docs/pivot_plan.md` M5 both flag that **inter-region
transfer overlaps Yaxin's remit** (she owns *deterministic* transfer + fairness; Marco owns the
*robust/DRO* transfer layer + crossover decision rule). The pivot plan rates this an **INTEGRITY**
item requiring a boundary statement, Annex A attribution, a citation, and an email to Bissan + Yaxin.

**Finding:** neither `capstone_thesis.tex` nor `full_thesis.tex` mentions Yaxin (grep count = 0 in
both), and **both Annex A statements claim sole authorship** (capstone lines 1753–1777). Yet the
**capstone now leans on the deterministic transfer result as its headline** (the 4.0–9.9 % lever,
§4.2 line 81 / 740). The capstone line 1776 ("The inter-region transfer channel is developed under
the supervisor's direction and is identified throughout as the author's day-ahead migration
scheduler") actively *claims* the channel without naming the teammate whose deterministic-transfer
model it overlaps.

**RESOLVED IN THE CAPSTONE (author decision 2026-06-18): keep no-Yaxin, sharpen the boundary.**
The standing decision is no Yaxin attribution ("we are not doing the same thing"). Rather than
attribute, the capstone now *re-frames* so the overlap is not an issue: §2.1 credits the
deterministic-migration **literature** (`radovanovic2022,wiesner2021`) as established background and
explicitly takes the migration mechanism as given; contributions (i) states the contribution is the
honest, $\Phi=0$-anchored *measurement* of spatial value (plus the screening rule and the
price-of-robustness decision rule), not the migration mechanism. This closes the "uncited headline
overlap" attack by positioning migration as known prior art and Marco's novelty as the
characterization. **Resolved 2026-06-18:** (a) the boundary edit is now mirrored into `full_thesis.tex` (D2 #1, done);
(b) Annex A in both theses softened to "the migration mechanism follows established carbon-aware
practice; my contribution is its robust treatment, the honest measurement, and the decision rules."
**Still the author's call:** the confirming email to the supervisor about the collaboration boundary.
No teammate is named, per the standing decision.

---

## Quick reference: what leads, what trails

- **Leads both theses:** the day-ahead migration scheduler (RQ1) and its savings → the screening rule (RQ2) → the crossover decision rule (RQ3).
- **Trails both theses:** the copula (one appendix line/paragraph), the tail-dependence diagnostic (appendix), the bare null (re-aimed as a tool, never a headline).
- **Capstone-only-as-pointer, extended-as-body:** online/rolling-horizon (Part 4, §7), multistage/condition-number theory (Part 5, §8), the full validation chapter (§9).
