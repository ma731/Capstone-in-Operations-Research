# The Price of Sophistication: when do spatial and robust models pay in carbon-aware data-center scheduling?

A working day-ahead migration scheduler, and an honest accounting of what each extra
layer of modelling sophistication actually buys.

**Research Capstone in Operations Research · IE School of Science & Technology · 2026**
**Student:** Marco Ortiz Togashi · **Supervisor:** Prof. Bissan Ghaddar

---

## The finding (TL;DR)

Carbon-aware schedulers shift compute toward cleaner hours and regions. Building on
single-region carbon DRO (Hall et al. 2024), this project asks a value-first question:
once you have a working scheduler, **which extra layer of sophistication is worth its
price** — active inter-region migration, a richer joint dependence model, or
distributional robustness?

The answer separates a lever that pays from two that mostly do not:

- **The lever (RQ1) — active migration pays.** Letting compute move *between* regions
  cuts out-of-sample $\mathrm{CVaR}_{0.95}$ by **4.0–9.9%** over a no-transfer
  $\Phi=0$ baseline (Western **4.0%**, Eastern **9.9%**, Diversified **9.0%**). This is
  the spatial value, and it comes from exploiting the diurnal mean carbon field across
  regions, not from a fancier dependence model.
- **The screening rule (RQ2) — passive covariance adds ≈0.** Across three US/Canada
  grids spanning the full dependence spectrum, modelling the joint *covariance* adds no
  robust scheduling value, and neither does a Gaussian, lower-tail Clayton, or even the
  maximal comonotone **copula**. A small **mean-dominance theorem** (an a-priori bound
  on the spatial gap) explains why: the covariance signal is *real* (worth up to +1.46%
  in a mean-flattened world) but *dominated* by the mean field, and the residual
  dependence is *non-elliptical* (upper-tail-independent, $\chi_L>\chi_U$), invisible to
  a covariance ball by construction.
- **The price of robustness (RQ3) — pays only past a crossover real grids don't reach.**
  Distributional robustness hedges day-ahead forecast error and begins to pay only above
  an emergency-severity crossover $M^\star\approx3$; data-grounded worst-tail emergencies
  across 17 zones reach only $M\approx1.4$, so on observed conditions the deterministic
  transfer scheduler is dominant.

The practical recommendation: a per-region marginal scheduler plus an **active
inter-region transfer channel** captures the value; a richer dependence model and a
robust layer are conditional options, not free wins.

Deliverables: `thesis/capstone_thesis.pdf` (the report), the A0 conference poster
(latest `poster/poster_capstone_v*.pdf`), and the defense slide deck
(`deck/capstone_defense.pptx`).

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
  (`src/models/algorithm_2b_mahalanobis.py`).
- **Falsification:** the *shuffled-marginals* test, fit the schedule on the joint
  covariance vs. a block-diagonal one with all cross-region structure destroyed, and
  compare out-of-sample $\mathrm{CVaR}_{0.95}$. Pre-registered: commit-lock →
  dry-run → single test read on 2025.
- **Phase 2:** copula schedulers (independence / Gaussian / Clayton / comonotone)
  via a CVaR sample-average LP over the same feasible set
  (`src/models/cvar_saa.py`, `src/models/copula_scenarios.py`).
- **Robustness:** Ledoit–Wolf shrinkage, seasonal & AR(1) residualization,
  Benjamini–Hochberg correction, walk-forward to 2024, tighter-ramp and
  utilization (50–95%) sensitivities, statistical-power (MDE) analysis.

## Reproduce the experiments

```bash
# Phase 1 shuffled-marginals (a region set; flags select estimator / ablation / etc.)
python -m scripts.run_case_experiment --region-set us_west
python -m scripts.run_case_experiment --region-set taskc --shrinkage
python -m scripts.run_case_experiment --region-set us_hetero --ablate-mean flat
python -m scripts.run_case_experiment --region-set taskc --ramp-mw 5        # tight ramp
python -m scripts.run_case_experiment --region-set taskc --utilization 0.95 # tight util

# Phase 2 copula schedulers
python -m scripts.run_copula_experiment --region-set us_west

# Figures (write to figures/, gitignored)
python -m scripts.plot_carbon_correlation --region-set us_west
python -m scripts.plot_finding
python -m scripts.plot_copula
python -m scripts.plot_robustness
```

Every number in the thesis traces to an archived summary table in
`docs/results_snapshots/` (license-safe derived statistics; see the finding figures
generated under `figures/`).

## Project structure

```
├── src/
│   ├── data/            # Electricity Maps ingestion, CFE capacity, temperature
│   ├── models/          # algorithm_1 (det. baseline), algorithm_2b (Mahalanobis DRO),
│   │                    #   feasible_set (shared X), cvar_saa, copula_scenarios,
│   │                    #   transfer_dro (Part 3), covariance
│   └── analysis/        # stratified_correlations, tail_dependence, metrics, plots
├── scripts/             # experiment runners + plotting (see docs/DEPRECATED.md for status)
├── tests/               # 194 pytest unit tests (CI on push/PR)
├── thesis/              # capstone_thesis.{tex,pdf} (the report)
├── poster/              # A0 conference poster (build_v*.js -> poster_capstone_v*.pdf)
├── deck/                # capstone_defense.pptx (defense deck) + build_deck.py
├── full_thesis/         # extended write-up (full_thesis.pdf, Parts 3-5 in body)
├── docs/
│   ├── decisions.md             # design-decision log
│   ├── results_snapshots/       # archived summary CSVs (license-safe)
│   ├── proposal_transfer_channel.md   # Part 3 (transfer DRO) proposal
│   ├── progress_note_v*.md      # phase history (v16 = Phase 2 close-out)
│   └── DEPRECATED.md            # which scripts are canonical / superseded
├── data/raw/            # Electricity Maps CSVs (gitignored, non-redistributable)
└── figures/             # generated plots (gitignored; embed into the committed PDFs)
```

## Setup

```bash
# uv (recommended)
uv venv && uv pip install -e ".[dev]"
# or: python -m venv .venv && pip install -e ".[dev]"

cp .env.example .env        # add ELECTRICITY_MAPS_TOKEN
pytest tests/               # 194 tests should pass
```

**Solvers:** HiGHS (LP / CVaR-SAA) and CLARABEL/ECOS/SCS (SOCP), all free and in the
dev extras. Gurobi is *not* required.

**Data licence:** carbon intensity is from Electricity Maps under a
**non-redistributable academic licence**. Raw CSVs live in `data/raw/`
(gitignored) and are **never committed**; only derived aggregate statistics are
archived. Do not redistribute the raw data.

## Status

- **Capstone report (`thesis/capstone_thesis.pdf`):** complete. The body develops the
  day-ahead migration scheduler and its 4.0–9.9% savings (RQ1), the screening rule for
  passive covariance and the mean-dominance bound (RQ2), and the price of robustness with
  its $M^\star\approx3$ crossover (RQ3); the richer dependence models (copulas) are
  confirmed in an appendix.
- **Extended thesis (`full_thesis/full_thesis.pdf`):** a longer, non-page-limited
  version that develops all five parts in the body and stress-tests them.
  - **Part 3 (active transfer):** inter-region flows cut out-of-sample CVaR by
    4.0--9.9% *deterministically* (by exploiting the spatial mean). A tail-risk
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
- Aas et al. 2009; Dißmann et al. 2013; Czado 2019, vine copulas
- Fan, Ji & Lejeune 2024, copula-ambiguity Wasserstein DRO

## License

Not yet licensed. Decide with the supervisor before any external publication.
The repository is private pending submission/defense.
