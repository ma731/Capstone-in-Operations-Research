"""prototype_gated_robustness.py -- roadmap D2 step 2: robustness as an option.

The gate prototype (prototype_contextual_gate.py) showed top-decile severity
days on California-Nevada are predictable day-ahead (AUC ~0.97). This
prototype asks the follow-up question that defines the contextual
price-of-robustness paper: does EXERCISING robustness only on predicted-severe
days beat both unconditional policies?

Design (all information day-ahead legal):
  - Two stage-1 commitments computed once from train-year scenarios with the
    canonical two-stage transfer model (same constants as
    run_part3_real_emergency): x_neutral (risk='mean') and x_robust
    (risk='cvar').
  - A logistic gate trained on <=2023 (lagged severity + calendar +
    perfect-forecast temperature) fires on ~top-decile predicted risk.
  - Four policies evaluated on every complete 2024 day via recourse_cost:
    always-neutral, always-robust, gated (robust iff the gate fires), and
    oracle-gated (robust iff the day truly is severe; the upper bound).

Discipline: prototype, not pre-registered; 2024 is the evaluation year and
2025 stays untouched for the future locked experiment. Prints a summary;
writes nothing to docs/results_snapshots.

Run: .venv\\Scripts\\python -m scripts.prototype_gated_robustness
"""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from scripts.prototype_contextual_gate import TARGET_Q, build_design
from src.analysis.metrics import cvar_upper_tail
from src.analysis.severity_evt import daily_joint_severity
from src.data.electricitymaps import load_all_zones, to_wide
from src.data.temperature import align_temperature_to_panel, load_temperature_wide
from src.models.covariance import DEFAULT_TZ, REGION_ORDER, build_daily_panel
from src.models.transfer_dro import recourse_cost, two_stage_commit

# Same operating point as run_part3_real_emergency.py
CEIL, UTIL, LAM = 50.0, 0.80, 30.0
S = 40
TRAIN_THROUGH = 2023
EVAL_YEAR = 2024
SEED = 20260719
FIRE_Q = 90.0            # gate fires on top decile of train predicted risk


def main() -> None:
    zones = list(REGION_ORDER)
    carbon_wide = to_wide(load_all_zones(zones))
    panel, dates = build_daily_panel(carbon_wide, region_order=zones, tz=DEFAULT_TZ)
    temp_wide = load_temperature_wide(zones)
    temp_panel, _ = align_temperature_to_panel(
        temp_wide, carbon_wide, region_order=zones, tz=DEFAULT_TZ)
    sev = daily_joint_severity(panel)
    df = build_design(sev, dates, temp_panel)

    train = df[df.index.year <= TRAIN_THROUGH]
    ev = df[df.index.year == EVAL_YEAR]
    thr_sev = float(np.percentile(train["sev"], TARGET_Q))
    y_tr = (train["sev"] >= thr_sev).to_numpy()
    X_tr = train.drop(columns="sev").to_numpy()
    X_ev = ev.drop(columns="sev").to_numpy()
    severe_ev = (ev["sev"] >= thr_sev).to_numpy()

    gate = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    gate.fit(X_tr, y_tr)
    p_thr = float(np.percentile(gate.predict_proba(X_tr)[:, 1], FIRE_Q))
    fired = gate.predict_proba(X_ev)[:, 1] >= p_thr
    tp = int((fired & severe_ev).sum())
    print(f"Gate on {EVAL_YEAR}: fires {fired.mean():.1%} of days; "
          f"severe base rate {severe_ev.mean():.1%}; "
          f"precision {tp / max(fired.sum(), 1):.2f}, "
          f"recall {tp / max(severe_ev.sum(), 1):.2f}")

    # Commitments from train scenarios (day-ahead world model = history <= 2023).
    R, T = panel.shape[1], panel.shape[2]
    wl = np.full(R, UTIL * CEIL * T)
    ceil = np.full((R, T), CEIL)
    Phi = 0.4 * wl.sum()
    yrs = dates.year.to_numpy()
    train_panel = panel[yrs <= TRAIN_THROUGH]
    rng = np.random.default_rng(SEED)
    scen = train_panel[rng.choice(len(train_panel), S, replace=False)]
    print(f"Solving commitments (S={S} train scenarios, R={R}) ...")
    x_neutral = two_stage_commit(scen, wl, ceil, transfer_budget=Phi,
                                 lam=LAM, risk="mean")
    x_robust = two_stage_commit(scen, wl, ceil, transfer_budget=Phi,
                                lam=LAM, risk="cvar")

    # Realized cost of each commitment on every complete eval day.
    date_to_row = {d: i for i, d in enumerate(dates)}
    ev_rows = [date_to_row[d] for d in ev.index]
    print(f"Evaluating {len(ev_rows)} days x 2 commitments ...")
    cost_n = np.array([recourse_cost(x_neutral, panel[i], ceil,
                                     transfer_budget=Phi, lam=LAM)
                       for i in ev_rows])
    cost_r = np.array([recourse_cost(x_robust, panel[i], ceil,
                                     transfer_budget=Phi, lam=LAM)
                       for i in ev_rows])
    policies = {
        "always-neutral": cost_n,
        "always-robust": cost_r,
        "gated": np.where(fired, cost_r, cost_n),
        "oracle-gated": np.where(severe_ev, cost_r, cost_n),
    }

    base_mean, base_cvar = cost_n.mean(), cvar_upper_tail(cost_n)
    print(f"\n{'policy':16s} {'mean':>12s} {'CVaR95':>12s} "
          f"{'dMean%':>8s} {'dCVaR%':>8s}")
    for name, c in policies.items():
        print(f"{name:16s} {c.mean():12.1f} {cvar_upper_tail(c):12.1f} "
              f"{100 * (c.mean() / base_mean - 1):+8.3f} "
              f"{100 * (cvar_upper_tail(c) / base_cvar - 1):+8.3f}")

    for label, mask in (("severe", severe_ev), ("normal", ~severe_ev)):
        if mask.sum() == 0:
            continue
        print(f"\n  {label} days (n={mask.sum()}): robust-vs-neutral mean gap "
              f"{100 * (cost_r[mask].mean() / cost_n[mask].mean() - 1):+.3f}%")


if __name__ == "__main__":
    main()
