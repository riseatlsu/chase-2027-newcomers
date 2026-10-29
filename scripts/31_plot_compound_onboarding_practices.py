#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Elijah Phifer"
__contact__ = "elijah.phifer@lsu.edu"

"""
RQ3 panels (to what extent do the repositories implement practices that
support newcomer onboarding?), styled to match the compound panels from
13_plot_inflow.py and 30_plot_compound_newcomers_contributions.py.

Figure - onboarding practices (full width, 2 panels, 6.99in with one 0.06in gap):
  widths (1.1 + 2.1 + 0.15) + (0.55 + 2.95 + 0.08)
  a) % of repositories with each of the six onboarding practices (README,
     CONTRIBUTING, code of conduct, PR template, issue template, newcomer
     labels)
  b) % of repositories by how many of the six practices they have

Inputs:
  out/filtered_repo_dataset.csv   - study sample (472 repos)

Outputs:
  figs/compound/rq3_{1_practice_adoption,2_practice_count}.{png,eps}

Panels are sized to be included in LaTeX at natural size (no width/height)
so the fonts print at their true size.
"""

import os
import sys

import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import GREEN, RED, PANEL_BG, GRID_COLOR, GRID_LINEWIDTH

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
FILTERED_CSV = os.path.join(REPO_ROOT, "out", "filtered_repo_dataset.csv")
OUT_DIR = os.path.join(REPO_ROOT, "figs", "compound")

PRACTICES = ["has_readme", "has_contributing", "has_code_of_conduct",
             "has_pr_template", "has_issue_template", "has_newcomer_labels"]

# Shared with the compound panels in 13_plot_inflow.py / 30_plot_compound_newcomers_contributions.py
FONT = LABEL_FONT = CATEGORY_FONT = 10  # IEEEtran body text size; one size for all text
BLUE = "#3498DB"
AX_H, TOP, RIGHT = 1.3, 0.15, 0.08
BOTTOM = 0.38
LEFT = 0.55
RC = {"font.size": FONT, "font.weight": "normal", "axes.labelweight": "normal",
      "axes.linewidth": 1.0,
      # Times, like the IEEEtran body text, so 10 pt here looks like 10 pt there;
      # TrueType (Type 42) embedding, since IEEE PDF checks reject Type 3 fonts.
      "font.family": "serif", "font.serif": ["Times New Roman", "Times", "STIXGeneral"],
      "mathtext.fontset": "stix", "pdf.fonttype": 42, "ps.fonttype": 42}

PRACTICE_LABELS = {"has_readme": "README", "has_contributing": "CONTRIBUTING",
                   "has_code_of_conduct": "Code of conduct", "has_pr_template": "PR template",
                   "has_issue_template": "Issue template", "has_newcomer_labels": "Newcomer labels"}
# One color per practice; README uses the BLUE of the other compound panels.
PRACTICE_COLORS = {"has_readme": BLUE, "has_newcomer_labels": GREEN,
                   "has_contributing": "#F28E2B", "has_pr_template": RED,
                   "has_code_of_conduct": "#76B7B2", "has_issue_template": "#B07AA1"}


def new_panel(ax_w, ax_h=AX_H, bottom=BOTTOM, left=LEFT, top=TOP, right=RIGHT, grid_axis="y"):
    fig_w, fig_h = left + ax_w + right, bottom + ax_h + top
    fig = plt.figure(figsize=(fig_w, fig_h))
    ax = fig.add_axes([left / fig_w, bottom / fig_h, ax_w / fig_w, ax_h / fig_h])
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=FONT, length=2.5, pad=1.5)
    ax.set_facecolor(PANEL_BG)
    ax.grid(True, axis=grid_axis, color=GRID_COLOR, linewidth=GRID_LINEWIDTH)
    ax.set_axisbelow(True)
    return fig, ax


