# Handoff — Carbon DRO Capstone

_Last updated: 2026-06-20. Latest commit: `c7e4399` on `main`._

This file is the single place to get oriented fast. For the regular-vs-extended
content split and the prioritized improvement lists, see [`thesis_split.md`](thesis_split.md).

---

## 1. What this is

IE School of Science & Technology Master's (Business Analytics & Data Science)
**Research Capstone in Operations Research**. Author: Marco Ortiz Togashi.
Supervisor: Prof. Bissan Ghaddar. Private repo `ma731/Capstone-in-Operations-Research`,
local clone at `OneDrive/Escritorio/Github/Capstone-in-Operations-Research`.

**Topic:** carbon-aware data-center scheduling. A day-ahead migration scheduler over a
Mahalanobis–Wasserstein DRO (SOCP), asking which layers of modelling *sophistication*
are worth their price.

**Framing (value-first, "The Price of Sophistication"):** three research questions.
- **RQ1 — the lever:** active inter-region migration cuts out-of-sample
  $\mathrm{CVaR}_{0.95}$ by **4.0–9.9%** over a no-transfer $\Phi=0$ baseline.
- **RQ2 — the screening rule:** modelling the joint covariance / copula adds **≈0**
  (a replicated null), explained by a mean-dominance theorem (Proposition 1).
- **RQ3 — the price of robustness:** DRO over day-ahead forecast error pays only past an
  emergency-severity crossover **M\*≈3**; real grids reach only **M≈1.4**, so the
  deterministic scheduler is dominant on observed data.

> This is a **pivot** away from an earlier "null result" framing. Do not reintroduce
> null-as-headline language. The null survives only as the RQ2 screening tool.

---

## 2. Verified numbers (do not drift from these)

| Quantity | Value | Source of truth |
|---|---|---|
| Transfer lever (the headline) | **4.0–9.9%** OOS $\mathrm{CVaR}_{0.95}$ reduction over $\Phi=0$ — Western **4.0%**, Eastern **9.9%**, Diversified **9.0%** | `docs/results_snapshots/part3_transfer_value_2026-06-15.csv` (from `scripts/run_part3_transfer_value.py`) |
| Robustness crossover | **M\*≈3**; real grids reach only **M≈1.4** | `scripts/plot_crossover.py`, `run_parts34_stability.py` |
| Screening-rule null | spatial gaps `< 0.4%` of CVaR, robust to estimator / BH / walk-forward | `docs/results_snapshots/` |
| Tests | **198** passing | `tests/` |
| Total vs carbon-blind | 11.7/12.5/15.8% ("12–16%") — **a SEPARATE metric**, lives in the FULL thesis only, NOT the capstone | `docs/results_snapshots/transfer_value_curve_2026-06-18.csv` |

**Do not conflate** the 4.0–9.9% CVaR-reduction lever with the 12–16% total-vs-carbon-blind
figure. An earlier draft's "4.7–10.1%" / "8–11 percentage-point" numbers were an
**unverified placeholder that conflated the two** — they are wrong and fully purged.

---

## 3. Deliverables and their state

| Artifact | Path | State |
|---|---|---|
| Capstone report (graded) | `thesis/capstone_thesis.pdf` (.tex) | Complete. 41pp total, **graded body 29pp** (appendix A starts p33), ≤30 limit with ~1pp margin. |
| Extended thesis | `full_thesis/full_thesis.pdf` (.tex) | Complete, 57pp. Develops Parts 3–5 in the body. |
| A0 poster | `poster/poster_capstone_v24.pdf` (`build_v24.js`) | **v24 is canonical.** Navy/gold IE identity. |
| Defense deck | `deck/capstone_defense.pptx` (`scripts/build_deck.py`) | Built, value-first, 18 slides. |
| Explainer (outside repo) | `OneDrive/Escritorio/Carbon DRO Capstone — Explained Simply.pdf` (+ `Carbon_Capstone_Explained.html`) | Value-first, current. Lives on the Desktop, NOT tracked in git. |

---

## 4. Deadlines (MBDS FT, per Dae-Jin Lee)

- **Report + poster: Mon June 29 2026, 12:00.** Report = single PDF, **MAX 30 pages**
  excluding refs/appendices, **12pt Times New Roman, 1.5 line spacing**, full refs.
- Group (2–3) requires an **Individual Contribution Statement (Annex A)** — already in
  both theses.
- Poster: **A0 portrait PDF**, publication-quality figures.
- **Oral presentations: Tue July 7.** ~15 min + Q&A; slides via Blackboard the night before.

---

## 5. Recently completed (this work stream)

- Pivot to value-first; corrected the transfer-lever number to the verified 4.0–9.9%
  across thesis, full thesis, deck, poster, and explainer.
- README rewritten value-first; MIT `LICENSE` added (scoped: code only; thesis/poster/deck
  © author; Electricity Maps data non-redistributable).
- Two stale work-log packets (`implementation_packet.md`, `body_restructure_packet.md`)
  marked **DEPRECATED**.
- Sharpened the contribution boundary in **both** theses (no teammate named): migration
  mechanism credited to established literature (`radovanovic2022`, `wiesner2021`);
  contribution scoped to the honest $\Phi=0$-anchored measurement + screening + decision
  rules; Annex A softened.
