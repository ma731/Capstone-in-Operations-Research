"""Benjamini-Hochberg multiple-testing correction over all spatial-gap cells.

We test many cells (case x regime x alpha x estimator-variant), so a few
'detectable' bootstrap CIs are expected by chance. This script recomputes the
bootstrap gap distribution from each results pkl (same seed/resamples as the
experiment), derives a two-sided bootstrap p-value per cell, and applies BH
across ALL cells. Cells surviving BH at q=0.05 are the only ones that count.

Run: .venv\\Scripts\\python -m scripts.bh_correction
"""
from __future__ import annotations

import pickle
import re
from pathlib import Path

import numpy as np
import pandas as pd

N_BOOT, SEED, CVAR_ALPHA = 1000, 20260524, 0.95


def cvar(v):
    n_tail = max(1, int(np.ceil(len(v) * (1 - CVAR_ALPHA))))
    return float(np.sort(v)[::-1][:n_tail].mean())


def boot_pvalue(j, s):
    rng = np.random.default_rng(SEED)
    gaps = np.empty(N_BOOT)
    for b in range(N_BOOT):
        idx = rng.integers(0, len(j), size=len(j))
        gaps[b] = cvar(s[idx]) - cvar(j[idx])
    p = 2 * min((gaps <= 0).mean(), (gaps >= 0).mean())
    return max(p, 1 / N_BOOT), float(np.median(gaps))


def main():
    rows = []
    for pkl_path in sorted(Path("results").glob("*_regimes_*.pkl")):
        m = re.match(r"(us_west|taskc|us_hetero|taskC)_regimes_[\d-]+(.*)\.pkl",
                     pkl_path.name)
        if not m:
            continue
        case, variant = m.group(1), (m.group(2).lstrip("_") or "baseline")
        with pkl_path.open("rb") as f:
            d = pickle.load(f)
        tests = d["test_results"]
        for r in d["summary_rows"]:
            j = next(t["per_day_emissions"] for t in tests
                     if t["regime"] == r["regime"] and t["alpha"] == r["alpha"]
                     and t["sigma_label"] == "joint")
            s = next(t["per_day_emissions"] for t in tests
                     if t["regime"] == r["regime"] and t["alpha"] == r["alpha"]
                     and t["sigma_label"] == "shuf")
            p, med = boot_pvalue(np.asarray(j), np.asarray(s))
            rows.append({"case": case, "variant": variant, "regime": r["regime"],
                         "alpha": r["alpha"], "gap_pct": r["gap_pct"], "p_boot": p})
    df = pd.DataFrame(rows).sort_values("p_boot").reset_index(drop=True)
    m = len(df)
    df["rank"] = np.arange(1, m + 1)
    df["bh_thresh"] = 0.05 * df["rank"] / m
    kmax = df.index[df["p_boot"] <= df["bh_thresh"]].max() if \
        (df["p_boot"] <= df["bh_thresh"]).any() else -1
    df["bh_significant"] = df.index <= kmax
    sig = df[df["bh_significant"]]
    print(f"{m} cells tested; BH(q=0.05) significant: {len(sig)}")
    if len(sig):
        print(sig[["case", "variant", "regime", "alpha", "gap_pct", "p_boot"]]
              .to_string(index=False, float_format=lambda x: f"{x:.4g}"))
        pos = sig[sig["gap_pct"] > 0]
        print(f"\nOf which POSITIVE (joint beats shuf): {len(pos)}; "
              f"max |gap| among significant: {sig['gap_pct'].abs().max():.3f}%")
    out = Path("results/bh_correction.csv")
    df.drop(columns=["rank", "bh_thresh"]).to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
