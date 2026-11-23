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

## 2026-11-23 — AI impact card with Claude; caller detection with `ast`

**What:** `card.py` asks Claude (`claude-opus-5-5`, effort `medium`, JSON-schema structured output) to write three parts of the card: what changed, what might break in each affected module, and up to three things the owner should check. Inputs: PR title and description, the rule-based affected modules, possible callers with code snippets, and the diff (cut at 150,000 characters, which the card then says). `callers.py` finds code in other modules that calls a function or class the PR changed, by parsing Python files with `ast`. Server-side refusal fallback is on (`fallbacks: "default"`).

**Why:** Interviewee B's problem was "I know which function I changed, but not where others use it". The rule-based owner list alone tells the owner *that* their module is touched, not *what might break*. The AI is fail-soft: if the call fails, refuses, or no key is set, the card is still posted with the rule-based list, and the merge gate never depends on the AI.

**Alternatives rejected:** a cheaper model (Sonnet/Haiku) — we start with the most capable model and will compare once we have a prompt test suite; letting the AI decide who must sign off — rejected in CP1, because an AI guess about callers can be wrong.

**Led by:** 李秉倫 (callers.py and card.py drafted with Claude subagents; reviewed by Codex)
