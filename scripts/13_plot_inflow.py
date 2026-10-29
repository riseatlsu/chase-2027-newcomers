#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Elijah Phifer"
__contact__ = "elijah.phifer@lsu.edu"

"""
RQ1 stratified inflow figure: mean newcomers per repository per month, grouped
by integrators, stars, ROS 2 distribution and owner type.

Input:
  scripts/tables/inflow.csv, scripts/tables/inflow_monthly.csv  (12_inflow.py)
  out/filtered_repo_dataset.csv                                (11_apply_exclusion_criteria.py)
Output:
  figs/compound/compound_{1_integrators,2_stars,3_distribution,4_owner}.{png,eps}
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import PANEL_BG, GRID_COLOR, GRID_LINEWIDTH

ZERO_PAD = 0.06  # fraction of the y-range shown below 0


class InflowVisualizer:
    def __init__(self, csv_path, output_folder, filtered_repos_csv):
        """
        Args:
            csv_path: Path to inflow.csv (written by 12_inflow.py); inflow_monthly.csv
                is read from the same folder
            output_folder: Folder to save the plots (panels go in its compound/ subfolder)
            filtered_repos_csv: Path to filtered_repo_dataset.csv (stratification variables)
        """
        self.csv_path = csv_path
        self.output_folder = output_folder
        self.filtered_repos_csv = filtered_repos_csv

        print(f"Loading data from: {csv_path}")
        self.df = pd.read_csv(csv_path)
        print(f"Loaded {len(self.df)} repositories")

        self.monthly_df = self._aggregate_to_monthly()
        self.month_columns = [col for col in self.monthly_df.columns if col != 'project']
        print(f"Loaded {len(self.month_columns)} months of data")

        # Per-repo stratification variables (integrators, stars)
        self.strat_df = self._load_stratification_data()

    def _extract_all_distributions(self):
        """
        Extract ALL ROS distributions for each repository (for multi-distro analysis).
        Returns a dictionary mapping project names to list of distributions.
        """
        if not self.filtered_repos_csv or not os.path.exists(self.filtered_repos_csv):
            print(f"Warning: Filtered repos CSV not found: {self.filtered_repos_csv}")
            return {row['project']: ['unknown'] for _, row in self.df.iterrows()}
        
        # Load the filtered repos dataset
        filtered_df = pd.read_csv(self.filtered_repos_csv)
        
        # Filter to only include repositories in inflow.csv
        allowed_projects = set(self.df['project'].values)
        filtered_df['project_key'] = filtered_df['Owner'] + '/' + filtered_df['Name']
        filtered_df = filtered_df[filtered_df['project_key'].isin(allowed_projects)]
        
        # Create a mapping using Owner/Name format to match inflow.csv project names
        distro_mapping = {}
        for _, row in filtered_df.iterrows():
            owner = row['Owner']
            name = row['Name']
            project_key = f"{owner}/{name}"
            distros = row.get('distros_present', '')
            
            if distros and '|' in distros:
                # Multiple distributions - return as list
                distro_mapping[project_key] = distros.split('|')
            elif distros:
                # Single distribution
                distro_mapping[project_key] = [distros]
            else:
                distro_mapping[project_key] = ['unknown']
        
        # Map each project in inflow.csv to its distributions
        repo_distros = {}
        for _, row in self.df.iterrows():
            project = row['project']
            if project in distro_mapping:
                repo_distros[project] = distro_mapping[project]
            else:
                repo_distros[project] = ['unknown']
        
        return repo_distros
    
    def _categorize_single_vs_multi_distro(self):
        """
        Categorize repositories as single-distro or multi-distro.
        Returns a dictionary mapping project names to category.
        """
        all_distros = self._extract_all_distributions()
        
        categorized = {}
        for project, distros in all_distros.items():
            if len(distros) == 1:
                categorized[project] = distros[0]
            else:
                categorized[project] = 'multi-distro'
        
        return categorized
    
    def _extract_owner_types(self):
        """
        Extract owner type (User/Organization) for each repository from filtered_repo_dataset.csv.
        Returns a dictionary mapping project names to owner types.
        """
        if not self.filtered_repos_csv or not os.path.exists(self.filtered_repos_csv):
            print(f"Warning: Filtered repos CSV not found: {self.filtered_repos_csv}")
            return {row['project']: 'unknown' for _, row in self.df.iterrows()}
        
        # Load the filtered repos dataset
        filtered_df = pd.read_csv(self.filtered_repos_csv)
        
        # Filter to only include repositories in inflow.csv
        allowed_projects = set(self.df['project'].values)
        filtered_df['project_key'] = filtered_df['Owner'] + '/' + filtered_df['Name']
        filtered_df = filtered_df[filtered_df['project_key'].isin(allowed_projects)]
        
        # Create a mapping using Owner/Name format to match inflow.csv project names
        owner_type_mapping = {}
        for _, row in filtered_df.iterrows():
            owner = row['Owner']
            name = row['Name']
            project_key = f"{owner}/{name}"
            owner_type = row.get('owner_type', 'unknown')
            
            # Normalize owner type
            if owner_type in ['User', 'Organization']:
                owner_type_mapping[project_key] = owner_type
            else:
                owner_type_mapping[project_key] = 'unknown'
        
        # Map each project in inflow.csv to its owner type
        repo_owner_types = {}
        unmapped_count = 0
        for _, row in self.df.iterrows():
            project = row['project']
            if project in owner_type_mapping:
                repo_owner_types[project] = owner_type_mapping[project]
            else:
                repo_owner_types[project] = 'unknown'
                unmapped_count += 1
        
        if unmapped_count > 0:
            print(f"  Could not find owner type for {unmapped_count} repositories")
        
        return repo_owner_types
    
    def _aggregate_to_monthly(self):
        """Load calendar-month inflow from inflow_monthly.csv (written by 12_inflow.py)."""
        monthly_csv = os.path.join(os.path.dirname(self.csv_path), 'inflow_monthly.csv')
        print(f"Loading calendar-month inflow from: {monthly_csv}")
        monthly = pd.read_csv(monthly_csv).set_index('project')
        monthly = monthly.reindex(self.df['project']).fillna(0).astype(int)
        return monthly.reset_index()

    def _load_stratification_data(self):
        """Load per-repo stratification columns from filtered_repo_dataset.csv."""
        if not self.filtered_repos_csv or not os.path.exists(self.filtered_repos_csv):
            print("Warning: filtered_repos_csv not available for stratification.")
            return None
        df = pd.read_csv(self.filtered_repos_csv)
        df['project_key'] = df['Owner'] + '/' + df['Name']
        allowed = set(self.df['project'].values)
        df = df[df['project_key'].isin(allowed)]
        return df.set_index('project_key')

    def _iqr_split(self, col):
        """Return strat_dict splitting repos into three tiers by IQR of col.

        Tier 1: value < Q1  (below interquartile range)
        Tier 2: Q1 <= value <= Q3  (within interquartile range)
        Tier 3: value > Q3  (above interquartile range)
        """
        if self.strat_df is None:
            return {}, 0, 0
        values = pd.to_numeric(self.strat_df[col], errors='coerce').dropna()
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        tier1 = f'Tier 1: < {q1:.0f}'
        tier2 = f'Tier 2: {q1:.0f}–{q3:.0f}'
        tier3 = f'Tier 3: > {q3:.0f}'
        strat = {}
        for project, row in self.strat_df.iterrows():
            val = pd.to_numeric(row.get(col), errors='coerce')
            if pd.isna(val):
                continue
            if val < q1:
                strat[project] = tier1
            elif val <= q3:
                strat[project] = tier2
            else:
                strat[project] = tier3
        return strat, q1, q3

    def _group_monthly(self, mapping):
        """Sum monthly inflow per group. Returns ({group: [counts]}, {group: n_repos})."""
        cols = self.month_columns
        totals, counts = {}, defaultdict(int)
        for _, row in self.monthly_df.iterrows():
            group = mapping.get(row['project'])
            if group is None:
                continue
            vals = pd.to_numeric(row[cols], errors='coerce').fillna(0).values
            totals[group] = totals.get(group, 0) + vals
            counts[group] += 1
        return totals, counts

    def plot_compound_panels(self):
        """Simplified panels for a 1x4 compound figure (integrators, stars,
        distribution, owner type), saved to figs/compound/. Each line is the
        group's mean newcomers per repository per month, so groups of
        different sizes can be compared.

        Sized to sit in one row across a 7.0in text width at 100% scale, so
        the fonts print at their true size. Every panel shares the same
        plot-area size and y-axis range; only the first panel carries the
        y-axis label and tick numbers, so it is wider than the others.
        Include each with \\includegraphics (no width/height) to keep scale.
        """
        TEXT_W, GAP = 7.0, 0.06           # row width and gap between panels (inches)
        LEFT, LEFT_LABEL = 0.06, 0.52     # left margin without / with y label + ticks
        RIGHT, BOTTOM, TOP = 0.08, 0.38, 0.42
        AX_W = (TEXT_W - 3 * GAP - LEFT_LABEL - 3 * LEFT - 4 * RIGHT) / 4
        AX_H = 1.05
        FONT = LEGEND_FONT = 10  # IEEEtran body text size; one size for all text
        YMAX, YSTEP = 1.0, 0.2

        def iqr_labels(col, fmt_low, fmt_mid, fmt_high):
            strat, q1, q3 = self._iqr_split(col)
            old = [f'Tier 1: < {q1:.0f}', f'Tier 2: {q1:.0f}–{q3:.0f}', f'Tier 3: > {q3:.0f}']
            new = [fmt_low.format(q1=q1, q3=q3), fmt_mid.format(q1=q1, q3=q3), fmt_high.format(q1=q1, q3=q3)]
            rename = dict(zip(old, new))
            return {p: rename[g] for p, g in strat.items()}, new

        integ_map, integ_order = iqr_labels('integrators_count', '0', '{q1:.0f}–{q3:.0f}', '>{q3:.0f}')
        stars_map, stars_order = iqr_labels('Number of stars', '<{q1:.0f}', '{q1:.0f}–{q3:.0f}', '>{q3:.0f}')
        # Integrator Q1 is 1, so "< Q1" means exactly 0; keep the label honest if that changes.
        if self._iqr_split('integrators_count')[1] != 1:
            integ_map, integ_order = iqr_labels('integrators_count', '<{q1:.0f}', '{q1:.0f}–{q3:.0f}', '>{q3:.0f}')

        distro_raw = self._categorize_single_vs_multi_distro()
        distro_map = {p: ('Multi' if c == 'multi-distro' else c.capitalize()) for p, c in distro_raw.items()}
        owner_map = {p: ('Org.' if o == 'Organization' else o) for p, o in self._extract_owner_types().items()}

        # Same colors and line styles as the standalone figures.
        tier_styles = [('#F1948A', '--'), ('#9B59B6', ':'), ('#7DCEA0', '-')]
        panels = [
            ('integrators', 'Integrators', integ_map, integ_order, tier_styles),
            ('stars', 'Stars', stars_map, stars_order, tier_styles),
            ('distribution', 'Distribution', distro_map, ['Multi', 'Humble', 'Jazzy', 'Kilted'],
             [('#F1948A', '-'), ('#1F618D', '-'), ('#7DCEA0', '-'), ('#9B59B6', '-')]),
            ('owner', 'Owner type', owner_map, ['Org.', 'User'],
             [('#3498DB', '-'), ('#E67E22', '--')]),
        ]

        out_dir = os.path.join(self.output_folder, 'compound')
        os.makedirs(out_dir, exist_ok=True)
        n_months = len(self.month_columns)

        with plt.rc_context({'font.size': FONT, 'font.weight': 'normal',
                             'axes.labelweight': 'normal', 'axes.linewidth': 1.0,
                             # Times, like the IEEEtran body text; Type 42 fonts for IEEE PDF checks.
                             'font.family': 'serif',
                             'font.serif': ['Times New Roman', 'Times', 'STIXGeneral'],
                             'mathtext.fontset': 'stix', 'pdf.fonttype': 42, 'ps.fonttype': 42}):
            for i, (key, title, mapping, order, styles) in enumerate(panels):
                totals, counts = self._group_monthly(mapping)
                totals = {g: v / counts[g] for g, v in totals.items()}  # mean per repository
                missing = set(totals) - set(order)
                if missing:
                    print(f"  Warning: {key} panel omits groups {sorted(missing)}")
                peak = max(max(v) for v in totals.values())
                if peak > YMAX:
                    print(f"  Warning: {key} peaks at {peak:.2f}, above shared YMAX={YMAX}")

                left = LEFT_LABEL if i == 0 else LEFT
                fig_w, fig_h = left + AX_W + RIGHT, BOTTOM + AX_H + TOP
                fig = plt.figure(figsize=(fig_w, fig_h))
                ax = fig.add_axes([left / fig_w, BOTTOM / fig_h, AX_W / fig_w, AX_H / fig_h])

                for group, (color, ls) in zip(order, styles):
                    if group not in totals:
                        continue
                    ax.plot(range(n_months), totals[group], color=color, linestyle=ls,
                            linewidth=2.0, label=group)

                ax.set_ylim(-ZERO_PAD * YMAX, YMAX)
                ax.set_yticks(np.arange(0, YMAX + YSTEP / 2, YSTEP))
                ax.set_xlim(-0.3, n_months - 0.7)
                ax.set_xticks(range(0, n_months, 3))
                ax.tick_params(labelsize=FONT, length=2.5, pad=1.5)
                ax.set_xlabel('Month', fontsize=FONT, labelpad=1)
                if i == 0:
                    ax.set_ylabel('Newcomers / repo', fontsize=FONT, labelpad=2)
                else:
                    ax.tick_params(axis='y', labelleft=False)
                ax.set_facecolor(PANEL_BG)
                ax.grid(True, axis='y', color=GRID_COLOR, linewidth=GRID_LINEWIDTH)
                ax.set_axisbelow(True)
                ax.spines[['top', 'right']].set_visible(False)

                # One legend row if it fits within the panel, otherwise two.
                # Legends fill column by column, so reorder entries to read
                # left to right across rows.
                handles, labels = ax.get_legend_handles_labels()
                for ncol in (len(order), 2):
                    idx = [i for c in range(ncol) for i in range(c, len(labels), ncol)]
                    legend = ax.legend([handles[i] for i in idx], [labels[i] for i in idx],
                                       loc='lower left', bbox_to_anchor=(-0.02, 1.0), ncol=ncol,
                                       frameon=False, handlelength=1.5,
                                       handletextpad=0.3, columnspacing=0.6, borderaxespad=0.1,
                                       labelspacing=0.3, prop={'size': LEGEND_FONT})
                    extent = legend.get_window_extent(fig.canvas.get_renderer())
                    if extent.x1 <= fig.bbox.x1:
                        break

                # Group sizes go in the LaTeX caption to keep the legends short.
                print(f"  {title}: " + ', '.join(f"{g} n={counts[g]}" for g in order if g in counts))
                base = os.path.join(out_dir, f'compound_{i + 1}_{key}')
                fig.savefig(base + '.png', dpi=300)
                fig.savefig(base + '.eps')
                plt.close(fig)
                print(f"Saved: {base}.png/eps")

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, 'tables', 'inflow.csv')
    output_folder = os.path.join(script_dir, '..', 'figs')
    filtered_repos_csv = os.path.join(script_dir, '..', 'out', 'filtered_repo_dataset.csv')

    if not os.path.exists(csv_path):
        print(f"ERROR: Could not find inflow.csv at: {csv_path}")
        print("Please run 12_inflow.py first to generate the data.")
    else:
        InflowVisualizer(csv_path, output_folder, filtered_repos_csv).plot_compound_panels()
