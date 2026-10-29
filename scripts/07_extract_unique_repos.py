import os
import csv
import json
import time
from collections import defaultdict, Counter

import requests
from dotenv import load_dotenv

load_dotenv()

IN_PATH = "out/diagnostics/resolved_ok.csv"
OUT_DIR = "out/repos"
os.makedirs(OUT_DIR, exist_ok=True)

OUT_REPOS = os.path.join(OUT_DIR, "github_repos_unique.csv")
OUT_REPOS_BY_DISTRO = os.path.join(OUT_DIR, "github_repos_unique_by_distro.csv")

# Reused if script 09 has already fetched a repo's general_info.json - avoids a
# redundant live API call for repos this pipeline has already seen.
DATA_ROOT = "scripts/data/ros_robotics_data"

CACHE_DIR = "cache/repo_canonical"
CACHE_PATH = os.path.join(CACHE_DIR, "resolve_cache.json")
os.makedirs(CACHE_DIR, exist_ok=True)

TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}" if TOKEN else "",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
REQUEST_SLEEP = 0.2


def load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def canonical_from_local(owner: str, repo: str):
    path = os.path.join(DATA_ROOT, f"{owner}__{repo}", "general_info.json")
    if not os.path.exists(path):
        return None
    try:
        snapshot = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None
    data = snapshot.get("data", snapshot)
    full_name = (data.get("full_name") or "").strip()
    return full_name or None


def canonical_from_api(owner: str, repo: str):
    url = f"https://api.github.com/repos/{owner}/{repo}"
    time.sleep(REQUEST_SLEEP)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
    except Exception as e:
        print(f"  [WARN] exception resolving {owner}/{repo}: {e}")
        return None
    if r.status_code == 200:
        return (r.json().get("full_name") or "").strip() or None
    print(f"  [WARN] {r.status_code} resolving {owner}/{repo}: {r.text[:120]}")
    return None


def resolve_canonical(owner: str, repo: str, cache: dict) -> str:
    """
    Resolve (owner, repo) to GitHub's current canonical "owner/repo" name.

    A repo that was renamed or transferred to a different org after rosdistro's
    release metadata was written would otherwise appear twice in the discovery
    list under its old and new names - each alias resolves to the same GitHub
    repo, but as distinct strings they'd survive this script's dedup and only
    collide downstream in script 10 (once it fetches live data and both aliases
    turn out to share a full_name), silently dropping one alias's distro/package
    coverage. Resolving here means script 09 also never wastes an API fetch on
    a repo it's already going to fetch under its current name.

    Falls back to the raw "owner/repo" string, unresolved, if GitHub can't be
    reached (e.g. rate-limited, repo deleted) - never drops a repo outright.
    """
    raw = f"{owner}/{repo}"
    key = raw.lower()
    if key in cache:
        return cache[key]

    canonical = canonical_from_local(owner, repo) or canonical_from_api(owner, repo) or raw
    cache[key] = canonical
    return canonical


def main():
    rows = list(csv.DictReader(open(IN_PATH, encoding="utf-8")))
    cache = load_cache()

    raw_pairs = set()
    for r in rows:
        owner = (r.get("github_owner") or "").strip()
        repo = (r.get("github_repo") or "").strip()
        if owner and repo:
            raw_pairs.add((owner, repo))

    print(f"[INFO] resolving canonical identity for {len(raw_pairs)} raw owner/repo strings...")
    canon_map = {}
    for i, (owner, repo) in enumerate(sorted(raw_pairs), start=1):
        canon_map[f"{owner}/{repo}"] = resolve_canonical(owner, repo, cache)
        if i % 200 == 0:
            save_cache(cache)
    save_cache(cache)

    # aggregate per CANONICAL repo (multiple raw aliases can map to one)
    agg = {}
    distros_per_repo = defaultdict(set)
    packages_per_repo = defaultdict(set)
    via_counter = defaultdict(Counter)
    distro_pkg_counter = defaultdict(Counter)
    aliases_per_repo = defaultdict(set)

    for r in rows:
        owner = (r.get("github_owner") or "").strip()
        repo_name = (r.get("github_repo") or "").strip()
        if not owner or not repo_name:
            continue
        raw = f"{owner}/{repo_name}"
        repo = canon_map.get(raw, raw)

        distro = (r.get("ros_distro") or "").strip()
        pkg = (r.get("package") or "").strip()
        via = (r.get("resolved_via") or "none").strip()

        distros_per_repo[repo].add(distro)
        packages_per_repo[repo].add(pkg)
        via_counter[repo][via] += 1
        distro_pkg_counter[repo][distro] += 1
        if raw.lower() != repo.lower():
            aliases_per_repo[repo].add(raw)

        if repo not in agg:
            agg[repo] = {
                "full_name": repo,
                "repo_url": (r.get("repo_url") or "").strip(),
            }

    out = []
    out_by_distro = []

    for repo, base in agg.items():
        distros = sorted(distros_per_repo[repo])
        n_pkgs = len(packages_per_repo[repo])

        via = via_counter[repo]
        via_str = ";".join([f"{k}:{v}" for k, v in via.most_common()])

        row = dict(base)
        row.update({
            "distros": "|".join(distros),
            "n_distros": len(distros),
            "n_packages_total": n_pkgs,
            "resolved_via_breakdown": via_str,
            "resolved_aliases": ";".join(sorted(aliases_per_repo[repo])),
        })
        out.append(row)

        for d in distros:
            out_by_distro.append({
                "full_name": repo,
                "ros_distro": d,
                "n_packages_in_distro": distro_pkg_counter[repo][d],
                "repo_url": base["repo_url"],
            })

    out.sort(key=lambda r: int(r["n_packages_total"]), reverse=True)
    out_by_distro.sort(key=lambda r: (r["ros_distro"], r["full_name"]))

    with open(OUT_REPOS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    with open(OUT_REPOS_BY_DISTRO, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out_by_distro[0].keys()))
        w.writeheader()
        w.writerows(out_by_distro)

    print(f"[OK] saved {OUT_REPOS} repos={len(out)}")
    print(f"[OK] saved {OUT_REPOS_BY_DISTRO} rows={len(out_by_distro)}")

    collapsed = {repo: aliases for repo, aliases in aliases_per_repo.items() if aliases}
    if collapsed:
        n_aliases = sum(len(v) for v in collapsed.values())
        print(f"[OK] collapsed {n_aliases} renamed/transferred alias(es) into {len(collapsed)} canonical repo(s):")
        for repo, aliases in sorted(collapsed.items()):
            print(f"    {repo}  <-  {', '.join(sorted(aliases))}")


if __name__ == "__main__":
    main()
