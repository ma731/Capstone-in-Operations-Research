# The Price of Sophistication: a pre-committed falsification test for when spatial and robust modelling pay in carbon-aware data-center scheduling

A working day-ahead migration scheduler, and an honest accounting of what each extra
layer of modelling sophistication actually buys.

**Research Capstone in Operations Research · IE School of Science & Technology · 2026**
**Student:** Marco Ortiz Togashi · **Supervisor:** Prof. Bissan Ghaddar

`223 tests collected (210 in public CI)` · `Python ≥ 3.10` · `free solvers only (no Gurobi needed)` · `every reported number traces to an archived snapshot`

---

## In one paragraph (plain words)

Data centers run a lot of flexible work (model training, batch jobs) that can wait a few
hours or run in a different region. Electricity is "cleaner" at some hours and places than
others, because wind, solar, and hydro come and go. A carbon-aware scheduler moves compute
toward the clean hours and clean regions to cut emissions. The interesting question here is
not "can we do this" (the field already does it at production scale), it is **how fancy the
model needs to be**. This project builds a real day-ahead scheduler and then prices three
optional layers of sophistication, one at a time:

1. letting jobs migrate between regions,
2. modelling how regions' carbon levels move together (covariance and copulas),
3. hedging against forecast error with distributionally robust optimization (DRO).

