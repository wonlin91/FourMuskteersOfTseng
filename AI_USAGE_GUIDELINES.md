# AI Usage Guidelines — Group 10 (ChangeSignal)

Version 2026-11-24, after the Week 12 cross-team review. Each rule can be checked by a reviewer from the pull request alone. Evidence for each change is at the end.

## 1. Which AI tools we use, for what, and not for what

| Tool | We use it for | We do not use it for |
|---|---|---|
| Claude Code, Codex, ChatGPT (coding assistants) | First drafts of code, tests and docs from a spec or issue we wrote; explaining unfamiliar code | Deciding what to merge; writing someone else's review; DECISIONS.md reasoning no team member agreed to |
| Codex (as a second, independent model) | Reviewing AI-generated code before a teammate reviews it | Approving PRs; replacing the human review |
| Claude API inside ChangeSignal (`claude-opus-5-5`) | Drafting the impact card text: what changed, what might break, checks for the owner | Deciding who must sign off or whether a PR can merge: that is rule-based (`modules.yml`) and human (owner approval) |

## 2. How we document AI use

- **R1. Every PR fills in the template's "AI assistance" section** (tool and model, what it generated, the instruction, what the author changed afterwards) **and ticks only the "How I checked it" boxes that are true**, saying why for any it leaves empty. "None" is a valid answer. A footer such as "Generated with Claude Code" does not count, and neither does an untouched template.
- **R2. Commits containing AI-generated code carry a `Co-Authored-By:` line** naming the AI.
- **R3. If an AI suggestion changed our approach**, it gets a DECISIONS.md entry whose "Led by" names the person who decided.
- **R4. Any change to `changesignal/prompts/`** includes before/after results from the prompt test suite (`evals/`) in the PR.

## 3. How we check AI output before it reaches `main`

- **R5. AI-generated code gets an independent AI review (Codex) before a teammate reviews it**, and the PR lists what that review found, what was fixed and what was not (with the reason).
- **R6. An AI review never replaces the human one: the approving teammate names at least one behaviour or failure case they checked** (not only "LGTM" or "tests pass").
- **R7. If a PR changes how ChangeSignal is installed, configured or run, the README is updated in the same PR, with a check a new user can follow** (for example: "after the owner approves, the commit goes from pending to success").
- **R8. A person, not an AI agent, performs every action other people see or are notified about**: opening or closing PRs and issues, requesting reviews, inviting collaborators, merging.
- **R9. API keys live only in the `LLM_API_KEY` GitHub environment (limited to `main`) or a local `.env` listed in `.gitignore`**; never in chat, prompts, PRs, commits or plain repository variables.

## 4. When we disagree about AI output

The **code steward** has the final say on whether AI-generated code is good enough to merge, not the person who prompted it. Evidence that counts: CI passes, the independent AI review is addressed (R5), and a teammate other than the author explains a behaviour they checked (R6). A vote is not evidence. The decision and its reason go in one sentence in DECISIONS.md.

## Evidence behind these rules

- **Slide-4 numbers** for the 16 PRs opened since 2026-11-10 and merged: mostly AI-generated 13/16 (the other 3 do not say); explainable by someone else 13/16 (approval by a non-author with a written comment of 80+ characters); saying what the AI did 11/16. The 5 that did not: #4 (footer only), #10, #19 and #20 (template left empty), #24. → **R1**
- **Week 12 review, A4:** Group 21 found that merged #26 left "I read every line" and "tests pass" unticked although the description reported the test results. → **R1** (tick what is true, explain what is not)
- **#22:** after two Codex reviews, 陳苡翔's human review found that the two workflows could overwrite a newer `owner-ack` verdict with an older one, which would let a PR merge without the owner's approval. → **R5 and R6** (AI review first, but never instead of a person)
- **#4:** three Codex rounds found ways the gate could turn green without the owner, which the passing tests missed. → **R5**
- **Week 12 review, finding 1 (issue #28):** our README's install list omits `changesignal-review.yml`, so an owner's approval would not recompute `owner-ack`; checking it, we also found the README does not explain the `LLM_API_KEY` environment. → **R7**
- **#7:** opened by an AI-assisted workflow before review, on top of an unmerged PR; it requested three teammates' reviews and had to be closed. → **R8**
- **2026-11-23:** the key had been stored as a plain environment *variable*, so the workflow could not read it as a secret and teammates could see it. → **R9**
