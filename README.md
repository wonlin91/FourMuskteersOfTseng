# FourMuskteersOfTseng
Final Project of "Ai-in-the-loop in Software Project Cycle". A course opened in NYCU in 2026.

## ChangeSignal

A GitHub Action for small module-based teams. When a pull request changes code owned by another member, ChangeSignal:

1. finds whose module is affected, using `.changesignal/modules.yml`;
2. posts an **impact card** on the PR (what changed, who may be affected, the author's reason);
3. requests the affected owners as reviewers and keeps the `changesignal/owner-ack` status **pending** until every affected owner approves the current commit.

> Status: walking skeleton. Owner detection and the GitHub flow work; caller detection and the AI-written card text are still stubs.

### Try it (two people)

1. **Author:** on a new branch in this repository, change a file owned by someone else (see `.changesignal/modules.yml`), e.g. `changesignal/card.py`, and open a PR.
2. Within about a minute the impact card appears, the owner is requested as reviewer, and `changesignal/owner-ack` shows *pending*.
3. **Owner:** review and approve the PR. The status turns *success*.
4. Pushing a new commit sets the status back to *pending* until the owner approves again.

PRs from forks are not supported (GitHub gives them a read-only token).

### Use it in another repository

1. Copy `.github/workflows/changesignal.yml`, `changesignal/` and `requirements.txt`.
2. Write `.changesignal/modules.yml` for that repository. Every owner must be a collaborator.
3. (Optional) In branch protection for `main`, require the status check `changesignal/owner-ack`.

### Develop

```bash
python -m pip install -r requirements.txt pytest
python -m pytest -q
```

| File | What it does | Owner |
|---|---|---|
| `.github/workflows/changesignal.yml`, `changesignal/main.py`, `changesignal/github_api.py` | Action, flow, GitHub REST calls | 李秉倫 |
| `.changesignal/modules.yml`, `changesignal/modules.py`, `changesignal/callers.py` | Module map, owner and caller detection | 蔡旺霖 |
| `changesignal/card.py`, `changesignal/prompts/` | Impact card and LLM prompt | 陳苡翔 |
| `practice/`, `tests/` | Practice repository for user tests, test suites | 楊子枋 |
