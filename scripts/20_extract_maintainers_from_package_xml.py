"""
20_extract_maintainers_from_package_xml.py

Walk every repository's file tree, locate each package.xml, and extract the
name/email of every <maintainer> entry declared in it. A single repo can
contain more than one ROS package (and therefore more than one package.xml),
so maintainers are recorded per package, not just per repo.

Input:
  out/repos/github_repos_unique.csv   — repo list (full_name column)

Output (per repo):
  scripts/data/ros_robotics_data/<owner>__<repo>/package_maintainers.json
  {
    "_meta": {...},
    "data": [
      {
        "path": "some_pkg/package.xml",
        "package_name": "some_pkg",
        "maintainers": [{"name": "Jane Doe", "email": "jane@example.com"}, ...]
      },
      ...
    ]
  }

Output (aggregated across all repos):
  out/package_maintainers.csv
    owner,repo,full_name,package_path,package_name,maintainer_name,maintainer_email
"""

import os
import csv
import json
import re
import time
import base64
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")
if not TOKEN:
    raise ValueError("GITHUB_TOKEN not set. Add it to your .env file.")

HEADERS_REST = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.join(SCRIPT_DIR, "..")
REPOS_CSV  = os.path.join(REPO_ROOT, "out", "repos", "github_repos_unique.csv")
DATA_ROOT  = os.path.join(SCRIPT_DIR, "data", "ros_robotics_data")
OUT_CSV    = os.path.join(REPO_ROOT, "out", "package_maintainers.csv")

REQUEST_SLEEP = 0.2


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


def fetch_rest(url: str, params: dict = None):
    time.sleep(REQUEST_SLEEP)
    r = requests.get(url, headers=HEADERS_REST, params=params)
    if r.status_code == 200:
        return r.json()
    print(f"  [REST] {r.status_code} for {url} :: {r.text[:200]}")
    return None


def get_default_branch(owner: str, repo: str) -> str | None:
    """Prefer the already-cached general_info.json to avoid an extra API call."""
    cached_path = os.path.join(DATA_ROOT, f"{owner}__{repo}", "general_info.json")
    if os.path.exists(cached_path):
        try:
            with open(cached_path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            branch = (obj.get("data") or {}).get("default_branch")
            if branch:
                return branch
        except Exception:
            pass

    info = fetch_rest(f"https://api.github.com/repos/{owner}/{repo}")
    return (info or {}).get("default_branch")


def find_package_xml_paths(owner: str, repo: str, branch: str) -> tuple[list[dict], bool]:
    """Return (list of {path, sha} for every package.xml blob, truncated flag)."""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}"
    tree = fetch_rest(url, params={"recursive": "1"})
    if not tree:
        return [], False

    entries = [
        {"path": e["path"], "sha": e["sha"]}
        for e in tree.get("tree", [])
        if e.get("type") == "blob" and e.get("path", "").split("/")[-1] == "package.xml"
    ]
    return entries, bool(tree.get("truncated"))


def fetch_blob_text(owner: str, repo: str, sha: str) -> str | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/git/blobs/{sha}"
    blob = fetch_rest(url)
    if not blob or blob.get("encoding") != "base64":
        return None
    try:
        return base64.b64decode(blob["content"]).decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] failed to decode blob {sha}: {e!r}")
        return None


def parse_maintainers(xml_text: str) -> tuple[str | None, list[dict]]:
    """Return (package_name, [{name, email}, ...]) from a package.xml's contents."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"  [WARN] malformed XML: {e!r}")
        return None, []

    package_name = (root.findtext("name") or "").strip() or None

    maintainers = []
    for node in root.findall(".//maintainer"):
        name = (node.text or "").strip() or None
        email = (node.get("email") or "").strip() or None
        if name or email:
            maintainers.append({"name": name, "email": email})

    return package_name, maintainers


def process_repo(owner: str, repo: str) -> list[dict]:
    branch = get_default_branch(owner, repo)
    if not branch:
        print(f"  [SKIP] no default branch for {owner}/{repo}")
        return []

    paths, truncated = find_package_xml_paths(owner, repo, branch)
    if truncated:
        print(f"  [WARN] tree listing truncated for {owner}/{repo}; some package.xml files may be missed")
    if not paths:
        return []

    results = []
    for entry in paths:
        text = fetch_blob_text(owner, repo, entry["sha"])
        if text is None:
            continue
        package_name, maintainers = parse_maintainers(text)
        results.append({
            "path": entry["path"],
            "package_name": package_name,
            "maintainers": maintainers,
        })

    return results


def build_aggregate_csv():
    """Scan every cached package_maintainers.json snapshot and write the combined CSV."""
    rows = []
    if os.path.isdir(DATA_ROOT):
        for folder in sorted(os.listdir(DATA_ROOT)):
            snapshot_path = os.path.join(DATA_ROOT, folder, "package_maintainers.json")
            if not os.path.exists(snapshot_path) or "__" not in folder:
                continue
            owner, repo = folder.split("__", 1)
            with open(snapshot_path, "r", encoding="utf-8") as f:
                snapshot = json.load(f)
            for pkg in snapshot.get("data", []):
                maintainers = pkg.get("maintainers") or []
                if not maintainers:
                    rows.append({
                        "owner": owner,
                        "repo": repo,
                        "full_name": f"{owner}/{repo}",
                        "package_path": pkg.get("path"),
                        "package_name": pkg.get("package_name"),
                        "maintainer_name": None,
                        "maintainer_email": None,
                    })
                for m in maintainers:
                    rows.append({
                        "owner": owner,
                        "repo": repo,
                        "full_name": f"{owner}/{repo}",
                        "package_path": pkg.get("path"),
                        "package_name": pkg.get("package_name"),
                        "maintainer_name": m.get("name"),
                        "maintainer_email": m.get("email"),
                    })

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    fieldnames = ["owner", "repo", "full_name", "package_path", "package_name",
                  "maintainer_name", "maintainer_email"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[OK] saved {OUT_CSV} ({len(rows)} rows)")


def main():
    repos = load_repos(REPOS_CSV)
    print(f"[INFO] {len(repos)} repos to process")

    skipped = 0
    fetched = 0
    failed = 0

    for i, (owner, repo) in enumerate(repos, start=1):
        folder = os.path.join(DATA_ROOT, f"{owner}__{repo}")
        out_path = os.path.join(folder, "package_maintainers.json")

        if os.path.exists(out_path):
            skipped += 1
            continue

        print(f"[{i}/{len(repos)}] {owner}/{repo}")
        try:
            packages = process_repo(owner, repo)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"  [ERR] {owner}/{repo}: {e!r}")
            failed += 1
            continue

        save_snapshot(
            packages,
            out_path,
            {"owner": owner, "repo": repo, "endpoint": "git/trees + git/blobs (package.xml)"},
        )
        n_maintainers = sum(len(p["maintainers"]) for p in packages)
        print(f"  [OK] package.xml files={len(packages)} maintainers={n_maintainers}")
        fetched += 1

    print(f"\n[DONE] fetched={fetched}  skipped(cached)={skipped}  failed={failed}")

    build_aggregate_csv()


if __name__ == "__main__":
    main()
