# Does spatial correlation of carbon intensity improve robust data-center scheduling?

A falsification study with a causal mechanism.

**Research Capstone in Operations Research · IE School of Science & Technology · 2026**
**Student:** Marco Ortiz Togashi · **Supervisor:** Prof. Bissan Ghaddar

---

## The finding (TL;DR)

Carbon-aware schedulers shift compute toward cleaner hours and regions. A natural
extension of single-region carbon DRO (Hall et al. 2024) is to treat carbon
intensity as a stochastic **vector** across coupled regions, so that **spatial
correlation** can inform the schedule. This project asks whether that helps.

**It does not, a replicated, robustness-checked null.** Across three US/Canada
grids spanning the full dependence spectrum, the spatial covariance adds no robust
$\mathrm{CVaR}_{0.95}$ scheduling value, and neither does a Gaussian, lower-tail
Clayton, or even the maximal comonotone **copula**. Two diagnostics explain why:

- **Mean-ablation** shows the covariance signal is *real* (worth up to +1.46% in a
  mean-flattened world) but *dominated* by the diurnal mean carbon field.
- **Tail-dependence** shows the residual dependence is *non-elliptical*
  (upper-tail-independent, radially asymmetric $\chi_L>\chi_U$), invisible to a
  covariance ball by construction.

A small **mean-dominance theorem** (a-priori bound on the spatial gap) ties it
together. The practical recommendation: a per-region marginal scheduler captures
essentially all the value; spatial value, if any, must come from an *active*
inter-region transfer channel, not a richer dependence model.

Deliverables: `thesis/capstone_thesis.pdf` (the report) and `thesis/poster_a0.pdf`
(the A0 poster).

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
├── tests/               # 187 pytest unit tests (CI on push/PR)
├── thesis/              # capstone_thesis.{tex,pdf}, poster_a0.{tex,pdf}
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
pytest tests/               # 187 tests should pass
```

**Solvers:** HiGHS (LP / CVaR-SAA) and CLARABEL/ECOS/SCS (SOCP), all free and in the
dev extras. Gurobi is *not* required.

**Data licence:** carbon intensity is from Electricity Maps under a
**non-redistributable academic licence**. Raw CSVs live in `data/raw/`
(gitignored) and are **never committed**; only derived aggregate statistics are
archived. Do not redistribute the raw data.

## Status

- **Capstone report (`thesis/capstone_thesis.pdf`):** complete. Phases 1 and 2 (the
  covariance and copula nulls plus the mean-dominance bound), with Part 3 (transfer
  DRO) as a clearly fenced, preliminary appendix.
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
  adversarial review) made the findings *more conservative, not larger*: the only
  positive result is the deterministic transfer value.
- **Code:** 187 unit tests, CI on push/PR; every reported number traces to an
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
