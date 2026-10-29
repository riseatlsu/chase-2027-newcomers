#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Elijah Phifer"
__contact__ = "elijah.phifer@lsu.edu"

"""
09e_refresh_pull_requests.py

Re-fetch every study repository's pull requests so the snapshot covers the
whole study window (May 2025 - April 2026). Script 09 only fetches
pull_requests.json when the file is missing, and most snapshots were taken
in Feb-Mar 2026, before the window ended: PRs opened after the fetch were
absent and PRs merged/closed after it still looked open.

Unlike script 09's fetcher, a failed page is retried and then aborts that
repo instead of being treated as the last page, and a snapshot is only
replaced when the new PR list is at least as long as the old one (PRs are
never removed from a repository, so a shorter list means a partial fetch).

Input:
  out/filtered_repo_dataset.csv   - study sample (full_name column)

Output (overwritten per repo, same record format as script 09):
  scripts/data/ros_robotics_data/<owner>__<repo>/pull_requests.json

Usage:
  GITHUB_TOKEN=$(gh auth token) python scripts/09e_refresh_pull_requests.py
"""

import csv
import json
import os
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(SCRIPT_DIR, "data", "ros_robotics_data")
FILTERED_CSV = os.path.join(SCRIPT_DIR, "..", "out", "filtered_repo_dataset.csv")

TOKEN = os.getenv("GITHUB_TOKEN")
if not TOKEN:
    raise ValueError("GitHub token not found. Set GITHUB_TOKEN in your environment (.env).")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
PER_PAGE = 100
REQUEST_SLEEP = 0.2
REQUEST_TIMEOUT = 30
RETRIES = 4


class FetchError(Exception):
    pass


def get_page(url, params):
    """GET one page, retrying transient failures and waiting out rate limits."""
    for attempt in range(1, RETRIES + 1):
        time.sleep(REQUEST_SLEEP)
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            print(f"    [retry {attempt}] {e}")
            time.sleep(5 * attempt)
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code in (403, 429) and r.headers.get("X-RateLimit-Remaining") == "0":
            wait = max(int(r.headers.get("X-RateLimit-Reset", "0")) - int(time.time()), 0) + 5
            print(f"    [rate limit] sleeping {wait}s")
            time.sleep(wait)
            continue
        print(f"    [retry {attempt}] HTTP {r.status_code}: {r.text[:120]}")
        time.sleep(5 * attempt)
    raise FetchError(f"page {params.get('page')} of {url} failed after {RETRIES} attempts")


def fetch_pull_requests(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    out, page = [], 1
    while True:
        batch = get_page(url, {"state": "all", "per_page": PER_PAGE, "page": page})
        if not batch:
            return out
        for pr in batch:
            out.append({
                "id": pr.get("id"),
                "number": pr.get("number"),
                "state": pr.get("state"),
                "title": pr.get("title"),
                "created_at": pr.get("created_at"),
                "closed_at": pr.get("closed_at"),
                "merged_at": pr.get("merged_at"),
                "user": (pr.get("user") or {}).get("login"),
            })
        page += 1


def main():
    with open(FILTERED_CSV, newline="", encoding="utf-8") as f:
        repos = [row["full_name"] for row in csv.DictReader(f)]

    refreshed, skipped, failed = 0, [], []
    for i, full_name in enumerate(repos, start=1):
        owner, repo = full_name.split("/", 1)
        path = os.path.join(DATA_ROOT, f"{owner}__{repo}", "pull_requests.json")
        old_n = 0
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                old_n = len(json.load(f).get("data") or [])
        try:
            prs = fetch_pull_requests(owner, repo)
        except FetchError as e:
            failed.append(full_name)
            print(f"[{i}/{len(repos)}] {full_name}: FAILED ({e}); old snapshot kept")
            continue
        if len(prs) < old_n:
            skipped.append(full_name)
            print(f"[{i}/{len(repos)}] {full_name}: {len(prs)} PRs < {old_n} before; old snapshot kept")
            continue
        snapshot = {
            "_meta": {
                "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "source": "github_rest", "endpoint": "/repos/{owner}/{repo}/pulls?state=all",
                "owner": owner, "repo": repo, "per_page": PER_PAGE,
            },
            "data": prs,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False, default=str)
        refreshed += 1
        print(f"[{i}/{len(repos)}] {full_name}: {old_n} -> {len(prs)} PRs")

    print(f"\n[DONE] refreshed {refreshed}/{len(repos)}; "
          f"kept old (shorter result) {len(skipped)}: {skipped}; failed {len(failed)}: {failed}")


if __name__ == "__main__":
    main()
