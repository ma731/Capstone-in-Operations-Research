"""Drift monitoring for the day-ahead forecast, and what it means for the thesis.

The scheduler plans on a forecast. The forecast is "re-trained" every day: it is the
mean of the same hour over the previous 14 days, so it always uses the latest data.
What can still go wrong is that the world drifts and the forecast gets worse. This
monitor measures that, month by month, against a baseline.

Why it matters beyond hygiene: RQ3 found that robust optimisation (DRO) only pays when
forecast surprises are large. A sustained rise in forecast error is exactly the signal
to re-check whether the robust layer now pays. So the monitor does not just raise an
alert; it says which thesis decision to revisit.

    python -m agentic.monitoring --portfolio us_west --start 2025-01-01 --end 2025-12-31

Needs the Electricity Maps snapshots (licensed, not in the public repo).
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from . import knowledge
from .scheduler import HISTORY_DAYS, _hourly

THRESHOLD = 1.5          # alert when a month's error is 1.5x the baseline
BASELINE_MONTHS = 3
REPORTS = Path(__file__).with_name("reports")


def daily_errors(zone: str, start: date, end: date) -> dict[date, float]:
    """Mean absolute error (gCO2eq/kWh) of the 14-day seasonal forecast, per day."""
    panel = _hourly(zone, start - timedelta(days=HISTORY_DAYS), end)
    out = {}
    for i in range(HISTORY_DAYS, panel.shape[0]):
        fc = panel[i - HISTORY_DAYS:i].mean(axis=0)
        out[start + timedelta(days=i - HISTORY_DAYS)] = float(np.abs(panel[i] - fc).mean())
    return out


def drift_report(zones: list[str], start: date, end: date, *, threshold: float = THRESHOLD,
                 baseline_months: int = BASELINE_MONTHS) -> dict:
    by_zone, alerts = {}, []
    for z in zones:
        errs = daily_errors(z, start, end)
        months: dict[str, list[float]] = {}
        for d, e in errs.items():
            months.setdefault(d.strftime("%Y-%m"), []).append(e)
        monthly = {m: float(np.mean(v)) for m, v in sorted(months.items())}
        keys = list(monthly)
        base = float(np.mean([monthly[k] for k in keys[:baseline_months]]))
        rows = []
        for m in keys:
            ratio = monthly[m] / base if base else float("nan")
            flag = m not in keys[:baseline_months] and ratio >= threshold
            rows.append({"month": m, "mae": round(monthly[m], 1), "ratio": round(ratio, 2), "drift": flag})
            if flag:
                alerts.append({"zone": z, "month": m, "ratio": round(ratio, 2)})
        by_zone[z] = {"baseline_mae": round(base, 1), "months": rows}
    if alerts:
        worst = max(alerts, key=lambda a: a["ratio"])
        action = (f"Forecast error rose to {worst['ratio']}x its baseline in {worst['zone']} ({worst['month']}). "
                  "Re-check whether the robust layer (RQ3) now pays there, and consider a better forecaster "
                  "before trusting the deterministic plan.")
    else:
        action = "Forecast error is stable: the deterministic scheduler stays the right choice (RQ3)."
    return {"period": f"{start} to {end}", "threshold": threshold, "baseline_months": baseline_months,
            "zones": by_zone, "alerts": alerts, "action": action}


def to_markdown(rep: dict, title: str) -> str:
    lines = [f"# Drift report: {title}", "", f"Period {rep['period']}. Alert when a month's forecast error is "
             f"{rep['threshold']}x the first {rep['baseline_months']} months' error.", "", f"**{rep['action']}**", ""]
    for z, info in rep["zones"].items():
        lines += [f"## {z} (baseline MAE {info['baseline_mae']} gCO2eq/kWh)", "", "| Month | MAE | x baseline | |",
                  "|---|---:|---:|---|"]
        lines += [f"| {r['month']} | {r['mae']} | {r['ratio']} | {'DRIFT' if r['drift'] else ''} |" for r in info["months"]]
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Monthly drift report for the day-ahead carbon forecast.")
    ap.add_argument("--portfolio", default="us_west", choices=["us_west", "taskc", "us_hetero"])
    ap.add_argument("--start", default="2025-01-01")
    ap.add_argument("--end", default="2025-12-31")
    a = ap.parse_args(argv)
    rep = drift_report(knowledge.portfolio_zones(a.portfolio), date.fromisoformat(a.start), date.fromisoformat(a.end))
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"drift_{a.portfolio}.md"
    out.write_text(to_markdown(rep, a.portfolio), encoding="utf-8")
    print(rep["action"])
    print(f"{len(rep['alerts'])} alert(s). Written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
