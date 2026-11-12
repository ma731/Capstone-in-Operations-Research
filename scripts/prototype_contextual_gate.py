"""prototype_contextual_gate.py -- roadmap D2 gate: are severe days predictable?

The contextual price-of-robustness direction only makes sense if high-severity
joint days are predictable from information available at day-ahead commit time.
This prototype answers that gate question before any scheduler is built: it
trains simple classifiers to flag "tomorrow is a top-decile joint-severity day"
from (a) lagged severity, (b) calendar structure, and (c) tomorrow's
temperature (the realized value, standing in for a perfect weather forecast,
so the temperature channel is an UPPER BOUND on what a real forecast gives).

Discipline note: this is a prototype, not a pre-registered experiment. It
trains on 2021-2023 and evaluates on 2024 ONLY. The 2025 year is deliberately
untouched so the eventual locked contextual-DRO experiment can use it as a
clean, single-read test set (same protocol as Phase 1).

If AUC on 2024 is near 0.5 on both panels, the direction dies here, honestly.
Prints a summary; writes nothing to docs/results_snapshots (prototypes never do).

Run: .venv\\Scripts\\python -m scripts.prototype_contextual_gate
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.analysis.severity_evt import daily_joint_severity
from src.data.electricitymaps import load_all_zones, to_wide
from src.data.temperature import align_temperature_to_panel, load_temperature_wide
from src.models.covariance import (
    DEFAULT_TZ,
    DEFAULT_TZ_ES_PT_FR,
    REGION_ORDER,
    REGION_ORDER_ES_PT_FR,
    build_daily_panel,
)

GRIDS = {
    "taskA": {"zones": list(REGION_ORDER), "tz": DEFAULT_TZ,
              "display": "California-Nevada"},
    "es_pt_fr": {"zones": list(REGION_ORDER_ES_PT_FR), "tz": DEFAULT_TZ_ES_PT_FR,
                 "display": "Iberia+France"},
}
TARGET_Q = 90.0          # "severe day" = top decile of joint severity (train-set quantile)
TRAIN_THROUGH = 2023
EVAL_YEAR = 2024         # 2025 stays untouched for the future locked experiment
SEED = 20260719
LAGS = (1, 2, 3, 7)


def build_design(sev: np.ndarray, dates: pd.DatetimeIndex,
                 temp_panel: np.ndarray) -> pd.DataFrame:
    """Feature matrix for predicting day d's severity with day-ahead info.

    Columns: lagged severity, 7-day rolling mean severity, calendar
    (month sin/cos, weekday, weekend), and day-d temperature summaries
    (perfect-forecast upper bound): per-zone daily mean, portfolio daily max.
    """
    df = pd.DataFrame(index=dates)
    df["sev"] = sev
    for lag in LAGS:
        df[f"sev_lag{lag}"] = df["sev"].shift(lag)
    df["sev_roll7"] = df["sev"].shift(1).rolling(7).mean()
    month = df.index.month.to_numpy()
    df["month_sin"] = np.sin(2 * np.pi * month / 12)
    df["month_cos"] = np.cos(2 * np.pi * month / 12)
    df["dow"] = df.index.dayofweek
    df["weekend"] = (df["dow"] >= 5).astype(float)
    zone_daily = temp_panel.mean(axis=2)          # (N, R) daily mean temp
    for r in range(zone_daily.shape[1]):
        df[f"temp_zone{r}"] = zone_daily[:, r]
    df["temp_max"] = temp_panel.max(axis=(1, 2))  # portfolio daily max
    return df.dropna()


def evaluate(df: pd.DataFrame, display: str) -> None:
    train = df[df.index.year <= TRAIN_THROUGH]
    test = df[df.index.year == EVAL_YEAR]
    thr = np.percentile(train["sev"], TARGET_Q)
    y_tr = (train["sev"] >= thr).to_numpy()
    y_te = (test["sev"] >= thr).to_numpy()
    X_tr = train.drop(columns="sev").to_numpy()
    X_te = test.drop(columns="sev").to_numpy()
    base = y_te.mean()
    print(f"\n--- {display}: {len(train)} train days (<= {TRAIN_THROUGH}), "
          f"{len(test)} eval days ({EVAL_YEAR}) ---")
    print(f"severe-day threshold (train q{TARGET_Q:.0f}): {thr:.3f}; "
          f"eval base rate: {base:.3f}")

    models = {
        "logit": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=2000)),
        "hgb": HistGradientBoostingClassifier(random_state=SEED),
    }
    for name, model in models.items():
        model.fit(X_tr, y_tr)
        p = model.predict_proba(X_te)[:, 1]
        auc = roc_auc_score(y_te, p) if 0 < y_te.mean() < 1 else float("nan")
        ap = average_precision_score(y_te, p)
        k = max(1, int(round(len(y_te) * (1 - TARGET_Q / 100))))
        top_k = np.argsort(p)[::-1][:k]
        prec_k = y_te[top_k].mean()
        print(f"  {name:6s}  AUC={auc:.3f}  AP={ap:.3f} (base {base:.3f})  "
              f"precision@top{k}={prec_k:.3f}")


def main() -> None:
    for cfg in GRIDS.values():
        carbon_wide = to_wide(load_all_zones(cfg["zones"]))
        panel, dates = build_daily_panel(
            carbon_wide, region_order=cfg["zones"], tz=cfg["tz"])
        temp_wide = load_temperature_wide(cfg["zones"])
        temp_panel, temp_dates = align_temperature_to_panel(
            temp_wide, carbon_wide, region_order=cfg["zones"], tz=cfg["tz"])
        if len(temp_dates) != len(dates) or not (temp_dates == dates).all():
            raise RuntimeError(
                "Temperature panel dates do not match carbon panel dates; "
                "check align_temperature_to_panel usage.")
        sev = daily_joint_severity(panel)
        df = build_design(sev, dates, temp_panel)
        evaluate(df, cfg["display"])


if __name__ == "__main__":
    main()
