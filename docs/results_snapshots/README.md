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
  `finegrid` = denser epsilon grid; `ty2024` = walk-forward (test year 2024).
- `bh_correction.csv` = Benjamini-Hochberg over all gap cells.

Columns: `regime, alpha, eps*_joint, eps*_shuf, joint_CVaR, shuf_CVaR, gap_pct,
gap_ci_lo, gap_ci_hi, detectable`. Positive gap = joint covariance beats shuffled.

Regenerate any of these with
`.venv\Scripts\python -m scripts.run_case_experiment --region-set <case> [flags]`.
