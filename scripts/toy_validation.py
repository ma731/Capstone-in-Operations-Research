"""toy_validation.py

Validation of Algorithm 1 (deterministic LP) and Algorithm 2b (Mahalanobis--Wasserstein
DRO) on the small instance from constraint_semantics.tex Section 3.

Prepared for the 28 May 2026 supervisor meeting with Prof. Bissan Ghaddar.

Hand-computed Algorithm 1 expected solution:
    Region 1: x = [0, 0, 10, 10, 10, 0] MWh, sum = 30 = W_1
    Region 2: x = [0, 0, 10, 10,  5, 0] MWh, sum = 25 = W_2
    Objective: 11,200 kgCO2eq = 11.2 tCO2eq

This script:
    1. Solves Algorithm 1, validates against the hand-computed answer.
    2. Builds a synthetic 12x12 covariance for the Mahalanobis penalty.
    3. Solves Algorithm 2b at epsilon in {0, 0.5, 2, 10}, for both
       joint and block-diagonal-by-region (shuffled) covariances.
    4. Validates that epsilon=0 reproduces Algorithm 1 exactly.
    5. Produces three plots:
       - A1 schedule, per region
       - A1 vs A2b at one epsilon, side-by-side
       - A2b schedule as epsilon varies
    6. Prints a summary table of schedules and deviations.

Self-contained: does not import the project's algorithm modules; uses CVXPY directly.
The formulations match algorithm_1.py and algorithm_2b_mahalanobis.py exactly.
"""
from __future__ import annotations

import numpy as np
import cvxpy as cp
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from pathlib import Path

# Output directory for plot files (relative to current working directory).
# Override with the TOY_OUTPUT_DIR environment variable if you want plots
# saved elsewhere — useful when running from outside the repo root.
OUTPUT_DIR = Path(__import__("os").environ.get("TOY_OUTPUT_DIR", "."))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
#  Toy instance (from constraint_semantics.tex Section 3)
# ============================================================================

R, T = 2, 6                                # 2 regions, 6 hourly intervals
CMAX = 10.0                                # MWh per cell ceiling
W = np.array([30.0, 25.0])                 # MWh per region demand
RHO = np.array([
    [400.0, 300.0, 150.0, 200.0, 250.0, 350.0],   # region 1 carbon intensity
    [350.0, 280.0, 180.0, 220.0, 240.0, 320.0],   # region 2 carbon intensity
])  # units: kgCO2eq/MWh (numerically equivalent to gCO2eq/kWh)


# ============================================================================
#  Algorithm 1: deterministic LP under known rho
# ============================================================================

def solve_a1(rho: np.ndarray, W: np.ndarray, cmax: float):
    """min  <rho, x>
       s.t. sum_t x_{r,t} >= W_r,  0 <= x_{r,t} <= cmax
    """
    R_, T_ = rho.shape
    x = cp.Variable((R_, T_), nonneg=True)
    constraints = [
        cp.sum(x, axis=1) >= W,
        x <= cmax,
    ]
    obj = cp.Minimize(cp.sum(cp.multiply(rho, x)))
    prob = cp.Problem(obj, constraints)
    prob.solve(solver=cp.CLARABEL)
    return x.value, prob.value


# ============================================================================
#  Synthetic covariance for the Mahalanobis penalty
# ============================================================================
#
# The full pipeline estimates Sigma from N=1815 historical days.  For a toy
# instance we don't have that, so we construct a synthetic Sigma by hand.  The
# structure mimics the empirical pattern documented in v10 Section 4: moderate
# within-region temporal correlation, stronger cross-region correlation at
# matched hours.  Flattening convention is row-major: vec(x)[r*T + t] = x_{r,t}.

