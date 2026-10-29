# Replication Package
The study analyzes 472 GitHub repositories of ROS 2 packages (Humble, Jazzy and Kilted) over a 12-month window, May 1, 2025 to April 30, 2026 (RQ1–RQ3), and a survey of 22 ROS package maintainers (RQ4). This repository holds the scripts, the data snapshots they read, and every figure, table and number in the paper.

## Quick start

Requires Python 3.12.

```bash
pip install -r requirements.txt
python run_pipeline.py
```

This reruns every offline step from the data snapshots in this repository and regenerates all figures in `figs/compound/`, the survey demographics table and `out/paper_numbers.csv`. It needs no GitHub token and finishes in a few minutes. `python run_pipeline.py --list` shows the steps.

To collect the data again from scratch:

```bash
echo "GITHUB_TOKEN=<your token>" > .env
python run_pipeline.py --all
```

This reruns package discovery and GitHub collection first. GitHub, ROS Index and rosdistro have changed since our snapshots were taken, so the results will differ from the paper's.

## Where each result comes from

| Paper | Output | Script |
|---|---|---|
| Table I (exclusion criteria) | `out/exclusion_statistics.txt`, `out/exclusion_summary.csv` | `11_apply_exclusion_criteria.py` |
| Fig. Newcomers per repository (RQ1) | `figs/compound/overview_{1_monthly_mean,2_total_per_repo}` | `30_plot_compound_newcomers_contributions.py` |
| Fig. Stratified inflow (RQ1) | `figs/compound/compound_{1_integrators,2_stars,3_distribution,4_owner}` | `13_plot_inflow.py` |
| Fig. Newcomer contributions (RQ2) | `figs/compound/contrib_{1_types,2_size,3_pr_outcome}` | `30_plot_compound_newcomers_contributions.py` |
| Fig. Onboarding practices (RQ3) | `figs/compound/rq3_{1_practice_adoption,2_practice_count}` | `31_plot_compound_onboarding_practices.py` |
| Table III (survey demographics) | `figs/compound/survey_demographics_table.tex` | `29_plot_survey_results.py` |
| Fig. Respondent background (RQ4) | `figs/compound/survey_bg_{1_experience,2_projects}` | `29_plot_survey_results.py` |
| Fig. Maintainers' views on onboarding (RQ4) | `figs/compound/survey_onboarding_{1_importance,2_yes_no}` | `29_plot_survey_results.py` |
| Numbers quoted in the text | `out/paper_numbers.csv` | `34_paper_numbers.py` |
| Survey quotes (P1–P22) | `survey/responses_anonymized.csv` | `29a_anonymize_survey.py` |

Table II (onboarding practices and references) and the method overview figure are not generated from data.

`out/paper_numbers.csv` lists the numbers the text quotes that no figure shows: the package-to-repository mapping shares, repositories meeting more than one exclusion criterion, the share of newcomers in the top 10% of repositories, first-commit extremes, first-PR follow-ups and survey response counts. Each row has a description.

## Pipeline

Scripts are numbered in run order. Steps marked *network* call the GitHub API or download from ROS Index and rosdistro; the others run offline.

