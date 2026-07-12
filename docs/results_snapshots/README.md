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
  locked pre-committed Task C script (same numbers).
- **variant:** none = baseline; `seasonal`/`ar1` = residualized covariance;
  `lw` = Ledoit-Wolf shrinkage; `ablate-level`/`ablate-flat` = mean-ablation;
  `finegrid` = denser epsilon grid; `ty2022`/`ty2023`/`ty2024` = walk-forward
  (train on the years before the test year, read the test year once; the spatial
  null holds in every one, max gap 0.21% of CVaR);
  `ramp5`/`util0.5`/`util0.95` = constraint-tightness sweeps;
  `cvar0.9`/`cvar0.99` = CVaR tail-level sweep (default metric is CVaR_0.95).
- `bh_correction.csv` = Benjamini-Hochberg over the pre-committed **144-cell** null
  family (4 grid-runs `taskC`/`taskc`/`us_west`/`us_hetero` x 9 regime-alpha cells x 4
  covariance estimators baseline/ar1/lw/seasonal = 144; this is the deck slide-7 scatter).
  The file also carries **54 mean-ablation positive-control** rows (`variant` in
  {`ablate-flat`, `ablate-level`}, the +1.46% instrument on deck slide 18), so it has
  144 + 54 = **198 data rows** total. BH q=0.05 is applied to the 144-cell family; the max
  |gap| among those is 0.355% (all inside the 0.4% margin), while several ablate rows
  exceed 0.4% by design.
- `<case>_copula_<date>.csv` = **Phase 2** copula schedulers. Columns:
  `regime, alpha, cvar_indep, cvar_gauss, cvar_clayton, clayton_theta, kendall_tau,
  gap_gauss_pct, gap_clayton_pct, gap_clayton_vs_gauss_pct, detectable_*`. Gap =
  reduction in out-of-sample CVaR_0.95 vs the independence baseline (positive = the
  structured copula helps). Regenerate with
  `.venv\Scripts\python -m scripts.run_copula_experiment --region-set <case>`.

Columns: `regime, alpha, eps*_joint, eps*_shuf, joint_CVaR, shuf_CVaR, gap_pct,
gap_ci_lo, gap_ci_hi, detectable`. Positive gap = joint covariance beats shuffled.

- `transfer_value_curve_<date>.csv` = **RQ1** transfer-value curve (out-of-sample
  CVaR_0.95 reduction vs the Phi=0 baseline, by transfer budget). Regenerate with
  `.venv\Scripts\python -m scripts.run_transfer_value_curve`.
- `part3_transfer_value_<date>.csv` = **RQ1** headline transfer value (CVaR vs Phi=0,
  per grid). `.venv\Scripts\python -m scripts.run_part3_transfer_value`.
- `part3_emergency_<date>.csv` / `part3_real_emergency_<date>.csv` = **RQ3** synthetic
  severity crossover M* and the data-grounded real-emergency test.
  `.venv\Scripts\python -m scripts.run_part3_emergency` / `run_part3_real_emergency`.
- `carbon_ceiling_<date>.csv` = **RQ3** realized carbon severity, per-region and joint
  (the M* reconciliation). `.venv\Scripts\python -m scripts.run_carbon_ceiling`.
- `part4_online_<date>.csv` = **RQ3** rolling online robust-vs-deterministic per grid
  (the disclosed adverse Diversified result). `.venv\Scripts\python -m scripts.run_part4_online`.
- `dro_tail_sensitivity_<date>.csv` = **RQ3** robust-vs-deterministic online gap at deeper
  tail levels (CVaR_0.90/0.95/0.99 and the worst day); confirms the null holds in the deep
  tail. `.venv\Scripts\python -m scripts.run_dro_tail_sensitivity`.
- `risk_measure_swap_<date>.csv` = **RQ2** generality probe: re-measures the
  joint-vs-shuffled gap under a **mean-variance** objective (a variance penalty that
  amplifies covariance, vs the standard-deviation penalty that dampens it), to show the
  spatial null is not an artifact of the robust scheduler's objective. Columns: `grid,
  objective, param, param_value, sched_diff_pct, cvar_gap_pct, oos_std_gap_pct,
  is_std_gap_pct, var_over_mean, boot_gap_pct, boot_lo_pct, boot_hi_pct`; `cvar_gap_pct` =
  (shuffled - joint)/joint OOS CVaR_0.95, positive = modelling covariance helps.
  `.venv\Scripts\python -m scripts.run_risk_measure_swap`.
- `block_bootstrap_<date>.csv` = **RQ2** serial-dependence check: re-bootstraps the spatial
  gap with a moving-block scheme (block length 1/7/14 days) so the worst-day clustering is
  respected. The block SE is 9-44% wider than iid, but every gap stays within the 0.4%
  materiality margin (widest bound 0.22%), so the equivalence null is not an artifact of the
  independent-day bootstrap. `.venv\Scripts\python -m scripts.run_block_bootstrap_check`.
- `tail_dependence_<date>.csv` = **RQ2 backup** upper/lower tail-dependence coefficients per
  region pair per grid, for the raw and the hour-of-day-**residual** series. Backs the deck
  slide-17 chi_L > chi_U asymmetry (e.g. residual CISO|LDWP 0.48/0.25, BANC|LDWP 0.40/0.17).
  Columns: `grid, display, series, n_obs, pair, pearson_rho, chi_U_emp, chi_U_gauss,
  chi_U_excess, chi_L_emp` (`chi_L_emp` = clean-together, `chi_U_emp` = dirty-together;
  positive `chi_U_excess` = dirty-tail co-movement a covariance ball cannot represent).
  Regenerate with `.venv\Scripts\python -m scripts.run_tail_dependence_snapshot`.
- `complexity_frontier_<date>.csv` = **RQ1/RQ2/RQ3** the complexity-value frontier (deck
  slide 6). Per grid, cumulative % emissions saved **vs a carbon-blind scheduler** as each
  modelling layer is added. The `+transfer` plateau is the measured `run_dayahead_savings`
  `save_aware` (Western 11.7, Eastern 12.5, Diversified 15.8); the flat tail encodes the
  RQ2/RQ3 nulls. Columns: `grid, display, layer_idx, layer, cumulative_saving_pct, kind,
  source` (the `kind`/`source` columns mark each point as measured / anchored-null /
  intermediate). NB the y-axis is a looser metric than the 4.0-9.9% CVaR-vs-Phi=0 headline.
  Read by `scripts/plot_complexity_frontier.py`; regenerate the plateau with
  `.venv\Scripts\python -m scripts.run_dayahead_savings`.

Regenerate any of these with
`.venv\Scripts\python -m scripts.run_case_experiment --region-set <case> [flags]`.
