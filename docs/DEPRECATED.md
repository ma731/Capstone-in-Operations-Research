# Script status index

Which experiment scripts are live, superseded, or kept as locked pre-registration
artifacts. Nothing here is deleted: pre-registered scripts are retained verbatim so
the committed configuration that produced a result can always be re-read.

## Canonical (use these)

| Script | Purpose |
|--------|---------|
| `scripts/run_case_experiment.py` | The generalized Phase 1 shuffled-marginals runner (`--region-set us_west\|taskc\|us_hetero`, `--shrinkage`, `--residualize`, `--ablate-mean`, `--test-year`, `--eps-grid`, `--ramp-mw`). Supersedes all the per-case runners below. |
| `scripts/run_copula_experiment.py` | Phase 2 copula schedulers (independence / Gaussian / Clayton / comonotone). |
| `scripts/calibrate_capacity.py` | Goldilocks calibration of the 3c capacity bounds. |
| `scripts/measure_complexity.py` | Solve-time / problem-dimension reporting. |

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
