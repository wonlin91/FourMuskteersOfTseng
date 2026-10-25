# Decisions Log

## 2026-09-21 — Initial code steward

**What:** Tank is the initial code steward for the team.

**Why:** He volunteered and has experience using Git.

## 2026-10-25 — Current code steward

**What:** 李秉倫 is the current code steward. The steward maintains branch protection on `main`, keeps the PR template and this log up to date, and breaks ties on cross-module, repository and architecture decisions (see Team Charter in CP1).

**Why:** Confirmed by the team when preparing CP1, so that one person is clearly responsible for repository settings going into the build phase.

## 2026-10-25 — Problem focus for CP1

**What:** We focus on unannounced changes to another member's module or to shared code in small (3–5 person) graduate-student teams, and on building a GitHub App ("ChangeSignal", working name) that drafts an impact summary and requires the affected owner's sign-off before merge.

**Why:** Two interviewees outside our team (a course-project front-end owner and a research-pipeline developer) independently described this problem, each costing 3 hours to a full day of rework, and both said LINE announcements and plain PR reviews did not prevent it. A third direction we heard about (reproducing old research results) was set aside because tools such as MLflow and DVC already cover much of it and it is hard to evaluate within the semester.

**Alternatives considered:** experiment-reproducibility tracking for research hand-over; relying on GitHub CODEOWNERS alone (rejected: path-based only, does not explain changes or find downstream callers).
