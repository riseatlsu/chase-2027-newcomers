#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Elijah Phifer"
__contact__ = "elijah.phifer@lsu.edu"

"""
First pull request of each newcomer, shared by 30_plot_compound_newcomers_contributions.py
(RQ2 outcome panel) and 34_paper_numbers.py (first-PR counts quoted in the text).

Newcomers keep the study's commit-based definition: an author whose first
commit to a repository falls in the study window (out/newcomer_first_commit_sizes.csv,
written by script 28; 1,624 newcomers). Each newcomer is matched to PR authors
of the same repository by GitHub login (case-insensitive), and their first PR
to that repository is taken from its full history, even if it was opened
before the window: that earlier PR is the newcomer's first attempt. Newcomers
with no matching PR (direct pushes, or commits with no GitHub login) are left
out. Bot accounts ([bot] logins) are ignored.

Because a newcomer is only on the list once a commit of theirs lands in the
repository, people whose first PR was rejected and who never contributed
again are not included (see Steinmacher et al.'s quasi-contributors).
Everything is cut off at the end of the study window (WINDOW_END): PRs opened
after it are ignored, and a PR merged or closed after it counts as still open.
The PR snapshots (09e_refresh_pull_requests.py) were taken after the window
ended, so they cover it in full.
"""

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
DATA_ROOT = os.path.join(SCRIPT_DIR, "data", "ros_robotics_data")
NEWCOMERS_CSV = os.path.join(REPO_ROOT, "out", "newcomer_first_commit_sizes.csv")

WINDOW_START, WINDOW_END = "2025-05-01", "2026-04-30"
_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _days(start, end):
    return (datetime.strptime(end, _FMT) - datetime.strptime(start, _FMT)).total_seconds() / 86400


def _by_end(ts):
    """True if the timestamp is set and falls on or before WINDOW_END."""
    return bool(ts) and ts[:10] <= WINDOW_END


def _prs_by_author(repo):
    path = os.path.join(DATA_ROOT, repo.replace("/", "__", 1), "pull_requests.json")
    with open(path, encoding="utf-8") as f:
        prs = json.load(f).get("data") or []
    by_author = {}
    for pr in prs:
        user = pr.get("user")
        if user and not user.endswith("[bot]"):
            by_author.setdefault(user.lower(), []).append(pr)
    for author_prs in by_author.values():
        author_prs[:] = [p for p in author_prs if p["created_at"][:10] <= WINDOW_END]
        author_prs.sort(key=lambda p: p["created_at"])
    return by_author


def newcomer_first_prs():
    """One row per commit-based newcomer who opened at least one PR, for their first PR.

    Columns: repo, outcome (Merged/Closed/Open as of WINDOW_END), days (to merge
    or close; NaN if open), opened (before window / in window), later_merged
    (a later PR was merged by WINDOW_END after a first PR that was not). Also returns the
    number of newcomers and how many had no matching PR.
    """
    newcomers = pd.read_csv(NEWCOMERS_CSV)
    cache, rows = {}, []
    for repo, author in zip(newcomers["repo"], newcomers["author"]):
        if repo not in cache:
            cache[repo] = _prs_by_author(repo)
        prs = cache[repo].get(str(author).lower())
        if not prs:
            continue
        first = prs[0]
        if _by_end(first.get("merged_at")):
            outcome, days = "Merged", _days(first["created_at"], first["merged_at"])
        elif _by_end(first.get("closed_at")):
            outcome, days = "Closed", _days(first["created_at"], first["closed_at"])
        else:
            outcome, days = "Open", np.nan
        created = first["created_at"][:10]
        opened = "before window" if created < WINDOW_START else "in window"
        later_merged = outcome != "Merged" and any(_by_end(p.get("merged_at")) for p in prs[1:])
        rows.append({"repo": repo, "outcome": outcome, "days": days, "opened": opened,
                     "later_merged": later_merged})
    df = pd.DataFrame(rows)
    return df, len(newcomers), len(newcomers) - len(df)


if __name__ == "__main__":
    df, n_newcomers, n_no_pr = newcomer_first_prs()
    print(f"{n_newcomers} newcomers; {n_no_pr} with no matching PR; {len(df)} first PRs")
    print(df["outcome"].value_counts().to_dict(), df["opened"].value_counts().to_dict())
