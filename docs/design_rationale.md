# ChangeSignal — Design Rationale (CP2)

Group 10 (FourMuskteersOfTseng) · lead: 李秉倫 · last updated 2026-11-29

Every decision below cites the DECISIONS.md entry, PR or review record behind it. Where no record exists we say so instead of supplying a reason after the fact.

## 1. Problem recap (from CP1)

- **Problem:** in small (3–5 person) graduate-student teams that split work by module, a member changes another member's module or shared code without telling the owner or recording why. The owner finds out at merge or integration. Sometimes nothing errors and the results are silently wrong. (CP1 §2; DECISIONS.md "Problem focus for CP1")
- **Evidence (CP1, two interviews outside the team, 20 Oct 2026):**
  - **Interviewee A** owned the front end of a 5-person course project. A back-end teammate changed A's login logic and the shared API config without telling A. This cost about 3 hours of rework and happened about 3 times in the last two weeks of the project.
  - **Interviewee B** owned similarity scoring in a 3-person research pipeline. Changes to candidate ordering and to shared pre-processing made the scores stop matching the candidates. There was no error, the wrong object was selected, and it took about 1 day to find. This happened 1–2 times a week during integration. B: "I know which function I changed, but not where other people use it."
- **Why existing tools fall short (CP1 table):**
  - LINE announcements depend on people remembering to send them.
  - PRs show *what* changed, not *why* or *who downstream* is affected.
  - CODEOWNERS is path-only: it does not explain a change or trace its callers.
- **Success definition (CP1 §4):** the owner reviews and accepts or rejects a cross-module change before merge, and fewer cross-module bugs reach `main`.

## 2. Key interaction decisions

Each decision is given as **Decision** · **Shaped by** · **Rejected**.

### D1. Rules decide who must sign off; the AI only explains
- **Decision:** the owners of touched paths come from `.changesignal/modules.yml`, by rule. Claude (`claude-opus-5-5`) only drafts the card text: what changed, what might break, and checks for the owner. The AI never approves, rejects or blocks.
- **Shaped by:**
  - Interviews A and B: the failure is that people do not know, and the agreement must come from a person.
  - The CP1 human–AI boundary table.
  - DECISIONS.md: "Problem focus for CP1"; "AI impact card with Claude; the API key stays out of PR code".
