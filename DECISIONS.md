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

**Known limits:** PRs from forks are skipped (read-only token, no secrets); comments are posted as `github-actions[bot]`; each run waits ~20–60 s for a runner.

**Led by:** 李秉倫

## 2026-11-23 — Walking skeleton design

**What:** Python + `requests`, one workflow triggered by `pull_request` and `pull_request_review`. Every run recomputes the full state (`reconcile`): changed files → module owners → card comment (edited in place via a hidden marker) → reviewer requests → commit status on the PR head SHA. Approval counts only for the current head commit, so a new push needs a fresh sign-off. In the skeleton, owner mapping and all GitHub writes are real; caller detection (`callers.py`) and the AI card text (`card.py`) are stubs for their owners to replace.

**Why:** Only `github_api.py` talks to GitHub, so the detect and card owners work with plain Python data and can develop in parallel. Recomputing on every event makes reruns safe.

**Alternatives rejected:** PyGithub with two workflows (extra SDK and two files to keep in sync); GitHub CLI + Python (an extra shell/Python boundary to debug). Options were compared with Codex as a design consultant.

**Led by:** 李秉倫

## 2026-11-23 — Module ownership for our own repository

**What:** `.changesignal/modules.yml` maps our code to owners: pipeline (workflow, `main.py`, `github_api.py`) → 李秉倫; detect (`modules.py`, `callers.py`, `.changesignal/`) → 蔡旺霖; card (`card.py`, `prompts/`) → 陳苡翔; practice repo and tests (`practice/`, `tests/`) → 楊子枋.

**Why:** We use ChangeSignal on our own repository while building it, so changes to a teammate's module already need that teammate's sign-off.

**Led by:** 李秉倫
