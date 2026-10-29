#!/usr/bin/env python3
"""
Run the pipeline behind the paper's figures, tables and numbers.

By default only the offline steps run: they rebuild the study sample,
newcomer inflow, every figure in figs/compound/ and out/paper_numbers.csv
from the data snapshots in this repository (scripts/data/ros_robotics_data/,
out/, scripts/tables/, survey/).

--all also reruns package discovery and GitHub data collection first. Those
steps call the GitHub API (set GITHUB_TOKEN in .env) and the live state of
GitHub, ROS Index and rosdistro has changed since the snapshots were taken,
so their results will differ from the paper's.

Usage:
  python run_pipeline.py          # offline: reproduce the paper from the snapshots
  python run_pipeline.py --all    # recollect everything, then run the analysis
  python run_pipeline.py --list   # show the steps without running them
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SCRIPTS = ROOT / "scripts"

# (script, needs network or files downloaded by a network step, what it produces)
STEPS = [
    ("00_download_ros_index_json.py", True, "ROS Index package lists (Humble, Jazzy, Kilted)"),
    ("01_build_mapping_from_rosdistro.py", True, "rosdistro repository tables"),
    ("02_join_index_with_rosdistro.py", True, "package -> repository mapping (reads 00/01 downloads)"),
    ("03_validate_and_stats.py", False, "mapping coverage summary"),
    ("05_fill_missing_from_index_html.py", True, "mapping gaps filled from index.ros.org pages"),
    ("06_diagnose_unresolved.py", False, "GitHub-resolved / non-GitHub / unresolved buckets"),
    ("07_extract_unique_repos.py", True, "unique GitHub repositories (renames merged)"),
    ("08_repo_overlap_table.py", False, "repositories per distribution"),
    ("09_extract_repo_features_and_commits.py", True, "per-repository GitHub snapshots"),
    ("09c_fetch_integrators.py", True, "integrators (accounts that merged a PR)"),
    ("09e_refresh_pull_requests.py", True, "full pull-request history"),
    ("10_build_final_repo_dataset.py", True, "out/final_repo_dataset.csv (884 repositories)"),
    ("11_apply_exclusion_criteria.py", False, "out/filtered_repo_dataset.csv (472), Table I"),
    ("12_inflow.py", False, "newcomer inflow tables"),
    ("28_newcomer_first_commit_size_analysis.py", True, "newcomers' first commits (size, type)"),
    ("13_plot_inflow.py", False, "Fig.: stratified inflow"),
    ("29_plot_survey_results.py", False, "Figs.: survey; Table: demographics"),
    ("30_plot_compound_newcomers_contributions.py", False, "Figs.: newcomer overview, contributions"),
    ("31_plot_compound_onboarding_practices.py", False, "Fig.: onboarding practices"),
    ("34_paper_numbers.py", False, "out/paper_numbers.csv"),
]


def main():
    run_all = "--all" in sys.argv
    steps = [s for s in STEPS if run_all or not s[1]]

    if "--list" in sys.argv:
        for script, needs_network, what in steps:
            print(f"{script:<45} {'network' if needs_network else 'offline':<8} {what}")
        return

    for script, _, what in steps:
        print(f"\n=== {script}: {what}", flush=True)
        result = subprocess.run([sys.executable, str(SCRIPTS / script)], cwd=ROOT)
        if result.returncode != 0:
            sys.exit(f"[FAIL] {script} exited with {result.returncode}")
    print(f"\n[OK] {len(steps)} steps finished")


if __name__ == "__main__":
    main()
