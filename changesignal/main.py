"""Entry point run by the GitHub Action.  Owner: LiLOUIS0803 (pipeline).

Every event recomputes the full state from GitHub (reconcile), so re-running a failed
or half-finished run is always safe.
"""
import json
import os
from pathlib import Path

from .callers import find_callers
from .card import build_card
from .github_api import MAX_PR_FILES, GitHubAPI
from .modules import find_affected, parse_modules

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


def reconcile(api, pr, changed_files, event_name, modules):
    number, head = pr["number"], pr["head_sha"]
    if pr.get("changed_files", 0) > MAX_PR_FILES:
        api.set_status(head, "failure",
                       f"PR changes more than {MAX_PR_FILES} files; ChangeSignal cannot see them all. Split it.")
        return {"affected": [], "missing": [], "state": "failure"}

    affected = find_affected(changed_files, modules, pr["author"])
    affected += find_callers(changed_files, modules)

    author = pr["author"].lower()
    owners = {a["owner"].lower(): a["owner"] for a in affected if a["owner"].lower() != author}
    approved = approved_owners(api.list_reviews(number), head)
    missing = sorted(owners[o] for o in owners if o not in approved)

    # The card records which commit it describes. If it is missing or stale (e.g. this review
    # run replaced a queued push run), redo the card and the reviewer requests here.
    existing = api.find_card(number)
    head_changed = existing is None or existing["head"] != head
    if head_changed or event_name == "pull_request":  # "edited" refreshes the author's reason
        if "diff" not in pr:
            pr["diff"] = api.get_diff(number)
        card = build_card(pr, affected)
        api.upsert_card(number, head, card["markdown"], existing)
    failed = api.request_reviewers(number, missing) if head_changed else []

    if not owners:
        state, desc = "success", "No other member's module is affected."
    elif missing:
        state, desc = "pending", "Waiting for sign-off: " + ", ".join("@" + m for m in missing)
    else:
        state, desc = "success", "All affected owners approved this commit."
    if failed:
        desc += " (could not request: " + ", ".join("@" + f for f in failed) + ")"
    api.set_status(head, state, desc)
    return {"affected": affected, "missing": missing, "state": state}


def load_base_modules(api, base_ref):
    """Read the module map from the base branch, so a PR cannot edit its own owners away."""
    text = api.get_file(MODULES_PATH, base_ref)
    if text is None:  # only when this PR is the one introducing the map
        print(f"::notice::{MODULES_PATH} not on {base_ref} yet; using this PR's copy.")
        text = Path(MODULES_PATH).read_text(encoding="utf-8")
    return parse_modules(text)


def main():
    event_name = os.environ["GITHUB_EVENT_NAME"]
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    api = GitHubAPI(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])
    number = event["pull_request"]["number"]

    # Fetch fresh state (the event can be stale) and make sure no push landed in between.
    for _ in range(3):
        pr = api.get_pr(number)
        files = api.list_pr_files(number)
        if api.get_pr(number)["head_sha"] == pr["head_sha"]:
            break
    else:
        print("PR head kept moving; the run for the newest push will finish the job.")
        return

    modules = load_base_modules(api, pr["base_ref"])
    result = reconcile(api, pr, files, event_name, modules)
    print(f"PR #{number} @ {pr['head_sha'][:7]}: {result['state']}; "
          f"affected={[a['module'] for a in result['affected']]}; missing={result['missing']}")


if __name__ == "__main__":
    main()
