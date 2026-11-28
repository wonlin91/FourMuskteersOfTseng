# Walking skeleton and merge day

## Walking skeleton

- **PR:** [#4 Walking skeleton: ChangeSignal as a GitHub Action](https://github.com/wonlin91/FourMuskteersOfTseng/pull/4)
  - Author: LiLOUIS0803. Merged by wonlin91 (code steward) on 2026-11-23 23:24 (UTC+8), after three Codex review rounds.
  - DECISIONS.md: "Walking skeleton design"; "Fixes from Codex review of the walking skeleton (PR #4)"; "Second Codex review of PR #4: make the gate fail closed"; "Third Codex review of PR #4 (blockers only)".
- **What it does end to end:**
  1. A PR's changed files are mapped to owners through `.changesignal/modules.yml`.
  2. The impact card is posted, and the owners are requested as reviewers.
  3. `changesignal/owner-ack` stays pending until every owner approves the current commit.

## Merge day: 2026-11-23

**Plan:** DECISIONS.md, "Merge plan for merge day" (wonlin91, code steward).
- Merge one PR at a time, using merge commits.
- Run pytest between merges.
- Order: #4 → #8 → #9 → #15.

**What happened** (GitHub merge times, UTC+8; all merged by wonlin91):

| Time | PR | Note |
|---|---|---|
| 22:20 | #10 decisions for CP2 | DECISIONS.md only |
| 22:59 | #17 merge plan and steward rotation | DECISIONS.md only |
| 23:04 | #16 PR template | `.github/pull_request_template.md` |
| 23:08 | #8 glob paths | Merged into #4's branch, so it reached `main` with #4 |
| 23:24 | **#4 walking skeleton** | Into `main` |
| 23:27 | #9 module-map validation | Merged into `feat/modules-glob` instead of `main` |
| 23:33 | #18 brings #9 into `main` | Follow-up for the line above |
| 00:19 (11/24) | #15 caller detection | Into `main` |
| 00:24 (11/24) | #21 steward handoff wonlin91 → FatFang | DECISIONS.md |

**Versus the plan:**
- The order held: #4, then #8 with #4, then #9 via #18, then #15.
- #9's base had changed, so a follow-up PR (#18) was needed to bring it into `main`. This was recorded in the 2026-11-24 handoff entry.
- pytest results between merges were not recorded.

**Gate on `main`:**
- On 2026-11-23, `main` had no branch protection.
- By the handoff entry of 2026-11-24 (#27), a ruleset required one approval and the `changesignal/owner-ack` status, and blocked force pushes.
- Re-checked through the rulesets API on 2026-11-28; still the same.

## Fresh-clone check: 2026-11-29

The plan's "done" criterion: someone who is not the steward clones the repository, follows only the README, and runs the main task end to end. It was listed as open in every steward handoff from 2026-11-24 on.

**Done on 2026-11-29:**
- Ran by Claude Code for 李秉倫, so this is not a teammate run.
- Cloned `main` at `24d22e4` into an empty folder, created a virtual environment, and followed README "Develop" only:
  `python -m pip install -r requirements.txt pytest`, then `python -m pytest -q`.
  Result: **213 passed** (Python 3.14.4, Windows).
- The main task on GitHub with the same ChangeSignal version that Group 21 reviewed (`6e2c1a0`):
  - Demo PRs #4 and #5 on `LiLOUIS0803/changesignal-demo` (2026-11-29) posted the card in 42 s and 34 s, requested `wonlin91`, and set `owner-ack` to pending. No approval was submitted on those PRs.
  - Approval → success on the demo repository was last shown on demo PR #1 (2026-11-23, an earlier version).

**Still open:**
- A teammate who is not the steward follows README "Set it up in your own repository" steps 1–8 in a new repository, up to the acceptance check: the same commit goes from pending to success after the owner approves.
- That would also be the first run of the README written in #34.