- Added Limitation (vi): the day-ahead forecast is deliberately a transparent
  climatological mean, not a learned model (answers Bissan's "DRO quality" point).
- Poster redesigned (v24) and promoted to canonical.
- Restored the Iberia (`es_pt_fr`) derived snapshots + scripts (a prior cleanup deleted
  them while the theses still cite Iberia — traceability regression, now fixed).
- `docs/thesis_split.md` written: regular-vs-extended split + improvement backlog.

---

## 6. Open / pending (nothing blocks submission)

1. **Supervisor boundary email** — confirming the collaboration boundary (author owns the
   robust/DRO + decision-rule layer; deterministic migration is established background).
   The text now stands without it; this is the author's call. **(human action)**
2. **Extended-thesis depth items** (optional, see `thesis_split.md` D2): promote Prop. 1 to
   a proved problem-class condition with a κ regime map; fully develop the two-stage robust
   transfer + M\* derivation; flesh out the rolling-horizon forecast-robustness sweep.
3. **Deck/explainer** are current but were not re-touched in the latest boundary pass; if
   the boundary framing should appear there too, mirror the one-line "migration is
   established; we price the layers" message.

---

## 7. How to build & verify

```bash
# from repo root, venv at .venv (Python 3.12.4)
.venv/Scripts/python -m pytest -q                 # 198 tests should pass

# thesis (run from the thesis dir)
cd thesis && latexmk -pdf -interaction=nonstopmode capstone_thesis.tex
cd full_thesis && latexmk -pdf -interaction=nonstopmode full_thesis.tex

# poster — MUST run from poster/ (script references figs/ relatively)
cd poster && node build_v24.js
"/c/Program Files/LibreOffice/program/soffice.exe" --headless --convert-to pdf --outdir . poster_capstone_v24.pptx

# deck
.venv/Scripts/python scripts/build_deck.py        # -> deck/capstone_defense.pptx
```

**Post-edit checklist for either thesis:** compile exit 0; page count (capstone graded
body ≤30, appendix A at p33); `grep -c -- "---"` returns 0 (no em-dashes); a case-insensitive
grep for any teammate name returns 0 (the standing scrub); no "undefined reference/citation" in
the log; the 4.0–9.9% number intact.

---

## 8. Hard constraints & gotchas (read before editing)

- **No em-dashes** (`---` / `—`). The author considers them an AI tell. Use commas,
  parentheses, colons; keep en-dash numeric ranges (`2021--2025`).
- **No teammate names** anywhere in either thesis or any artifact (the prior collaborator
  reference has been fully scrubbed repo-wide). Standing decision: "we are not doing the same
  thing." The deterministic migration mechanism is framed as established background (credited to
  the literature, `radovanovic2022`/`wiesner2021`), not attributed to any individual.
- **Honest $\Phi=0$ baseline**, never a strawman. **No** carbon-ceiling impossibility-theorem
  overclaim (the text deliberately resists one).
- **Electricity Maps raw CSVs are non-redistributable.** They live (gitignored) in
  `data/raw/electricitymaps/` and `archive_iberia_removed/`. **Never commit raw data; only
  derived stats** go in `docs/results_snapshots/`.
- **Never `git add -A`.** `archive_iberia_removed/` holds raw EM data (gitignored, but stage
  explicitly anyway). Before any commit: `git diff --cached --name-only | grep -iE
  'electricitymap|archive_iberia|node_modules|data/raw'` must be empty.
- **Commit/push only when asked.**
- **Poster versioning:** `poster/build_v*.js` and `poster/poster_capstone_v*.{pdf,pptx}`
  are **gitignored**; only v24 is force-added (tracked). A future v25 needs `git add -f`.
  Run `node build_vNN.js` from inside `poster/` or it fails on `figs/`.
- **`results/`** holds gitignored intermediate outputs; **`docs/results_snapshots/`** holds
  the license-safe derived CSVs that every thesis number traces to.
- **Iberia (`es_pt_fr`)** is retained as low-correlation external validity. If you ever scrub
  it, remove its citations from BOTH theses too, or you re-break traceability.

---

## 9. Key file map

```
thesis/capstone_thesis.tex      # graded report (≤30pp body)
full_thesis/full_thesis.tex     # extended write-up (Parts 3-5 in body)
poster/build_v24.js             # canonical poster source (pptxgenjs)
scripts/build_deck.py           # defense deck builder (python-pptx)
scripts/run_part3_transfer_value.py   # the honest 4.0-9.9% experiment
src/models/                     # algorithm_1, algorithm_2b_mahalanobis, transfer_dro, cvar_saa, copula_scenarios, feasible_set
docs/thesis_split.md            # regular-vs-extended split + improvement backlog
docs/results_snapshots/         # license-safe derived stats (traceability)
docs/decisions.md               # design-decision log
docs/DEPRECATED.md              # which scripts are canonical vs superseded
docs/{implementation_packet,body_restructure_packet}.md   # DEPRECATED work-logs
```

---

## 10. Environment

venv at `.venv` (Python 3.12.4, uv-built, `.[dev]`). Solvers: **HiGHS** (LP/CVaR-SAA),
**CLARABEL/ECOS/SCS** (SOCP) — all free; Gurobi not required. LaTeX via `latexmk`.
Poster: Node + pptxgenjs, PDF via LibreOffice headless (`soffice.exe`). `gh` CLI authed as
`ma731`. CI runs pytest on push/PR (excludes the data-dependent `test_electricitymaps.py`).
