#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Elijah Phifer"
__contact__ = "elijah.phifer@lsu.edu"

"""
Size (lines added/deleted) of each newcomer's first commit.

Re-derives the exact same newcomer set as 12_inflow.py (per-repo first
in-window commit, author identity = author_login else raw author name,
pre-window authors excluded) directly from each repo's commits.json, then
looks up that commit's additions/deletions.

first_commits_by_author.json (built once by script 09) is NOT used as the
source of truth here: it can go stale relative to commits.json whenever a
repo's commits.json gets refreshed (new real-world commits land) without
first_commits_by_author.json being regenerated - script 09 only rebuilds it
when the file is entirely missing, not when it's out of date. Checked
2026-09-24: 332 of 1,624 true newcomers (20.4%) had a stale or missing
entry there. Where a cached entry's date matches the freshly-computed
first-window date exactly, it's reused (no API call needed); otherwise the
commit's stats are fetched live via /repos/{owner}/{repo}/commits/{sha}.

Input:
  out/filtered_repo_dataset.csv                              - study sample (472 repos)
  scripts/data/ros_robotics_data/<owner>__<repo>/commits.json - full commit history
  scripts/data/ros_robotics_data/<owner>__<repo>/first_commits_by_author.json - cache, reused where still valid

Output:
  out/newcomer_first_commit_sizes.csv
    repo, author, date, additions, deletions, files_changed, commit_type, source
    (plotted by 30_plot_compound_newcomers_contributions.py)
"""

import os
import csv
import json
import time
from datetime import datetime, date

import requests
from dotenv import load_dotenv

from commit_type_classifier import classify_from_files_v2

load_dotenv()

WINDOW_START = date(2025, 5, 1)
REFERENCE_DATE = date(2026, 4, 30)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
DATA_ROOT = os.path.join(SCRIPT_DIR, "data", "ros_robotics_data")
FILTERED_CSV = os.path.join(REPO_ROOT, "out", "filtered_repo_dataset.csv")

OUT_CSV = os.path.join(REPO_ROOT, "out", "newcomer_first_commit_sizes.csv")

TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}" if TOKEN else "",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
REQUEST_SLEEP = 0.2
REQUEST_TIMEOUT = 30


def load_json_data(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return d.get("data", d) if isinstance(d, dict) else d


def extract_author_and_date(commit):
    author = commit.get("author_login") or commit.get("author")
    return author, commit.get("date")


def find_newcomer_first_commits(commits):
    """Same logic as 12_inflow.py's get_project_weekly_series, but also
    keeps the commit sha so the size lookup below can find the right one."""
    pre_window_authors = set()
    for c in commits:
        author, date_str = extract_author_and_date(c)
        if author and date_str:
            try:
                d = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").date()
            except Exception:
                continue
            if d < WINDOW_START:
                pre_window_authors.add(author)

    first_window = {}  # author -> (date, sha)
    for c in commits:
        author, date_str = extract_author_and_date(c)
        if not (author and date_str):
            continue
        try:
            d = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").date()
        except Exception:
            continue
        if WINDOW_START <= d <= REFERENCE_DATE and author not in pre_window_authors:
            if author not in first_window or d < first_window[author][0]:
                first_window[author] = (d, c.get("sha"))

    return first_window


def fetch_commit_stats(owner, repo, sha):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
    time.sleep(REQUEST_SLEEP)
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        print(f"  [WARN] exception fetching {owner}/{repo}@{sha}: {e}")
        return None
    if r.status_code != 200:
        print(f"  [WARN] {r.status_code} fetching {owner}/{repo}@{sha}")
        return None
    data = r.json()
    stats = data.get("stats") or {}
    files = data.get("files") or []
    return {
        "additions": int(stats.get("additions", 0) or 0),
        "deletions": int(stats.get("deletions", 0) or 0),
        "files_changed": len(files),
        "commit_type": classify_from_files_v2(files)[0],
    }


def main():
    rows = list(csv.DictReader(open(FILTERED_CSV, newline="", encoding="utf-8")))
    print(f"[INFO] {len(rows)} repos in study sample")

    out_rows = []
    cached_hits = 0
    fetched = 0
    failed = 0

    for i, row in enumerate(rows, start=1):
        owner = (row.get("Owner") or "").strip()
        name = (row.get("Name") or "").strip()
        if not owner or not name:
            continue

        repo_dir = os.path.join(DATA_ROOT, f"{owner}__{name}")
        commits_path = os.path.join(repo_dir, "commits.json")
        fcba_path = os.path.join(repo_dir, "first_commits_by_author.json")
        if not os.path.exists(commits_path):
            continue

        commits = load_json_data(commits_path)
        first_window = find_newcomer_first_commits(commits)
        if not first_window:
            continue

        fcba_by_author = {}
        if os.path.exists(fcba_path):
            for e in load_json_data(fcba_path):
                fcba_by_author[e.get("author")] = e

        if i % 50 == 0 or i == len(rows):
            print(f"[{i}/{len(rows)}] {owner}/{name} - {len(first_window)} newcomer(s) so far this repo")

        for author, (d, sha) in first_window.items():
            cached = fcba_by_author.get(author)
            cached_date_matches = (
                cached
                and cached.get("date")
                and datetime.strptime(cached["date"], "%Y-%m-%dT%H:%M:%SZ").date() == d
            )

            if cached_date_matches:
                additions = cached.get("additions", 0) or 0
                deletions = cached.get("deletions", 0) or 0
                files_changed = cached.get("files_changed", 0) or 0
                commit_type = cached.get("commit_type") or classify_from_files_v2(cached.get("files") or [])[0]
                source = "cached"
                cached_hits += 1
            else:
                stats = fetch_commit_stats(owner, name, sha) if sha else None
                if stats is None:
                    failed += 1
                    continue
                additions = stats["additions"]
                deletions = stats["deletions"]
                files_changed = stats["files_changed"]
                commit_type = stats["commit_type"]
                source = "fetched"
                fetched += 1

            out_rows.append({
                "repo": f"{owner}/{name}",
                "author": author,
                "date": d.isoformat(),
                "additions": additions,
                "deletions": deletions,
                "files_changed": files_changed,
                "commit_type": commit_type,
                "source": source,
            })

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["repo", "author", "date", "additions", "deletions", "files_changed", "commit_type", "source"])
        w.writeheader()
        w.writerows(out_rows)

    print(f"\n[OK] saved {OUT_CSV} ({len(out_rows)} newcomer first-commit rows)")
    print(f"[INFO] {cached_hits} reused from cache, {fetched} fetched live, {failed} failed/skipped")



if __name__ == "__main__":
    main()
