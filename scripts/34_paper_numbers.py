#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Elijah Phifer"
__contact__ = "elijah.phifer@lsu.edu"

"""
Numbers quoted in the paper's text that no figure or other script output
shows: package-to-repository mapping shares, overlapping exclusion criteria,
newcomer concentration, first-commit extremes, first-PR follow-ups and survey
response counts.

Input:
  out/mapping_packages_to_github_with_index_html.csv  (05_fill_missing_from_index_html.py)
  out/diagnostics/non_github_url.csv                  (06_diagnose_unresolved.py)
  out/repos/github_repos_unique.csv                   (07_extract_unique_repos.py)
  out/final_repo_dataset.csv                          (10_build_final_repo_dataset.py)
  out/exclusion_summary.csv                           (11_apply_exclusion_criteria.py)
  out/filtered_repo_dataset.csv                       (11_apply_exclusion_criteria.py)
  scripts/tables/inflow_monthly.csv                   (12_inflow.py)
  out/newcomer_first_commit_sizes.csv                 (28_newcomer_first_commit_size_analysis.py)
  scripts/data/ros_robotics_data/*/pull_requests.json (via newcomer_first_prs.py)
  survey/response_counts.csv                          (29a_anonymize_survey.py)

Output:
  out/paper_numbers.csv
    section, statistic, value, description
"""

import os

import numpy as np
import pandas as pd

from newcomer_first_prs import newcomer_first_prs

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
OUT = os.path.join(REPO_ROOT, "out")
MAPPING_CSV = os.path.join(OUT, "mapping_packages_to_github_with_index_html.csv")
NON_GITHUB_CSV = os.path.join(OUT, "diagnostics", "non_github_url.csv")
UNIQUE_REPOS_CSV = os.path.join(OUT, "repos", "github_repos_unique.csv")
FINAL_CSV = os.path.join(OUT, "final_repo_dataset.csv")
EXCLUSION_CSV = os.path.join(OUT, "exclusion_summary.csv")
FILTERED_CSV = os.path.join(OUT, "filtered_repo_dataset.csv")
MONTHLY_CSV = os.path.join(SCRIPT_DIR, "tables", "inflow_monthly.csv")
SIZES_CSV = os.path.join(OUT, "newcomer_first_commit_sizes.csv")
SURVEY_COUNTS_CSV = os.path.join(REPO_ROOT, "survey", "response_counts.csv")
OUT_CSV = os.path.join(OUT, "paper_numbers.csv")

PRACTICES = ["has_readme", "has_contributing", "has_code_of_conduct",
             "has_pr_template", "has_issue_template", "has_newcomer_labels"]


def pct(part, whole):
    return round(100 * part / whole, 1)


def mapping_numbers(add):
    section = "Method: mapping packages to repositories"
    mapping = pd.read_csv(MAPPING_CSV)
    n_entries = len(mapping)
    n_non_github = len(pd.read_csv(NON_GITHUB_CSV))
    n_no_url = int(mapping["repo_url"].isna().sum())
    add(section, "package_entries", n_entries,
        "Packages listed on ROS Index for Humble, Jazzy and Kilted (one entry per package and distribution)")
    add(section, "entries_not_github", n_non_github,
        "Entries whose source repository is hosted outside GitHub")
    add(section, "entries_not_github_pct", pct(n_non_github, n_entries), "% of package entries")
    add(section, "entries_no_repository", n_no_url, "Entries with no repository URL in rosdistro or ROS Index")
    add(section, "entries_no_repository_pct", pct(n_no_url, n_entries), "% of package entries")

    repos = pd.read_csv(UNIQUE_REPOS_CSV)
    n_repos = len(repos)
    multi_distro = int((repos["n_distros"] > 1).sum())
    multi_pkg = repos["n_packages_total"] > 1
    add(section, "unique_github_repos", n_repos,
        "Unique GitHub repositories after merging distributions and renamed/transferred repositories")
    add(section, "repos_in_multiple_distros", multi_distro,
        "Repositories released for more than one distribution (merged into one entry, not excluded)")
    add(section, "repos_in_multiple_distros_pct", pct(multi_distro, n_repos), "% of unique repositories")
    add(section, "repos_hosting_multiple_packages", int(multi_pkg.sum()),
        "Repositories that host more than one package")
    add(section, "repos_hosting_multiple_packages_pct", pct(multi_pkg.sum(), n_repos), "% of unique repositories")
    add(section, "packages_in_shared_repos", int(repos.loc[multi_pkg, "n_packages_total"].sum()),
        "Distinct packages that live in a repository shared with other packages")
    add(section, "packages_in_shared_repos_pct",
        pct(repos.loc[multi_pkg, "n_packages_total"].sum(), repos["n_packages_total"].sum()),
        "% of distinct packages in GitHub repositories")
    add(section, "repos_with_data", len(pd.read_csv(FINAL_CSV)),
        "Repositories with collected GitHub data (input to the exclusion criteria)")


