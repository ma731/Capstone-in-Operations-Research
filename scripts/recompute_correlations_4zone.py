"""Recompute aggregate, hour-of-day, and seasonal correlations on the 4-zone
panel (US-CAL-CISO, US-CAL-BANC, US-CAL-LDWP, US-NW-NEVP) and emit
LaTeX-ready table snippets plus a refreshed hour-of-day figure.

Run from project root:
    python scripts/recompute_correlations_4zone.py

Writes (creates dirs if missing):
    docs/snippets/table_means.tex       - Table 1 (mean CI by zone, 2024)
    docs/snippets/table_aggregate.tex   - Table 2 (4x4 aggregate, 2024 + full)
    docs/snippets/table_hourly.tex      - Table 3 (4 representative hours)
    docs/snippets/table_seasonal.tex    - Table 4 (DJF/MAM/JJA/SON)
    docs/stratified_results.txt         - full 24h breakdown + seasonal dump
    figures/correlation_by_hour.pdf     - refreshed two-panel figure
    figures/correlation_by_hour.png     - PNG sibling for quick view

Also prints all numbers to stdout for verification before pasting snippets.
"""
from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.data.electricitymaps import load_all_zones, to_wide
from src.analysis.stratified_correlations import (
    correlations_by_hour,
    correlations_by_season,
)

# --- Config ---------------------------------------------------------------
ZONES = ["US-CAL-CISO", "US-CAL-BANC", "US-CAL-LDWP", "US-NW-NEVP"]
YEARS = [2021, 2022, 2023, 2024, 2025]
REPRESENTATIVE_HOURS = [2, 6, 10, 18]  # overnight, dawn ramp, solar peak, evening
SEASONS_ORDER = ["DJF", "MAM", "JJA", "SON"]

# CA-internal first, then CA-NV cross. Used for column ordering in stratified tables.
PAIR_ORDER = [
    "BANC-CISO", "BANC-LDWP", "CISO-LDWP",
    "BANC-NEVP", "CISO-NEVP", "LDWP-NEVP",
]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNIPPETS_DIR = PROJECT_ROOT / "docs" / "snippets"
FIGURES_DIR = PROJECT_ROOT / "figures"
SNIPPETS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


# --- Helpers --------------------------------------------------------------
def short_zone(zone_id: str) -> str:
    """US-CAL-BANC -> BANC; US-NW-NEVP -> NEVP."""
    return re.sub(r"^US-[A-Z]+-", "", zone_id)


def short_pair(pair_label: str) -> str:
    """'US-CAL-BANC-US-NW-NEVP' -> 'BANC-NEVP'. Splits at the 2nd 'US-'."""
    idx = pair_label.find("US-", 3)
    if idx == -1:
        return pair_label
    left = pair_label[: idx - 1]   # strip the joining '-'
    right = pair_label[idx:]
    return f"{short_zone(left)}-{short_zone(right)}"


def make_pivot(long_df: pd.DataFrame) -> pd.DataFrame:
    """Long stratified output -> wide table (rows=stratum, cols=pair_short)."""
    df = long_df.copy()
    df["pair_short"] = df["pair"].map(short_pair)
    return df.pivot_table(index="stratum", columns="pair_short", values="correlation")


def latex_comma(n: int) -> str:
    """11035 -> '11{,}035' (LaTeX thousands separator without thinspace)."""
    return f"{n:,}".replace(",", "{,}")


# --- 1. Load + aggregate --------------------------------------------------
print("=" * 72)
print("Loading 4-zone panel...")
print("=" * 72)
long_df = load_all_zones(ZONES, years=YEARS)
wide = to_wide(long_df)
print(f"Wide panel shape: {wide.shape}")
print(f"Time range: {wide.index.min()} to {wide.index.max()}")
nan_by_zone = wide.isna().sum().to_dict()
print(f"NaN per zone: {nan_by_zone}")

means_full = wide.mean().round(1)
mask_2024 = wide.index.year == 2024
wide_2024 = wide.loc[mask_2024]
means_2024 = wide_2024.mean().round(1)

print("\nMean lifecycle CI per zone (gCO2eq/kWh):")
print("  full 2021-2025:")
for z in ZONES:
    print(f"    {short_zone(z):6s}  {means_full[z]:6.1f}")
print("  2024 only:")
for z in ZONES:
    print(f"    {short_zone(z):6s}  {means_2024[z]:6.1f}")

