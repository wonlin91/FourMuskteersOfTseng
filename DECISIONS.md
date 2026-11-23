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

## 2026-11-23 — Module map rules: one owner per path, malformed map fails

**What:** In `.changesignal/modules.yml`, a path may belong to only one module, so every file has at most one owner. `**/` matches zero or more folders. A malformed map (unknown key, duplicate name, owner that is not a GitHub username, a path that can never match) fails the check instead of passing.

**Why:** If a file has no clear owner, or a typo hides a path, the owner is silently not asked. That is the failure ChangeSignal exists to prevent. We chose a failed check over a silent pass.

**Alternatives considered:** allowing a path in two modules and asking both owners (not chosen: ownership would be ambiguous). Two different globs that overlap are not detected yet.

**Led by:** wonlin91. **PRs:** #8, #9 (issues #5, #6).

## 2026-11-23 — Code steward handoff

**What:** wonlin91 acted as code steward for PR #4 (walking skeleton), handed over by 李秉倫, who wrote that PR. The review approved commit d16093e and left four items to track: files in no module are ignored; `affected` is not filtered by author in `reconcile`; `find_callers` needs the diff; paths that never match raise no error. wonlin91 is the current code steward from this date.

**Why:** Every member has to be code steward at least once before CP2, and the author of a PR was not the one to approve it.

**Open items:** unowned files (issue to be opened); author filter in `reconcile` (waiting for 李秉倫 to confirm); `find_callers` contract (PR #7 was closed, so unresolved); never-matching paths (done in PR #9).

**Led by:** 李秉倫 (handoff), wonlin91 (steward).