def build_synthetic_sigma(R: int, T: int,
                          sigma: float = 50.0,
                          rho_temporal: float = 0.3,
                          rho_cross: float = 0.6) -> np.ndarray:
    """Build a 12x12 covariance with the following structure:
        Diagonal:               sigma^2
        Within-region (r=r'):   sigma^2 * rho_temporal
        Cross-region same hour: sigma^2 * rho_cross
        Cross-region diff hour: sigma^2 * rho_cross * rho_temporal
    """
    dim = R * T
    Sigma = np.zeros((dim, dim))
    for i in range(dim):
        r_i, t_i = divmod(i, T)
        for j in range(dim):
            r_j, t_j = divmod(j, T)
            if i == j:
                Sigma[i, j] = sigma ** 2
            elif r_i == r_j:                          # same region
                Sigma[i, j] = sigma ** 2 * rho_temporal
            elif t_i == t_j:                          # same hour, diff region
                Sigma[i, j] = sigma ** 2 * rho_cross
            else:                                     # diff region, diff hour
                Sigma[i, j] = sigma ** 2 * rho_cross * rho_temporal
    return Sigma


def block_diagonal_by_region(Sigma: np.ndarray, R: int, T: int) -> np.ndarray:
    """Zero out cross-region blocks: preserve within-region temporal structure,
    destroy cross-region structure.  This is the 'shuffled' counterfactual.
    """
    Sigma_shuf = Sigma.copy()
    dim = R * T
    for i in range(dim):
        r_i = i // T
        for j in range(dim):
            r_j = j // T
            if r_i != r_j:
                Sigma_shuf[i, j] = 0.0
    return Sigma_shuf


def regularize_and_cholesky(Sigma: np.ndarray, eta: float = 1e-5) -> np.ndarray:
    """Scale-adaptive ridge then lower-triangular Cholesky.
    Same convention as src/models/covariance.py in the main project.
    """
    dim = Sigma.shape[0]
    delta = eta * np.trace(Sigma) / dim
    Sigma_reg = Sigma + delta * np.eye(dim)
    return np.linalg.cholesky(Sigma_reg)


# ============================================================================
#  Algorithm 2b: Mahalanobis-Wasserstein SOCP
# ============================================================================

def solve_a2b(rho_bar: np.ndarray, L: np.ndarray, W: np.ndarray,
              cmax: float, eps: float):
    """min  <rho_bar, x> + eps * ||L^T vec(x)||_2
       s.t. sum_t x_{r,t} = W_r,  0 <= x_{r,t} <= cmax
    L: lower-triangular Cholesky factor of the regularized Sigma.
    Returns (x_opt, total_obj, linear_part).
    """
    R_, T_ = rho_bar.shape
    x = cp.Variable((R_, T_), nonneg=True)
    # row-major vec via explicit hstack of rows
    x_vec = cp.hstack([x[r, :] for r in range(R_)])
    constraints = [
        cp.sum(x, axis=1) == W,
        x <= cmax,
    ]
    linear = cp.sum(cp.multiply(rho_bar, x))
    penalty = eps * cp.norm(L.T @ x_vec, 2)
    obj = cp.Minimize(linear + penalty)
    prob = cp.Problem(obj, constraints)
    prob.solve(solver=cp.CLARABEL)
    return x.value, prob.value, float(linear.value)


# ============================================================================
#  Run validation
# ============================================================================

print("=" * 78)
print("  TOY VALIDATION  (R=2, T=6, from constraint_semantics.tex Section 3)")
print("=" * 78)

# ---------- Algorithm 1 ----------
print("\n[Algorithm 1: deterministic LP under known rho]\n")
x_a1, obj_a1 = solve_a1(RHO, W, CMAX)

print(f"  Region 1 schedule (MWh):  {np.round(x_a1[0], 2)}")
print(f"  Region 2 schedule (MWh):  {np.round(x_a1[1], 2)}")
print(f"  Region 1 sum:  {x_a1[0].sum():.2f}  (target W_1 = {W[0]:.1f})")
print(f"  Region 2 sum:  {x_a1[1].sum():.2f}  (target W_2 = {W[1]:.1f})")
print(f"  Total emissions:  {obj_a1:.2f} kgCO2eq  =  {obj_a1/1000:.3f} tCO2eq")

# Validate against hand-computed answer
expected_a1 = np.array([
    [0.0, 0.0, 10.0, 10.0, 10.0, 0.0],
    [0.0, 0.0, 10.0, 10.0,  5.0, 0.0],
])
schedule_match = np.allclose(x_a1, expected_a1, atol=1e-6)
obj_match = abs(obj_a1 - 11200.0) < 1e-3
print(f"\n  Hand-computed match (schedule): {schedule_match}")
print(f"  Hand-computed match (objective): {obj_match}")
assert schedule_match and obj_match, "Algorithm 1 does not match hand-computed solution"
print("  Algorithm 1 validation: PASS")