corr_full = wide.corr().round(3)
corr_2024 = wide_2024.corr().round(3)
print(f"\nAggregate correlations, full panel (n={len(wide):,}):")
print(corr_full)
print(f"\nAggregate correlations, 2024 only (n={len(wide_2024):,}):")
print(corr_2024)


# --- 2. Stratified --------------------------------------------------------
hourly_long = correlations_by_hour(wide)
seasonal_long = correlations_by_season(wide)

hourly_pivot = make_pivot(hourly_long).round(3)[PAIR_ORDER]
seasonal_pivot = make_pivot(seasonal_long).round(3).reindex(SEASONS_ORDER)[PAIR_ORDER]

hourly_n = hourly_long.groupby("stratum")["n_samples"].first().astype(int)
seasonal_n = seasonal_long.groupby("stratum")["n_samples"].first().astype(int)

print("\nHour-of-day correlations:")
print(hourly_pivot)
print(f"n per hour: {hourly_n.iloc[0]:,}")

print("\nSeasonal correlations:")
print(seasonal_pivot)
print(f"n per season: {dict(seasonal_n)}")


# --- 3. LaTeX snippets ----------------------------------------------------
def latex_table_means() -> str:
    rows = [f"{z} & {means_2024[z]:.1f} \\\\" for z in ZONES]
    return "\n".join([
        r"\begin{table}[ht]",
        r"\centering",
        r"\caption{Mean lifecycle carbon intensity by zone, 2024 (gCO$_2$eq/kWh).}",
        r"\label{tab:means}",
        r"\begin{tabular}{lr}",
        r"\toprule",
        r"Zone & Mean CI (gCO$_2$eq/kWh) \\",
        r"\midrule",
        *rows,
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])


def latex_table_aggregate() -> str:
    short_names = [short_zone(z) for z in ZONES]
    cols = "lcccc|cccc"
    header = " & " + " & ".join(short_names) + " & " + " & ".join(short_names) + r" \\"
    body_rows = []
    for z_row in ZONES:
        row_vals = [short_zone(z_row)]
        for z_col in ZONES:
            row_vals.append(f"{corr_2024.loc[z_row, z_col]:.3f}")
        for z_col in ZONES:
            row_vals.append(f"{corr_full.loc[z_row, z_col]:.3f}")
        body_rows.append(" & ".join(row_vals) + r" \\")
    return "\n".join([
        r"\begin{table}[ht]",
        r"\centering",
        r"\small",
        r"\caption{Pairwise Pearson correlations of raw hourly lifecycle CI, 4-zone panel. "
        r"Full panel: $n = " + latex_comma(len(wide)) + r"$ (2021--2025; no missing hours "
        r"after join). 2024 only: $n = " + latex_comma(len(wide_2024)) + r"$.}",
        r"\label{tab:corr}",
        r"\setlength{\tabcolsep}{5pt}",
        r"\begin{tabular}{" + cols + "}",
        r"\toprule",
        r" & \multicolumn{4}{c|}{\textbf{2024 only}} & \multicolumn{4}{c}{\textbf{Full 2021--2025}} \\",
        header,
        r"\midrule",
        *body_rows,
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])


def latex_table_hourly() -> str:
    hour_labels = {
        2: "02:00 (overnight)",
        6: "06:00 (dawn ramp)",
        10: "10:00 (solar peak)",
        18: "18:00 (evening)",
    }
    cols = "l" + "c" * len(PAIR_ORDER)
    header = "Local hour & " + " & ".join(PAIR_ORDER) + r" \\"
    body_rows = []
    for h in REPRESENTATIVE_HOURS:
        vals = [hour_labels[h]] + [f"{hourly_pivot.loc[h, p]:.3f}" for p in PAIR_ORDER]
        body_rows.append(" & ".join(vals) + r" \\")
    return "\n".join([
        r"\begin{table}[ht]",
        r"\centering",
        r"\small",
        r"\caption{Hour-of-day correlations at four representative local hours "
        r"(Pacific time), 2021--2025, 4-zone panel. Full 24-hour breakdown in "
        r"\texttt{docs/stratified\_results.txt}.}",
        r"\label{tab:hourly}",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{" + cols + "}",
        r"\toprule",
        header,
        r"\midrule",
        *body_rows,
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])


