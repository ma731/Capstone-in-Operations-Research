# Reproducibility

How to reproduce every number cited in the thesis, deck, and paper, from a fresh machine. Added July 2026 as part of the post-defense reproducibility hardening for the journal submission.

## 1. Environment

Python >= 3.10, free solvers only (no commercial licenses needed).

```bash
git clone https://github.com/ma731/Capstone-in-Operations-Research.git
cd Capstone-in-Operations-Research
python -m venv .venv
# Windows: .venv\Scripts\activate      Unix: source .venv/bin/activate
pip install -e ".[dev]"
# exact pins used during development are in requirements-lock.txt
```

## 2. Verify the code (no licensed data needed)

```bash
pytest -q --ignore=tests/test_electricitymaps.py
```

Expected: **188 passed, 5 skipped** (verified 2026-07-12 on Python 3.12 / Ubuntu). The 5 skips plus the ignored Electricity Maps test file require the licensed raw carbon-intensity data (see section 5); with that data present the full suite is 202 tests. Two DeprecationWarnings from upstream libraries are expected and unrelated to results.

Test coverage on `src/` is 79% (branchless line coverage, pytest-cov); CI enforces a 75% floor.

## 3. Verify the cited numbers (snapshot integrity)

Every number in the write-ups traces to a CSV in `docs/results_snapshots/`. Their SHA-256 digests are frozen in `MANIFEST.sha256`:

```bash
python -m scripts.make_provenance_manifest --check
```

Expected: `OK: 82 snapshots match the manifest.` Any edit to an archived CSV fails this check (and the CI test `tests/test_snapshot_manifest.py`). New results must be committed as NEW dated files; existing snapshots never change.

## 4. Regenerate the headline experiments

Each snapshot's regeneration command is documented in `docs/results_snapshots/README.md`. The headline set:

```bash
python -m scripts.run_part3_transfer_value     # RQ1: 4.04 / 9.91 / 9.04 % CVaR_0.95 reduction
python -m scripts.run_copula_experiment --region-set taskc   # RQ2 null (per region set)
python -m scripts.run_part3_emergency          # RQ3: severity crossover M* (first significant M=3.0)
python -m scripts.run_carbon_ceiling           # RQ3: realized severities (incl. BPAT 5.12x)
python -m scripts.run_block_bootstrap_check    # serial-dependence-aware CIs
python -m scripts.bh_correction                # multiple-testing correction over all gap cells
```

Determinism: the stochastic samplers are seed-deterministic (enforced by `tests/test_determinism.py`), so regeneration with the scripts' fixed seeds reproduces the archived values. Regenerated outputs are written with today's date; compare against the archived dated snapshot rather than overwriting it.

## 5. Data and licensing

- Carbon intensity: Electricity Maps, under a non-redistribution academic license. Raw CSVs live in `data/raw/` and are **gitignored; never commit them**. Obtain access via Electricity Maps' academic program and place files per `src/data/` ingestion docs.
- Temperature: Open-Meteo ERA5 (CC-BY), committed in the repo.
- The archived snapshots contain only derived aggregate statistics and are license-safe by design.

## 6. What is pre-defense vs post-defense

The scientific content (models, experiments, snapshots, thesis numbers) predates the 2026-07-07 defense; dates are verifiable in git history and in the snapshot filenames. The reproducibility hardening added in July 2026 (this file, the SHA-256 manifest + integrity test, seed-determinism tests, CI coverage floor) certifies and protects that record without altering it.
