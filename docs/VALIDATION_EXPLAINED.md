# How This Thesis Validates Its Claims, and Why Each Choice Was Made That Way

**Repo:** github.com/ma731/Capstone-in-Operations-Research · **Thesis:** "The Price of Sophistication" · **Author:** Marco Ortiz Togashi, supervised by Prof. Bissan Ghaddar · **Document date:** 2026-07-12

This document explains, in plain language, every layer of validation in the project: what each mechanism is, where it lives in the repository, why that method was chosen over the obvious alternatives, and the literature it rests on. It is written so that a reader with no operations-research background can follow the logic, while every technical term is **highlighted**, defined on first use, and cited. All file paths are real and all numbers are taken from the archived snapshot CSVs (verifiable via `python -m scripts.make_provenance_manifest --check`).

The one-paragraph context: the thesis builds a working day-ahead scheduler that moves flexible data-center compute toward cleaner hours and regions, then prices three optional layers of modelling sophistication, asking which layer actually improves worst-day emissions. The answer (inter-region transfer pays 4.04–9.91%; dependence modelling adds under 0.4%; distributional robustness pays only past an emergency severity of about 3x) is only as credible as the validation behind it. That validation has nine layers.

---

## Layer 1 — The risk metric: why CVaR and not the mean, or VaR

**What it is.** All headline results are measured in **CVaR₀.₉₅** (Conditional Value-at-Risk at the 95% level), implemented in `src/analysis/metrics.py` as the empirical mean of the worst 5% of days. In plain words: instead of asking "how do emissions look on average," the thesis asks "how bad are the bad days," because grid emergencies and dirty-grid days are precisely when carbon-aware scheduling matters.

**Why not the mean?** A scheduler can look excellent on average while failing exactly when the grid is stressed; averaging washes out the tail, which is the object of study.

**Why not VaR?** **VaR** (Value-at-Risk, the 95th-percentile threshold itself) tells you where the bad tail *starts* but nothing about how bad it gets beyond that point, and it is not a **coherent risk measure**: it can penalize diversification, violating the subadditivity axiom that a sensible risk measure should satisfy (Artzner, Delbaen, Eber and Heath, 1999). CVaR averages over the whole tail, is coherent (Acerbi and Tasche, 2002), and — decisively for this project — admits the linear-programming reformulation of Rockafellar and Uryasev (2000), which is what makes CVaR *optimizable* inside the scheduler rather than merely reportable after the fact.

**Guarding against the choice itself.** Because any single tail level is a free parameter a skeptic can attack, the repo re-runs the headline experiments at CVaR₀.₉₀ and CVaR₀.₉₉ (`*_cvar0.9.csv`, `*_cvar0.99.csv` snapshots, 2026-06-15): the qualitative conclusions (which layer pays, which does not, the ordering of the crossover) hold at both, so the finding is not an artifact of picking 0.95.

**References.** Artzner, P., Delbaen, F., Eber, J.-M., Heath, D. (1999), "Coherent Measures of Risk," *Mathematical Finance* 9(3); Rockafellar, R.T., Uryasev, S. (2000), "Optimization of Conditional Value-at-Risk," *Journal of Risk* 2(3); Acerbi, C., Tasche, D. (2002), "On the coherence of expected shortfall," *Journal of Banking & Finance* 26(7).

---

## Layer 2 — Pre-committed falsification: the hypothesis was locked before the answer was known

