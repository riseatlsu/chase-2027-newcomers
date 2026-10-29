"""
09c_fetch_integrators.py

Identify integrators for each repository — contributors who have merged at least
one pull request. The existing pull_requests.json files were saved without the
merged_by field, so this script re-fetches that information via the GitHub
GraphQL API (100 merged PRs per request) and writes a per-repo integrators.json.

Input:
  out/repos/github_repos_unique.csv   — repo list (full_name column)

Output (per repo):
  scripts/data/ros_robotics_data/<owner>__<repo>/integrators.json
  {
    "integrators":       ["login1", "login2", ...],
    "integrators_count": N
  }
"""

import os
import sys
import csv
import json
import re
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")
if not TOKEN:
    raise ValueError("GITHUB_TOKEN not set. Add it to your .env file.")

HEADERS_GQL = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

GRAPHQL_URL  = "https://api.github.com/graphql"
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT    = os.path.join(SCRIPT_DIR, "..")
REPOS_CSV    = os.path.join(REPO_ROOT, "out", "repos", "github_repos_unique.csv")
DATA_ROOT    = os.path.join(SCRIPT_DIR, "data", "ros_robotics_data")

REQUEST_SLEEP = 0.25

GQL_MERGED_BY = """
query($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequests(first: 100, after: $cursor, states: MERGED) {
      pageInfo { hasNextPage endCursor }
      nodes {
        mergedBy { login }
      }
    }
  }
}
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def save_snapshot(data, path: str, meta: dict):
    snapshot = {
        "_meta": {"fetched_at": utc_now_iso(), **meta},
        "data": data,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)


def load_repos(csv_path: str) -> list[tuple[str, str]]:
    repos = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            full_name = (row.get("full_name") or "").strip()
            if not full_name:
                for key in ("html_url", "repo_url", "url"):
                    v = (row.get(key) or "").strip()
                    m = re.search(r"github\.com/([^/]+)/([^/#?.]+)", v)
                    if m:
                        full_name = f"{m.group(1)}/{m.group(2)}"
                        break
            if "/" in full_name:
                owner, repo = full_name.split("/", 1)
                repos.append((owner.strip(), repo.strip()))
    return repos


def fetch_gql(query: str, variables: dict):
    time.sleep(REQUEST_SLEEP)
    try:
        r = requests.post(GRAPHQL_URL, headers=HEADERS_GQL,
                          json={"query": query, "variables": variables},
                          timeout=30)
    except requests.RequestException as e:
        print(f"  [GQL] request failed: {e}")
        return None
    if r.status_code == 200:
        payload = r.json()
        if "errors" in payload:
            print(f"  [GQL] errors: {payload['errors'][:1]}")
            return None
        return payload
    print(f"  [GQL] {r.status_code} :: {r.text[:200]}")
    return None


def fetch_integrators(owner: str, repo: str) -> list[str] | None:
    """Return sorted list of unique logins who merged at least one PR.

    Returns None if any page fails, so a partial list is never saved as if
    it were complete.
    """
    integrators: set[str] = set()
    cursor = None

    while True:
        variables = {"owner": owner, "repo": repo, "cursor": cursor}
        payload = fetch_gql(GQL_MERGED_BY, variables)
        if not payload:
            return None

        repository = (payload.get("data") or {}).get("repository")
        if repository is None:
            print("  [GQL] repository not found")
            return None

        pr_conn = repository.get("pullRequests") or {}
        nodes = pr_conn.get("nodes") or []

        for node in nodes:
            merged_by = node.get("mergedBy")
            if merged_by and merged_by.get("login"):
                integrators.add(merged_by["login"])

        page_info = pr_conn.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")

    return sorted(integrators)


def main():
    repos = load_repos(REPOS_CSV)
    print(f"[INFO] {len(repos)} repos to process")

    skipped = 0
    fetched = 0
    failed  = 0

    for i, (owner, repo) in enumerate(repos, start=1):
        folder   = os.path.join(DATA_ROOT, f"{owner}__{repo}")
        out_path = os.path.join(folder, "integrators.json")

        if os.path.exists(out_path):
            skipped += 1
            continue

        print(f"[{i}/{len(repos)}] {owner}/{repo}")
        integrators = fetch_integrators(owner, repo)

        if integrators is None:
            print("  [FAIL] not saved; rerun to retry")
            failed += 1
            continue

        data = {
            "integrators":       integrators,
            "integrators_count": len(integrators),
        }
        save_snapshot(
            data,
            out_path,
            {"owner": owner, "repo": repo, "endpoint": "graphql/pullRequests[MERGED].mergedBy"},
        )
        print(f"  [OK] integrators={len(integrators)}")
        fetched += 1

    print(f"\n[DONE] fetched={fetched}  skipped(cached)={skipped}  failed={failed}")


if __name__ == "__main__":
    main()
