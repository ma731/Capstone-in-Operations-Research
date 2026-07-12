# Deck provenance map

Every number and figure in the defense deck (`defense_fallback.pdf` / the repo's
`deck/capstone_defense.pptx`), traced to its archived source under
`docs/results_snapshots/` and the figure script that draws it. This makes the deck's own
claim — *"every number on these slides traces to an archived file in the repository"* —
checkable in one pass. Corrections to a handful of slide labels are tracked separately in
[`deck_errata.md`](deck_errata.md).

Legend: ✅ traces to a committed snapshot · 🔷 derived/illustrative (see note) ·
✏️ label needs a deck edit (see errata).

| Deck slide | Claim / number | Archived source (`docs/results_snapshots/`) | Figure · script |
|---|---|---|---|
| 4 | CVaR = mean of the worst 5 % of days; Φ=0 honest baseline | ✅ `full_thesis` abstract; `src/analysis/metrics.py::cvar_upper_tail` | — |
| 5 | Transfer lever **4.0 / 9.9 / 9.0 %** (Western/Eastern/Diversified) | ✅ `part3_transfer_value_2026-06-15.csv` (us_west 4.04, taskc 9.91, us_hetero 9.04) | `transfer_value_curve.png` · `run_transfer_value_curve.py` |
| 5 | "80 % may move", "saving saturates ~20 %" | ✅ `transfer_value_curve_2026-06-24.csv` (`budget_frac` 0→0.8; flat by 0.2) | ↑ same |
| 6 | Complexity–value frontier ("one jump, then flat") | 🔷 `complexity_frontier_2026-07-05.csv` — metric is *cumulative saving vs a carbon-blind scheduler* (looser than the 4.0–9.9 % CVaR-vs-Φ=0 headline); the +transfer plateau = `run_dayahead_savings.py` `save_aware` | `complexity_frontier.png` · `plot_complexity_frontier.py` |
| 7 | 144-dot ±0.4 % null scatter | ✅ `bh_correction.csv` — the **144 non-ablate** rows (baseline/ar1/lw/seasonal); max \|gap\| 0.355 % | `cv_curve.png` · `plot_cv_curve.py` |
| 8 / 18 | **+1.46 %** mean-leveling positive control | ✅ `bh_correction.csv` row `us_hetero,ablate-flat,R2_varcap,0.3` = 1.4557 %; also `us_hetero_regimes_2026-06-10_ablate-flat.csv` | — |
| 9 | "everyday premium 1.0 %" | ✏️ 🔷 schematic dial — no archived source; nearest archived mean premiums are negative (`_robust_value.out`). See errata. | schematic |
| 10 / 11 | Crossover **M\*≈3** | ✅ `part3_emergency_2026-06-15.csv` (us_west first significant at M=3.0) | `crossover.png` · `plot_crossover.py` |
| 10 / 11 / 19 | Median worst spike **≈1.43×**; portfolio 1.3–1.9× | ✅ `carbon_ceiling_2026-06-24.csv` (17 region rows; median 1.4269; joint 1.34/1.29/1.89) | `plot_ceiling.py` · `run_carbon_ceiling.py` |
| 19 | BPAT 5.12×, CA-ON 2.57×, US-SW-PNM 1.90×, Uri **1.28×** | ✅ `carbon_ceiling_2026-06-24.csv` (BPAT 5.1198, CA-ON 2.5674, PNM 1.9015, Uri event 1.2831) | ↑ same |
| 12 | Real data 2021–2025, **17 US/Canada zones**, Electricity Maps | ✅ `full_thesis` §Data; `carbon_ceiling_2026-06-24.csv` (17 region rows, all US/Canada — see errata re "Iberia") | `ci_corr_heatmap_us_west.png` · `plot_carbon_correlation.py` |
| 12 | "correlation up to 0.78 on the US West" | ✅ `tail_dependence_2026-07-05.csv` (us_west residual max `pearson_rho` 0.779) | ↑ same |
| 12 / 13 | 202 unit tests; CI on push; walk-forward to 2022–24 | ✅ `pytest --collect-only`=202; `.github/workflows/test.yml`; `*_regimes_*_ty2022/ty2023/ty2024.csv` | — |
| 13 / 18 | Block bootstrap, BH, per-cell TOST equivalence | ✅ `block_bootstrap_2026-06-27.csv`; `bh_correction.csv`; `scripts/equivalence_and_bound.py` | `robustness.png` · `plot_robustness.py` |
| 16 | Shuffled-marginals falsification (joint vs block-diagonal) | ✅ `*_regimes_2026-06-10.csv` + variants (`gap_pct`) | `schedule_us_west.png` · `plot_schedule.py` |
| 17 | Tail asymmetry χ_L > χ_U (CISO/LDWP 0.48/0.25, …) | ✅ `tail_dependence_2026-07-05.csv` (**residual** series) | `tail_dependence_taskc.png` · `plot_tail_dependence.py` |

**Figures that recompute from raw data.** `transfer_value_curve.png`, `ci_corr_heatmap_us_west.png`,
`cv_curve.png`, `schedule_us_west.png`, and `tail_dependence_taskc.png` are drawn by scripts
that read the raw Electricity Maps CSVs in `data/raw/` (gitignored, non-redistributable).
Their **numbers** are archived (above), but the **image bitmaps** are not byte-regenerable
from a fresh clone without the licensed data. This is by design (license), not a gap.
