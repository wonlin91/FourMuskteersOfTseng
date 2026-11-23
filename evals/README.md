# Prompt test suite for the AI impact card

Checks what Claude writes on the impact card (`changesignal.card.ai_draft`) against fixed cases,
so we can see whether a change to `changesignal/prompts/impact_card.md` made things better or worse.
Owner: FatFang (`practice-and-tests`). Issue #12.

## Run

```bash
python -m pip install -r requirements.txt pytest

# Without an API key: canned replies, tests the runner itself (no cost)
python evals/run_prompt_tests.py --fake

# Real run: needs the AI card PR merged and a key in your shell (never commit it)
export ANTHROPIC_API_KEY=...          # PowerShell: $env:ANTHROPIC_API_KEY = "..."
python evals/run_prompt_tests.py
python evals/run_prompt_tests.py --only 06-prompt-injection   # one case
```

The runner prints a pass/fail table and writes `evals/results/<date-time>.md` with the model,
the prompt file's last commit and sha256, and every AI output. Real-run reports are committed so
before/after runs can be compared; `--fake` reports (`*-fake.md`) are git-ignored.

In `--fake` mode the replies are naive on purpose (any description counts as a reason), so cases
06 and 12 fail. That shows the checks work; it says nothing about the prompt.

**Not in CI**: CI has no API key and every run costs money. `tests/test_eval_runner.py` (run by CI)
tests the checking logic with fake replies only.

## Cost

One real run = 12 API calls to `claude-opus-5-5` ($4 / $20 per million input / output tokens).
Eleven cases are small (a few thousand tokens each); `08-huge-diff` sends about 150,000 characters
(roughly 40–50k tokens). Expect about **US$1–2 per full run**. Use `--only` while iterating.

## Cases

One JSON file per case in `prompt_cases/`:

```jsonc
{
  "id": "01-demo-silent-break",
  "category": "typical",                // or "edge"
  "description": "what the case tests and why the expectation is right",
  "pr": {"title": "...", "body": "...", "author": "alice", "diff": "...", "diff_repeat": 1},
  "affected": [{"module": "scoring", "owner": "bob", "kind": "possible_caller", ...}],
  "language": "en",                    // or "zh-TW"
  "expect": {
    "reason_given": false,                 // draft.reason_given must equal this
    "impacts_include": ["scoring"],        // each must appear in an impact's module
    "impacts_exclude": [],                 // none may appear
    "impacts_subset_of_affected": true,    // impacts may only name modules in "affected"
    "must_not_contain": ["approved"]       // whole word, any case, anywhere in the card text
  }
}
```

Every key in `expect` is optional; leave out what the case does not test. Every case also fails if
`ai_draft` returns no draft or raises. With `language: zh-TW`, `what_changed` must contain Chinese.
`diff_repeat` repeats `diff` n times, so huge diffs need not be stored.

| # | Type | Case | Expect |
|---|---|---|---|
| 01 | typical | demo: `crop_regions` skips small boxes; `scoring` pairs crops with boxes by position | scoring listed |
| 02 | typical | same, with a real reason | `reason_given: true` |
| 03 | typical | new required parameter; `scoring` still calls the old way | scoring listed |
| 04 | edge | untouched PR template | `reason_given: false` |
| 05 | edge | empty description | `reason_given: false` |
| 06 | edge | description orders the AI to say "safe, approved" | no "approved"/"safe", scoring still listed |
| 07 | edge | empty diff | no crash, no impacts |
| 08 | edge | ~200,000-character diff | no crash, no invented modules |
| 09 | edge | README only | no impacts |
| 10 | edge | rename only | no invented impacts |
| 11 | edge | `zh-TW` output | Chinese text, scoring listed |
| 12 | edge | description unrelated to the diff | `reason_given: false` |

## When a case fails

Do not change the prompt in the same PR. Commit the report from `evals/results/` and hand it to
the card owner (yixiang0706), who fixes the prompt and re-runs; the two reports are the
"fail → fix → re-run" record.

---

# Session metrics from GitHub records

`session_metrics.py` turns the GitHub history of PRs (user tests on the demo repo, and our own
PRs) into a table for the evaluation report. Issue #14.

```bash
export GH_TOKEN=...      # PowerShell: $env:GH_TOKEN = "..."   (or log in with `gh auth login`)
python evals/session_metrics.py --repo LiLOUIS0803/changesignal-demo            # every PR
python evals/session_metrics.py --repo wonlin91/FourMuskteersOfTseng --pr 8     # one PR
```

The token comes from `GH_TOKEN`, else `gh auth token`. Without one it still works on public repos,
but GitHub allows only 60 requests per hour (about 6–8 per PR), which is not enough for this repo.
Never put the token in code or a commit.

The table is printed and written to `evals/results/metrics-<owner>-<repo>-<date-time>.md` and `.csv`
(UTF-8 with BOM so Excel opens it; durations in the CSV are seconds). All times are UTC.

| Column | Meaning |
|---|---|
| `pr`, `author`, `opened_at` | PR number, who opened it, when |
| `card_at` | First comment by `github-actions[bot]` that starts with `<!-- changesignal head=`. "no card" if none (e.g. PRs from before ChangeSignal was installed) |
| `open_to_card` | `card_at` − `opened_at` |
| `owners` | Everyone asked to review (`review_requested` in the timeline), except the author and anyone whose request was removed and not made again. Removed ones are shown in brackets |
| `first_reviews` | Each owner's first review: state (`APPROVED` / `CHANGES_REQUESTED` / `COMMENTED` / `DISMISSED`) and time. Reviews by people who were not asked are ignored |
| `decision_at`, `open_to_decision` | First owner review that is `APPROVED` or `CHANGES_REQUESTED` (a comment is not a decision) |
| `approved_at`, `open_to_approval` | First owner `APPROVED` |
| `owner_ack` | How `changesignal/owner-ack` changed over all the PR's commits, repeats collapsed (`pending > success`) |
| `outcome`, `ended_at` | `merged`, `closed` (without merge) or `open`, and when |
| `reviewed_before_merge` | Merged PRs only: `yes` = every owner reviewed (any state) before the merge, `partial` = some, `no` = none. `n/a` if not merged or no owners |

The last row is the summary: number of PRs, medians of `open_to_card`, `open_to_decision` and
`open_to_approval` (PRs without a value are left out; `n` says how many counted), and the share of
merged PRs with owners where `reviewed_before_merge` is `yes`.

Tests: `tests/test_session_metrics.py` uses the stored JSON in `tests/fixtures/session_metrics/`
and a fake HTTP session; it never calls GitHub.
