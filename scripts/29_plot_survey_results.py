#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Elijah Phifer"
__contact__ = "elijah.phifer@lsu.edu"

"""
Compound-figure panels for the numerical and yes/no questions of the
maintainer onboarding survey (Qualtrics export), styled to match the
compound panels from 13_plot_inflow.py and 30_plot_compound_newcomers_contributions.py
(true-size 10pt text, same green/red palette).

Reads the anonymized responses written by 29a_anonymize_survey.py: the 22
respondents who consented (online consent and, for EU respondents, GDPR
consent) and finished the survey.

Figure A - respondent background (one column, 2 panels):
  a) years of experience in software development, OSS and ROS
  b) number of OSS projects contributed to
  Outliers (beyond 1.5xIQR) are not drawn, matching the other box plots.

Figure B - onboarding in the project community (full width, 2 panels):
  a) Q3_1 importance of onboarding to project sustainability (1-5 Likert)
  b) Q1 / Q18 / Q21 / Q24 yes/no questions

Table - respondent demographics (highest degree, major, profession) as a
  LaTeX table, since these are categorical counts.

Input:
  survey/responses_anonymized.csv

Output (figs/compound/):
  survey_bg_{1_experience,2_projects}.{png,eps}
  survey_onboarding_{1_importance,2_yes_no}.{png,eps}
  survey_demographics_table.tex

Panels are sized to be included in LaTeX at natural size (no width/height)
so the fonts print at their true size.
"""

import os
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
from config import PROJECT_ROOT, GREEN, RED, PANEL_BG, GRID_COLOR, GRID_LINEWIDTH

IN_PATH = PROJECT_ROOT / "survey" / "responses_anonymized.csv"
OUT_DIR = PROJECT_ROOT / "figs" / "compound"

# Shared with the compound panels in 13_plot_inflow.py / 30_plot_compound_newcomers_contributions.py
FONT = LABEL_FONT = CATEGORY_FONT = 10  # IEEEtran body text size; one size for all text
BLUE, NEUTRAL = "#3498DB", "#D5D8DC"
ZERO_PAD = 0.06
RIGHT, BOTTOM, BOTTOM_NO_XLABEL = 0.08, 0.38, 0.22
LEFT = 0.55          # room for tick numbers + y-axis label
BOX_LW = 1.5
GAP = 0.06           # \hspace between panels in LaTeX
RC = {"font.size": FONT, "font.weight": "normal", "axes.labelweight": "normal",
      "axes.linewidth": 1.0,
      # Times, like the IEEEtran body text, so 10 pt here looks like 10 pt there;
      # TrueType (Type 42) embedding, since IEEE PDF checks reject Type 3 fonts.
      "font.family": "serif", "font.serif": ["Times New Roman", "Times", "STIXGeneral"],
      "mathtext.fontset": "stix", "pdf.fonttype": 42, "ps.fonttype": 42}

YES_COLOR, NO_COLOR = GREEN, RED

EXPERIENCE_COLS = [
    ("Software Experience", "Software"),
    ("OSS Experience", "OSS"),
    ("ROS Experience", "ROS"),
]

# Substantive yes/no questions (consent, follow-up and "anything else?" items are omitted).
YES_NO_QUESTIONS = [
    ("Q1", "Community actively tries\nto attract newcomers"),
    ("Q18", "Formal onboarding\nprocess"),
    ("Q21", "Resources dedicated to\nnewcomer support"),
    ("Q24", "AI-based solutions could\nhelp support newcomers"),
]


def blend_with_white(hex_color, alpha):
    """Solid equivalent of hex_color at the given alpha over white (EPS has no alpha)."""
    rgb = np.array([int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]) / 255
    return tuple(alpha * rgb + (1 - alpha))


# Diverging red -> neutral -> green scale for the 1-5 Likert item.
LIKERT_COLORS = [RED, blend_with_white(RED, 0.5), NEUTRAL, blend_with_white(GREEN, 0.5), GREEN]
LIKERT_LABELS = ["1\nNot at all", "2", "3", "4", "5\nExtremely"]


