# The Price of Sophistication: when do spatial and robust models pay in carbon-aware data-center scheduling?

A working day-ahead migration scheduler, and an honest accounting of what each extra
layer of modelling sophistication actually buys.

**Research Capstone in Operations Research · IE School of Science & Technology · 2026**
**Student:** Marco Ortiz Togashi · **Supervisor:** Prof. Bissan Ghaddar

`194 passing unit tests` · `Python ≥ 3.10` · `free solvers only (no Gurobi needed)` · `every reported number traces to an archived snapshot`

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
  Data-grounded worst-tail emergencies across 17 zones reach only $M\approx1.4$, so on
  observed conditions the deterministic transfer scheduler is dominant. Under multi-seed
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
| **RQ3** | Does hedging forecast error with DRO pay over the plain scheduler, and do real grids reach that regime? | Only above a severity crossover near a tripling that real grids never reach (about 1.4x) | a conditional option, not a free win |

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
  compare out-of-sample $\mathrm{CVaR}_{0.95}$. Pre-registered: commit-lock,
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
| RQ3 real worst-tail emergency severity (17 zones) | median $M\approx1.43$ | `carbon_ceiling_2026-06-24.csv` |
| RQ3 robustness crossover | first material, significant robust gain at $M\approx3$ | `part3_emergency_2026-06-15.csv` |

## Reproduce the experiments

The fastest check needs no API token and no license:

```bash
pytest tests/ -q
# expected: 194 passed in roughly 20s. A handful of benign CVXPY
# "Defaulting to the SCIPY backend" warnings from the 3-D transfer
# variable are expected and harmless.
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

For byte-identical reported digits, install the pinned versions in
`requirements-lock.txt`; a plain `pip install -e .` reaches the same conclusions but the
last digits can shift if a different solver build is selected.

## Project structure

```
├── src/
│   ├── data/            # Electricity Maps ingestion, CFE capacity, temperature
│   ├── models/          # algorithm_1 (det. baseline), algorithm_2b (Mahalanobis DRO),
│   │                    #   feasible_set (shared X), cvar_saa, copula_scenarios,
│   │                    #   transfer_dro (Part 3), online_transfer (Part 4), covariance
│   └── analysis/        # stratified_correlations, tail_dependence, metrics, plots
├── scripts/             # experiment runners + plotting (see docs/DEPRECATED.md for status)
├── tests/               # 194 pytest unit tests (CI on push/PR)
├── thesis/              # capstone_thesis.{tex,pdf} (the graded report)
├── full_thesis/         # extended write-up (full_thesis.pdf, Parts 3-5 in body)
├── poster/              # A0 conference poster (build_v*.js -> poster_capstone_v*.pdf; v24 canonical)
├── deck/                # capstone_defense.pptx (defense deck; built by scripts/build_deck.py)
├── docs/
│   ├── decisions.md             # design-decision log
│   ├── results_snapshots/       # archived summary CSVs (license-safe; every number traces here)
│   ├── proposal_transfer_channel.md   # Part 3 (transfer DRO) proposal
│   ├── progress_note_v*.md      # phase history (v16 = Phase 2 close-out)
│   ├── HANDOFF.md / thesis_split.md   # orientation + content split
│   └── DEPRECATED.md            # which scripts are canonical / superseded
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
pytest tests/               # 194 tests should pass
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
  beat the plain plan; real emergencies across 17 zones only reach about $M=1.4$.
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
- **Code:** 194 unit tests, CI on push/PR; every reported number traces to an
  archived, license-safe snapshot in `docs/results_snapshots/`.

## Key references

- Hall et al. 2024, Wasserstein DRO for carbon-aware scheduling, [arXiv:2410.21510](https://arxiv.org/abs/2410.21510)
- Wijayawardana & Chien 2025, variable-capacity datacenter scheduling, SoCC '25
- Mohajerin Esfahani & Kuhn 2018, Wasserstein DRO, *Math. Program.* 171
- Rockafellar & Uryasev 2000, CVaR optimization, *J. Risk* 2(3)
- Bertsimas & Sim 2004, the price of robustness, *Oper. Res.* 52(1)
- Aas et al. 2009; Dißmann et al. 2013; Czado 2019, vine copulas
- Fan, Ji & Lejeune 2024, copula-ambiguity Wasserstein DRO

## License

**Code:** MIT (see [`LICENSE`](LICENSE)), the source in `src/`, `scripts/`, and
`tests/` is free to use, modify, and redistribute.

This MIT grant is **scoped to the code only**. It does **not** cover:

- **The thesis text, poster, and deck** (`thesis/`, `full_thesis/`, `poster/`,
  `deck/`), © 2026 Marco Ortiz Togashi, all rights reserved pending
  submission/defense; do not redistribute without permission.
- **The carbon-intensity data**, supplied by Electricity Maps under a
  **non-redistributable academic licence**. Raw CSVs are gitignored and never
  committed; only derived aggregate statistics are archived. Do not redistribute
  the raw data.

Before any external publication of the thesis itself, confirm with the supervisor.
