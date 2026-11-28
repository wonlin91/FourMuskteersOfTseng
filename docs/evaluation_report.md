# ChangeSignal — Interim Evaluation Report (CP2)

2026-11-29 · Group 10 · Lead: 李秉倫; metrics tool: 楊子枋 (`evals/session_metrics.py`, issue #14)

We report only what we observed. Internal checks by team members are labelled **internal** and are not counted as user tests.

## 1. What we set out to show (CP1)

**Success definition (CP1 §4):** when one member changes code in another member's module, the owner reviews and accepts or rejects the change before it is merged, instead of discovering it at integration, and fewer cross-module bugs reach `main`.

**CP1 method:** structured observation and a 5-minute interview with pairs from outside the team. Each pair does a baseline task (plain PRs and LINE) and a ChangeSignal task, in counterbalanced order, with one seeded silent break per task. **CP1 minimum:** at least 6 pairs (12 people outside the team).

**Where we are:** 2 sessions with people outside the team:
- the Week 12 cross-team review by Group 21, run by the reviewers themselves (E2);
- one observed owner review by P2 (E7).

The baseline condition has **not** been run, and both sessions fall well short of the 6 pairs planned in CP1. Section 4 lists what this leaves untested.

## 2. Evidence

| # | What | Who | Date | Counted as user test? | Source |
|---|---|---|---|---|---|
| E1 | Internal rehearsal, demo PR #1 | wonlin91 (author), LiLOUIS0803 (owner) | 2026-11-23 | No (team members who knew the seeded break) | `LiLOUIS0803/changesignal-demo#1`; metrics file below |
| E2 | Week 12 cross-team review | Group 21 (4 people outside the team) | 2026-11-23/24 | **Yes, Session 1** (self-run by the reviewers, not observed by us) | Group 21's Week 12 lab; our issues #28–#30 |
| E3 | Prompt test suite, 13 cases, live model | yixiang0706, FatFang | 2026-11-24 | No (automated) | `evals/results/20261124-*.md`; PR #26 |
| E4 | Internal controlled trial: reason vs. empty description | team role-play, one account | 2026-11-29 | No | demo PRs #4, #5; `user-testing/20261129-changesignal-roleplay.md` |
| E6 | Internal follow-up after requiring `owner-ack`: the broken fix vs. a corrected fix | team, one account (`LiLOUIS0803`) | 2026-11-29 | No (the operator knew the seeded break) | demo PRs #6, #7; `user-testing/20261129-changesignal-participant-record.md` |
| E7 | Owner review of the seeded break by an outside participant (P2) | P2 (outside the team); facilitator 李秉倫 | 2026-11-29 | **Yes, Session 2** (observed; limits below) | demo PRs #9, #10; facilitator's notes |
| E5 | Merge-day fresh clone of `main` | run by Claude Code for 李秉倫 | 2026-11-29 | No | `docs/merge_day.md` |

### E1 — Internal rehearsal (demo PR #1)
- **Change:** wonlin91 changed `crop_regions` to skip boxes smaller than 32 px. This is the seeded silent break: `scoring.py` pairs scores with boxes by position, so `run.py` selects `book` instead of `cup`. The demo repository's tests stay green.
- **Card:** listed `scoring` and named `zip(boxes, scores)` at `pipeline/scoring.py:18`. It also warned that `max()` raises `ValueError` when every box is filtered out.
- **Owner:** LiLOUIS0803 requested changes, then approved. `owner-ack` went `pending` → `success`.

### E2 — Session 1: Group 21's cross-team review
Group 21 ran our `main` at `6e2c1a0` on their own machines, following Track A.

**What they did:**
- Simulated a change to a file owned by another member.
- Checked that `owner-ack` went `pending` → `success` after the owner approved, and back to `pending` after a new commit.
- Ran case 12 without an API key.
- Read PR #26 and demo PR #1.
- 199 tests passed for them.

**Findings, and what we changed:**

| Group 21 finding | Severity they gave | Our change |
|---|---|---|
| README omits `changesignal-review.yml`, so an owner's approval would not recompute `owner-ack` | blocks the main task (in another repo) | #28 → PR #34: step-by-step setup with both workflows, the `LLM_API_KEY` environment, and an acceptance check |
| Without the AI, an unrelated description (case 12, a lunch notice) was shown as "reason given" | confusing | #29 → PR #32: shown as unverified ("please check that it explains this change"), with a regression test |
| Green status said "No other member's module is affected" while a caller's owner had been asked | confusing | #30 → PR #33: the status names the owners who were asked |
| PR #26 reported test results but left "I read every line" and "tests pass" unticked | — | Guideline R1 (PR #31) |

**Strength they named:** the card's "what could go wrong, where in the code, what to check" let an owner verify the AI's claim with their own input.

**Limits:**
- We did not observe the session.
- There was no seeded-break owner task and no interview, so this session gives no data on owner awareness or time.

### E3 — Prompt test suite
Model `claude-opus-5-5`, rule-based checks (DECISIONS.md "Prompt test cases and how they are checked").

| Run | Prompt commit | Result |
|---|---|---|
| 2026-11-24 02:09 | `37b80a7` | 12/12 |
| 2026-11-24 02:14 (case 13 added) | `37b80a7` | 12/13: case 13 (two risks in one module) failed |
| 2026-11-24 02:16 (prompt fixed in PR #26) | `33c3653` | 13/13 |

This is the required fail → fix → rerun cycle. It is one run per prompt version, so it is not a reliability rate.

### E4 — Internal controlled trial (2026-11-29)
**Setup:**
- Two PRs were opened 4 seconds apart from the same account (`LiLOUIS0803`). PR #4 had a reason in the description; PR #5 had an empty description.
- Both made the same `crop_regions` change and also edited a docstring in `pipeline/candidates.py` (owned by `wonlin91`) to trigger a cross-member sign-off.
- No owner review was submitted, nobody was interviewed, and both PRs were closed about 70 s after they were opened.

**What the trial showed:**
- **Reason check:** the card said "reason given" on PR #4 and asked for a reason on PR #5.
- **Risk warning:** both cards warned that crops could be paired with the wrong boxes.
- **Downstream code missing:** neither card named `scoring.py`. The author account owns `scoring`, and ChangeSignal leaves the author's own modules off the card, so this comes from the role setup. In E1 the author did not own `scoring`, and the card named it.
- **Seeded break reproduced:** run locally, the change selected `book` instead of `cup`, and the 3 existing tests still passed.
- **Merge not blocked:** GitHub did not block either PR, because the demo repository did not require `changesignal/owner-ack`. We added that requirement after the trial (verified 2026-11-29); in E6 both PRs were blocked.

### E6 — Internal follow-up after requiring `owner-ack` (2026-11-29)
**Setup:**
- Two PRs, opened one after the other from `LiLOUIS0803`. Both also edited `pipeline/candidates.py` so that `wonlin91` was requested.
- No owner review was submitted. Each PR was closed about 1 minute after it was opened.

**PR #6 — the broken fix:**
- It is the same `crop_regions` change as E4.
- The card warned that the shortened crop list could pair scores with the wrong boxes. It did not name `scoring.py`, for the same role-setup reason as E4.
- Run locally, it selected `book` instead of `cup`, and the 3 tests still passed.
- With all boxes filtered out, it raised `ValueError`.

**PR #7 — the corrected fix:** it moves the filter to the candidate stage, so boxes and scores stay aligned.
- Run locally, it selected `cup` again. With all boxes filtered out, it reported that no candidate was left, instead of crashing.
- The card raised a different risk: the 32-pixel threshold may silently drop a real small target.

**Gate:** with `changesignal/owner-ack` now required, the trial log records GitHub showing both PRs as `blocked` while waiting for the owner. The required check itself was verified through the branch-protection API.

### E7 — Session 2: owner review by P2 (2026-11-29)

**Participant and setup:**
- P2 is outside the team, a CS master's student (year 1). P2 was not told about the seeded break.
- Demo PR #9 made `wonlin91` the owner of `preprocess` and `scoring`.
- The facilitator opened demo PR #10 (the `crop_regions` change, with a one-line reason) from `LiLOUIS0803`.
- P2 reviewed on that account as the owner and wrote the decision as a PR comment, since the author account cannot review its own PR.

**What happened:**
- The card appeared 27 s after the PR opened. It listed `preprocess` and `scoring`, named `zip(boxes, scores)` at `pipeline/scoring.py:18`, and warned about the all-filtered `ValueError`.
- 6 min 41 s after the card, P2 commented "request changes". P2 stated that cup's score had gone to book, that an all-filtered input raises `ValueError`, and asked for one shared filtered list and two regression tests.

**From the facilitator's notes (close to verbatim):**
- Card usefulness: 4/5. P2 said the card's pointer to `zip(boxes, scores)` showed where to look, and that a tiny example (two boxes, one score) would have made it faster.
- Willingness: P2 would try it on a shared lab pipeline, but would read it less if it often flagged unrelated files.

**Not recorded:** whether P2 ran `run.py`; interview questions 1, 2, 4 and 6; the reaction at the reveal.

### E5 — Merge day
- Fresh clone of `main` at `24d22e4`, following only README "Develop": 213 tests passed (Python 3.14.4).
- `main`'s ruleset requires 1 approval and the `changesignal/owner-ack` status.
- Details: `docs/merge_day.md`.

### Measured times (`evals/session_metrics.py` on the demo repository)

| PR | Open → card | Open → owner decision | Open → approval | `owner-ack` |
|---|---|---|---|---|
| #1 (E1) | 33 s | 8 m 38 s (changes requested) | 12 m 13 s | pending → success |
| #4 (E4) | 42 s | — | — | pending |
| #5 (E4) | 34 s | — | — | pending |
| #6 (E6) | 34 s | — | — | pending |
| #7 (E6) | 36 s | — | — | pending |
| #10 (E7) | 27 s | 6 m 41 s after the card (decision as a comment) | — | pending (closed unmerged) |

Median time from PR opened to card: 34 s (n = 6). These include the Actions runner start-up; LLM time alone is not recorded.

## 3. Metrics against CP1 thresholds

| Metric (CP1) | Threshold (CP1) | Evidence | Status |
|---|---|---|---|
| Owner awareness before merge | Owners review ≥ 90% of cross-module changes before merge | E7: P2 knew before deciding that scores were paired with the wrong boxes (1/1). E1: 1/1, but the owner was a team member who knew the break. | 1 user session; far below the planned sample |
| Escaped breaks | Seeded break caught before merge in ≥ 5 of 6 pairs, clearly more than baseline | E7: caught (1 of 1), changes requested. E1: changes requested. E4: no owner decision. Tests stayed green in all of them, so tests alone would not catch it. No baseline. | 1 of the 6 planned pairs; no baseline |
| Time to diagnose | Minutes from failing integration to finding the change | Not measured | Not tested |
| Card quality | ≥ 70% of cards rated 4–5; < 1 in 5 cards lists a wrong module | E7: rated 4/5 (n = 1). Wrong modules: 0 of 6 demo cards listed a module that was not touched. In E6 the card for the corrected fix raised a different, relevant risk (small targets dropped). Prompt suite: 13/13 after one fix (E3). | n = 1 rating |
| Overhead per PR | Median < 5 min per PR | Machine time: median 34 s to card (n = 6). Human time: E7 owner decision 6 min 41 s after the card (n = 1); perceived overhead was not asked. | Not enough data |
| Author wrote a reason | (CP1 interview metric) | E4: the card told the two cases apart (reason / no reason). E2 showed that, without the AI, unrelated text passed as a reason; fixed in #32. | Internal only |

## 4. What we have not tested yet

- **Enough observed sessions with people outside the team:** we planned at least 6 pairs in CP1, and have 1 self-run peer review (E2) and 1 observed owner review (E7). In E7 the author was a team member, the owner used a team account, and the decision was a comment rather than a formal review.
- **The baseline condition** (plain PR and LINE): no comparison exists.
- **Card ratings and interview metrics beyond one person:** one rating (4/5), one willingness answer, and no perceived-overhead answer.
- **More than one scenario:** only the `crop_regions` image-pipeline case; no front-end or API case like interviewee A's.
- **Use over time:** multiple owners, many PRs over time (noise, fatigue), and an owner who replies the next day.
- **Installation by a team that is not ours:** Group 21 ran our repo locally. Nobody outside the team has followed the new README into their own repository yet.
- **Cost per card:** not measured. The full prompt suite costs about US$1–2 per run (README).

## 5. Threats to validity

- **Internal checks are not user tests.** In E1 and E4 the participants designed the seeded break.
- **Session 1 was self-run by the reviewers.** We did not observe it, and its goal was a review, not the CP1 task.
- **Session 2 had several weak points:**
  - one participant;
  - the facilitator was also the author;
  - the participant used a team account;
  - the notes are close to verbatim, not a recording;
  - the card pointed straight at the faulty line, so finding the break was assisted by the tool under test. This is what the tool is for, but it says nothing about a card that misses the line.
- **One run per condition.** LLM output varies between runs; a correct card is not a quality rate.
- **Role setup affects the card.** In E4 the author owned `scoring`, so the card left it off; E1 and E4 are not directly comparable.
- **Tiny seeded demo.** The task is role-played on a small repository with no real deadline or stakes.
- **We built and judge the tool.** We wrote the tool, the scenario and the checks. Mitigations:
  - the CP1 thresholds were fixed in advance;
  - the prompt suite uses fixed rule checks rather than an LLM judge;
  - the session times come from GitHub records via `session_metrics.py`, not from self-report.
- **Sample:** CP1 interviewees, Group 21 and planned participants are all graduate students.
- **Versions:**
  - The demo repository runs ChangeSignal from `main` at `6e2c1a0`, the version Group 21 reviewed. It does not yet include #32–#35.
  - `main` is now at `24d22e4`.

## 6. Next steps to CP3

- [ ] Run observed sessions with people outside the team, using the `user-testing/` kit, and add the baseline condition. If the CP1 threshold of 6 pairs is reduced, record the reason in DECISIONS.md.
- [ ] Update the demo repository to the current `main` (#32–#35) before the next session.
- [ ] Decide whether the card should mention the author's own downstream code (E4).
- [ ] Measure tokens and cost per card from the API usage fields.
- [ ] Re-check open PRs when `modules.yml` changes on `main` (deferred in "Third Codex review of PR #4 (blockers only)").
