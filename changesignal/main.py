"""Entry point run by the GitHub Action.  Owner: LiLOUIS0803 (pipeline).

Every event recomputes the full state from GitHub (reconcile), so re-running a failed
or half-finished run is always safe.
"""
import json
import os
from pathlib import Path

from .callers import find_callers
from .card import build_card
from .github_api import GitHubAPI
from .modules import find_affected, load_modules

MODULES_PATH = ".changesignal/modules.yml"


def approved_owners(reviews, head_sha):
    """Logins (lowercase) whose latest decisive review on `head_sha` is APPROVED.

    Approval is per commit: a new push needs a fresh approval. COMMENTED reviews are ignored;
    CHANGES_REQUESTED and DISMISSED count as not approved.
    """
    latest = {}
    for r in reviews:  # GitHub returns reviews oldest first
        if r.get("commit_id") != head_sha or r.get("state") == "COMMENTED":
            continue
        login = ((r.get("user") or {}).get("login") or "").lower()
        latest[login] = r["state"]
    return {login for login, state in latest.items() if state == "APPROVED"}


def reconcile(api, pr, changed_files, event_name, modules_path=MODULES_PATH):
    modules = load_modules(modules_path)
    affected = find_affected(changed_files, modules, pr["author"])
    affected += find_callers(changed_files, modules)

    author = pr["author"].lower()
    owners = {a["owner"].lower(): a["owner"] for a in affected if a["owner"].lower() != author}
    approved = approved_owners(api.list_reviews(pr["number"]), pr["head_sha"])
    missing = sorted(owners[o] for o in owners if o not in approved)

    # The card and reviewer requests only change when the code changes, not on reviews.
    if event_name == "pull_request":
        card = build_card(pr, affected)
        api.upsert_comment(pr["number"], card["markdown"])
        api.request_reviewers(pr["number"], missing)

    if not owners:
        state, desc = "success", "No other member's module is affected."
    elif missing:
        state, desc = "pending", "Waiting for sign-off: " + ", ".join("@" + m for m in missing)
    else:
        state, desc = "success", "All affected owners approved this commit."
    api.set_status(pr["head_sha"], state, desc)
    return {"affected": affected, "missing": missing, "state": state}


def main():
    event_name = os.environ["GITHUB_EVENT_NAME"]
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    api = GitHubAPI(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])

    number = event["pull_request"]["number"]
    pr = api.get_pr(number)  # fetch fresh: the event payload can be stale
    pr["diff"] = api.get_diff(number) if event_name == "pull_request" else ""
    files = api.list_pr_files(number)

    result = reconcile(api, pr, files, event_name)
    print(f"PR #{number} @ {pr['head_sha'][:7]}: {result['state']}; "
          f"affected={[a['module'] for a in result['affected']]}; missing={result['missing']}")


if __name__ == "__main__":
    main()
