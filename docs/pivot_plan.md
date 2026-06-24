# Pivot plan — value-first thesis by June 29

Consolidated from `docs/thesis_change_map.md` + the multi-agent quality audit (5 reviewers,
verified against the repo). State: **code is sound (194 tests pass), the value-first results
exist; only the narrative + two integrity items need work.**

## The two things that would actually sink the defense
- **M1 — baseline strawman (INTEGRITY, do first).** `run_dayahead_savings.py` and
  `run_transfer_value_curve.py` compare vs a **uniform** per-region spread, not the honest
  comparator. Fix: report (a) carbon-aware-no-transfer (Φ=0, same feasible set) vs carbon-blind,
  and (b) full-transfer vs Φ=0 = **the 4.0–9.9% CVaR-reduction spatial lever** (verified;
  earlier drafts said "+8–11 pt", a different carbon-blind decomposition — superseded).
  Make Φ=0 the reference line.
  Retire "12–16% vs carbon-blind." (Note: `greedy_sort_schedule_multiregion` ignores ramp/thermal
  constraints, so use the Φ=0 rolling baseline on the *same* feasible set, not the raw greedy sort.)
  Re-run 3 grids, re-snapshot. ~2–3 h.
- **M5 — Migration-boundary framing (RESOLVED, INTEGRITY).** The deterministic transfer savings (the
  4.0–9.9% lever) are framed as established background (`radovanovic2022,wiesner2021`); the contribution
  is the **robust/stochastic** layer + the crossover decision rule. Handled by the boundary framing in
  the lit review and Annex A, not by attribution. ~1 h.

## MUST-FIX (narrative spine, Bissan's signals)
- **M6 — sign-off first.** Email Bissan the one-paragraph new spine + `thesis_change_map.md` before
  20 h of rewriting. Blocking, async. 0.5 h.
- **M2 — re-spine title + abstract** value-first; demote the null to one clause. 4–5 h.
- **M3 — promote Part 3 (transfer + crossover)** from "preliminary appendix" into main Results as the
  OR contribution, framed as a *decision rule*, keeping the honest "real grids stay below M*" bound. 4–6 h.
- **M4 — re-point the DRO** to day-ahead forecast-error (daily, not yearly); **demote copula** to a
  one-paragraph appendix. Keep Prop 1 as a diagnostic. 5–6 h.

## SHOULD-DO
- **S1** day-ahead savings bar chart (the opening Results figure). 1.5 h.
- **S2** migrate transfer-curve + new plots to `plotstyle` (serif/Times, 300 dpi); relabel
  "vs carbon-blind" → "vs Φ=0 greedy". 1.5 h.
- **S3** rewrite Conclusions as an explicit practitioner **decision rule**. 2 h.
- **S4** unit test: robust layer reduces CVaR under fat-tailed error. 0.5 h.
- **S5** hold the 30-page budget; overflow → `full_thesis/`.

## NICE-TO-HAVE
- **N1** poster v23 (reorder to value-first; v22 already flags transfer). **N2** deck (July 7, defer).
- **N3** style sweep of surviving figures. **N4** synthetic-vs-real crossover side-by-side panel.

## NEW (post-audit): the extra grids
- **Alberta (CA-AB) + Ontario (CA-ON) crossover** — the make-or-break shot: does robustness cross M*
  on a *real* volatile grid? Timeboxed, parallel (cowork). Pre-wire + run once data is staged.
- **South-central / New Mexico set** — optional 4th grid; wire in once data located.
- *Blocker:* the downloaded CA-AB / PNM files are named differently and not yet in
  `data/raw/electricitymaps/` — need their path to stage them.

## Critical path
1. **Today:** M6 (Bissan sign-off email) + M5 (migration-boundary framing) — both blocking, async.
2. **On sign-off:** M1 (baseline) → S1/S2 (figures).
3. **Jun 19–24:** M2, M3, M4 (the rewrite).
4. **Jun 25:** S3, S5 — body-complete checkpoint.
5. **Jun 26–28:** N1 poster, proofread, page-count, PDF build.
6. **Jun 29:** submit. Deck (N2) continues to July 7.