def load_responses(path) -> pd.DataFrame:
    # Already filtered to consented, finished respondents by 29a_anonymize_survey.py.
    return pd.read_csv(path)


def numeric(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce").dropna()


def new_panel(ax_w, ax_h, bottom=BOTTOM, left=LEFT, top=0.15, right=RIGHT, grid_axis="y"):
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


def tukey_split(s, k=1.5):
    """Split s into (kept, outliers) using the box plot's fences Q1 - k*IQR, Q3 + k*IQR."""
    q1, q3 = s.quantile([0.25, 0.75])
    mask = s.between(q1 - k * (q3 - q1), q3 + k * (q3 - q1))
    return s[mask], s[~mask]


def box(ax, series_list, labels):
    """Vertical box plots without outliers (beyond 1.5xIQR); returns the top whisker across boxes."""
    ax.boxplot([s.values for s in series_list], widths=0.55, patch_artist=True, showfliers=False,
               boxprops=dict(linewidth=BOX_LW, facecolor=blend_with_white(BLUE, 0.6)),
               whiskerprops=dict(linewidth=BOX_LW), capprops=dict(linewidth=BOX_LW),
               medianprops=dict(color="black", linewidth=BOX_LW + 0.5))
    for s, label in zip(series_list, labels):
        outliers = tukey_split(s)[1]
        if len(outliers):
            print(f"  {label}: {len(outliers)} outliers not shown: {sorted(outliers.tolist())}")
    ax.set_xticks(range(1, len(series_list) + 1), labels, fontsize=CATEGORY_FONT)
    ax.tick_params(axis="x", length=0)
    return max(tukey_split(s)[0].max() for s in series_list)


def stacked_yes_no(ax, rows, label_font=CATEGORY_FONT):
    """Horizontal 100% stacked Yes/No bars, one per (label, answers) row, top to bottom.
    Each segment is labeled with its count and percentage."""
    y = np.arange(len(rows))[::-1]
    for yi, (_, answers) in zip(y, rows):
        n = len(answers)
        n_yes = int(answers.eq("Yes").sum())
        segments = ((0, n_yes, YES_COLOR), (100 * n_yes / n, n - n_yes, NO_COLOR))
        for left, count, color in segments:
            width = 100 * count / n
            ax.barh(yi, width, left=left, height=0.7, color=color, edgecolor="black", linewidth=0.8)
            if not count:
                continue
            label = ax.text(left + width / 2, yi, f"{count} ({width:.0f}%)", ha="center",
                            va="center", fontsize=LABEL_FONT, clip_on=False)
            if not fits_inside(ax, label, width):
                # Too narrow: place it just past the segment (past 100% for the
                # right-hand segment, into the panel's right margin).
                label.set_x(left + width + 1.5)
                label.set_ha("left")
    ax.set_yticks(y, [label for label, _ in rows], fontsize=label_font, linespacing=1.0)
    ax.tick_params(axis="y", length=0)
    ax.set_ylim(-0.55, len(rows) - 0.45)
    ax.set_xlim(0, 100)
    ax.set_xticks(range(0, 101, 25))
    ax.set_xlabel("% of respondents", labelpad=1)


def fits_inside(ax, text, width_pct, pad_px=6):
    """Whether the rendered text fits inside a bar segment width_pct (% of the x-axis) wide."""
    renderer = ax.figure.canvas.get_renderer()
    seg_px = ax.get_window_extent(renderer).width * width_pct / 100
    return text.get_window_extent(renderer).width + pad_px <= seg_px



def yes_no_legend(ax):
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=c, edgecolor="black", linewidth=0.8)
               for c in (YES_COLOR, NO_COLOR)]
    ax.legend(handles, ["Yes", "No"], loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2,
              frameon=False, handlelength=1.2, handletextpad=0.4, columnspacing=1.0,
              borderaxespad=0.1, fontsize=LABEL_FONT)


# ---------------------------------------------------------------------- #
#  Figures                                                                 #
# ---------------------------------------------------------------------- #

