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

## 2026-11-23 — Build ChangeSignal as a GitHub Action, not a GitHub App

**What:** The CP2 prototype runs as a GitHub Action in the repository (`.github/workflows/changesignal.yml`) instead of a hosted GitHub App.

**Why:** An Action needs no server, webhook endpoint or private-key handling, so all four members can work on the same Python code and we can finish within the CP2 window. What users see is the same as the App design in CP1: an impact card comment, the owner requested as reviewer, and a `changesignal/owner-ack` status that blocks merge until the owner approves.

**Alternative rejected:** GitHub App (custom bot identity, faster response, one install for many repositories), because hosting and key management would take most of our remaining time and would likely fall on one person. The core logic is kept separate from the Action entry point so it can be wrapped in an App later.

**Known limits:** PRs from forks are skipped (read-only token, no secrets); comments are posted as `github-actions[bot]`; each run waits ~20–60 s for a runner. Because a PR runs its own copy of the workflow and `changesignal/` code, a PR that edits those files could weaken its own gate. The module map is read from the base branch, and those files are owned by the pipeline module, so such a PR still asks 李秉倫 to sign off, but this is not tamper-proof. Our users are teammates who forget to tell each other, not attackers, so we accept this for the prototype. A GitHub App would remove it. Two PRs with the same head commit share one commit status.

**Led by:** 李秉倫

## 2026-11-23 — Walking skeleton design

**What:** Python + `requests`, one workflow triggered by `pull_request` and `pull_request_review`. Every run recomputes the full state (`reconcile`): changed files → module owners (map read from the base branch) → card comment (edited in place; a hidden marker records which commit it describes) → reviewer requests → commit status on the PR head SHA. Approval counts only for the current head commit, so a new push needs a fresh sign-off. In the skeleton, owner mapping and all GitHub writes are real; caller detection (`callers.py`) and the AI card text (`card.py`) are stubs for their owners to replace.

**Why:** Only `github_api.py` talks to GitHub, so the detect and card owners work with plain Python data and can develop in parallel. Recomputing on every event makes reruns safe.

**Alternatives rejected:** PyGithub with two workflows (extra SDK and two files to keep in sync); GitHub CLI + Python (an extra shell/Python boundary to debug). Options were compared with Codex as a design consultant.

**Led by:** 李秉倫

## 2026-11-23 — Module ownership for our own repository

**What:** `.changesignal/modules.yml` maps our code to owners: pipeline (workflow, `main.py`, `github_api.py`) → 李秉倫; detect (`modules.py`, `callers.py`, `.changesignal/`) → 蔡旺霖; card (`card.py`, `prompts/`) → 陳苡翔; practice repo and tests (`practice/`, `tests/`) → 楊子枋.

**Why:** We use ChangeSignal on our own repository while building it, so changes to a teammate's module already need that teammate's sign-off.

**Led by:** 李秉倫

## 2026-11-23 — Fixes from Codex review of the walking skeleton (PR #4)

**What:** Before asking teammates to review, we had Codex review PR #4. It requested changes. We fixed: (1) the module map is read from the base branch, so a PR cannot remove its own owners; (2) the PR head is re-checked after listing files, so a push in between cannot be approved with the old file list; (3) renamed files count under both the old and the new path, and PRs over GitHub's 3,000-file limit fail instead of passing unchecked; (4) the card records which commit it describes, so a review run that replaced a queued push run still refreshes the card and reviewer requests; (5) one invalid reviewer no longer blocks requests to the others; (6) editing only the PR text no longer re-requests reviewers; (7) tests use their own small module map and run from any folder.

**Not fixed (recorded as known limits above):** a PR can still edit the workflow code that judges it; two PRs sharing a head commit share one status.

**Why:** Each fixed issue could let a cross-module change show as approved without the owner's sign-off, which is the one thing ChangeSignal must not do.

**Led by:** 李秉倫 (review by Codex; fixes drafted with Claude)

## 2026-11-23 — Second Codex review of PR #4: make the gate fail closed

**What:** Codex re-reviewed the fixes and again requested changes. We fixed: (1) a missing, empty or mistyped `modules.yml` (e.g. `module:` instead of `modules:`) is now rejected with a failing status instead of being read as "no owners" and passing; (2) the status is set to pending before any fallible step, and any error turns it red, so an old green status on the same commit cannot survive a failed run; (3) the module map is read at the PR's exact base commit, and the run also notices if the PR's base changes while files are being listed; (4) reviewer requests no longer depend on the card: every run asks each missing owner who has not been asked and has not reviewed this commit, so a failed request is retried.

**Not fixed:** an old-format card from the first skeleton commit is not recognised (only PR #4 had one; it was deleted by hand).

**Why:** The rule we follow is that ChangeSignal may wrongly block a PR but must never wrongly let one through.

**Led by:** 李秉倫 (review by Codex; fixes drafted with Claude)

## 2026-11-23 — Third Codex review of PR #4 (blockers only)

**What:** We asked Codex to report only issues that could turn `changesignal/owner-ack` green without the owner's approval. Fixed: the workflow now sets the status to pending as its first step, before installing anything, so a run that fails early (e.g. on a dismissed approval) cannot leave an old green status. Deferred: when `modules.yml` changes on `main`, open PRs are not re-checked, so a PR that was green before a file gained an owner stays green. This needs a new trigger (push to `main` touching the map → re-run every open PR) and is planned as a follow-up PR.

**Why:** We stopped reviewing in rounds here. The remaining issue needs the ownership map to change while PRs are open, which is rare in a four-person team; we record it rather than delay the skeleton.

**Led by:** 李秉倫 (review by Codex; fix drafted with Claude)

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

## 2026-11-23 — Prompt test cases and how they are checked

**What:** Prompt tests for the AI impact card live in `evals/` (issue #12). Each case is one JSON file in `evals/prompt_cases/` with the PR, the `affected` list and an `expect` block. The runner checks only machine-checkable properties: `reason_given` equals the expected value; `impacts_include` / `impacts_exclude` match module names (case-insensitive, substring, so "scoring (bob)" counts as scoring); `impacts_subset_of_affected` fails any module the detector did not report; `must_not_contain` is a whole-word, any-case search over all card text; `zh-TW` cases need Chinese in `what_changed`. A missing draft or a crash fails the case. Every report records the model and the prompt file's commit and sha256. Real runs are manual, not in CI.

**Why:** Fixed rule checks give the same verdict on every run, so a before/after comparison shows a change in the prompt, not a change in the grader. `must_not_contain` is strict on purpose: owners skim the card, so even quoting "approved" from an injected instruction is a failure.

**Alternatives considered:** an LLM judge that grades the wording (not chosen: costs a second call per case and its verdict can drift between runs); exact-match on the whole output (not chosen: wording changes on every run); running the suite in CI (not chosen: needs a secret and costs money on every push).

**Led by:** FatFang. **Issue:** #12.