| Step | Script | Network | What it does |
|---|---|---|---|
| Discover | `00_download_ros_index_json.py` | yes | Download the package lists of ROS Index for Humble, Jazzy and Kilted |
| | `01_build_mapping_from_rosdistro.py` | yes | Read each distribution's repositories and released packages from rosdistro |
| | `02_join_index_with_rosdistro.py` | yes¹ | Map each package to its source repository (source URL, then doc, then release) |
| | `03_validate_and_stats.py` | | Print mapping coverage per distribution |
| | `05_fill_missing_from_index_html.py` | yes | Fill unmapped packages from the "Checkout URI" on their index.ros.org page |
| | `06_diagnose_unresolved.py` | | Split entries into GitHub, non-GitHub and unresolved |
| | `07_extract_unique_repos.py` | yes | One row per GitHub repository; renamed or transferred repositories merged under their current name |
| | `08_repo_overlap_table.py` | | Count repositories per distribution and across distributions |
| Collect | `09_extract_repo_features_and_commits.py` | yes | Save per-repository GitHub snapshots to `scripts/data/ros_robotics_data/` |
| | `09c_fetch_integrators.py` | yes | Integrators: accounts that merged at least one PR |
| | `09e_refresh_pull_requests.py` | yes | Full pull-request history of the 472 repositories |
| | `10_build_final_repo_dataset.py` | yes² | One row of features per repository → `out/final_repo_dataset.csv` (884) |
| Filter | `11_apply_exclusion_criteria.py` | | Exclusion criteria → `out/filtered_repo_dataset.csv` (472) |
| Analyze | `12_inflow.py` | | Newcomers per repository per week and per month → `scripts/tables/inflow*.csv` |
| | `28_newcomer_first_commit_size_analysis.py` | yes³ | Size and type of each newcomer's first commit → `out/newcomer_first_commit_sizes.csv` |
| | `13_plot_inflow.py`, `29`–`31` | | Figures and Table III |
| | `34_paper_numbers.py` | | `out/paper_numbers.csv` |

¹ Reads the files 00 and 01 download into `cache/`, which is not in the repository.
² Fetches the size of a few community files from the API.
³ Reuses cached commit stats where possible; 9 of the 1,624 commits are fetched live.

Shared modules: `commit_type_classifier.py` (classifies a commit as code, configuration, documentation, assets or other by file extension) and `newcomer_first_prs.py` (each newcomer's first pull request). `config.py` holds the shared figure colors.

### Definitions

- **Newcomer:** an author whose first commit to a repository falls in the study window. Authors are identified by GitHub login, or by commit author name when no login is linked. Repositories younger than 12 months are excluded.
- **Integrators:** accounts that merged at least one pull request in the repository's history.
- **First PR outcome:** each newcomer's first pull request to the repository, matched by GitHub login (case-insensitive). Outcomes are as of April 30, 2026. Bot accounts are excluded.

## Data

- `scripts/data/ros_robotics_data/<owner>__<repo>/`: GitHub API snapshots for the 884 repositories (metadata, commits, contributors, pull requests, issues, labels, community files, integrators). Each file records when it was fetched in `_meta.fetched_at`. Commit histories were collected after the study window closed (May and September 2026), and pull requests in October 2026. 39 extra folders hold only `general_info.json` for repositories listed in rosdistro under an earlier name; `07_extract_unique_repos.py` uses them to merge each one into its current name.
- `out/`: intermediate and final datasets (`mapping_packages_to_github*.csv`, `diagnostics/`, `repos/`, `final_repo_dataset.csv`, `filtered_repo_dataset.csv`, `exclusion_*`, `newcomer_first_commit_sizes.csv`, `paper_numbers.csv`).
- `scripts/tables/`: newcomer inflow per repository, by ISO week (`inflow.csv`) and calendar month (`inflow_monthly.csv`).

## Survey

`survey/` holds the anonymized survey data:

- `responses_anonymized.csv`: answers of the 22 respondents who consented and finished the survey, numbered P1–P22 in order of submission (the IDs quoted in the paper).
- `questionnaire.csv`: the text of every survey question. The `in_responses` column marks which ones appear in the responses.
- `response_counts.csv`: responses recorded, consented and complete.

`29a_anonymize_survey.py` builds these files from the raw Qualtrics export, which is not shared because it contains names, email addresses, IP addresses and locations. The script drops all Qualtrics metadata, the consent answers, the list of OSS projects each respondent contributed to (it identifies them), and the question about joining future studies. It also redacts five project, library or tool names in open-ended answers that would identify a respondent's project. The redactions are listed in the script.

Survey participants were the maintainers listed in the `package.xml` files of the 472 repositories (`20_extract_maintainers_from_package_xml.py`, `21_filter_maintainer_emails_for_final_dataset.py`, `22_unique_maintainer_emails.py`). Their outputs contain maintainer email addresses and are not included. `out/package_xml_coverage_report.txt` and `out/final_repos_missing_package_xml.csv` give the counts reported in the paper.
