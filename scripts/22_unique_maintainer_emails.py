"""
22_unique_maintainer_emails.py

Collapse out/package_maintainers_final_repos.csv down to one row per unique
maintainer email, listing every repository (from the final repo dataset) that
maintainer is associated with.

A maintainer's displayed name can vary slightly across package.xml files
(e.g. different capitalization); the most frequently used spelling for each
email is kept as maintainer_name, and any other spellings seen are recorded in
maintainer_name_variants.

Input:
  out/package_maintainers_final_repos.csv   — output of 21_filter_maintainer_emails_for_final_dataset.py

Output:
  out/unique_maintainer_emails.csv
    maintainer_email, maintainer_name, maintainer_name_variants,
    repo_count, repositories
"""

import os
import csv
from collections import Counter, defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.join(SCRIPT_DIR, "..")

IN_CSV  = os.path.join(REPO_ROOT, "out", "package_maintainers_final_repos.csv")
OUT_CSV = os.path.join(REPO_ROOT, "out", "unique_maintainer_emails.csv")

REPO_SEP = "; "


def main():
    with open(IN_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    names_by_email = defaultdict(Counter)
    repos_by_email = defaultdict(set)
    skipped_no_email = 0

    for row in rows:
        email = (row.get("maintainer_email") or "").strip().lower()
        if not email:
            skipped_no_email += 1
            continue

        name = (row.get("maintainer_name") or "").strip()
        if name:
            names_by_email[email][name] += 1

        repo = (row.get("final_dataset_full_name") or row.get("full_name") or "").strip()
        if repo:
            repos_by_email[email].add(repo)

    out_rows = []
    for email in sorted(repos_by_email):
        name_counts = names_by_email.get(email, Counter())
        if name_counts:
            primary_name = name_counts.most_common(1)[0][0]
            variants = sorted(n for n in name_counts if n != primary_name)
        else:
            primary_name = ""
            variants = []

        repos = sorted(repos_by_email[email])

        out_rows.append({
            "maintainer_email": email,
            "maintainer_name": primary_name,
            "maintainer_name_variants": REPO_SEP.join(variants),
            "repo_count": len(repos),
            "repositories": REPO_SEP.join(repos),
        })

    fieldnames = ["maintainer_email", "maintainer_name", "maintainer_name_variants",
                  "repo_count", "repositories"]
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    multi_repo = sum(1 for r in out_rows if r["repo_count"] > 1)
    print(f"[OK] saved {OUT_CSV} ({len(out_rows)} unique maintainers)")
    print(f"[INFO] maintainers in >1 repo: {multi_repo}")
    print(f"[INFO] rows skipped (no email): {skipped_no_email}")


if __name__ == "__main__":
    main()
