#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Elijah Phifer"
__contact__ = "elijah.phifer@lsu.edu"

"""
RQ1 significance tests for the stratified inflow figure (13_plot_inflow.py).

Each repository is one observation: its total newcomers over the 12 months.
The monthly counts of one repository are not independent, so the tests use
the per-repository totals rather than the monthly means drawn in the figure.
The totals are skewed counts with many zeros, so the tests are rank-based.

For each stratification (integrators, stars, distribution, owner type), every
pair of groups is compared with a two-sided Mann-Whitney U test, and the
p-values within the stratification are Holm-corrected
(scikit_posthocs.posthoc_mannwhitney). Owner type has one pair, so its
correction changes nothing. The U statistic and effect size come from
scipy.stats.mannwhitneyu; Cliff's delta is read off U, delta = 2U/(n1*n2) - 1
(positive when the first group tends to have more newcomers).

Groups are the same as in the figure (InflowVisualizer in 13_plot_inflow.py).

Input:
  scripts/tables/inflow.csv, scripts/tables/inflow_monthly.csv  (12_inflow.py)
  out/filtered_repo_dataset.csv                                (11_apply_exclusion_criteria.py)
Output:
  scripts/tables/inflow_group_tests.csv
"""

import importlib.util
import itertools
import os

import pandas as pd
import scikit_posthocs as sp
from scipy import stats

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(SCRIPT_DIR, 'tables', 'inflow_group_tests.csv')

# 13_plot_inflow.py starts with a digit, so it cannot be imported by name.
_spec = importlib.util.spec_from_file_location('plot_inflow', os.path.join(SCRIPT_DIR, '13_plot_inflow.py'))
plot_inflow = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plot_inflow)


def main():
    viz = plot_inflow.InflowVisualizer(
        os.path.join(SCRIPT_DIR, 'tables', 'inflow.csv'),
        os.path.join(SCRIPT_DIR, '..', 'figs'),
        os.path.join(SCRIPT_DIR, '..', 'out', 'filtered_repo_dataset.csv'))
    totals = viz.monthly_df.set_index('project')[viz.month_columns].sum(axis=1)

    # Same groups and labels as plot_compound_panels().
    integ, q1, q3 = viz._iqr_split('integrators_count')
    integ = {p: ('0' if g.startswith('Tier 1') else f'{q1:.0f}-{q3:.0f}' if g.startswith('Tier 2') else f'>{q3:.0f}')
             for p, g in integ.items()}
    stars, s1, s3 = viz._iqr_split('Number of stars')
    stars = {p: (f'<{s1:.0f}' if g.startswith('Tier 1') else f'{s1:.0f}-{s3:.0f}' if g.startswith('Tier 2') else f'>{s3:.0f}')
             for p, g in stars.items()}
    distro = {p: ('Multi' if c == 'multi-distro' else c.capitalize())
              for p, c in viz._categorize_single_vs_multi_distro().items()}
    owner = {p: ('Org.' if o == 'Organization' else o) for p, o in viz._extract_owner_types().items()}

    out = []
    print()
    for name, mapping, order in [
        ('integrators', integ, ['0', f'{q1:.0f}-{q3:.0f}', f'>{q3:.0f}']),
        ('stars', stars, [f'<{s1:.0f}', f'{s1:.0f}-{s3:.0f}', f'>{s3:.0f}']),
        ('distribution', distro, ['Multi', 'Humble', 'Jazzy', 'Kilted']),
        ('owner', owner, ['Org.', 'User']),
    ]:
        df = pd.DataFrame({'group': pd.Series(mapping)})
        df = df[df['group'].isin(order)].join(totals.rename('newcomers'))
        groups = {g: df.loc[df['group'] == g, 'newcomers'].values for g in order}
        print(f'[{name}] ' + ', '.join(f'{g} n={len(v)} median={pd.Series(v).median():g}'
                                       for g, v in groups.items()))

        p_holm = sp.posthoc_mannwhitney(df, val_col='newcomers', group_col='group',
                                        alternative='two-sided', p_adjust='holm')
        for a, b in itertools.combinations(order, 2):
            res = stats.mannwhitneyu(groups[a], groups[b], alternative='two-sided')
            delta = 2 * res.statistic / (len(groups[a]) * len(groups[b])) - 1
            print(f'    {a} vs {b}: U={res.statistic:.1f}, p={res.pvalue:.4g}, '
                  f'p_holm={p_holm.loc[a, b]:.4g}, Cliff\'s delta={delta:.3f}')
            out.append([name, a, b, len(groups[a]), len(groups[b]), res.statistic,
                        res.pvalue, p_holm.loc[a, b], delta])

    pd.DataFrame(out, columns=['factor', 'group_a', 'group_b', 'n_a', 'n_b', 'U', 'p', 'p_holm',
                               'cliffs_delta']).to_csv(OUT_PATH, index=False)
    print(f'\n[OK] saved {OUT_PATH}')


if __name__ == '__main__':
    main()
