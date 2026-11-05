# What this means for an enterprise running AI

Most of the compute this project schedules is AI work: model training, fine-tuning,
evaluation and batch inference. Those jobs can often wait a few hours or run in another
region. Every company scaling AI is meeting the cost of that compute, in money, energy and
carbon. This page turns the research into the questions a company would ask.

## 1. The decision rule: price each layer before you build it

The capstone's method is a value test, and it applies to any AI investment:

| Step | In the capstone | In a client's AI portfolio |
|---|---|---|
| Start from a working baseline | a day-ahead scheduler, no migration | the current process, or the simplest model |
| Add one layer at a time | migration, then co-movement, then robustness | a better model, more data, an agent, a new tool |
| Measure what each layer buys, out of sample | worst-day emissions on held-out days | the business KPI, against a control group |
| Fund what pays, skip what does not | migration pays; the other two do not | stop pilots that do not beat the baseline |

Here one layer paid and two did not. The two that did not are the expensive ones: joint
dependence models and distributionally robust optimisation need specialist skills, more
data and slower solves. **Knowing not to build them is part of the value.**

## 2. An illustrative value case for the layer that pays

**Measured:** letting flexible compute move between regions cut worst-day emissions
(CVaR 95%, the average of the worst 5% of days) by **4.0% to 9.9%** across three grids.

**Not measured, so not claimed:** the effect on an average day. The case below values only
the worst ~18 days a year.

**Assumptions** (change them in [`scripts/value_case.py`](../scripts/value_case.py)):
400 g CO2 per kWh on a bad day, a carbon price of EUR 70 per tonne, and the measured
reduction carrying over to a fleet with a similar share of flexible work on similar grids.

| Flexible AI compute | Worst-day emissions | CO2 avoided on worst days, per year | At the carbon price |
|---|---|---|---|
| Enterprise AI team: 5 MW | 48 t/day | 35 to 86 t | EUR 2,442 to 5,992 |
| Large AI programme: 25 MW | 240 t/day | 174 to 428 t | EUR 12,211 to 29,960 |
| AI training campus: 100 MW | 960 t/day | 698 to 1,712 t | EUR 48,843 to 119,841 |

## 3. What a value strategist would tell the client

- **At a carbon price alone, this is modest below campus scale.** For a 5 MW AI team it is
  a few thousand euros a year. That is an honest result, and it means the business case
  rests on more than the carbon price: worst-day exposure is when grids are strained,
  carbon reporting targets, and the fact that the lever is cheap to build.
- **The lever is an operating decision, not a research project.** Migrating flexible jobs
  needs a scheduler and a policy for which jobs may move. It does not need a richer model.
- **Skip the sophistication that does not pay.** On these grids, co-movement models and
  robust optimisation added under 0.4% and only pay in grid emergencies about three times
  worse than any observed. Revisit only if the client's grids are far more volatile.
- **Measure before scaling.** The same discipline as the research: agree the baseline, run
  the scheduler on a slice of jobs, compare worst days, then decide.

## Reproduce

```bash
python scripts/value_case.py          # the table above
python scripts/plot_value_ladder.py   # figures/value_ladder.svg, read from the archived snapshots
```