The result is a clean separation: **one layer pays, two mostly do not.** Any unfamiliar term
below is defined in the [glossary](#glossary-plain-english) near the bottom.

---

## The finding (TL;DR)

Carbon-aware schedulers shift compute toward cleaner hours and regions. Building on
single-region carbon DRO (Hall et al. 2024), this project asks a value-first question:
once you have a working scheduler, **which extra layer of sophistication is worth its
price**, active inter-region migration, a richer joint dependence model, or distributional
robustness?

The answer separates a lever that pays from two that mostly do not:

- **The lever (RQ1): active migration pays.** Letting compute move *between* regions
  cuts out-of-sample $\mathrm{CVaR}_{0.95}$ by **4.0–9.9%** over a no-transfer
  $\Phi=0$ baseline (Western **4.0%**, Eastern **9.9%**, Diversified **9.0%**). This value
  comes from exploiting the diurnal mean carbon field across regions, not from a fancier
  dependence model. The migration mechanism itself is established carbon-aware practice; the
  contribution is the honest $\Phi=0$-anchored measurement of what it buys.
- **The screening rule (RQ2): passive covariance adds about zero.** Across three US/Canada
  grids spanning the full dependence spectrum, modelling the joint *covariance* adds no
  robust scheduling value, and neither does a Gaussian, lower-tail Clayton, or even the
  maximal comonotone **copula**. A **mean-dominance** argument explains why: the covariance
  signal is *real* (worth up to +1.46% in a mean-flattened world) but *dominated* by the mean
  field, and the residual dependence is *non-elliptical* (upper-tail-independent,
  $\chi_L>\chi_U$), invisible to a covariance ball by construction. Proposition 1 gives an
  a-priori bound on this gap, but on the real grids it is a conservative certificate rather
  than a tight prediction; the mean-ablation and the comonotone-copula ceiling are what
  establish the null empirically.
- **The price of robustness (RQ3): pays only past a crossover real grids do not reach.**
  Distributional robustness hedges day-ahead forecast error and begins to pay only above an
  emergency-severity crossover $M^\star\approx3$ (where $M$ is the multiple by which a
  region's carbon intensity spikes in a rare grid emergency, so $M=3$ is a tripling).
  Data-grounded joint-grid severities are $M=1.29$--$1.89$, below the material crossover,
  so on observed conditions the deterministic transfer scheduler is dominant. Individual
  very-low-carbon zones can have larger ratios, which is why the comparison is made on the
  same joint portfolio axis as the scheduler. Under multi-seed
  testing the crossover itself survives on the Western grid only, and there only marginally,
  so RQ3 is reported as a tested decision rule, not a universal threshold.

The practical recommendation: a per-region marginal scheduler plus an **active
inter-region transfer channel** captures the value; a richer dependence model and a
robust layer are conditional options, not free wins.

## Research questions at a glance

| | Question (plain words) | Answer | Verdict |
|---|---|---|---|
| **RQ1** | Does letting jobs move between regions cut worst-day emissions, and what drives the saving? | Yes, 4.0–9.9% over a like-for-like no-transfer baseline; the driver is the average carbon field, not dependence | the lever that pays |
| **RQ2** | Does modelling how regions co-move (covariance, copulas) improve worst-day emissions? | No, the gap stays below 0.4% of CVaR and survives a full robustness battery | a screening rule for when to skip it |
| **RQ3** | Does hedging forecast error with DRO pay over the plain scheduler, and do real grids reach that regime? | Only above a severity crossover near a tripling; realized joint-grid severity is 1.29x--1.89x | a conditional option, not a free win |

## The three grids

| Display name | Internal key | Zones | Character |
|---|---|---|---|
| **Western US** | `us_west` | CISO, BANC, LDWP, NEVP, AZPS | strongly correlated (WECC) |
| **Eastern US–Canada** | `taskc` | CA-ON, NYISO, MISO, PJM | strongly correlated (Eastern Interconnection) |
| **Diversified** | `us_hetero` | CISO (solar), ERCOT (wind), BPAT (hydro) | engineered near-uncorrelated (adversarial best case) |

Corroborated by a California–Nevada subset (`taskA`) and an Iberia–France panel
(`es_pt_fr`) at the low-correlation end.

## Method

- **Model:** Mahalanobis–Wasserstein DRO, $\min\langle\bar\rho,x\rangle +
  \varepsilon\lVert L^\top x\rVert_2$, solved as a second-order cone program
  (`src/models/algorithm_2b_mahalanobis.py`). A single shared feasible set
  (`src/models/feasible_set.py`) is used by every scheduler, so any difference in the
  schedule is attributable to the objective and nothing else.
- **Falsification:** the *shuffled-marginals* test, fit the schedule on the joint
  covariance vs. a block-diagonal one with all cross-region structure destroyed, and
  compare out-of-sample $\mathrm{CVaR}_{0.95}$. Pre-committed: commit-lock,
  then dry-run, then a single test read on 2025.
- **Transfer lever (Part 3):** inter-region load flows let compute migrate
  (`src/models/transfer_dro.py`); executed load is conserved by construction, and a
  transfer budget $\Phi$ bounds relocation. $\Phi=0$ is the honest no-transfer baseline.
- **Phase 2:** copula schedulers (independence / Gaussian / Clayton / comonotone)
  via a CVaR sample-average LP over the same feasible set
  (`src/models/cvar_saa.py`, `src/models/copula_scenarios.py`).
- **Robustness battery:** Ledoit–Wolf shrinkage, seasonal & AR(1) residualization,
  Benjamini–Hochberg correction, walk-forward to 2024, tighter-ramp and
  utilization (50–95%) sensitivities, a statistical-power (MDE) analysis, and a per-cell
  TOST equivalence test that turns "we found nothing" into the affirmative claim "any
  effect above the 0.4% materiality margin is ruled out."

## Headline numbers and where they come from

Every number in the thesis traces to an archived, license-safe summary CSV under
`docs/results_snapshots/` (derived aggregate statistics only, never the raw licensed data).
The three headline numbers:

| Claim | Value | Snapshot |
|---|---|---|
| RQ1 transfer lever (OOS $\mathrm{CVaR}_{0.95}$ reduction over $\Phi=0$) | Western 4.04%, Eastern 9.91%, Diversified 9.04% | `part3_transfer_value_2026-06-15.csv` (plateau corroborated by `transfer_value_curve_2026-06-24.csv`) |
| RQ3 real worst-tail emergency severity (17 zones) | per-zone median $M\approx1.43$; joint grids $M=1.29$--$1.89$ | `carbon_ceiling_2026-06-24.csv` |
| RQ3 robustness crossover | first material, significant robust gain at $M\approx3$ | `part3_emergency_2026-06-15.csv` |

A full slide-by-slide provenance map for the defense deck (every number → archived CSV →
figure script) is in [`docs/deck_provenance.md`](docs/deck_provenance.md); a short list of
known slide-label corrections is in [`docs/deck_errata.md`](docs/deck_errata.md).

## Future work (in progress)

The capstone is graded and frozen at the thesis pin; the repo now moves toward
publication. The full plan (directions, venues, timing) is in
[`docs/roadmap_papers.md`](docs/roadmap_papers.md). Three directions are active on the
`paper-expansion` branch, all additive (no graded result is touched):

1. **Signal robustness: does the null survive a marginal-emissions signal?**
   The whole study runs on *average* carbon intensity. The field is split on
   average vs. marginal signals (e-Energy'24 shows they produce conflicting
   schedules), so replicating the Phase 1 falsification under a marginal signal
   tests whether the dependence null is signal-specific or fundamental. Status:
   loader + pre-registered protocol scaffolded
   ([`docs/protocols/marginal_signal_protocol.md`](docs/protocols/marginal_signal_protocol.md));
   blocked on marginal data access (WattTime or Electricity Maps premium).
2. **State-conditional robustness: a contextual price-of-robustness.** RQ3 says
   unconditional DRO does not pay below $M^\star\approx3$. The conditional question:
   are high-severity days *predictable* from covariates known day-ahead
   (temperature, lagged carbon, calendar), so a scheduler can exercise robustness
   as an option only when the predicted regime warrants it? Status: gating
   prototype (`scripts/prototype_contextual_gate.py`) quantifies day-ahead
   predictability of high-severity days on the two locally-cached panels.
3. **Calibrated emergency severity via extreme value theory.** The $M^\star$
   crossover currently uses a stylised multiplier plus empirical top-5% pools
   (`run_part3_real_emergency.py`). The EVT upgrade fits a generalized Pareto tail
   to realized joint-severity ratios and reports return periods for
   $M \ge 2, 2.5, 3$: "a crossover-grade day is a 1-in-$N$-year event," anchored
   on real events (the 2022 French nuclear outage is in the panel). Status:
   `src/analysis/severity_evt.py` + `scripts/run_severity_evt.py`, snapshot under
   `docs/results_snapshots/`.

Target venues: ACM e-Energy 2027 (fall cycle) for the compressed RQ1+RQ2 paper with
direction 1; e-Energy winter cycle / SoCC for directions 2+3; an OR journal (with
supervisor) for the Part 5 screening condition; HotCarbon 2027 as the position-paper
staging ground. The new modules carry their own unit tests under the same discipline:
the suite grew from 202 to 223 collected tests (189 to 210 in CI) with these additions.

## Reproduce the experiments

The fastest check needs no API token and no license:

```bash
pytest tests/ -q
# expected without licensed raw data / optional phase-2 extras: 223 collected,
# with the corresponding integration tests skipped (currently 205 passed, 18 skipped).
```

The experiments themselves:

```bash
# Phase 1 shuffled-marginals (a region set; flags select estimator / ablation / etc.)
python -m scripts.run_case_experiment --region-set us_west
python -m scripts.run_case_experiment --region-set taskc --shrinkage
python -m scripts.run_case_experiment --region-set us_hetero --ablate-mean flat
python -m scripts.run_case_experiment --region-set taskc --ramp-mw 5        # tight ramp
python -m scripts.run_case_experiment --region-set taskc --utilization 0.95 # tight util

# Phase 2 copula schedulers
python -m scripts.run_copula_experiment --region-set us_west

# Part 3 transfer lever and the price-of-robustness crossover
python -m scripts.run_part3_transfer_value
python -m scripts.run_part3_emergency

# Figures (write to figures/, mostly gitignored)
python -m scripts.plot_carbon_correlation --region-set us_west
python -m scripts.plot_finding
python -m scripts.plot_copula
python -m scripts.plot_robustness
```

For the fully resolved environment, use the tracked `uv.lock` (`uv sync --frozen
--extra dev`). `constraints-numerics.txt` records the validated numerical and solver
versions used for the reported runs. Reproduction is judged against the archived
rounded values and declared tolerances; last digits can vary across platforms or
solver builds.

## Project structure

```
├── src/
│   ├── data/            # Electricity Maps ingestion, CFE capacity, temperature
│   ├── models/          # algorithm_1 (det. baseline), algorithm_2b (Mahalanobis DRO),
│   │                    #   feasible_set (shared X), cvar_saa, copula_scenarios,
│   │                    #   transfer_dro (Part 3), online_transfer (Part 4), covariance
│   └── analysis/        # stratified_correlations, tail_dependence, metrics, plots
├── scripts/             # experiment runners + plotting
├── tests/               # 223 pytest tests collected; 210 collected in CI
├── thesis/              # capstone_thesis.{tex,pdf} (the graded report)
├── full_thesis/         # extended write-up (full_thesis.pdf, Parts 3-5 in body)
├── poster/              # A0 poster (build_v24.js -> .pptx; PDF exported from it)
├── deck/                # capstone_defense.pptx (defense deck; built by scripts/build_deck.py)
├── docs/
│   ├── results_snapshots/       # archived summary CSVs (license-safe; every number traces here)
│   ├── snippets/                # paste-ready table/figure LaTeX snippets
│   └── stratified_results.txt   # stratified-correlation results dump
├── data/raw/            # carbon CSVs (Electricity Maps, gitignored); temperature CSVs (Open-Meteo ERA5, committed, CC-BY)
└── figures/             # generated plots, mostly gitignored; a few static figures
                         #   (correlation_by_hour/season, the IE logo) committed for the PDFs
```

## Which file is the deliverable

The repo carries several write-ups and formats. The canonical ones:

| Artifact | Path | What it is |
|---|---|---|
| **Capstone report (graded)** | `thesis/capstone_thesis.pdf` | the 30-page report, the primary deliverable |
| Extended thesis | `full_thesis/full_thesis.pdf` | longer, non-page-limited version developing Parts 3 to 5 in the body |
| A0 poster | `poster/poster_capstone_v24.pdf` | canonical conference poster (v24) |
| Defense deck | `deck/capstone_defense.pptx` | presentation slides, built by `scripts/build_deck.py` |

Other files under `thesis/` (`paper_twocolumn`, `poster_a0`, `phase1_results`,
`status_report`) are legacy or alternate-format outputs kept for history; they are not the
graded deliverable.

## Setup

```bash
# uv (recommended)
uv venv && uv pip install -e ".[dev]"
# or: python -m venv .venv && pip install -e ".[dev]"

cp .env.example .env        # add ELECTRICITY_MAPS_TOKEN (only needed to re-fetch raw data)
pytest tests/               # 223 collected; data/optional-dependency tests may skip
```

**Solvers (all free, all in the default install):** HiGHS for the LP and CVaR-SAA
schedulers, CLARABEL / SCS for the SOCP. Gurobi is **not** required; it is an optional
comparison arm only, available via the `gurobi` extra (`pip install -e ".[gurobi]"`).

**Data licence:** carbon intensity is from Electricity Maps under a
**non-redistributable academic licence**; its raw CSVs live in `data/raw/` and are
**gitignored, never committed** (only derived aggregate statistics are archived). The
Open-Meteo ERA5 temperature CSVs under `data/raw/temperature/` are CC-BY and *are*
committed. Do not redistribute the Electricity Maps data.

## Glossary (plain English)

Short version of the heavy jargon. The thesis carries a fuller glossary in an appendix
(`\label{app:glossary}`).

- **Carbon intensity:** how dirty the electricity is right now (grams of CO2 per kWh). It
  swings hour by hour and region by region with wind, solar, and hydro.
- **Carbon-aware scheduling:** deciding when and where to run flexible jobs so they land in
  the cleanest hours and regions.
- **Day-ahead:** committing tomorrow's plan today, using a forecast, because you cannot wait
  for each hour to arrive.
- **CVaR (and $\mathrm{CVaR}_{0.95}$):** "how bad are the bad days." $\mathrm{CVaR}_{0.95}$
  is the average emissions across the worst 5% of days, not the average over all days.
- **DRO (distributionally robust optimization):** instead of trusting one forecast,
  optimize against the worst plausible forecast in a whole cloud of them. Like packing for
  weather a bit worse than predicted.
- **Wasserstein ball (radius $\varepsilon$):** the cloud of plausible futures, all
  distributions within distance $\varepsilon$ of the data. $\varepsilon=0$ trusts the data
  exactly; larger $\varepsilon$ is more cautious.
- **Mahalanobis distance:** a distance that accounts for how regions move together (via the
  covariance), so two correlated regions count as closer.
- **SOCP (second-order cone program):** a well-behaved convex problem that solvers crack
  fast and to guaranteed optimality. The robust objective reduces to one.
- **Copula:** the part of a joint distribution that captures only how variables move
  together, with each variable's own behaviour stripped out.
- **Comonotone copula:** the most extreme coupling, all regions rising and falling in
  perfect lockstep. Used as a worst-case ceiling: if even perfect synchrony adds nothing,
  nothing weaker will.
- **Tail dependence ($\chi_L$ vs $\chi_U$):** whether regions hit their extremes together.
  Here $\chi_L>\chi_U$ means they sync up when clean but decouple when dirty, an effect plain
  correlation cannot see.
- **Mean-dominance:** the central screening result: the swing in average carbon dwarfs the
  cross-region dependence, so any covariance or copula model can move the schedule only by a
  provably tiny amount.
- **Shuffled-marginals test:** the falsification experiment, fit the scheduler twice, once
  with real cross-region links and once with those links destroyed but each region's own
  pattern intact, then compare worst-day emissions. The difference is the value of spatial
  correlation.
- **Severity $M$ and crossover $M^\star$:** $M$ is how many times worse carbon spikes in a
  rare emergency ($M=3$ is a tripling). $M^\star\approx3$ is where the robust layer starts to
  beat the plain plan. The 17-zone per-zone median is $M\approx1.43$; on the comparable
  joint-grid axis, realized severity is $M=1.29$--$1.89$.
- **Transfer budget $\Phi$:** the dial for how much compute may migrate between regions.
  $\Phi=0$ is the honest no-transfer baseline; turning it up delivers the 4.0–9.9% saving.
  "Logical" migration means jobs move over the network between the operator's own sites, the
  power grids need not be physically connected.

## Status

- **Capstone report (`thesis/capstone_thesis.pdf`):** complete. The body develops the
  day-ahead migration scheduler and its 4.0–9.9% savings (RQ1), the screening rule for
  passive covariance and the mean-dominance bound (RQ2), and the price of robustness with
  its $M^\star\approx3$ crossover (RQ3); the richer dependence models (copulas) are
  confirmed in an appendix.
- **Extended thesis (`full_thesis/full_thesis.pdf`):** a longer, non-page-limited
  version that develops all five parts in the body and stress-tests them.
  - **Part 3 (active transfer):** inter-region flows cut out-of-sample CVaR by
    4.0–9.9% *deterministically* (by exploiting the spatial mean). A tail-risk
    crossover appears only under *synthetic* over-stress and **does not survive
    data-grounded emergencies**, so robustifying the transfer pays nowhere
    data-grounded.
  - **Part 4 (online):** a rolling-horizon controller. Robustness is immaterial under
    forecast error (its sign flips with the forecast) and counterproductive on the
    structureless grid.
  - **Part 5 (theory):** a dimensionless mean-dominance ratio that screens when
    cross-coordinate dependence can ever matter (ordinal on these grids).

  The uniform-rigor pass (multi-seed stability, equivalence tests, an independent
  adversarial review) made the findings *more conservative, not larger*: the value
  concentrates in the deterministic transfer lever, with the dependence and robust
  layers priced as conditional rather than free.
- **Code:** 202 tests collected (189 in public CI), CI on push/PR; every reported number traces
  to an archived, license-safe snapshot in `docs/results_snapshots/`.

### What validation proves

Validation is organised as an evidence chain rather than a single “tests passed” claim:

`source and configuration → model invariants → numerical behaviour → archived results → public claims`

Each link is checked separately. This matters because a correct optimizer can still be
fed the wrong data, a statistically sound experiment can still be quoted incorrectly,
and a correct README can still point to a missing or stale artifact. No single unit test
can detect all of those failure modes.

#### The two automated CI gates

Every push and pull request must pass two ordered jobs in
`.github/workflows/test.yml`:

1. **Repository validation.** Python first compiles every source, script, and test file.
   It then runs `python -m scripts.validate_repository`. A failure stops the workflow,
   so the numerical suite is not allowed to give a misleading green result when the
   repository or publication layer is inconsistent.
2. **Numerical pytest suite.** After the first gate passes, CI installs the declared
   project and solver dependencies and runs 189 data-independent tests. In the current
   validated run, 184 passed and five were expected skips. The complete suite collects
   202 tests; the remaining 13 exercise licensed Electricity Maps ingestion and run only
   where the authorised raw files are available.

The 189 public-CI tests deliberately cover different kinds of evidence:

| Validation target | Representative tests | What a failure would reveal |
|---|---|---|
| Optimizer and reformulation correctness | `test_algorithm_1.py`, `test_algorithm_2a.py`, `test_algorithm_2b_mahalanobis.py` | Objective, ambiguity-set, solver, or reformulation behaviour no longer matches the intended model. |
| Feasibility and physical constraints | `test_constraints_taskA.py`, `test_capacity.py`, `test_carbon_budget.py` | A schedule violates workload conservation, capacity, ramping, transfer, or carbon-budget assumptions. |
| Dependence and tail analysis | `test_covariance.py`, `test_stratified_correlations.py`, `test_tail_dependence.py`, `test_phase2_copula.py` | Covariance, stratification, copula, or tail-dependence calculations have changed or become internally inconsistent. |
| Transfer and robustness mechanisms | `test_transfer_dro.py`, `test_online_transfer.py`, `test_emergency_inject.py`, `test_part5_condition.py` | The active-transfer lever, online comparison, severity stress test, or mean-dominance condition no longer behaves as claimed. |
| Claim and result binding | `test_claim_binding.py`, `test_carbon_ceiling_snapshot.py`, `test_risk_measure_swap_snapshot.py` | A reported headline, severity bound, or robustness result has drifted away from its committed result table. |
| Data interfaces and derived inputs | `test_temperature.py`, `test_es_pt_fr.py`, plus the licensed `test_electricitymaps.py` | Parsing, alignment, units, region mapping, or expected data coverage is broken. |

This mix is stronger than relying only on end-to-end regression numbers. Invariant and
feasibility tests can identify *why* an implementation is wrong; synthetic positive
controls check that the pipeline can detect a signal when one is deliberately inserted;
and snapshot tests catch later changes to the specific quantities used in the thesis.

#### What `scripts/validate_repository.py` does

This small fail-fast validator covers publication and provenance risks that ordinary
model tests do not address:

- `_check_required_files()` requires the canonical thesis, extended thesis, poster,
  deck, licence files, dependency lock, and headline result snapshots. A release cannot
  silently omit the artifact that the README describes.
- `_check_public_links()` resolves local Markdown links and HTML image sources, catching
  broken public navigation and missing explainer graphics.
- `_check_headline_snapshots()` reads the committed CSVs and checks the RQ1 transfer
  reductions (4.04%, 9.91%, and 9.04%) and the RQ3 joint-severity values (1.34, 1.29,
  and 1.89). It then checks that the README states the same values. This binds the
  narrative to archived machine-readable evidence instead of duplicated prose alone.
- `_check_document_dates()` protects the fixed June 2026 dates in all three manuscript
  sources from accidental regeneration changes.
- `_check_tex_assets_and_public_privacy()` parses every `\\includegraphics` reference in
  the thesis sources, requires the referenced file to exist in a clean checkout, and
  prevents the handwritten signature from reappearing in the public copy.
- `_check_project_metadata()` parses `pyproject.toml`, requires every documented default
  solver to be declared, and verifies that the canonical poster sources and exports are
  not accidentally hidden by `.gitignore`.

The validator exits immediately with a specific error when any condition fails. That
“fail closed” design is useful for a research repository: uncertainty or missing evidence
blocks the green CI status instead of being reduced to a warning that can be overlooked.

#### How this supports the reported results

The automated gates establish that the published numbers are traceable to versioned
outputs, that the implementation still satisfies the intended mathematical and physical
constraints, and that the public documents have not drifted away from those outputs.
The study-level validation then tests whether the findings are stable rather than merely
repeatable: walk-forward out-of-sample evaluation limits look-ahead bias; multi-seed and
sensitivity runs test dependence on arbitrary settings; bootstrap confidence intervals
quantify sampling uncertainty; equivalence tests distinguish “no material effect” from
an underpowered failure to reject; and Benjamini–Hochberg correction controls the false
discovery rate across the many comparison cells. Synthetic positive controls further
show that the method is capable of finding covariance or robustness value when the data
are constructed to contain it, strengthening the interpretation of a null on the real
grids.

This is the strongest practical public-validation design for this project because it
combines independent checks at the code, model, statistics, artifact, and claim levels
while respecting the Electricity Maps licence. It is also reproducible: `uv.lock`
resolves the complete Python environment, and the derived aggregate snapshots needed to
audit the public claims are committed without redistributing the licensed observations.

#### Scope and limitation

A green public workflow is strong evidence of implementation integrity, internal
consistency, traceability, and stability; it is not, by itself, proof that the scientific
conclusions are universally true. Public CI does not independently download and recompute
the Electricity Maps observations. The 13 ingestion tests and a complete raw-to-result
reproduction require the licence-holder's local raw-data directory. Snapshot checks also
confirm agreement with archived outputs rather than independently recreating those
outputs. Stating these boundaries explicitly makes the validation more credible: another
authorised researcher can distinguish what GitHub verifies automatically from what must
be replicated with the licensed source data.

## Key references

- Hall et al. 2024, Wasserstein DRO for carbon-aware scheduling, [arXiv:2410.21510](https://arxiv.org/abs/2410.21510)
- Wijayawardana & Chien 2025, variable-capacity datacenter scheduling, SoCC '25
- Mohajerin Esfahani & Kuhn 2018, Wasserstein DRO, *Math. Program.* 171
- Rockafellar & Uryasev 2000, CVaR optimization, *J. Risk* 2(3)
- Bertsimas & Sim 2004, the price of robustness, *Oper. Res.* 52(1)
- Aas et al. 2009; Dißmann et al. 2013; Czado 2019, vine copulas
- Fan, Ji & Lejeune 2024, copula-ambiguity Wasserstein DRO

## License

**Code:** MIT (see [`LICENSES/MIT-CODE.txt`](LICENSES/MIT-CODE.txt)); the source in
`src/`, `scripts/`, and `tests/`, plus `pyproject.toml`, is free to use, modify, and
redistribute under that licence.

This MIT grant is **scoped to the code only**. It does **not** cover:

- **The thesis text, poster, and deck** (`thesis/`, `full_thesis/`, `poster/`,
  `deck/`, and `capstone_explained.html`), © 2026 Marco Ortiz Togashi, all rights reserved pending
  submission/defense; do not redistribute without permission.
- **The carbon-intensity data**, supplied by Electricity Maps under a
  **non-redistributable academic licence**. Raw CSVs are gitignored and never
  committed; only derived aggregate statistics are archived. Do not redistribute
  the raw data.

Before any external publication of the thesis itself, confirm with the supervisor.
The root [`LICENSE`](LICENSE) is the authoritative scope notice for repository content.
