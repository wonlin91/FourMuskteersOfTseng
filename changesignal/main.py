"""Entry point run by the GitHub Action.  Owner: LiLOUIS0803 (pipeline).

Every event recomputes the full state from GitHub (reconcile), so re-running a failed
or half-finished run is always safe. The gate fails closed: the status is set to pending
before anything can go wrong, and any error leaves it red, never green.
"""
import json
import os
import subprocess
from pathlib import Path

from .callers import find_callers
from .card import build_card
from .github_api import MAX_PR_FILES, GitHubAPI
from .modules import ModuleMapError, find_affected, parse_modules

MODULES_PATH = ".changesignal/modules.yml"
PR_EVENTS = ("pull_request", "pull_request_target")
# Where the PR head is checked out for caller detection. The workflow runs ChangeSignal's own
# code from the base branch and checks the PR out separately, only to parse it (never run it).
REPO_ROOT = os.environ.get("CHANGESIGNAL_REPO_ROOT", ".")


def approved_owners(reviews, head_sha):
    """Logins (lowercase) whose latest decisive review on `head_sha` is APPROVED.

    Approval is per commit: a new push needs a fresh approval. COMMENTED reviews are ignored;
    CHANGES_REQUESTED and DISMISSED count as not approved.
    """
    latest = {}
    for r in reviews:  # GitHub returns reviews oldest first
        if r.get("commit_id") != head_sha or r.get("state") == "COMMENTED":
            continue
        latest[_login(r)] = r["state"]
    return {login for login, state in latest.items() if state == "APPROVED"}


def _login(review):
    return ((review.get("user") or {}).get("login") or "").lower()


def reconcile(api, pr, changed_files, event_name, modules, patches=None, write_card=True):
    """write_card=False (review events): the run has no API key, so it leaves the AI card
    alone; reviewer requests and the status are still recomputed."""
    number, head = pr["number"], pr["head_sha"]
    if pr.get("changed_files", 0) > MAX_PR_FILES:
        api.set_status(head, "failure",
                       f"PR changes more than {MAX_PR_FILES} files; ChangeSignal cannot see them all. Split it.")
        return {"affected": [], "missing": [], "state": "failure"}

    affected = find_affected(changed_files, modules, pr["author"])
    author = pr["author"].lower()
    # Callers in the author's own modules need no one else's sign-off; leave them off the card.
    affected += [c for c in find_callers(changed_files, modules, REPO_ROOT, patches)
                 if c["owner"].lower() != author]

    # Owners of touched paths must sign off (rule). Owners of possible callers are asked to
    # review but do not block: caller detection is a guess (CP1: the owner decides whether
    # a suggested caller matters).
    owners = {a["owner"].lower(): a["owner"] for a in affected
              if a["kind"] == "owned_path" and a["owner"].lower() != author}
    suggested = {a["owner"].lower(): a["owner"] for a in affected
                 if a["kind"] == "possible_caller" and a["owner"].lower() not in owners}
    # Card: redo it when it is missing or describes an older commit, and on any PR event
    # ("edited" refreshes the reason). This comes BEFORE reading the reviews: the AI call is
    # slow, and a verdict computed from reviews read before it could overwrite a newer one
    # (e.g. an approval dismissed during the call).
    existing = api.find_card(number)
    if write_card and (existing is None or existing["head"] != head or event_name in PR_EVENTS):
        if "diff" not in pr:
            pr["diff"] = api.get_diff(number)
        card = build_card(pr, affected)
        api.upsert_card(number, head, card["markdown"], existing)

    reviews = api.list_reviews(number)
    approved = approved_owners(reviews, head)
    missing = sorted(owners[o] for o in owners if o not in approved)

    # Requests: ask every missing owner who is not already asked and has not reviewed this
    # commit yet. Stateless, so a failed request is retried on the next run, while an owner
    # who just requested changes is not asked again because the author edited the PR text.
    asked = {login.lower() for login in api.requested_logins(number)}
    reviewed_here = {_login(r) for r in reviews if r.get("commit_id") == head}
    to_request = [m for m in missing + sorted(suggested.values())
                  if m.lower() not in asked and m.lower() not in reviewed_here
                  and m.lower() not in approved]
    failed = api.request_reviewers(number, to_request) if to_request else []

    if not owners:
        state, desc = "success", "No other member's module is affected."
    elif missing:
        state, desc = "pending", "Waiting for sign-off: " + ", ".join("@" + m for m in missing)
    else:
        state, desc = "success", "All affected owners approved this commit."
    if failed:  # put it first so the 140-character limit cannot cut it off
        desc = "Cannot request " + ", ".join("@" + f for f in failed) + " (collaborator?). " + desc
    api.set_status(head, state, desc)
    return {"affected": affected, "missing": missing, "state": state}


