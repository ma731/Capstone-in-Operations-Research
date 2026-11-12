# Publication roadmap (post-capstone)

Status date: 2026-07-19. Thesis graded (pinned at `97a34ca` lineage, defended
2026-07-07); this document plans the path from the graded capstone to submitted
papers. Work lives on the `paper-expansion` branch and is strictly additive:
no graded result, locked config, or archived snapshot is modified.

## Positioning

The competitive landscape has moved since the lit review was frozen:

- DRO-for-carbon-scheduling papers are appearing that add sophistication
  (LSTM forecasting + adaptive Wasserstein radius + battery dispatch,
  J. Cloud Computing 2026, ext. of IEEE CloudCom 2025). Our stance is the
  referee of that arms race: a pre-committed protocol measuring what each
  layer of sophistication actually buys.
- An "honest accounting" camp is emerging and getting published:
  limitations of spatiotemporal shifting (2024), systematic evaluation of
  carbon-aware workflow execution (2025). We join it with the strongest
  falsification discipline in the group (pre-registration, TOST equivalence,
  two-grid replication).
- The average-vs-marginal signal debate (e-Energy'24; "Moving Beyond Marginal
  Carbon Intensity," 2025) is unresolved and directly intersects our design:
  everything here runs on average CI. Nobody has asked whether *dependence
  modelling* pays under a marginal signal.

## The five directions

### D1. Marginal-signal replication (active, blocked on data)

Question: does the dependence null survive when the scheduler optimizes a
marginal-emissions signal instead of average CI? Marginal signals are spikier
and less spatially smooth, so this is a real test of whether the null is
signal-specific or fundamental. Either outcome publishes: survival makes the
null a much stronger general claim; a flip locates exactly where dependence
modelling lives.

- Scaffolded: `src/data/marginal_signal.py` (provider-agnostic loader),
  `docs/protocols/marginal_signal_protocol.md` (pre-registered design, locked
  before any test-set read).
- Blocked on: marginal CI data. Options: WattTime (v3 API, academic access
  program), Electricity Maps premium marginal stream. Average-CI licence does
  not cover it.
- Cost once data lands: a data swap + re-run of the locked Phase 1 pipeline.

### D2. Contextual price of robustness (active)

Question: RQ3 rejects *unconditional* robustness below M* ~ 3. Is robustness
worth exercising as a *conditional option*, switched on only when day-ahead
covariates predict a high-severity day? Connects the crossover decision rule
to the contextual-DRO literature (contextual DRO for AI datacenters,
arXiv 2607.00099; end-to-end conditional RO, arXiv 2403.04670).

- Gate question first (cheap, decisive): are high-severity joint days
  predictable at all from covariates known day-ahead? If AUC is near 0.5 the
  direction dies honestly; if predictability is material, build the
  conditional scheduler. Prototype: `scripts/prototype_contextual_gate.py`
  (temperature, lagged carbon, calendar features; walk-forward evaluation;
  perfect-foresight temperature as an upper bound).
- Full version: two-stage commit with a covariate-gated robustness switch,
  evaluated under the same falsification discipline (pre-registered,
  bootstrap-quantified), on real workload traces if D5 lands.
- Prototype findings (2026-07-19, train <= 2023, eval 2024, 2025 untouched):
  - Gate: CA-NV severe days ARE predictable day-ahead (logit AUC 0.97,
    precision@top-decile 0.64 vs base 0.08). ES-PT-FR: zero 2024 days cross
    the train-era threshold; the 2022 crisis was a regime shift, so severity
    there is crisis-driven, not covariate-predictable.
  - Gated policy (`scripts/prototype_gated_robustness.py`): with a working
    gate (precision 0.68, recall 0.79), all four policies (always-neutral,
    always-robust, gated, oracle-gated) land within 0.2% mean / 0.06% CVaR
    of each other, below the 0.4% margin; robustness helps LESS on severe
    days (-0.04%) than normal days (-0.20%).
  - Reading: predictability is not the bottleneck, severity magnitude is
    (consistent with D3: the CA-NV tail is bounded at M~1.41 << M*~3). On
    average-CI signals the contextual escape hatch is closed on both panels,
    one per failure mode: predictable-but-small (CA-NV) vs
    large-but-unpredictable (ES-PT-FR). This sharpens P2's framing and makes
    D1 (marginal signal, spikier tails) the live route to a positive
    contextual result.

### D3. EVT-calibrated emergency severity (active)

Question: how rare is a crossover-grade day, really? The current emergency
model is a stylised multiplier (`run_part3_emergency.py`) plus empirical
top-5% pools (`run_part3_real_emergency.py`). The upgrade: fit a generalized
Pareto (peaks-over-threshold) tail to realized daily joint-severity ratios
and report return periods for M >= 2, 2.5, 3, with threshold-sensitivity and
bootstrap CIs, anchored on named events (FR 2022 nuclear outage is in the
panel; check where it sits in the fitted tail).

- Module: `src/analysis/severity_evt.py`; runner: `scripts/run_severity_evt.py`;
  snapshot: `docs/results_snapshots/severity_evt_<date>.csv` (dimensionless
  ratios only, licence-safe).
- Local data covers the CA-NV panel (`taskA`) and ES-PT-FR; the us_west /
  taskc / us_hetero grids need their raw CSVs re-fetched before the paper run.

### D4. The screening condition as a general OR contribution (with supervisor)

Part 5's mean-dominance ratio, with Proposition 1 tightened so the bound is
conclusive rather than a one-sided filter, validated on 2-3 other allocation
domains (storage arbitrage, EV fleet charging, spatial supply chains).
Position against copula-ambiguity DRO (JOTA 2024) as the practitioner screen
for when that machinery can be skipped. Target: EJOR or Computers & OR.
This is the paper to co-author with Prof. Ghaddar; her sole graded criticism
("further validation and computational testing") is exactly what D3 + this
deliver.

### D5. Systems-venue hardening

Required for e-Energy/SoCC reviewers regardless of direction: replace the
synthetic flexible load with public cluster traces (Azure Packing Trace,
Google ClusterData) and add published baselines (CASPER; learning-augmented
spatiotemporal online allocation, arXiv 2408.07831) next to the Phi=0
self-baseline. Engineering, not research, but it is the accept/reject margin.

## Venue plan

| Paper | Content | Venue | Deadline |
|---|---|---|---|
| P1 | RQ1+RQ2 compressed + D1 (marginal replication) + as much D5 as fits | ACM e-Energy 2027, fall cycle | ~late Sept 2026 |
| P2 | D2 + D3: contextual price of robustness with calibrated emergencies | e-Energy 2027 winter cycle or SoCC 2027 | ~Jan 2027 / ~Mar 2027 |
| P3 | D4: screening condition, tightened bound, cross-domain | EJOR / Computers & OR | journal, no deadline |
| P4 (optional) | Position paper: "stop modelling correlation you cannot use" | HotCarbon 2027 | ~May 2027 |

Both ACM venues are double-blind: prepare an anonymized fork of this repo at
submission time, and check the Electricity Maps academic licence terms for
artifact-evaluation compatibility (aggregate snapshots are already
licence-safe; raw data stays out).

## Discipline

The thesis rules carry over unchanged: additive optional kwargs (existing
behaviour never changes, new constraints default OFF), tests mirror existing
suites, pre-registration for any experiment that reads the test years
(dry-run gate, then commit-locked config, then a single test read), every
numeric claim traces to an archived snapshot.