def save(fig, name):
    os.makedirs(OUT_DIR, exist_ok=True)
    base = os.path.join(OUT_DIR, name)
    fig.savefig(base + ".png", dpi=300)
    fig.savefig(base + ".eps")
    plt.close(fig)
    print(f"Saved: {base}.png/eps  ({fig.get_figwidth():.2f} x {fig.get_figheight():.2f} in)")


def pct_text(count, total):
    p = 100 * count / total
    return f"{count}\n({p:.1f}%)" if 0 < p < 1 else f"{count}\n({p:.0f}%)"


# ---------------------------------------------------------------------- #
#  Data                                                                    #
# ---------------------------------------------------------------------- #

def practice_flags(repos_df):
    return repos_df[PRACTICES].apply(lambda c: c.astype(str).str.lower().eq("true"))


def plot_practice_count(repos_df):
    has = practice_flags(repos_df)
    per_repo = has.sum(axis=1)
    levels = list(range(len(PRACTICES) + 1))
    counts = per_repo.value_counts().reindex(levels, fill_value=0)
    n = len(per_repo)
    print(f"  Practices per repo (n={n}): median {per_repo.median():g}; " +
          ", ".join(f"{k}: {v}" for k, v in counts.items()))

    with plt.rc_context(RC):
        fig, ax = new_panel(2.95)
        pct = 100 * counts.values / n
        ymax = 65
        if pct.max() > ymax * 0.8:
            print(f"  Warning: practice % near the y-limit {ymax}")
        ax.bar(levels, pct, width=0.7, color=BLUE, edgecolor="black", linewidth=0.8)
        for x, c, h in zip(levels, counts.values, pct):
            ax.text(x, h + ymax * 0.02, pct_text(c, n), ha="center", va="bottom",
                    fontsize=LABEL_FONT, linespacing=1.0)
        ax.set_ylim(0, ymax)
        ax.set_yticks(range(0, 61, 20))
        ax.set_xticks(levels)
        ax.set_xlim(-0.5, len(PRACTICES) + 0.5)
        ax.tick_params(axis="x", length=0)
        ax.set_xlabel("# Practices (of 6)", labelpad=1)
        ax.set_ylabel("% of repositories", labelpad=2)
        save(fig, "rq3_2_practice_count")
    return counts


def plot_practice_adoption(repos_df):
    """Horizontal bars: % of repositories with each practice, most common on top."""
    has = practice_flags(repos_df)
    n = len(has)
    counts = has.sum().sort_values()  # ascending, so barh puts the largest on top
    print("  Practice adoption: " + ", ".join(f"{PRACTICE_LABELS[k]} {v} ({100 * v / n:.0f}%)"
                                              for k, v in counts[::-1].items()))
    with plt.rc_context(RC):
        fig, ax = new_panel(1.9, left=1.3, right=0.15, grid_axis="x")  # right: "100" tick
        ax.set_xlim(0, 100)
        renderer = fig.canvas.get_renderer()
        for y, (key, c) in enumerate(counts.items()):
            pct = 100 * c / n
            ax.barh(y, pct, height=0.65, color=PRACTICE_COLORS[key], edgecolor="black", linewidth=0.8)
            label = ax.text(pct + 2, y, f"{c} ({pct:.0f}%)", ha="left", va="center",
                            fontsize=LABEL_FONT)
            if label.get_window_extent(renderer).x1 > ax.get_window_extent(renderer).x1:
                label.set_x(pct - 2)  # no room past the bar end: label inside it
                label.set_ha("right")
        ax.set_yticks(range(len(counts)), [PRACTICE_LABELS[k] for k in counts.index],
                      fontsize=CATEGORY_FONT)
        ax.tick_params(axis="y", length=0)
        ax.set_ylim(-0.55, len(counts) - 0.45)
        ax.set_xticks(range(0, 101, 50))
        ax.set_xlabel("% of repositories", labelpad=1)
        save(fig, "rq3_1_practice_adoption")


def main():
    repos_df = pd.read_csv(FILTERED_CSV)
    plot_practice_adoption(repos_df)
    plot_practice_count(repos_df)


if __name__ == "__main__":
    main()