def load_modules_for(api, pr):
    """The module map as of the PR's base commit, so a PR cannot edit its own owners away."""
    text = api.get_file(MODULES_PATH, pr["base_sha"])
    if text is None:  # only the PR that introduces the map
        print(f"::notice::{MODULES_PATH} not on {pr['base_ref']} yet; using this PR's copy.")
        text = api.get_file(MODULES_PATH, pr["head_sha"])
    if text is None:
        raise ModuleMapError(f"{MODULES_PATH} not found")
    return parse_modules(text)


def run(api, number, event_name, checkout_sha=None, write_card=True):
    """checkout_sha: the commit checked out on disk. Caller detection parses those files
    with line numbers from the PR patch, so they must be the PR head the patch describes."""
    # Fetch fresh state (the event can be stale) and make sure no push or base change
    # landed while we were listing files.
    for _ in range(3):
        pr = api.get_pr(number)
        if pr["changed_files"] > MAX_PR_FILES:
            return reconcile(api, pr, [], event_name, [])
        files, patches = api.list_pr_changes(number)
        latest = api.get_pr(number)
        if (latest["head_sha"], latest["base_sha"]) == (pr["head_sha"], pr["base_sha"]):
            break
    else:
        api.set_status(latest["head_sha"], "pending", "PR kept changing during the check; re-run the job.")
        return {"state": "pending", "affected": [], "missing": []}

    if checkout_sha and checkout_sha != pr["head_sha"]:
        # A newer push arrived after this run started; its own run checks the new head.
        api.set_status(pr["head_sha"], "pending", "PR changed while checking; the run for the newest push decides.")
        return {"state": "pending", "affected": [], "missing": []}

    try:
        modules = load_modules_for(api, pr)
    except ModuleMapError as e:
        api.set_status(pr["head_sha"], "failure", f"Invalid {MODULES_PATH}: {e}")
        raise
    return reconcile(api, pr, files, event_name, modules, patches, write_card)


def _checkout_sha():
    try:
        out = subprocess.run(["git", "-C", REPO_ROOT, "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None  # not a git checkout (e.g. local runs): skip the check


def main():
    event_name = os.environ["GITHUB_EVENT_NAME"]
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    api = GitHubAPI(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])
    number = event["pull_request"]["number"]

    head = api.get_pr(number)["head_sha"]
    checkout = _checkout_sha()
    if checkout and checkout != head:
        # An old run (e.g. re-run from the Actions tab) for a commit that is no longer the PR
        # head: touch nothing, so it cannot overwrite the current head's verdict.
        print(f"Checked-out {checkout[:7]} is not the PR head {head[:7]}; nothing to do.")
        return

    # Fail closed: replace any earlier verdict on this commit before doing anything fallible.
    api.set_status(head, "pending", "ChangeSignal is checking this commit...")
    try:
        result = run(api, number, event_name, checkout,
                     write_card=os.environ.get("CHANGESIGNAL_WRITE_CARD", "1") != "0")
    except ModuleMapError:
        raise  # status already set to failure with the reason
    except Exception as e:
        api.set_status(head, "error", f"ChangeSignal failed ({type(e).__name__}); see the run log.")
        raise
    print(f"PR #{number}: {result['state']}; "
          f"affected={[a['module'] for a in result['affected']]}; missing={result['missing']}")


if __name__ == "__main__":
    main()