def plot_background(df):
    """Figure A: one-column, two panels (3.47in total with the LaTeX gap)."""
    exp = [numeric(df, col) for col, _ in EXPERIENCE_COLS]
    projects = numeric(df, "Contributions")
    ax_h = 1.3
    with plt.rc_context(RC):
        fig, ax = new_panel(1.68, ax_h, bottom=BOTTOM_NO_XLABEL, left=LEFT - 0.08)
        top = 40
        if box(ax, exp, [lbl for _, lbl in EXPERIENCE_COLS]) > top:
            print(f"  Warning: experience above y-limit {top}")
        ax.set_xlim(0.35, 3.5)  # room left of "Software" so it clears the "0" tick
        ax.set_ylim(-ZERO_PAD * top, top)
        ax.set_yticks(range(0, top + 1, 10))
        ax.set_ylabel("Years of experience", labelpad=2)
        save(fig, "survey_bg_1_experience")

        fig, ax = new_panel(0.55, ax_h, bottom=BOTTOM_NO_XLABEL)
        top = 30
        if box(ax, [projects], ["Projects"]) > top:
            print(f"  Warning: projects above y-limit {top}")
        ax.set_ylim(-ZERO_PAD * top, top)
        ax.set_yticks(range(0, top + 1, 10))
        ax.set_ylabel("# OSS projects", labelpad=2)
        save(fig, "survey_bg_2_projects")
    return exp, projects


def plot_onboarding(df):
    """Figure B: full width, two panels (6.99in total with the LaTeX gap)."""
    imp = numeric(df, "Q3_1").astype(int)
    levels = [1, 2, 3, 4, 5]
    counts = imp.value_counts().reindex(levels, fill_value=0).values
    rows = [(label, df[col].dropna()) for col, label in YES_NO_QUESTIONS]

    # Taller than the other panels so the two-line question labels don't touch.
    ax_h, top = 1.5, 0.3  # room above the yes/no bars for the legend; same height for both panels
    with plt.rc_context(RC):
        # Wide enough that neighbouring two-line bar labels don't touch.
        fig, ax = new_panel(2.45, ax_h, left=LEFT - 0.1, top=top, right=0.1)  # right: "Extremely"
        n = counts.sum()
        ymax = 10
        if counts.max() > ymax * 0.75:
            print(f"  Warning: Likert counts near the y-limit {ymax}")
        ax.bar(levels, counts, width=0.65, color=LIKERT_COLORS, edgecolor="black", linewidth=0.8)
        for lvl, c in zip(levels, counts):
            ax.text(lvl, c + ymax * 0.02, f"{c}\n({100 * c / n:.0f}%)", ha="center", va="bottom",
                    fontsize=LABEL_FONT, linespacing=1.0)
        ax.set_ylim(0, ymax)
        ax.set_yticks(range(0, ymax + 1, 2))
        ax.set_xticks(levels, LIKERT_LABELS, fontsize=CATEGORY_FONT, linespacing=1.0)
        ax.set_xlim(0.3, 5.6)  # room beside the outer bars for "Not at all" / "Extremely"
        ax.tick_params(axis="x", length=0)
        ax.set_ylabel("# Respondents", labelpad=2)
        save(fig, "survey_onboarding_1_importance")

        # Total width: (0.45 + 2.45 + 0.1) + GAP + (1.57 + 1.76 + 0.6) = 6.99in;
        # the right margin holds labels of segments too narrow to label inside.
        label_w, bars_w = 1.57, 1.76
        fig, ax = new_panel(bars_w, ax_h, left=label_w, top=top, right=0.6, grid_axis="x")
        stacked_yes_no(ax, rows)
        # Rules between rows, extended left under the two-line question labels,
        # so each label clearly belongs to its bar.
        x0 = -(label_w - 0.03) / bars_w  # left edge of the label area, in axes fractions
        for boundary in np.arange(len(rows) - 1.5, 0, -1):
            ax.axhline(boundary, xmin=x0, xmax=1, color="#BBBBBB", linewidth=0.6, clip_on=False)
        yes_no_legend(ax)
        save(fig, "survey_onboarding_2_yes_no")
    return imp, rows



