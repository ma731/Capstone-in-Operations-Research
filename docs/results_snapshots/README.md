# Result snapshots

Committed copies of the experiment **summary tables** that the progress notes and
thesis cite. The live `results/` directory is gitignored (it also holds large
`.pkl` schedules); these CSVs are archived here so every number in the write-ups
has a tracked source.

**License-safe:** these files contain only *derived aggregate statistics*
(CV-selected epsilon, test CVaR, spatial gaps, bootstrap CIs, BH p-values). They do
**not** contain Electricity Maps raw carbon intensity, so the non-redistribution
academic license does not apply.

## Filename key

`<case>_regimes_<date>[_<variant>].csv`

- **case:** `taskA` (CA/NV), `es_pt_fr` (Iberia), `taskc`/`us_west`/`us_hetero`
  (the three v15 cases). Lowercase `taskc` = generalized runner; `taskC` = the
  locked pre-registered Task C script (same numbers).
- **variant:** none = baseline; `seasonal`/`ar1` = residualized covariance;
  `lw` = Ledoit-Wolf shrinkage; `ablate-level`/`ablate-flat` = mean-ablation;
  `finegrid` = denser epsilon grid; `ty2024` = walk-forward (test year 2024);
  `ramp5`/`util0.5`/`util0.95` = constraint-tightness sweeps;
  `cvar0.9`/`cvar0.99` = CVaR tail-level sweep (default metric is CVaR_0.95).
- `bh_correction.csv` = Benjamini-Hochberg over all gap cells.
- `<case>_copula_<date>.csv` = **Phase 2** copula schedulers. Columns:
  `regime, alpha, cvar_indep, cvar_gauss, cvar_clayton, clayton_theta, kendall_tau,
  gap_gauss_pct, gap_clayton_pct, gap_clayton_vs_gauss_pct, detectable_*`. Gap =
  reduction in out-of-sample CVaR_0.95 vs the independence baseline (positive = the
  structured copula helps). Regenerate with
  `.venv\Scripts\python -m scripts.run_copula_experiment --region-set <case>`.

Columns: `regime, alpha, eps*_joint, eps*_shuf, joint_CVaR, shuf_CVaR, gap_pct,
gap_ci_lo, gap_ci_hi, detectable`. Positive gap = joint covariance beats shuffled.

Regenerate any of these with
`.venv\Scripts\python -m scripts.run_case_experiment --region-set <case> [flags]`.