def exclusion_numbers(add):
    section = "Method: filtering repositories"
    excl = pd.read_csv(EXCLUSION_CSV)
    reasons = excl["exclusion_reasons"].fillna("").astype(str)
    excluded = reasons.str.len() > 0
    multiple = reasons.str.contains(r"[;,|]")
    add(section, "repos_excluded", int(excluded.sum()), "Repositories meeting at least one exclusion criterion")
    add(section, "repos_multiple_criteria", int(multiple.sum()),
        "Excluded repositories meeting more than one criterion")
    add(section, "repos_multiple_criteria_pct_of_excluded", pct(multiple.sum(), excluded.sum()),
        "% of excluded repositories")
    add(section, "repos_multiple_criteria_pct_of_all", pct(multiple.sum(), len(pd.read_csv(FINAL_CSV))),
        "% of all repositories with collected data")


def rq1_numbers(add):
    section = "RQ1: newcomer inflow"
    monthly = pd.read_csv(MONTHLY_CSV).set_index("project")
    totals = monthly.sum(axis=1).sort_values(ascending=False)
    n_repos, n_newcomers = len(totals), int(totals.sum())
    top_n = int(n_repos * 0.10)
    add(section, "newcomers_total", n_newcomers, "Newcomers across all repositories, May 2025 - April 2026")
    add(section, "newcomers_per_month_mean", round(n_newcomers / monthly.shape[1], 1),
        "Mean newcomers per month across all repositories")
    add(section, "newcomers_per_repo_median", float(totals.median()), "Median 12-month total per repository")
    add(section, "repos_no_newcomers", int((totals == 0).sum()), "Repositories with no newcomers in the 12 months")
    add(section, "repos_no_newcomers_pct", pct((totals == 0).sum(), n_repos), "% of repositories")
    add(section, "top10pct_repos", top_n, "Number of repositories in the top 10% by newcomers")
    add(section, "top10pct_newcomer_share_pct", pct(totals.iloc[:top_n].sum(), n_newcomers),
        "% of all newcomers received by the top 10% of repositories")


def rq2_numbers(add):
    section = "RQ2: first contributions"
    sizes = pd.read_csv(SIZES_CSV)
    n = len(sizes)
    for col in ("additions", "deletions"):
        q1, med, q3 = np.percentile(sizes[col], [25, 50, 75])
        add(section, f"first_commit_{col}_median", float(med), f"Median lines {col[:-1] + 'ed'} in a first commit")
        add(section, f"first_commit_{col}_q1", float(q1), "First quartile")
        add(section, f"first_commit_{col}_q3", float(q3), "Third quartile")
        add(section, f"first_commit_{col}_max", int(sizes[col].max()), "Largest first commit")
    add(section, "first_commit_additions_p99", float(np.percentile(sizes["additions"], 99)),
        "99th percentile of lines added in a first commit")
    thousands = int((sizes["additions"] >= 1000).sum())
    add(section, "first_commits_adding_1000_plus", thousands, "First commits adding at least 1,000 lines")
    add(section, "first_commits_adding_1000_plus_pct", pct(thousands, n), "% of first commits")

    prs, n_newcomers, n_no_pr = newcomer_first_prs()
    not_merged = prs["outcome"] != "Merged"
    add(section, "newcomers_with_pr", len(prs), "Newcomers who opened a PR by April 30, 2026")
    add(section, "newcomers_without_pr", n_no_pr, "Newcomers with no matching PR by April 30, 2026")
    add(section, "first_pr_before_window", int((prs["opened"] == "before window").sum()),
        "Newcomers whose first PR was opened before May 1, 2025")
    add(section, "first_pr_not_merged", int(not_merged.sum()), "First PRs closed or still open on April 30, 2026")
    add(section, "first_pr_not_merged_later_merged", int(prs["later_merged"].sum()),
        "Of those, newcomers who had a later PR merged by April 30, 2026")


def rq3_numbers(add):
    section = "RQ3: onboarding practices"
    repos = pd.read_csv(FILTERED_CSV)
    per_repo = repos[PRACTICES].apply(lambda c: c.astype(str).str.lower().eq("true")).sum(axis=1)
    four_plus = int((per_repo >= 4).sum())
    add(section, "repos_4plus_practices", four_plus, "Repositories with four or more of the six practices")
    add(section, "repos_4plus_practices_pct", pct(four_plus, len(repos)), "% of repositories")


def survey_numbers(add):
    section = "RQ4: survey"
    for _, row in pd.read_csv(SURVEY_COUNTS_CSV).iterrows():
        add(section, f"responses_{row['stage']}", int(row["n"]), row["description"])


def main():
    rows = []

    def add(section, statistic, value, description):
        value = float(value)
        value = int(value) if value.is_integer() else round(value, 1)
        rows.append({"section": section, "statistic": statistic, "value": value, "description": description})

    mapping_numbers(add)
    exclusion_numbers(add)
    rq1_numbers(add)
    rq2_numbers(add)
    rq3_numbers(add)
    survey_numbers(add)

    out = pd.DataFrame(rows, dtype=object)
    out.to_csv(OUT_CSV, index=False)
    with pd.option_context("display.max_rows", None, "display.width", 120):
        print(out[["section", "statistic", "value"]].to_string(index=False))
    print(f"\n[OK] saved {OUT_CSV} ({len(out)} numbers)")


if __name__ == "__main__":
    main()