# Answer text -> table label, in table order. Unlisted answers are reported as a warning.
DEMOGRAPHICS = [
    ("Education Level", "Degree", [
        ("Doctorate (Ph.D, M.D., J.D., etc.)", "Doctorate"),
        ("Maser's degree (M.S., M.A., etc.)", "Master's"),  # typo is in the survey's answer text
        ("Bachelor's degree (4 year degree)", "Bachelor's"),
        ("Some college, no degree", "Some college, no degree"),
        ("Less than high school", "Less than high school"),
    ]),
    ("Major", "Major", [
        ("Computer Science", "Computer science"),
        ("Computer Engineering", "Computer engineering"),
        ("Electrical Engineering", "Electrical engineering"),
        ("Mechanical Engineering", "Mechanical engineering"),
        ("Industrial Engineering", "Industrial engineering"),
        ("Other", "Other"),
    ]),
    ("Profession", "Profession", [
        ("Industry", "Industry"),
        ("Academia", "Academia"),
        ("Student", "Student"),
        ("Other", "Other"),
    ]),
]


def write_demographics_table(df):
    """Column-wide LaTeX table of respondent demographics, in the paper's table style
    (\\small tabularx at \\columnwidth, booktabs rules); answers nobody chose are omitted."""
    n = len(df)
    lines = [
        "% Requires \\usepackage{booktabs,tabularx}. Generated by scripts/29_plot_survey_results.py.",
        "\\begin{table}[h]",
        "    \\centering",
        f"    \\caption{{Demographics of the {n} survey participants.}}",
        "    \\label{tab:survey-demographics}",
        "    \\small",
        "    \\begin{tabularx}{\\columnwidth}{@{}l X rr@{}}",
        "        \\toprule",
        "        \\textbf{Category} & \\textbf{Response} & \\textbf{n} & \\textbf{\\%} \\\\",
    ]
    for col, heading, answers in DEMOGRAPHICS:
        counts = df[col].value_counts()
        unknown = set(counts.index) - {a for a, _ in answers}
        if unknown:
            print(f"  Warning: {col} answers missing from the table: {sorted(unknown)}")
        # Most common first, "Other" last.
        rows = sorted(((counts.get(a, 0), label) for a, label in answers if counts.get(a, 0)),
                      key=lambda r: (r[1] == "Other", -r[0]))
        lines.append("        \\midrule")
        for i, (c, label) in enumerate(rows):
            # Category name on its group's first row only, like the RQ column of the metrics table.
            lines.append(f"        {heading if i == 0 else '   '} & {label} & {c} & {100 * c / n:.1f} \\\\")
    lines += ["        \\bottomrule", "    \\end{tabularx}", "\\end{table}", ""]
    path = os.path.join(OUT_DIR, "survey_demographics_table.tex")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Saved: {path}")


def main():
    df = load_responses(IN_PATH)
    print(f"[INFO] {len(df)} respondents who consented and finished the survey")

    exp, projects = plot_background(df)
    imp, yes_no = plot_onboarding(df)
    write_demographics_table(df)

    print("\n[SUMMARY]")
    for (col, _), s in zip(EXPERIENCE_COLS + [("Contributions", "")], exp + [projects]):
        print(f"  {col:<20} n={len(s):2d} median={s.median():5.1f} mean={s.mean():5.1f} "
              f"min={s.min():g} max={s.max():g}")
    print(f"  {'Q3_1 importance':<20} n={len(imp):2d} median={imp.median():g} "
          f"counts={imp.value_counts().sort_index().to_dict()}")
    print("\n  Yes/no questions:")
    for (col, _), (_, answers) in zip(YES_NO_QUESTIONS, yes_no):
        print(f"    {col:<4} n={len(answers):2d} yes={answers.eq('Yes').sum():2d} no={answers.eq('No').sum():2d}")


if __name__ == "__main__":
    main()