# ---------- Synthetic Sigma ----------
print("\n[Building synthetic covariance for Mahalanobis penalty]\n")
Sigma_joint = build_synthetic_sigma(R, T, sigma=50.0,
                                    rho_temporal=0.3, rho_cross=0.6)
Sigma_shuf = block_diagonal_by_region(Sigma_joint, R, T)

print(f"  Sigma_joint:  12x12, sigma=50 kgCO2/MWh, rho_temporal=0.3, rho_cross=0.6")
print(f"  Sigma_shuf:   block-diagonal-by-region (cross-region blocks zeroed)")

# Sanity check: trace preserved (diagonal entries unchanged)
assert np.allclose(np.trace(Sigma_joint), np.trace(Sigma_shuf)), \
    "shuf should preserve diagonal"
print(f"  trace(Sigma_joint) = trace(Sigma_shuf) = {np.trace(Sigma_joint):.2f}  "
      f"(diagonal preserved)")

# Verify positive-definiteness of regularized version
L_joint = regularize_and_cholesky(Sigma_joint)
L_shuf = regularize_and_cholesky(Sigma_shuf)
print(f"  Both regularized Sigmas factored successfully (PSD confirmed).")

# ---------- Algorithm 2b at multiple epsilons ----------
print("\n[Algorithm 2b at varying epsilon]\n")
EPSILONS = [0.0, 5.0, 10.0, 25.0]

results = {}
for eps in EPSILONS:
    xj, oj, linj = solve_a2b(RHO, L_joint, W, CMAX, eps)
    xs, os_, lins = solve_a2b(RHO, L_shuf, W, CMAX, eps)
    results[eps] = {
        'joint': {'x': xj, 'obj': oj, 'linear': linj, 'penalty': oj - linj},
        'shuf':  {'x': xs, 'obj': os_, 'linear': lins, 'penalty': os_ - lins},
    }

# Validate epsilon=0 reproduces A1
x_a2b_eps0 = results[0.0]['joint']['x']
match_eps0 = np.allclose(x_a2b_eps0, expected_a1, atol=1e-5)
print(f"  epsilon=0 reproduces Algorithm 1 exactly: {match_eps0}")
assert match_eps0, "Algorithm 2b at eps=0 must reduce to Algorithm 1"
print("  Algorithm 2b epsilon=0 reduction validation: PASS")

# Print schedules side by side
print(f"\n  {'eps':>6}  {'cov':>5}  {'region 1 (MWh)':<38}  {'region 2 (MWh)':<38}  "
      f"{'emissions (kg)':>14}  {'pen (kg)':>10}")
print("  " + "-" * 120)
for eps in EPSILONS:
    for cov_label in ['joint', 'shuf']:
        r = results[eps][cov_label]
        xfmt = lambda v: "[" + ", ".join(f"{vi:5.2f}" for vi in v) + "]"
        print(f"  {eps:>6.1f}  {cov_label:>5}  {xfmt(r['x'][0]):<38}  "
              f"{xfmt(r['x'][1]):<38}  {r['linear']:>14.2f}  {r['penalty']:>10.2f}")

# Joint vs shuf schedule deviation per epsilon
print("\n  Joint-vs-shuffled schedule deviation per epsilon (max absolute, MWh):")
for eps in EPSILONS:
    diff = np.abs(results[eps]['joint']['x'] - results[eps]['shuf']['x']).max()
    print(f"    epsilon = {eps:>5.1f}:  max |x_joint - x_shuf| = {diff:.4f} MWh")

# Deviation from A1 as eps grows
print("\n  Spreading vs A1 per epsilon (sum of absolute deviations, MWh):")
print("  larger value = schedule spreads further from the greedy-fill A1 solution")
for eps in EPSILONS:
    for cov_label in ['joint', 'shuf']:
        x_arr = results[eps][cov_label]['x']
        dev = np.abs(x_arr - expected_a1).sum()
        print(f"    epsilon = {eps:>5.1f}, {cov_label:>5}:  ||x - x_A1||_1 = {dev:.4f}")


