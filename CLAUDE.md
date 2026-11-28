# CLAUDE.md

Guidance for AI coding assistants (Claude Code, Codex) working in this repository. Read it before changing anything. Human teammates follow the same rules in [AI_USAGE_GUIDELINES.md](AI_USAGE_GUIDELINES.md).

## Project in one paragraph

ChangeSignal is a GitHub Action for small module-based student teams. When a pull request changes code owned by another member, it finds the affected owners from `.changesignal/modules.yml`, posts an impact card on the PR, requests those owners as reviewers, and keeps the commit status `changesignal/owner-ack` pending until every affected owner approves the current commit. Claude drafts part of the card text; it never decides who must sign off or whether the PR can merge. See [README.md](README.md) for setup and [DECISIONS.md](DECISIONS.md) for why things are the way they are.

## Architecture

```
PR event ─► main.py ─► modules.py   files → owners (rules, from the base commit's modules.yml)
                   ├─► callers.py   ast: code in other modules that calls a changed function
                   ├─► card.py      card text; Claude drafts "what changed / what might break / checks"
                   │    └─ reason.py   offline check of the PR description (no AI)
                   └─► github_api.py  the only file that talks to GitHub (comment, reviewers, status)
```

| Path | What it does | Owner (module) |
|---|---|---|
| `.github/workflows/`, `changesignal/main.py`, `changesignal/github_api.py`, `changesignal/__init__.py`, root files (`README.md`, `CLAUDE.md`, `DECISIONS.md`, `AI_USAGE_GUIDELINES.md`, `CONTRIBUTORS.md`, `pyproject.toml`, `requirements.txt`, `.gitignore`, PR template), `docs/` | Action, flow, GitHub calls, repo documents | LiLOUIS0803 (pipeline) |
| `.changesignal/`, `changesignal/modules.py`, `changesignal/callers.py` | Module map, owner and caller detection | wonlin91 (detect) |
| `changesignal/card.py`, `changesignal/prompts/`, `changesignal/reason.py` | Impact card, LLM prompt, offline reason check | yixiang0706 (card) |
| `practice/`, `tests/`, `evals/` | Practice repo, tests, prompt test suite, session metrics | FatFang (practice-and-tests) |

Two workflows: `changesignal.yml` (`pull_request_target`, PR events, has the API key) and `changesignal-review.yml` (review events, no key). Both share one concurrency group per PR.

## Invariants: do not break these

1. **The gate fails closed.** ChangeSignal may wrongly block a PR but must never wrongly let one through. The status is set to pending before any step that can fail; a missing or malformed `modules.yml` fails the check. (DECISIONS.md: "Second Codex review of PR #4: make the gate fail closed", "Third Codex review of PR #4", "Module map rules: one owner per path, malformed map fails")
2. **The AI only explains.** The card is fail-soft: if the Claude call fails, the rule-based card is still posted. Never make the gate, the owner list or the reviewer requests depend on the LLM. (DECISIONS.md: "AI impact card with Claude; the API key stays out of PR code")
3. **Possible callers are suggestions.** Owners found by `callers.py` are requested and shown on the card but never become required sign-offs. (DECISIONS.md: "Possible callers are suggested reviewers, not required sign-offs")
4. **The module map is read from the PR's base commit**, so a PR cannot edit its own owners away (`load_modules_for` in `main.py`).
5. **PR code never runs with the key.** `pull_request_target` runs workflow and ChangeSignal code from `main`; the PR head is checked out into `pr-head/` only to be parsed with `ast`. Do not add steps that execute PR code in that job.
6. **Every tracked file has an owner.** `tests/test_modules.py::test_every_tracked_file_has_an_owner` fails if a file matches no module. When you add a file in a path the map does not cover, add the path to `.changesignal/modules.yml` in the same PR. (DECISIONS.md: "Give every file an owner")

## How to work here

```bash
python -m pip install -r requirements.txt pytest
python -m pytest -q                         # what CI runs
python evals/run_prompt_tests.py --fake     # prompt-suite runner, no API cost
python evals/run_prompt_tests.py --only 06-prompt-injection   # real run, needs ANTHROPIC_API_KEY in your shell
```

- Real prompt-test runs cost about US$1–2 for the full suite and are not in CI (`evals/README.md`).
- Work on a branch; never push to `main` (protected: one approval and `changesignal/owner-ack` required).
- Fill in the PR template's "AI assistance" section and tick only true boxes (R1). AI-written commits carry a `Co-Authored-By:` line (R2).
- AI-generated code gets a Codex review before a teammate reviews it (R5).
- Any change under `changesignal/prompts/` includes before/after prompt-suite results in the PR (R4).
- A change to how ChangeSignal is installed, configured or run updates the README in the same PR (R7).

## What not to do

- Do not open or close PRs or issues, request reviews, invite collaborators or merge on a person's behalf (R8). Prepare the branch and the text; the person does the visible action.
- Never put API keys in code, prompts, PRs, commits, chat or repository variables. The key lives only in the `LLM_API_KEY` environment (limited to `main`) or a git-ignored local `.env` (R9).
- Do not change ownership in `.changesignal/modules.yml` without the affected owner's approval.
- Do not weaken a fail-closed check to make a test pass, and do not let AI output decide merge.
- Do not record results, quotes or numbers in docs that are not in a PR, a test report or DECISIONS.md.
