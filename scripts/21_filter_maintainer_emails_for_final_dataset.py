"""
21_filter_maintainer_emails_for_final_dataset.py

Restrict the maintainer emails extracted by 20_extract_maintainers_from_package_xml.py
to only the repositories in the study sample, and report which of those repositories
have no package.xml at all.

NOTE: despite the script/file names below ("final dataset" / "final_repos"), the
reference repo list is out/filtered_repo_dataset.csv - the exclusion-filtered
472-repo study sample used by every other analysis stage (12-19) - not the larger,
pre-exclusion out/final_repo_dataset.csv (884 repos). This was changed 2026-09-22 so
the maintainer/affiliation analysis (this script + 22-26 downstream) describes the
same population as the rest of the paper, instead of a separate, larger one. File and
variable names still say "final_repos" purely for historical/backward-compatibility
reasons (other scripts read those exact output filenames) - it does not mean
final_repo_dataset.csv.

Some repositories were renamed/transferred on GitHub after
out/repos/github_repos_unique.csv was built (e.g. "ros-planning/navigation2" ->
"ros-navigation/navigation2"). scripts/data/ros_robotics_data/<owner>__<repo>/ folders
and out/package_maintainers.csv use the *original* name that was queried, while
out/filtered_repo_dataset.csv's full_name column holds the *canonical* name GitHub
returned for the repo (from general_info.json). This script reconciles the two via
general_info.json before filtering/reporting, so renamed repos aren't misreported as
missing a package.xml.

Input:
  out/filtered_repo_dataset.csv       — the study-sample repo list (full_name column)
  out/package_maintainers.csv         — output of 20_extract_maintainers_from_package_xml.py
  scripts/data/ros_robotics_data/<owner>__<repo>/general_info.json  — canonical full_name

Output:
  out/package_maintainers_final_repos.csv   — maintainer rows restricted to study-sample repos
  out/final_repos_missing_package_xml.csv   — study-sample repos with no package.xml found
  out/package_xml_coverage_report.txt       — human-readable summary
"""

import os
import csv
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.join(SCRIPT_DIR, "..")
DATA_ROOT  = os.path.join(SCRIPT_DIR, "data", "ros_robotics_data")

FINAL_DATASET_CSV   = os.path.join(REPO_ROOT, "out", "filtered_repo_dataset.csv")
MAINTAINERS_CSV      = os.path.join(REPO_ROOT, "out", "package_maintainers.csv")

OUT_FILTERED_CSV = os.path.join(REPO_ROOT, "out", "package_maintainers_final_repos.csv")
OUT_MISSING_CSV  = os.path.join(REPO_ROOT, "out", "final_repos_missing_package_xml.csv")
OUT_REPORT       = os.path.join(REPO_ROOT, "out", "package_xml_coverage_report.txt")


def load_final_dataset_repos() -> list[str]:
    with open(FINAL_DATASET_CSV, newline="", encoding="utf-8") as f:
        return [r["full_name"].strip() for r in csv.DictReader(f) if r.get("full_name")]


def build_canonical_name_map() -> dict[str, str]:
    """Map the full_name used in package_maintainers.csv -> the canonical
    full_name GitHub reports today (from general_info.json), for every fetched repo."""
    mapping = {}
    if not os.path.isdir(DATA_ROOT):
        return mapping

    for folder in os.listdir(DATA_ROOT):
        if "__" not in folder:
            continue
        fetched_full_name = folder.replace("__", "/", 1)

        canonical = fetched_full_name
        gi_path = os.path.join(DATA_ROOT, folder, "general_info.json")
        if os.path.exists(gi_path):
            try:
                with open(gi_path, "r", encoding="utf-8") as f:
                    gi = json.load(f)
                fn = (gi.get("data") or {}).get("full_name")
                if fn:
                    canonical = fn
            except Exception:
                pass

        mapping[fetched_full_name] = canonical

    return mapping


def main():
    final_repos = load_final_dataset_repos()
    final_repo_set = set(final_repos)
    print(f"[INFO] final repo dataset: {len(final_repo_set)} repositories")

    canonical_map = build_canonical_name_map()

    with open(MAINTAINERS_CSV, newline="", encoding="utf-8") as f:
        maintainer_rows = list(csv.DictReader(f))

    filtered_rows = []
    repos_with_package_xml = set()
    total_emails = 0
    unique_emails = set()

    for row in maintainer_rows:
        canonical = canonical_map.get(row["full_name"], row["full_name"])
        if canonical not in final_repo_set:
            continue

        out_row = dict(row)
        out_row["final_dataset_full_name"] = canonical
        filtered_rows.append(out_row)

        repos_with_package_xml.add(canonical)

        email = (row.get("maintainer_email") or "").strip()
        if email:
            total_emails += 1
            unique_emails.add(email.lower())

    fieldnames = ["owner", "repo", "full_name", "final_dataset_full_name",
                  "package_path", "package_name", "maintainer_name", "maintainer_email"]
    os.makedirs(os.path.dirname(OUT_FILTERED_CSV), exist_ok=True)
    with open(OUT_FILTERED_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered_rows)
    print(f"[OK] saved {OUT_FILTERED_CSV} ({len(filtered_rows)} rows)")

    missing_repos = sorted(final_repo_set - repos_with_package_xml)
    with open(OUT_MISSING_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["full_name"])
        for full_name in missing_repos:
            writer.writerow([full_name])
    print(f"[OK] saved {OUT_MISSING_CSV} ({len(missing_repos)} rows)")

    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("PACKAGE.XML / MAINTAINER EMAIL COVERAGE REPORT (study sample: filtered_repo_dataset.csv)\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"Repositories in study sample:                {len(final_repo_set)}\n")
        f.write(f"Repositories with >=1 package.xml found:    {len(repos_with_package_xml)} "
                f"({100 * len(repos_with_package_xml) / len(final_repo_set):.1f}%)\n")
        f.write(f"Repositories with NO package.xml found:     {len(missing_repos)} "
                f"({100 * len(missing_repos) / len(final_repo_set):.1f}%)\n\n")

        f.write(f"Total maintainer emails found (rows):       {total_emails}\n")
        f.write(f"Unique maintainer emails found:             {len(unique_emails)}\n\n")

        f.write("NOTES:\n")
        f.write("-" * 70 + "\n")
        f.write("  - 'No package.xml found' means the repo's default-branch git tree\n")
        f.write("    contained no file named package.xml (not that maintainers were absent\n")
        f.write("    from an existing package.xml).\n")
        f.write("  - Repos renamed/transferred on GitHub since github_repos_unique.csv was\n")
        f.write("    built are matched via general_info.json's canonical full_name, so a\n")
        f.write("    rename does not appear here as a missing package.xml.\n\n")

        f.write("REPOSITORIES WITH NO package.xml:\n")
        f.write("-" * 70 + "\n")
        for full_name in missing_repos:
            f.write(f"  {full_name}\n")
        f.write("=" * 70 + "\n")

    print(f"[OK] saved {OUT_REPORT}")
    print(f"\n[SUMMARY] final repos={len(final_repo_set)} "
          f"with_package_xml={len(repos_with_package_xml)} "
          f"missing={len(missing_repos)} "
          f"total_emails={total_emails} unique_emails={len(unique_emails)}")


if __name__ == "__main__":
    main()
