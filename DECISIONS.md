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

**What:** In `.changesignal/modules.yml`, the same path string may not appear in two modules. Overlapping paths such as `pkg/` and `pkg/report.py` are not detected yet, so a file can still end up with two owners. `**/` matches zero or more folders. A malformed map (unknown key, duplicate name, owner that is not a GitHub username, a path that can never match) fails the check instead of passing.

**Why:** If a file has no clear owner, or a typo hides a path, the owner is silently not asked. That is the failure ChangeSignal exists to prevent. We chose a failed check over a silent pass.

**Alternatives considered:** allowing a path in two modules and asking both owners (not chosen: ownership would be ambiguous). Two different globs that overlap are not detected yet.

**Led by:** wonlin91. **PRs:** #8, #9 (issues #5, #6).

## 2026-11-23 — Code steward handoff

**What:** wonlin91 acted as code steward for PR #4 (walking skeleton), handed over by 李秉倫, who wrote that PR. The review approved commit d16093e and left four items to track: files in no module are ignored; `affected` is not filtered by author in `reconcile`; `find_callers` needs the diff; paths that never match raise no error. wonlin91 is the current code steward from this date.

**Why:** Every member has to be code steward at least once before CP2, and the author of a PR was not the one to approve it.

**Open items:** unowned files (issue not opened yet); author filter in `reconcile` and the `find_callers` contract (both addressed in PR #15, not merged yet); never-matching paths (PR #9, not merged yet).

**Led by:** 李秉倫 (handoff), wonlin91 (steward).

## 2026-11-23 — Merge plan for merge day

**What:** Merge the open PRs into `main` one at a time, in this order:
1. #4 walking skeleton (LiLOUIS0803). Needs sign-off from FatFang and yixiang0706; wonlin91 has approved d16093e.
2. #8 glob paths (wonlin91): retarget to `main` first. Needs FatFang (`tests/`).
3. #9 module-map validation (wonlin91): retarget to `main` after #8 is merged. Needs FatFang.
4. #15 caller detection (LiLOUIS0803): retarget to `main`. Needs wonlin91 and FatFang.

#10 (DECISIONS.md) is already merged. A PR opened after this entry goes after #15.

**How:**
- Merge method: "Create a merge commit", not squash. #8, #9 and #15 are stacked on #4's branch. After a merge commit, `git rebase origin/main` is enough; after a squash each would need `git rebase --onto origin/main <old base>`.
- The code steward (wonlin91) merges. Each PR's author retargets it to `main` and rebases it. A PR whose diff still contains another PR's commits is not merged.
- Before each merge: update with `main`, resolve conflicts together, run `python -m pytest -q`. After each merge: run pytest again on `main`.
- Conflicts: `DECISIONS.md` (#4 and #15 add entries): keep both sides, ordered by date. Code conflicts: the author resolves, and the affected owner approves the new head again.
- If a merge breaks `main`: use GitHub's Revert button, fix on a branch, merge again.
- Done means: the four PRs are merged or closed, pytest is green on `main`, and someone who is not the steward clones the repo, follows only the README and runs the main task end to end.

**After #4:** `main` has no branch protection today (checked 2026-11-23). Once #4 is merged, require the `changesignal/owner-ack` status check and log it here.

**Why:** #8, #9 and #15 are stacked on #4, so merging out of order would put unreviewed commits into `main`. One merge at a time, with a test between, shows which merge broke something.

**Led by:** wonlin91 (code steward)

## 2026-11-23 — Code steward rotation until CP2 (proposed)

**What:** wonlin91 11/23–24 (merge day) → FatFang 11/25 → yixiang0706 11/26–27 → LiLOUIS0803 11/28–29. Each steward approves at least two PRs during the turn, each with at least one specific comment, and when the turn ends adds a one-line handoff note here. Proposed by wonlin91; each member confirms by approving the PR that adds this entry.

**Why:** CP2 requires every member to have been code steward at least once and to have approved at least two PRs as steward, recorded in DECISIONS.md.

**Led by:** wonlin91 (code steward)
