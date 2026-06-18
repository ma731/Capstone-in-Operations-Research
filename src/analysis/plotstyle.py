"""Publication-quality matplotlib style for the capstone figures.

One import, one call: ``from src.analysis.plotstyle import apply_style; apply_style()``.
Serif type (Times, to match the 12pt Times New Roman report), restrained spines, the
IE brand palette, and 300-dpi output, so every figure looks like a paper, not a default
matplotlib plot. Colours are exported for per-series use.
"""
from __future__ import annotations

import matplotlib as mpl

# --- IE brand palette ---
NAVY = "#0E2A52"
GOLD = "#E69F00"
SAGE = "#4A7C59"
RUST = "#B3402F"
BLUE = "#2E6FB0"
INK = "#16202E"
MUTED = "#5b6675"
LINE = "#d9dee6"
TINT = "#f3f6fb"
PALETTE = [NAVY, GOLD, SAGE, RUST, BLUE]


def apply_style() -> None:
    """Install the publication style globally for the current process."""
    mpl.rcParams.update({
        # type: serif to match the Times New Roman report body
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Tinos", "Georgia", "DejaVu Serif", "serif"],
        "mathtext.fontset": "stix",
        "font.size": 12,
        "axes.titlesize": 13.5,
        "axes.labelsize": 12.5,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "legend.fontsize": 11,
        # color + line
        "axes.prop_cycle": mpl.cycler(color=PALETTE),
        "lines.linewidth": 2.4,
        "lines.markersize": 6,
        "lines.solid_capstyle": "round",
        # axes: clean, light, no top/right spines
        "axes.edgecolor": "#33414f",
        "axes.linewidth": 0.9,
        "axes.labelcolor": INK,
        "axes.titlecolor": NAVY,
        "axes.titleweight": "bold",
        "axes.titlepad": 12,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.axisbelow": True,
        # grid: faint horizontal guidelines
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": LINE,
        "grid.linewidth": 0.8,
        "grid.alpha": 0.7,
        # ticks
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.direction": "out",
        "ytick.direction": "out",
        # output
        "figure.dpi": 120,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "figure.facecolor": "white",
        "legend.frameon": False,
    })


def save(fig, stem: str) -> None:
    """Save a figure to figures/<stem>.{png,pdf} at publication dpi."""
    from pathlib import Path
    Path("figures").mkdir(exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(f"figures/{stem}.{ext}")
