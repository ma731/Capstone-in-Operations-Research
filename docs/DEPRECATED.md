# Script status index

Which experiment scripts are live, superseded, or kept as locked pre-registration
artifacts. Nothing here is deleted: pre-registered scripts are retained verbatim so
the committed configuration that produced a result can always be re-read.

## Canonical (use these)

| Script | Purpose |
|--------|---------|
| `scripts/run_case_experiment.py` | The generalized Phase 1 shuffled-marginals runner (`--region-set us_west\|taskc\|us_hetero`, `--shrinkage`, `--residualize`, `--ablate-mean`, `--test-year`, `--eps-grid`, `--ramp-mw`, `--utilization`, `--cvar-alpha`). `--cvar-alpha` sets the CVaR tail level (default 0.95 reproduces the pre-registered runs; 0.90/0.99 get a filename suffix). Supersedes all the per-case runners below. |
| `scripts/run_copula_experiment.py` | Phase 2 copula schedulers (independence / Gaussian / Clayton / comonotone). |
| `scripts/equivalence_and_bound.py` | Post-hoc examiner-review analyses from archived snapshots (no test-set re-read): per-cell TOST equivalence, numerical Proposition-1 bound, and joint-vs-shuffled covariance conditioning. |
| `scripts/run_part3_transfer_value.py` | Part 3 Finding 1: active-transfer out-of-sample CVaR reduction (4.0--9.9%). |
| `scripts/run_part3_emergency.py` | Part 3 crossover, single-seed bootstrap. **Superseded for the thesis headline** by `run_parts34_stability.py` (multi-seed): the single-seed crossovers on the weakly structured grids were scenario-seed noise. Kept for the finer M-grid only. |
| `scripts/run_part4_online.py`, `run_part5_condition.py`, `run_part5_kappa.py`, `run_parts34_stability.py` | Parts 4--5 experiments and the Parts 3--4 multi-seed stability run. |
| `scripts/calibrate_capacity.py` | Goldilocks calibration of the 3c capacity bounds. |
| `scripts/measure_complexity.py` | Solve-time / problem-dimension reporting. |
| `src/models/transfer_dro.py` | Part 3 canonical module (one-shot transfer DRO, two-stage commit, recourse). Tested in `tests/test_transfer_dro.py`. Supersedes the `scripts/prototype_*transfer*.py` and `run_transfer_experiment.py` prototypes (which produced the Appendix B numbers and are kept for provenance). |

## Locked pre-registration artifacts (keep, do not edit or delete)

| Script | Why kept |
|--------|----------|
| `scripts/run_shuffled_marginals_taskc_experiment.py` | The commit-locked Task C run; its config is the pre-registration of record. Reproduced by `run_case_experiment.py --region-set taskc`. |
| `scripts/run_shuffled_marginals_taskA_experiment.py` | The locked Task A (California/Nevada) run. |
| `scripts/calibrate_taskA_regimes.py`, `scripts/calibrate_es_pt_fr_regimes.py` | Per-panel regime calibrations referenced in `docs/decisions.md`. |
| `scripts/toy_validation*.py` | Standalone supervisor-meeting demos (self-contained; do not import project algorithms). |

## Superseded (retained for history; prefer the canonical runner)

| Script | Replaced by |
|--------|-------------|
| `scripts/run_shuffled_marginals_experiment.py` | `run_case_experiment.py` (was the Task A utilization-sweep harness). |
| `scripts/run_shuffled_marginals_components_experiment.py` | `run_case_experiment.py`. |
| `scripts/run_shuffled_marginals_es_pt_fr_experiment.py` | `run_case_experiment.py` (Iberia panel). |
