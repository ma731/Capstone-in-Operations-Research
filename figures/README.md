# Publication figures

The figures in this directory are versioned so the TeX publications build from a
clean clone without access to the non-redistributable Electricity Maps raw data.

- Most figures are generated from the archived aggregate CSVs in
  `docs/results_snapshots/` using the `scripts/plot_*.py` modules.
- Figures also used by the canonical poster are mirrored from `poster/figs/`.
- `case_summary`, `scenario_convergence`, and `scenario_tail` are publication
  snapshots extracted from the canonical PDFs. Their original generation scripts
  require licensed raw inputs that cannot be committed. These snapshots preserve
  the already-published visual output; they are not presented as an independent
  recomputation.

Public CI verifies that every referenced asset exists and that archived headline
values remain internally consistent. Full scientific reproduction additionally
requires the licensed raw data, as described in the root README.
