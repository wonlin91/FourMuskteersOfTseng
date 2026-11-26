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

### Set it up in your own repository (for reviewers and TAs)

You need **two GitHub accounts**: an *author* who changes code and an *owner* who owns the module that gets changed. The author cannot approve their own PR, and ChangeSignal skips modules owned by the PR's author.

1. **Create a public repository** and add the second account as a collaborator with **write** access (the invitation must be accepted). A public repository avoids plan limits on environments; this project's own repository is public.
2. **Copy these files** from this repository into yours:
   - `changesignal/` (the whole folder)
   - `requirements.txt`
   - `.github/workflows/changesignal.yml` (PR events: posts the card, requests owners, sets the gate)
   - `.github/workflows/changesignal-review.yml` (review events: recomputes the gate after an approval)
   - `.changesignal/modules.yml`

   You need **both** workflow files. Without `changesignal-review.yml`, nothing recomputes the status when the owner approves, so `changesignal/owner-ack` stays *pending* until some later PR event (for example the next push).
3. **Edit `.changesignal/modules.yml`.** Replace our owners with your two usernames and our paths with paths that exist in your repository. Two modules with different owners are enough; the syntax (folders, files, `*` / `**` patterns) is explained in the comment at the top of the file. Example:

   ```yaml
   modules:
     - name: backend
       owner: account-a        # GitHub username, must be a collaborator
       paths: ["backend/"]
     - name: frontend
       owner: account-b
       paths: ["frontend/"]
   ```

   Add one small file under each folder (for example `backend/app.py` and `frontend/app.py`) so there is something to change. A malformed map makes the status fail with a short message that names the module and the field.
4. **Commit and push directly to `main`.** The workflows run from the default branch (`pull_request_target`), so a PR that only adds them does not trigger them.
5. **(Optional) Turn on the AI summary.** In *Settings → Environments*, create an environment named `LLM_API_KEY` (the workflow references it by that name), set *Deployment branches* to the default branch only (`main`), and add an environment **secret** (not a variable) named `LLM_API_KEY` containing an Anthropic API key. Limiting it to `main` means only the workflow from your default branch can read the key. Never put a key in the repository, a PR or the README. Without a key the card is still posted: it says that the AI summary is unavailable and lists the affected modules from the rules, which is complete. Optional repository variable `CHANGESIGNAL_LANG` = `zh-TW` writes the card in Traditional Chinese.
6. **Author:** create a branch in the same repository (forks are not supported), change `frontend/app.py` (the other account's module) and open a PR to `main`.
7. **Within about a minute** you should see: an *impact card* comment from `github-actions[bot]`, the owner requested as reviewer, and the status `changesignal/owner-ack` *pending* ("Waiting for sign-off: @account-b").
8. **Owner:** open the PR, choose *Review changes → Approve*. The `ChangeSignal review` run finishes and the status turns *success*. **Acceptance check:** on the PR's *Commits* tab, the same commit that was *pending* in step 7 now shows `changesignal/owner-ack` as *success*. If it does, the installation works. Pushing another commit sets it back to *pending* until the owner approves that commit.
9. **(Optional)** Only after step 8 has worked once: in branch protection (or a ruleset) for `main`, require the status check `changesignal/owner-ack`, so a pending status blocks the merge button. If you require it before the workflows are on `main`, no run ever reports the status and every PR is blocked.

**If something does not work**

| Symptom | Likely cause |
|---|---|
| No card, no status | The two workflow files are not on `main` yet, or Actions is disabled for the repository |
| Status stays *pending* after approval | `changesignal-review.yml` is missing, or the approval was on an older commit |
| Status says "Cannot request @name (collaborator?)" | That owner is not a collaborator, or the username in `modules.yml` has a typo |
| Status says "Invalid .changesignal/modules.yml: ..." | Read the message; it names the module and the field to fix |
| Nothing happens for a PR from a fork | Fork PRs are skipped on purpose |
| Card says "AI summary unavailable" | No `LLM_API_KEY` secret (expected), the key was saved as a variable instead of a secret, the environment is not allowed on `main`, or the API call failed; the owner list is still correct |

### Develop

```bash
python -m pip install -r requirements.txt pytest
python -m pytest -q
```

Prompt tests for the AI card (not in CI, real runs cost about US$1–2): see [`evals/README.md`](evals/README.md).

| File | What it does | Owner |
|---|---|---|
| `.github/workflows/changesignal.yml`, `changesignal/main.py`, `changesignal/github_api.py` | Action, flow, GitHub REST calls | 李秉倫 |
| `.changesignal/modules.yml`, `changesignal/modules.py`, `changesignal/callers.py` | Module map, owner and caller detection | 蔡旺霖 |
| `changesignal/card.py`, `changesignal/prompts/` | Impact card and LLM prompt | 陳苡翔 |
| `practice/`, `tests/`, `evals/` | Practice repository for user tests, test suites, AI prompt tests | 楊子枋 |
