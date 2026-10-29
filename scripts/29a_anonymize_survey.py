#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Elijah Phifer"
__contact__ = "elijah.phifer@lsu.edu"

"""
Anonymize the maintainer survey (Qualtrics export) for the replication package.

The raw export is not public: it holds recipient names and emails, IP
addresses and locations. This script keeps only the respondents who
consented (online consent and, for EU respondents, GDPR consent) and
finished the survey, and only the answers analyzed in the paper:

  - drops every Qualtrics metadata column (dates, IP, location, response and
    recipient IDs, recipient name/email, distribution channel, language);
  - drops the consent answers (all kept respondents consented), Q33 (names of
    the OSS projects each respondent contributed to, which identifies them)
    and Q26 (willingness to join future studies);
  - numbers respondents P1-P22 in order of submission, the IDs quoted in the
    paper;
  - redacts project, library and tool names in the open-ended answers that
    would point to a respondent's project (REDACTIONS below).

Run by the authors, who hold the raw export; everyone else uses the outputs.

Input (not in the repository):
  out/survey_results/ROS package maintainers’ perceived challenges for onboarding newcomers_October 29, 2026_08.22.csv

Output (survey/):
  responses_anonymized.csv  one row per respondent, Participant + kept answers
  questionnaire.csv         every survey question: column, question text
  response_counts.csv       recorded, consented and complete responses
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
from config import PROJECT_ROOT

IN_PATH = (PROJECT_ROOT / "out" / "survey_results" /
           "ROS package maintainers’ perceived challenges for onboarding newcomers_October 29, 2026_08.22.csv")
OUT_DIR = PROJECT_ROOT / "survey"

# Qualtrics metadata, not survey questions.
METADATA_COLS = ["StartDate", "EndDate", "Status", "IPAddress", "Progress", "Duration (in seconds)",
                 "Finished", "RecordedDate", "ResponseId", "RecipientLastName", "RecipientFirstName",
                 "RecipientEmail", "ExternalReference", "LocationLatitude", "LocationLongitude",
                 "DistributionChannel", "UserLanguage", "Q_DL"]
# Questions left out of the public responses (see the docstring).
DROPPED_QUESTIONS = ["Future Research", "Online Consent", "GDPR", "QID38", "Q33", "Q26"]

# (participant, column, text in the answer, replacement). Each must match exactly once.
REDACTIONS = [
    ("P2", "Q22", "caret_doc", "[project documentation]"),
    ("P7", "Q2A", "Regarding the PyTrees project : Providing a more modern Python version of behavior trees "
                  "that is competitive with BehaviorTree.CPP. The latter is a great library, but a Python "
                  "version has its own use case.",
                  "Regarding the [project]: Providing a more modern [redacted] version of [redacted] that is "
                  "competitive with [another library]. The latter is a great library, but a [redacted] "
                  "version has its own use case."),
    ("P7", "Q23", "behavior trees", "[domain]"),
    ("P17", "Q16", "Zulip chat", "[chat platform]"),
    ("P19", "Q19", "MoveIt or MTC", "[project] or [subproject]"),
]


def main():
    # Row 0 holds each column's question text; row 1 holds Qualtrics import IDs.
    raw = pd.read_csv(IN_PATH, dtype=str, keep_default_na=False)
    questions, df = raw.iloc[0], raw.iloc[2:].reset_index(drop=True)

    consented = df["Online Consent"].eq("Yes, I agree to participate")
    gdpr_declined = df["QID38"].eq("I do not give consent")
    # "Finished" is also True for people the consent questions screen out,
    # so it only counts as completion together with consent.
    finished = df["Finished"].eq("True")
    keep = consented & ~gdpr_declined & finished

    # Submission order = RecordedDate order; P1-P22 follow it.
    kept = df[keep].sort_values("RecordedDate", kind="stable").reset_index(drop=True)
    answer_cols = [c for c in df.columns if c not in METADATA_COLS + DROPPED_QUESTIONS]
    out = kept[answer_cols].copy()
    out.insert(0, "Participant", [f"P{i + 1}" for i in range(len(out))])

    for pid, col, old, new in REDACTIONS:
        row = out.index[out["Participant"] == pid][0]
        text = out.at[row, col]
        if text.count(old) != 1:
            raise SystemExit(f"Redaction for {pid} {col} no longer matches: {old!r}")
        out.at[row, col] = text.replace(old, new)

    os.makedirs(OUT_DIR, exist_ok=True)
    out.to_csv(OUT_DIR / "responses_anonymized.csv", index=False)

    question_cols = [c for c in df.columns if c not in METADATA_COLS]
    pd.DataFrame({"column": question_cols,
                  "question": [questions[c] for c in question_cols],
                  "in_responses": [c in answer_cols for c in question_cols]}
                 ).to_csv(OUT_DIR / "questionnaire.csv", index=False)

    counts = [("recorded", len(df), "responses recorded by Qualtrics (started the survey)"),
              ("consented", int((consented & ~gdpr_declined).sum()),
               "agreed to the online consent and did not decline GDPR consent"),
              ("complete", int(keep.sum()), "consented and finished; the respondents analyzed")]
    pd.DataFrame(counts, columns=["stage", "n", "description"]).to_csv(
        OUT_DIR / "response_counts.csv", index=False)

    print(f"[OK] {len(out)} of {len(df)} responses kept, {len(answer_cols)} answer columns, "
          f"{len(REDACTIONS)} redactions")
    print(f"[OK] saved {OUT_DIR}/responses_anonymized.csv, questionnaire.csv, response_counts.csv")


if __name__ == "__main__":
    main()