# ============================================================================
#  Plots
# ============================================================================

# Match the documents' aesthetic: navy + gold + sage + rust on cream
NAVY = '#0c1e3e'
GOLD = '#8b6914'
GOLD_LIGHT = '#b89535'
SAGE = '#5d7a5a'
RUST = '#8b3a0e'
CREAM = '#faf7f0'
GREY = '#9a9a9a'

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times', 'DejaVu Serif', 'Bitstream Vera Serif'],
    'font.size': 10,
    'axes.edgecolor': NAVY,
    'axes.labelcolor': NAVY,
    'xtick.color': '#5a5a5a',
    'ytick.color': '#5a5a5a',
    'axes.facecolor': CREAM,
    'figure.facecolor': CREAM,
    'savefig.facecolor': CREAM,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.grid': True,
    'grid.color': '#c9bfa6',
    'grid.linestyle': ':',
    'grid.linewidth': 0.5,
})

HOURS = np.arange(1, T + 1)


# ---------- Plot 1: A1 schedule, per region ----------
fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)

for i, ax in enumerate(axes):
    ax.bar(HOURS, x_a1[i], color=NAVY, width=0.65, edgecolor='none')
    # overlay ceiling line
    ax.axhline(CMAX, color=RUST, linestyle='--', linewidth=1, alpha=0.7,
               label=f'capacity ceiling ({CMAX:.0f} MWh)')
    ax.set_xlabel('Hour of horizon')
    ax.set_title(f'Region {i+1}   '
                 r'$\sum_t x^{\star}_{r,t} = $' + f'{x_a1[i].sum():.0f} MWh'
                 + f'  =  $W_{i+1}$', fontsize=11, pad=10)
    ax.set_xticks(HOURS)
    ax.set_ylim(0, CMAX * 1.25)
    # annotate non-zero bars with values
    for h, v in zip(HOURS, x_a1[i]):
        if v > 0.01:
            ax.text(h, v + 0.4, f'{v:.0f}', ha='center', fontsize=9, color=NAVY)

axes[0].set_ylabel('Energy allocated (MWh)')
axes[0].legend(loc='upper left', frameon=False, fontsize=9)

fig.suptitle('Algorithm 1: deterministic schedule under known $\\rho$',
             fontsize=12, color=NAVY, y=1.02)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'toy_a1_schedule.pdf', bbox_inches='tight')
plt.savefig(OUTPUT_DIR / 'toy_a1_schedule.png', bbox_inches='tight', dpi=150)
plt.close()


# ---------- Plot 2: A1 vs A2b side-by-side at a representative epsilon ----------
eps_show = 10.0  # large enough to produce visible spreading away from greedy fill
xj_show = results[eps_show]['joint']['x']

fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
bar_width = 0.32

for i, ax in enumerate(axes):
    bars1 = ax.bar(HOURS - bar_width/2, x_a1[i], width=bar_width,
                   color=NAVY, label='A1 (deterministic)', edgecolor='none')
    bars2 = ax.bar(HOURS + bar_width/2, xj_show[i], width=bar_width,
                   color=GOLD_LIGHT, label=f'A2b (DRO, $\\varepsilon={eps_show}$, joint)',
                   edgecolor='none')
    ax.axhline(CMAX, color=RUST, linestyle='--', linewidth=1, alpha=0.7)
    ax.set_xlabel('Hour of horizon')
    ax.set_xticks(HOURS)
    ax.set_ylim(0, CMAX * 1.25)
    ax.set_title(f'Region {i+1}', fontsize=11)

axes[0].set_ylabel('Energy allocated (MWh)')
axes[0].legend(loc='upper left', frameon=False, fontsize=9)

fig.suptitle(
    f'A1 vs A2b: schedule comparison at $\\varepsilon = {eps_show}$  '
    f'(emissions: A1 = {obj_a1:.0f} kg,  A2b = {results[eps_show]["joint"]["linear"]:.0f} kg)',
    fontsize=12, color=NAVY, y=1.02)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'toy_a1_vs_a2b.pdf', bbox_inches='tight')
plt.savefig(OUTPUT_DIR / 'toy_a1_vs_a2b.png', bbox_inches='tight', dpi=150)
plt.close()