def latex_table_seasonal() -> str:
    season_labels = {
        "DJF": "DJF (winter)", "MAM": "MAM (spring)",
        "JJA": "JJA (summer)", "SON": "SON (autumn)",
    }
    cols = "l" + "c" * len(PAIR_ORDER) + "c"
    header = "Season & " + " & ".join(PAIR_ORDER) + r" & $n$ \\"
    body_rows = []
    for s in SEASONS_ORDER:
        vals = [season_labels[s]]
        vals += [f"{seasonal_pivot.loc[s, p]:.3f}" for p in PAIR_ORDER]
        vals.append(latex_comma(int(seasonal_n[s])))
        body_rows.append(" & ".join(vals) + r" \\")
    return "\n".join([
        r"\begin{table}[ht]",
        r"\centering",
        r"\small",
        r"\caption{Pairwise correlations by meteorological season, 2021--2025, "
        r"4-zone panel. DJF/MAM/JJA/SON = winter/spring/summer/autumn.}",
        r"\label{tab:season}",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{" + cols + "}",
        r"\toprule",
        header,
        r"\midrule",
        *body_rows,
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])


for fname, content in [
    ("table_means.tex", latex_table_means()),
    ("table_aggregate.tex", latex_table_aggregate()),
    ("table_hourly.tex", latex_table_hourly()),
    ("table_seasonal.tex", latex_table_seasonal()),
]:
    (SNIPPETS_DIR / fname).write_text(content + "\n", encoding="utf-8")
print(f"\nWrote 4 LaTeX snippets to {SNIPPETS_DIR}")


# --- 4. Figure: two-panel hour-of-day correlation -------------------------
hourly_for_plot = hourly_long.copy()
hourly_for_plot["pair_short"] = hourly_for_plot["pair"].map(short_pair)

ca_pairs = ["BANC-CISO", "BANC-LDWP", "CISO-LDWP"]
nv_pairs = ["BANC-NEVP", "CISO-NEVP", "LDWP-NEVP"]

fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
for ax, pairs, title in [
    (axes[0], ca_pairs, "California-internal pairs"),
    (axes[1], nv_pairs, "California-Nevada cross-pairs"),
]:
    for p in pairs:
        sub = hourly_for_plot[hourly_for_plot["pair_short"] == p].sort_values("stratum")
        ax.plot(sub["stratum"], sub["correlation"], marker="o", markersize=3.5, label=p)
    ax.axvspan(8, 14, alpha=0.10, color="gold")
    ax.set_xlabel("Hour of day (local Pacific time)")
    ax.set_title(title, fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_xticks(range(0, 25, 4))
    ax.set_xlim(-0.5, 23.5)
    ax.legend(loc="lower left", fontsize=9, framealpha=0.85)

axes[0].set_ylabel("Pearson correlation of hourly CI")
axes[0].set_ylim(0, 1)
fig.tight_layout()
fig.savefig(FIGURES_DIR / "correlation_by_hour.pdf", bbox_inches="tight")
fig.savefig(FIGURES_DIR / "correlation_by_hour.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"Refreshed figure: {FIGURES_DIR / 'correlation_by_hour.pdf'} (+ .png)")


# --- 5. Stratified results dump -------------------------------------------
strat_path = PROJECT_ROOT / "docs" / "stratified_results.txt"
with open(strat_path, "w", encoding="utf-8") as f:
    f.write("Stratified correlations, 4-zone panel\n")
    f.write("Zones: US-CAL-CISO, US-CAL-BANC, US-CAL-LDWP, US-NW-NEVP\n")
    f.write(f"Period: {wide.index.min()} to {wide.index.max()} (UTC)\n")
    f.write(f"n = {len(wide):,} hourly observations\n")
    f.write("=" * 72 + "\n\n")
    f.write("HOUR-OF-DAY (local Pacific time)\n")
    f.write("-" * 72 + "\n")
    f.write(hourly_pivot.to_string())
    f.write(f"\n\nn per hour ~= {int(hourly_n.iloc[0]):,}\n\n")
    f.write("SEASON\n")
    f.write("-" * 72 + "\n")
    f.write(seasonal_pivot.to_string())
    f.write("\n\nn per season:\n")
    for s in SEASONS_ORDER:
        f.write(f"  {s}  {int(seasonal_n[s]):,}\n")
print(f"Wrote {strat_path}")

print("\nDone.")