- **Rejected:**
  - Letting the AI decide which owners must sign off (PR #7 and PR #22 decision sections: "AI guesses can be wrong").
  - CODEOWNERS alone (path-only, no explanation, no callers).

### D2. Merge is blocked by a commit status until owners approve the current commit
- **Decision:** `changesignal/owner-ack` stays `pending` until every owner of a touched path has approved the PR's **current head commit**. A new push needs a fresh sign-off.
- **Shaped by:** the CP1 interaction sketch (owner sign-off before merge); DECISIONS.md "Walking skeleton design".
- **Rejected:** a plain "1 approving review" rule, because any member can approve, not only the affected owner.
- **Enforcement:**
  - **Our repository:** the `main` ruleset requires one approving review and the `changesignal/owner-ack` status, and blocks force pushes and deletion (checked with `gh api` on 2026-11-28).
  - **Demo repository** (`LiLOUIS0803/changesignal-demo`): branch protection was on, but its list of required status checks was empty during the 2026-11-29 internal trial (§3.2). The status showed `pending`, but GitHub did not block the merge. The required check was added on 2026-11-29, after the trial (verified via the branch-protection API).
  - README step 9 (PR #34) now tells installers to require the check only after the acceptance check in step 8 has passed once.

### D3. GitHub Action instead of GitHub App
- **Decision:** ChangeSignal ships as a GitHub Action (`.github/workflows/changesignal.yml`). The core logic is kept separate so it can be wrapped in an App later.
- **Shaped by:** team capacity and the CP2 timeline. DECISIONS.md: "Build ChangeSignal as a GitHub Action, not a GitHub App".
- **Rejected:** a GitHub App, because hosting and key management would take most of the remaining time and would likely fall on one person.
- **Accepted costs** (DECISIONS.md "AI impact card with Claude…", "Known limits"):
  - Each run waits about 20–60 s for a runner.
  - Comments are posted as `github-actions[bot]`.
  - PRs from forks are skipped.
  - A collaborator's PR can still add or edit a workflow and write a green status, so the gate is not tamper-proof. Only a GitHub App would remove this.

### D4. Fail closed for the gate, fail soft for the AI
- **Decision:**
  - **The gate may wrongly block, but must never wrongly let a PR through.** A missing or malformed `modules.yml` fails the check. The status is set to `pending` as the first workflow step. The module map is read at the PR's base commit.
  - **The AI is the opposite.** If the Claude call fails, refuses or returns an unexpected shape, the rule-based card is still posted with the affected modules and a note that the AI summary is unavailable. The merge gate never depends on the AI.
- **Shaped by:**
  - Three Codex review rounds of PR #4 and the module map rules. DECISIONS.md: "Fixes from Codex review of the walking skeleton (PR #4)", "Second Codex review of PR #4: make the gate fail closed", "Third Codex review of PR #4 (blockers only)", "Module map rules: one owner per path, malformed map fails".
  - The fail-soft rule for the AI is recorded in "AI impact card with Claude; the API key stays out of PR code".
  - Group 21's review confirmed the fail-soft path: with no API key, the card still listed the affected modules and owners (§3.1).
- **Rejected:**
  - Treating an empty or mistyped map as "no owners", because it would pass silently.
  - Blocking the PR when the AI is down, because it would make the AI part of the gate.

### D5. Possible callers are suggested reviewers, not required sign-offs
- **Decision:** `ast` caller detection finds code in other modules that calls a changed function. The owners of that code are requested as reviewers and shown on the card as possible callers, but they do not block the merge.
- **Shaped by:** interview B ("not where other people use it"); Codex's review of the caller-detection branch, which found both misses and false matches. DECISIONS.md: "Possible callers are suggested reviewers, not required sign-offs".
- **Rejected:** requiring sign-off from callers' owners, because a heuristic would become part of the gate.
- **Follow-up (§3.1, finding 3):** when only callers' owners were asked, the green status still said "No other member's module is affected." Since PR #33 it names who was asked, for example: "No sign-off required; asked 1 possible downstream owner to look: @Carol".

### D6. The card favours silent failures and asks for the author's reason
- **Decision:** the prompt asks for:
  - a behaviour-level "what changed";
  - risks tied to evidence in the diff, preferring silent failures such as misaligned data;
  - risks grouped by module;
  - up to 3 checks for the owner;
  - a flag when no reason is given (template text does not count).
- **Shaped by:**
  - Interview B (silently wrong results) and the CP1 output table ("any missing reason flagged").
  - DECISIONS.md "Rule-based PR reason detection (Issue #11)", "Combine risks that affect one module" (prompt suite 12/13 → 13/13), and "Prompt test cases and how they are checked".
- **Rejected:**
  - Keeping only the first entry per module in the renderer, because it would drop the second risk and its evidence ("Combine risks that affect one module").
  - Checking only whether the description is non-empty ("Rule-based PR reason detection").
  - No other alternative card formats are recorded.
- **Follow-up (§3.1, finding 2):** without the AI, any description with at least 10 non-whitespace characters counted as a reason. Since PR #32, a description that has text is shown as *unverified* ("please check that it explains this change"), not as "reason given".

### D7. Changed from CP1: no separate "author confirms the card" step
- **What differs:** in CP1's flow, the author confirmed or edited the AI card before the owner was asked. The prototype posts the card and requests the owners in the same run.
- **Record:** no decision recorded in DECISIONS.md. The team has to decide before CP3 whether to keep this or restore the step, and log the choice.

### D8. Other decisions
- **Ownership of our own repository (dogfooding):** we use ChangeSignal on the repository we build it in (DECISIONS.md "Module ownership for our own repository"). Since PR #35, every tracked file has an owner: the root files and `docs/` belong to the pipeline module, and a test fails if a tracked file matches no module (DECISIONS.md "Give every file an owner…").
- **Card language:** the repository variable `CHANGESIGNAL_LANG=zh-TW` gives a Traditional Chinese card. It was introduced in PR #7 and carried into PR #22; the README documents it in step 5. No decision recorded on why it is a repository-wide variable rather than per PR.
- **Installation is part of the product:** if a PR changes how ChangeSignal is installed, configured or run, it must update the README in the same PR (guideline R7). This came from Group 21's finding 1 (§3.1) and was fixed in PR #34. The README now lists both workflows and the `LLM_API_KEY` environment, and gives an acceptance check: after the owner approves, the same commit goes from `pending` to `success`.

## 3. User-testing findings

Only sessions with people outside the team count as user tests. Internal runs are reported separately in §3.2 and are labelled internal.

### 3.1 Session 1 — Week 12 cross-team review by Group 21 (peer-review session)

| Item | Content |
|---|---|
| Date | 2026-11-23/24; the review was sent to us via LINE on 2026-11-23 |
| Who | Group 21: 4 people outside our team (another course group) |
| Format | **Peer review run by the reviewers themselves.** We did not facilitate or observe the session. The reviewers did not play an owner facing the seeded break, and we ran no interview. |
| Version | our `main` at `6e2c1a0`, run by the reviewers on their own machines |
| What they did | A1: simulated a change to a file owned by "Bob", got a card, the owner was requested and the status was `pending`; the owner approved the current commit and it became `success`; a new commit set it back to `pending`; 199 tests passed. A2: with no API key, ran case 12 (the diff changes image cropping, the description is a lunch announcement). A3: read the labels and the module table. A4: read PR #26 and demo PR #1. |
| Source | Group 21's Week 12 submission, Part 1; our Week 12 submission, Part 2 |

**Not tested in this session:**
- a real owner deciding on the seeded `crop_regions` break with their own account;
- an observed timeline;
- card ratings;
- willingness to adopt;
- a fresh installation in another repository (finding 1 was "based on reading the two workflows").

**Problems found:**

| # | Problem (as Group 21 reported it) | Severity (theirs) | Design change | Record |
|---|---|---|---|---|
| 1 | The README's "Use it in another repository" listed only `changesignal.yml`, not `changesignal-review.yml`, so an owner's approval would not recompute `owner-ack`. We also found that the README did not explain the `LLM_API_KEY` environment. | blocks the main task (when installed in another repository) | The README lists both workflows and the key environment, with a step-by-step setup and an acceptance check | issue #28 → PR #34 (merged 2026-11-28); guideline R7 |
| 2 | Without the AI, unrelated text (case 12, a lunch announcement) passed the "≥10 non-whitespace characters" reason rule, so the card said a reason was given | will confuse users or reviewers | A description with text is shown as *unverified*, with a request to check it explains the change | issue #29 → PR #32 (merged 2026-11-27) |
| 3 | When only a downstream caller's owner was asked, `owner-ack` was green with the text "No other member's module is affected." | will confuse users or reviewers | The status names the downstream owners who were asked | issue #30 → PR #33 (merged 2026-11-28) |
| A4 | PR #26 reported test results but left "I read every line" and "tests pass" unticked | — | Rule: tick only the boxes that are true and say why for the rest | guideline R1, PR #31 (merged 2026-11-26) |

**Strength they named:** demo PR #1's card tied the risk to the code location `zip(boxes, scores)`, so the owner could check it with their own input (cup → book, tests still passing). We kept this combination of predicted failure, code location and owner question.

### 3.2 Internal controlled trial, 2026-11-29 (not a user test)

**Setup:** team role-play on `LiLOUIS0803/changesignal-demo` at `322927f`, whose ChangeSignal copy matches our `main` at `6e2c1a0`.

**How it ran:**
- Both PRs were opened from the same account, `LiLOUIS0803`, 4 seconds apart: PR #4 with a reason in the description, PR #5 with an empty description.
- That account owns `preprocess` and `scoring` in the demo map. To trigger a cross-member sign-off, both PRs also edited a docstring in `pipeline/candidates.py`, which is owned by `wonlin91`.
- No owner review was submitted, no one was interviewed, and both PRs were closed unmerged.
- Source: `user-testing/20261129-changesignal-roleplay.md`.

**Tool results (from GitHub records and local runs):**

| | PR #4 (reason given) | PR #5 (empty description) |
|---|---|---|
| Card after PR opened | 42 s | 34 s |
| Reason line on card | reason given in the description | asks the author to add a reason |
| `owner-ack` | `pending`, waiting for `@wonlin91` | `pending`, waiting for `@wonlin91` |
| GitHub merge state | not blocked (`mergeable_state: unstable`; no required checks in the demo repo) | same |
| Local `python run.py` | `cup` → `book`; the 3 existing tests pass | same |

**What the trial showed:**
- Both cards warned that scores could be paired with the wrong boxes. Both listed that risk under `candidates` and did not name the consuming code, `pipeline/scoring.py`'s `zip(boxes, scores)`.
  - This comes from the setup, not the prompt: the author account owns `scoring`, and ChangeSignal leaves the author's own modules off the card. In the 2026-11-23 rehearsal (demo PR #1), where the author did not own `scoring`, the card listed `scoring`, named `zip(boxes, scores)` at `pipeline/scoring.py:18`, and warned that `max()` raises `ValueError` when every box is filtered out.
- Neither card mentioned that `ValueError`, for the same reason: it lives in `scoring`, which was not on these cards.
- `pending` did not stop the merge, because the demo repository did not require `changesignal/owner-ack` (D2).

**Limits:**
- Same account for both PRs, and the role mapping was reversed (the author owned `scoring`).
- One run per condition; LLM output varies between runs.
- Both PRs were closed about 70 s after they were opened, so no one reviewed them as an owner.
- No owner decision and no human data.
- This trial is not a user test and is not counted as one.

### 3.3 Session 2 — scheduled, not yet run

> **Placeholder.** Not completed as of 2026-11-29.
>
> **Plan:** people outside the team, using the `user-testing/` kit (task cards `02` and `03`, observation sheet `04`, interview `05`, findings template `06`), on the demo repository with `changesignal/owner-ack` required. The author edits `pipeline/preprocess.py` from the `candidates` owner's account, and the owner (`preprocess` + `scoring`) submits a real review on GitHub. Only data observed in that session will be added here.

## 4. Design changes made because of findings

| # | Finding (source) | Change | Issue / PR | Status |
|---|---|---|---|---|
| 1 | README install misses the review workflow and the key environment (Session 1, #1) | Step-by-step setup, both workflows, `LLM_API_KEY` environment, acceptance check; rule R7 | #28 → #34 | Done (merged 2026-11-28) |
| 2 | Unrelated text shown as "reason given" without the AI (Session 1, #2) | Shown as unverified, with a regression test for case 12 | #29 → #32 | Done (merged 2026-11-27) |
| 3 | Green status says "no other module affected" when a caller's owner was asked (Session 1, #3) | Status names the owners who were asked; tests for both texts | #30 → #33 | Done (merged 2026-11-28) |
| 4 | Checkboxes unticked although tests were reported (Session 1, A4) | Guideline R1 | #31 | Done (merged 2026-11-26) |
| 5 | When the author also owns the downstream module (`scoring`), the card leaves it off, so the reviewer from another module is not pointed to `zip(boxes, scores)` or the all-filtered `ValueError` (internal trial, §3.2; compare demo PR #1) | None yet. Owners of their own modules are skipped by design (the author cannot sign off for themself); whether the card should still mention the author's own downstream code is open | — | Open, from internal trial |
| 6 | Demo repository did not require `changesignal/owner-ack`, so `pending` did not block the merge (internal trial, §3.2) | Required the check on the demo repository's `main` (verified via the branch-protection API, 2026-11-29); README step 9 already covers installers | — | Done (2026-11-29) |

**Already tracked, not from user tests:**
- Unowned files asked nobody to review: resolved by PR #35 (every tracked file has an owner, enforced by a test).
- Re-checking open PRs when `modules.yml` changes on `main`: deferred in "Third Codex review of PR #4 (blockers only)".
- Overlapping paths (for example `pkg/` and `pkg/report.py`) are not detected: noted in "Give every file an owner…".