# ---------- Plot 3: A2b epsilon sweep ----------
fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True, sharey=True)
colors = [NAVY, GOLD_LIGHT, SAGE, RUST]

for idx, eps in enumerate(EPSILONS):
    ax = axes[idx // 2, idx % 2]
    xj = results[eps]['joint']['x']
    bw = 0.38
    for i in range(R):
        offset = (i - 0.5) * bw
        ax.bar(HOURS + offset, xj[i], width=bw, color=colors[i*2 % len(colors)],
               edgecolor='none',
               label=f'Region {i+1}' if idx == 0 else None)
    ax.axhline(CMAX, color=RUST, linestyle='--', linewidth=1, alpha=0.5)
    ax.set_title(f'$\\varepsilon = {eps}$   '
                 f'emissions = {results[eps]["joint"]["linear"]:.0f} kg,   '
                 f'penalty = {results[eps]["joint"]["penalty"]:.0f} kg',
                 fontsize=10)
    ax.set_xticks(HOURS)
    ax.set_ylim(0, CMAX * 1.25)
    if idx >= 2:
        ax.set_xlabel('Hour of horizon')
    if idx % 2 == 0:
        ax.set_ylabel('Energy allocated (MWh)')

axes[0, 0].legend(loc='upper left', frameon=False, fontsize=9)

fig.suptitle('Algorithm 2b (joint $\\widehat{\\Sigma}$): schedule as Wasserstein radius $\\varepsilon$ grows',
             fontsize=12, color=NAVY, y=1.01)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'toy_a2b_sweep.pdf', bbox_inches='tight')
plt.savefig(OUTPUT_DIR / 'toy_a2b_sweep.png', bbox_inches='tight', dpi=150)
plt.close()


# ---------- Plot 4: Joint vs Shuf at a single epsilon ----------
eps_compare = 10.0  # large enough that any difference is visible
xj = results[eps_compare]['joint']['x']
xs = results[eps_compare]['shuf']['x']

fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
bar_width = 0.32

for i, ax in enumerate(axes):
    ax.bar(HOURS - bar_width/2, xj[i], width=bar_width, color=NAVY,
           label='$\\widehat{\\Sigma}^{\\rm joint}$', edgecolor='none')
    ax.bar(HOURS + bar_width/2, xs[i], width=bar_width, color=GOLD_LIGHT,
           label='$\\widehat{\\Sigma}^{\\rm shuf}$ (block-diagonal)', edgecolor='none')
    ax.axhline(CMAX, color=RUST, linestyle='--', linewidth=1, alpha=0.5)
    ax.set_xlabel('Hour of horizon')
    ax.set_xticks(HOURS)
    ax.set_ylim(0, CMAX * 1.25)
    ax.set_title(f'Region {i+1}', fontsize=11)

axes[0].set_ylabel('Energy allocated (MWh)')
axes[0].legend(loc='upper left', frameon=False, fontsize=9)

diff = np.abs(xj - xs).max()
fig.suptitle(
    f'Algorithm 2b joint vs shuffled $\\widehat{{\\Sigma}}$ at $\\varepsilon = {eps_compare}$  '
    f'(max schedule deviation: {diff:.3f} MWh)',
    fontsize=12, color=NAVY, y=1.02)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'toy_joint_vs_shuf.pdf', bbox_inches='tight')
plt.savefig(OUTPUT_DIR / 'toy_joint_vs_shuf.png', bbox_inches='tight', dpi=150)
plt.close()


print("\n" + "=" * 78)
print("  PLOTS GENERATED")
print("=" * 78)
print(f"  Written to: {OUTPUT_DIR.resolve()}")
print("    toy_a1_schedule.pdf        - A1 deterministic schedule, per region")
print(f"    toy_a1_vs_a2b.pdf          - A1 vs A2b side-by-side at eps={eps_show}")
print("    toy_a2b_sweep.pdf          - A2b schedule as eps grows in {0, 5, 10, 25}")
print(f"    toy_joint_vs_shuf.pdf      - A2b joint vs shuffled covariance at eps={eps_compare}")
print("\n  All plots also saved as .png at 150 dpi for slide insertion.")
print()