**What it is.** The central RQ2 test (does modelling how regions' carbon levels move together add scheduling value?) was designed as a **pre-committed falsification test**: the comparison, the metric, and what would count as "no effect" were fixed in a locked script *before* the decisive results existed. The locked artifact is the capital-`taskC` runner, whose output is archived separately from the later generalized lowercase-`taskc` runner precisely so the pre-committed run remains distinguishable (`docs/results_snapshots/README.md` documents this naming deliberately).

**Why this and not "run experiments, then report"?** Because the alternative invites — even in good faith — the **garden of forking paths**: with many defensible analysis choices, a researcher exploring freely will eventually find a configuration where the effect appears, and the reported p-values no longer mean what they claim (Gelman and Loken, 2014). Pre-registration removes that degree of freedom: the analysis was chosen blind to the outcome, so a null result is a *finding*, not a failure to search hard enough (Nosek et al., 2018). Philosophically this is Popper's demarcation put into practice: a claim is scientific insofar as it specifies in advance what evidence would refute it (Popper, 1959). The thesis's title finding — sophistication mostly does *not* pay — is only publishable because the test that produced it could not have been quietly re-tuned until it did.

**The falsification arm.** The mechanism is a **shuffle comparison**: the scheduler is run once with the true joint covariance of regions and once with a "shuffled" covariance in which cross-region blocks are zeroed (regions rendered independent while each region's own behavior is preserved). If knowing the co-movement matters, the joint model must beat the shuffled one out of sample; the observed gap is under 0.4% of CVaR, inside the confidence band of zero.

**References.** Popper, K. (1959), *The Logic of Scientific Discovery*; Nosek, B.A., Ebersole, C.R., DeHaven, A.C., Mellor, D.T. (2018), "The preregistration revolution," *PNAS* 115(11); Gelman, A., Loken, E. (2014), "The statistical crisis in science," *American Scientist* 102(6).

---

## Layer 3 — Validating the test itself: claim-binding tests and the positive control

A null result raises two immediate objections, and the repo answers both *structurally*, not rhetorically. This layer is the direct answer to "did we validate the test, or just run it?" — yes, on both fronts.

**Objection A: "Maybe your shuffled comparator is broken, so the comparison is meaningless."** Answered by `tests/test_claim_binding.py`, a file that is unusual and worth understanding: where the rest of the suite checks that the code is implemented correctly, this file pins the *thesis's own theoretical statements* as executable tests, so the paper's central arguments are enforced in continuous integration rather than merely asserted in prose. Concretely it proves: (1) the shuffled matrix is still a mathematically valid covariance — **positive semidefinite** (all eigenvalues ≥ 0, the defining property of a covariance matrix) — so the falsification arm compares two *legitimate* models, not a real model against a broken one; (2) CVaR's **translation invariance** (shifting all outcomes by a constant shifts CVaR by exactly that constant), the algebraic backbone of the thesis's Proposition 1; (3) the Proposition 1 **mean-dominance bound** holds numerically on a solved instance; and (4) the bound's consequence — that scaling the mean field up drowns the fixed covariance term — is monotone as claimed. If any of these ever stops holding, the test suite fails and the thesis's argument is flagged before a human reads a single result.

**Objection B: "Maybe your pipeline couldn't detect an effect even if one existed."** Answered by a **positive control**, borrowed from laboratory practice: inject a condition where the effect *must* exist and confirm the instrument sees it. Here, the mean carbon field is flattened (**mean-ablation**, the `ablate-flat` snapshot variants), removing the signal that Proposition 1 says dominates; in that ablated world, covariance information is worth **+1.46%** and the pipeline detects it cleanly. So the instrument works; the real-world null (<0.4%) is therefore informative: the co-movement signal is *real but dominated*, not absent and not invisible. Without this control, "we found nothing" would be indistinguishable from "our code finds nothing" — the classic weakness of null-result papers.

**Why this way and not a power analysis on paper?** A theoretical power calculation depends on distributional assumptions the thesis would then have to defend separately; an injected known effect tests the *actual* end-to-end pipeline, assumptions and code included. The two objections and their structural answers together mean the RQ2 null is doubly guarded: the comparator is proven valid, and the detector is proven sensitive.

---

## Layer 4 — The stress-test ceiling: copulas up to the mathematical worst case

**What it is.** Correlation (covariance) only captures *linear* dependence. A skeptic could grant the covariance null but object: "real grids might co-move in nonlinear, tail-heavy ways your covariance model cannot express." The thesis closes this escape route with **copulas** — functions that describe the dependence structure between random variables separately from their individual distributions, which Sklar's theorem guarantees is always possible (Sklar, 1959). `src/models/copula_scenarios.py` implements four dependence regimes: independence; a **Gaussian copula** (dependence like a multivariate normal); a **Clayton copula**, whose defining feature is *lower-tail* dependence — regions crashing to their cleanest states together — sampled by the exact Marshall–Olkin frailty construction (Clayton, 1978; Marshall and Olkin, 1988); and, decisively, the **comonotone** coupling, the upper **Fréchet bound** (Fréchet, 1951): every region perfectly rank-locked to every other, the *mathematically maximal* possible dependence.

**Why include the comonotone case?** It converts an open-ended objection into a closed one. Instead of arguing about which realistic copula family is right, the thesis tests the ceiling: if even *perfect* co-movement buys no robust scheduling value in this problem, then no achievable dependence structure can — the mean-dominance mechanism, not the choice of dependence model, is doing the work. This is the strongest form the null can take: "we tested your best case for you, and it still doesn't help."

**Why numpy-only samplers?** Zero heavy dependencies means the dependence machinery is fully auditable in a few hundred lines and reproducible anywhere — a deliberate reproducibility choice, now additionally enforced by seed-determinism tests (Layer 8).

**References.** Sklar, A. (1959), "Fonctions de répartition à n dimensions et leurs marges," *Publ. Inst. Statist. Univ. Paris* 8; Clayton, D.G. (1978), "A model for association in bivariate life tables...," *Biometrika* 65(1); Marshall, A.W., Olkin, I. (1988), "Families of multivariate distributions," *JASA* 83(403); Fréchet, M. (1951), "Sur les tableaux de corrélation dont les marges sont données," *Ann. Univ. Lyon*.

---

## Layer 5 — Robustness sweeps: every free knob turned, on purpose

**What it is.** Any empirical result depends on estimation choices a critic can call arbitrary. The repo's answer is systematic: every free knob is re-run at alternative settings, each producing its own dated snapshot (the `_seasonal`, `_ar1`, `_lw`, `_ramp5`, `_util0.5`, `_util0.95`, `_cvar0.9`, `_cvar0.99` variant files).

**The covariance estimator, specifically.** Sample covariance matrices in high dimensions (here R×T can exceed the number of observed days) are notoriously ill-conditioned: eigenvalues are systematically over-dispersed and the matrix may be near-singular. The pre-committed alternative is **Ledoit–Wolf shrinkage** (`src/models/covariance.py`), which optimally blends the sample covariance toward a structured target and is *asymptotically the best-conditioned estimator in its class* (Ledoit and Wolf, 2004). Seasonal and AR(1) **residualization** variants additionally check that the conclusion is not an artifact of predictable daily/annual cycles masquerading as cross-region dependence. Constraint-tightness sweeps (ramp limits, utilization caps) check the *optimization* side the same way the estimator sweeps check the *statistics* side.

**Why sweeps and not a single "best" configuration?** Because the thesis's claim is about a mechanism (mean dominance), not a configuration. A mechanism-level claim is only credible if it survives configuration changes; a result that flips when the estimator changes is a fact about the estimator. Every sweep preserved the sign and ordering of the headline findings, and that survival — not any single run — is the evidence.

**Reference.** Ledoit, O., Wolf, M. (2004), "A well-conditioned estimator for large-dimensional covariance matrices," *Journal of Multivariate Analysis* 88(2).

---

## Layer 6 — Honest uncertainty: block bootstrap, not textbook error bars

**What it is.** Confidence intervals on the reported gaps come from a **moving-block bootstrap** (`scripts/run_block_bootstrap_check.py`; snapshot `block_bootstrap_2026-06-27.csv`): instead of resampling individual days independently, the procedure resamples *contiguous runs of days* of length L, preserving the serial dependence structure within each block.

**Why not the ordinary (i.i.d.) bootstrap?** Efron's original bootstrap (Efron, 1979) assumes observations are independent. Daily carbon intensities are emphatically not — weather systems, demand cycles and outages persist across days — and resampling days independently destroys that persistence, producing standard errors that are *too small* and confidence intervals that are falsely reassuring. The block bootstrap is the standard correction for stationary dependent data (Künsch, 1989; the stationary-bootstrap variant of Politis and Romano, 1994, is the main alternative and would serve equally). The repo goes one step further and *reports the block-to-i.i.d. standard-error ratio*, i.e., it quantifies exactly how much the naive method would have understated uncertainty — turning a methodological footnote into a checkable number.

**Why this matters for a null result.** The RQ2 conclusion is "the gap is within ±0.4%, indistinguishable from zero." That statement is only as honest as its interval; an i.i.d. interval would have been narrower, making the null look *stronger* than the data support. Choosing the wider, dependence-aware interval is choosing the version of the analysis least favorable to a clean story — the direction of conservatism a skeptical reviewer wants to see.

**References.** Efron, B. (1979), "Bootstrap methods: another look at the jackknife," *Annals of Statistics* 7(1); Künsch, H.R. (1989), "The jackknife and the bootstrap for general stationary observations," *Annals of Statistics* 17(3); Politis, D.N., Romano, J.P. (1994), "The stationary bootstrap," *JASA* 89(428).

---

## Layer 7 — Multiple testing: Benjamini–Hochberg over every gap cell

**What it is.** The experiments produce many gap estimates (regions × regimes × variants). Testing many hypotheses at the conventional 5% level guarantees spurious "significant" cells by chance alone — roughly one false positive per twenty true nulls. `scripts/bh_correction.py` applies the **Benjamini–Hochberg procedure** across *all* gap cells jointly, controlling the **false discovery rate** (the expected fraction of declared discoveries that are false) at the stated level (Benjamini and Hochberg, 1995); the corrected results are archived in `bh_correction.csv`.

**Why BH and not Bonferroni?** **Bonferroni** controls the stricter family-wise error rate (probability of even one false positive) by dividing the significance level by the number of tests — safe, but so conservative with many correlated tests that real effects get buried. BH trades that extremity for power while still controlling the error rate that matters for a discovery table. Crucially, the correction here cuts *against* the thesis's convenience: applied to a mostly-null landscape it removes any temptation to promote a lucky cell (say, one region-regime combination with an uncorrected p just under 0.05) into a headline. The thesis's significance claims — like "the robust-vs-deterministic gain first becomes significant at severity M = 3.0, CI [0.07, 6.94]" — survive correction; that is what makes them quotable.

**Reference.** Benjamini, Y., Hochberg, Y. (1995), "Controlling the false discovery rate: a practical and powerful approach to multiple testing," *JRSS Series B* 57(1).

---

## Layer 8 — Out-of-sample discipline: walk-forward, never random splits

**What it is.** Every headline number is **out-of-sample**: the scheduler's parameters are fitted on one period and evaluated on data it never saw. The evaluation scheme is **walk-forward** (the `ty2022`, `ty2023`, `ty2024` snapshot variants): train on the years before a test year, then read that test year exactly once. Across all three test years the spatial-null gap moves by at most **0.21%** of CVaR — the result is stable across time, not a fluke of one lucky year.

**Why not standard k-fold cross-validation?** Random k-fold splits shuffle time away: with serially dependent data, a training fold containing the day *after* a test day leaks information backward, and the resulting scores are optimistically biased — the time-series literature is unambiguous that evaluation must respect temporal order (Tashman, 2000; Bergmeir and Benítez, 2012). Walk-forward is also the honest simulation of deployment: a real scheduler only ever knows the past. The "read the test year once" rule matters as much as the split itself: repeatedly evaluating against the same test set and adjusting turns a test set into a validation set and silently reintroduces the forking-paths problem of Layer 2.

**Determinism (added post-defense, July 2026).** Reproducing a stochastic pipeline requires that seeds actually pin the randomness; `tests/test_determinism.py` now enforces that the copula samplers return bit-identical draws under a fixed seed, closing the gap between "reproducible in principle" and "reproducible in fact."

**References.** Tashman, L.J. (2000), "Out-of-sample tests of forecasting accuracy: an analysis and review," *International Journal of Forecasting* 16(4); Bergmeir, C., Benítez, J.M. (2012), "On the use of cross-validation for time series predictor evaluation," *Information Sciences* 191.

---

## Layer 9 — Provenance and adverse disclosure: every number traceable, including the unflattering ones

**What it is.** The live `results/` directory is gitignored (it holds large binaries); every number cited anywhere is instead archived as a dated, license-safe summary CSV in `docs/results_snapshots/`, with the regeneration command for each file documented in that folder's README. Since July 2026 the directory is additionally frozen by a **SHA-256 manifest** (`MANIFEST.sha256`, generated by `scripts/make_provenance_manifest.py`) and an integrity test (`tests/test_snapshot_manifest.py`) that fails CI if any archived CSV is ever edited: results are append-only by construction, not just by convention. SHA-256 is a cryptographic hash — any change to a file, even one byte, produces a different digest — so the manifest makes silent revision of the evidentiary record detectable by anyone.

**Adverse results are in the record, not the drawer.** The snapshots include the findings that cut against a tidy story: the rolling online comparison where the robust method *loses* on the Diversified grid (`part4_online_2026-06-15.csv`), and the BPAT region whose realized emergency severity of **5.12×** sits far beyond the M*≈3 crossover — the apparent outlier is annotated in the defense materials rather than trimmed. This is the practical answer to publication bias (Rosenthal's "file drawer problem," 1979): a reader can check not only that the reported numbers are real but that the *unreported* ones do not exist, because the archive is the complete set and its integrity is hash-verified.

**Why not "results available on request"?** Because that phrase is where reproducibility goes to die: request-based access rots with inboxes and graduations. Committed, license-safe, hash-frozen aggregates cost nothing and survive their author's availability. (Raw Electricity Maps data is excluded by its non-redistribution academic license; the snapshots contain derived statistics only, which is exactly why they *can* be public.)

**Reference.** Rosenthal, R. (1979), "The file drawer problem and tolerance for null results," *Psychological Bulletin* 86(3).

---

## Summary table

| Layer | Threat it neutralizes | Mechanism | Where | Key reference |
|---|---|---|---|---|
| 1. CVaR₀.₉₅ + tail sweeps | Averages hiding tail failure; incoherent VaR; cherry-picked tail level | Coherent tail metric, LP-optimizable; re-run at 0.90/0.99 | `src/analysis/metrics.py`, `*_cvar0.9/0.99` | Rockafellar–Uryasev 2000 |
| 2. Pre-committed falsification | Forking paths; tuned-until-significant | Locked taskC script; shuffle comparison fixed ex ante | locked runner + snapshots | Nosek et al. 2018 |
| 3. Claim-binding + positive control | "Test is broken" / "test is blind" | Thesis claims as CI tests; injected +1.46% detected | `tests/test_claim_binding.py`, `ablate-flat` | lab-control practice |
| 4. Copulas to the Fréchet bound | "Your model can't see nonlinear dependence" | Clayton lower-tail + comonotone worst case | `src/models/copula_scenarios.py` | Sklar 1959 |
| 5. Estimator/constraint sweeps | "Result is an artifact of one configuration" | Ledoit–Wolf, residualization, tightness sweeps | `_lw/_ar1/_seasonal/...` snapshots | Ledoit–Wolf 2004 |
| 6. Block bootstrap | Falsely tight error bars under serial dependence | Contiguous-day resampling; block/iid ratio reported | `run_block_bootstrap_check.py` | Künsch 1989 |
| 7. Benjamini–Hochberg | Lucky cells promoted to findings | FDR control across all gap cells | `scripts/bh_correction.py` | Benjamini–Hochberg 1995 |
| 8. Walk-forward + determinism | Temporal leakage; irreproducible randomness | Train-past/test-future, read-once; seeded samplers | `ty2022–24` snapshots; `test_determinism.py` | Bergmeir–Benítez 2012 |
| 9. Hash-frozen provenance + adverse disclosure | Silent revision; file-drawer bias | SHA-256 manifest in CI; adverse snapshots committed | `MANIFEST.sha256`, `part4_online` | Rosenthal 1979 |

**Suite status (verified 2026-07-12):** 188 passed, 5 skipped without the licensed raw data (202 with it); coverage 79% of `src/` with a 75% CI floor; snapshot manifest covering all 82 archived CSVs verified clean.

The through-line of all nine layers is one principle: at every fork, the design chooses the option *least* favorable to a convenient conclusion — the coherent metric over the flattering average, the locked test over the tuned one, the ceiling copula over the arguable one, the wider honest interval over the narrow naive one, the corrected significance over the lucky cell, the future-only split over the leaky one, and the complete hash-frozen record over the curated highlight reel. That asymmetry, applied consistently, is what "rigor" means here.
