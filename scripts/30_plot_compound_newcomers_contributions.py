#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Elijah Phifer"
__contact__ = "elijah.phifer@lsu.edu"

"""
Panels for two compound figures in the paper, styled to match the
stratified compound panels from 13_plot_inflow.py (text printed at
true size, same color palette, y-ranges that start just below 0).

Figure 1 - newcomer overview (one column, 2 panels):
  a) mean newcomers per repository per month
  b) box plot of total newcomers per repository over the 12-month window

Figure 2 - newcomer contributions (full width, 3 panels):
  a) type of each newcomer's first commit (code/config/docs/other)
  b) lines added vs. deleted in each newcomer's first commit
  c) outcome of each newcomer's first PR to the repository (commit-based
     newcomers, first PR from the full history; see newcomer_first_prs.py):
     merged, closed without merging, or still open

Inputs:
  scripts/tables/inflow_monthly.csv          - from 12_inflow.py
  out/newcomer_first_commit_sizes.csv        - from 28_newcomer_first_commit_size_analysis.py
  scripts/data/ros_robotics_data/<owner>__<repo>/pull_requests.json

Outputs:
  figs/compound/overview_{1_monthly_mean,2_total_per_repo}.{png,eps}
  figs/compound/contrib_{1_types,2_size,3_pr_outcome}.{png,eps}

Panels are sized to be included in LaTeX at natural size (no width/height)
so the fonts print at their true size.
"""

import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.cbook import boxplot_stats

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import GREEN, RED, PANEL_BG, GRID_COLOR, GRID_LINEWIDTH
from newcomer_first_prs import newcomer_first_prs

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
MONTHLY_CSV = os.path.join(SCRIPT_DIR, "tables", "inflow_monthly.csv")
SIZES_CSV = os.path.join(REPO_ROOT, "out", "newcomer_first_commit_sizes.csv")
OUT_DIR = os.path.join(REPO_ROOT, "figs", "compound")

# Shared with the stratified compound panels (13_plot_inflow.py)
FONT = LABEL_FONT = CATEGORY_FONT = 10  # IEEEtran body text size; one size for all text
BLUE, GRAY = "#3498DB", "#95A5A6"
# One color per contribution type; code uses the BLUE of the other compound panels.
TYPE_COLORS = {"code": BLUE, "config": GREEN, "docs": "#F28E2B",
               "other": RED, "assets": "#76B7B2"}
ZERO_PAD = 0.06
AX_H, BOTTOM, TOP, RIGHT = 1.05, 0.38, 0.15, 0.08
BOTTOM_NO_XLABEL = 0.22  # category names only, no x-axis title
LEFT = 0.55          # room for tick numbers + y-axis label
BOX_LW = 1.5

RC = {"font.size": FONT, "font.weight": "normal", "axes.labelweight": "normal",
      "axes.linewidth": 1.0,
      # Times, like the IEEEtran body text, so 10 pt here looks like 10 pt there;
      # TrueType (Type 42) embedding, since IEEE PDF checks reject Type 3 fonts.
      "font.family": "serif", "font.serif": ["Times New Roman", "Times", "STIXGeneral"],
      "mathtext.fontset": "stix", "pdf.fonttype": 42, "ps.fonttype": 42}


def blend_with_white(hex_color, alpha):
    """Solid equivalent of hex_color at the given alpha over white (EPS has no alpha)."""
    rgb = np.array([int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]) / 255
    return tuple(alpha * rgb + (1 - alpha))


def new_panel(ax_w, ax_h=AX_H, bottom=BOTTOM, left=LEFT, right=RIGHT):
    fig_w, fig_h = left + ax_w + right, bottom + ax_h + TOP
    fig = plt.figure(figsize=(fig_w, fig_h))
    ax = fig.add_axes([left / fig_w, bottom / fig_h, ax_w / fig_w, ax_h / fig_h])
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=FONT, length=2.5, pad=1.5)
    ax.set_facecolor(PANEL_BG)
    ax.grid(True, axis="y", color=GRID_COLOR, linewidth=GRID_LINEWIDTH)
    ax.set_axisbelow(True)
    return fig, ax


def save(fig, name):
    os.makedirs(OUT_DIR, exist_ok=True)
    base = os.path.join(OUT_DIR, name)
    fig.savefig(base + ".png", dpi=300)
    fig.savefig(base + ".eps")
    plt.close(fig)
    print(f"Saved: {base}.png/eps")


def box(ax, data, fills, labels):
    """Box plots without outlier points, matching script 28's style."""
    bp = ax.boxplot(data, widths=0.55, patch_artist=True, showfliers=False,
                    boxprops=dict(linewidth=BOX_LW), whiskerprops=dict(linewidth=BOX_LW),
                    capprops=dict(linewidth=BOX_LW),
                    medianprops=dict(color="black", linewidth=BOX_LW + 0.5))
    for patch, fill in zip(bp["boxes"], fills):
        patch.set_facecolor(fill)
    ax.set_xticks(range(1, len(data) + 1), labels, fontsize=CATEGORY_FONT)
    top = max(boxplot_stats(d)[0]["whishi"] for d in data) * 1.1
    ax.set_ylim(-ZERO_PAD * top, top)


def pct_bars(ax, labels, counts, colors, ymax, as_counts=False):
    """Bars of % of total (or raw counts), each labeled with its count and percentage."""
    pct = 100 * np.array(counts) / sum(counts)
    heights = np.array(counts) if as_counts else pct
    ax.bar(labels, heights, width=0.65, color=colors, edgecolor="black", linewidth=0.8)
    for x, (c, p, h) in enumerate(zip(counts, pct, heights)):
        p_text = f"{p:.1f}" if 0 < p < 1 else f"{p:.0f}"
        ax.text(x, h + ymax * 0.02, f"{c:,}\n({p_text}%)", ha="center", va="bottom",
                fontsize=LABEL_FONT, linespacing=1.0)
    ax.set_ylim(0, ymax)
    ax.tick_params(axis="x", length=0, labelsize=CATEGORY_FONT)


# ---------------------------------------------------------------------- #
#  Data                                                                    #
# ---------------------------------------------------------------------- #

def first_pr_outcomes():
    """Outcome of each newcomer's first PR to the repository (commit-based
    newcomers; first PR taken from the full history, see newcomer_first_prs.py)."""
    prs, n_newcomers, n_no_pr = newcomer_first_prs()
    print(f"  Newcomers {n_newcomers}: {len(prs)} opened a PR, {n_no_pr} have no matching PR; "
          f"first PR opened {prs['opened'].value_counts().to_dict()}")
    return prs["outcome"].value_counts()


# ---------------------------------------------------------------------- #
#  Figures                                                                 #
# ---------------------------------------------------------------------- #

def plot_overview():
    monthly = pd.read_csv(MONTHLY_CSV).set_index("project")
    mean_per_month = monthly.mean(axis=0).values
    totals = monthly.sum(axis=1).values
    print(f"  Repos: {len(monthly)}; mean newcomers/repo/month "
          f"{mean_per_month.min():.2f}-{mean_per_month.max():.2f}; "
          f"12-month total per repo median {np.median(totals):.0f}, "
          f"Q1-Q3 {np.percentile(totals, 25):.0f}-{np.percentile(totals, 75):.0f}, "
          f"max {totals.max():.0f}")

    with plt.rc_context(RC):
        # One-column figure: taller panels leave room for the y-axis labels.
        overview_h = 1.3
        fig, ax = new_panel(1.55, overview_h)
        n = len(mean_per_month)
        ax.plot(range(n), mean_per_month, color=BLUE, linewidth=2.0,
                marker="o", markersize=3.5)
        ax.set_xticks(range(0, n, 3))
        ax.set_xlim(-0.3, n - 0.7)
        ax.set_ylim(-ZERO_PAD * 0.4, 0.4)
        ax.set_yticks(np.arange(0, 0.41, 0.1))
        ax.set_xlabel("Month", labelpad=1)
        ax.set_ylabel("Newcomers / repo", labelpad=2)
        save(fig, "overview_1_monthly_mean")

        fig, ax = new_panel(0.6, overview_h)
        box(ax, [totals], [blend_with_white(BLUE, 0.6)], [""])
        ax.set_yticks(range(0, int(ax.get_ylim()[1]) + 1, 2))
        ax.tick_params(axis="x", length=0)
        ax.set_xlabel("Per repo", labelpad=1)
        ax.set_ylabel("12-month total", labelpad=2)
        save(fig, "overview_2_total_per_repo")


def plot_contributions():
    sizes = pd.read_csv(SIZES_CSV)
    types = sizes["commit_type"].value_counts()
    order = ["code", "config", "docs", "other", "assets"]
    unexpected = set(types.index) - set(order)
    if unexpected:
        print(f"  Warning: commit types not plotted: {sorted(unexpected)}")
    type_counts = [int(types.get(t, 0)) for t in order]
    print(f"  First-commit types (n={sum(type_counts)}): " +
          ", ".join(f"{t} {c}" for t, c in zip(order, type_counts)))

    outcomes = first_pr_outcomes()
    pr_order = ["Merged", "Closed", "Open"]
    pr_counts = [int(outcomes.get(k, 0)) for k in pr_order]
    print(f"  First PR outcomes (n={sum(pr_counts)}): " +
          ", ".join(f"{k} {c}" for k, c in zip(pr_order, pr_counts)))

    with plt.rc_context(RC):
        # Margins trimmed to what the 10 pt text needs, so the category names
        # have room not to touch; 4-digit ticks need a wider left margin.
        fig, ax = new_panel(2.43, bottom=BOTTOM_NO_XLABEL, left=LEFT + 0.04, right=0.02)
        pct_bars(ax, [t.capitalize() for t in order], type_counts,
                 [TYPE_COLORS[t] for t in order], 1400, as_counts=True)
        ax.set_yticks(range(0, 1201, 400))
        ax.set_ylabel("# Newcomers", labelpad=2)
        save(fig, "contrib_1_types")

        fig, ax = new_panel(1.12, bottom=BOTTOM_NO_XLABEL, left=LEFT - 0.03, right=0.02)
        box(ax, [sizes["additions"].values, sizes["deletions"].values],
            [GREEN, RED], ["Added", "Deleted"])  # same fills as script 28
        ax.tick_params(axis="x", length=0)
        ax.set_ylabel("Lines changed", labelpad=2)
        save(fig, "contrib_2_size")

        fig, ax = new_panel(1.63, bottom=BOTTOM_NO_XLABEL, left=LEFT - 0.03, right=0.02)
        pct_bars(ax, pr_order, pr_counts, [GREEN, RED, GRAY], 120)  # headroom for the ~87% label
        ax.set_yticks(range(0, 101, 25))
        ax.set_ylabel("% of first PRs", labelpad=2)
        save(fig, "contrib_3_pr_outcome")


if __name__ == "__main__":
    plot_overview()
    plot_contributions()
