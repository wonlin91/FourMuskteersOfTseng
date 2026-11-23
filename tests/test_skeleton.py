"""Walking-skeleton tests: the whole flow with a fake GitHub API.  Run: python -m pytest -q"""
from pathlib import Path

from changesignal.github_api import GitHubAPI
import pytest

from changesignal.main import approved_owners, load_modules_for, reconcile, run
from changesignal.modules import ModuleMapError, find_affected, load_modules, parse_modules

HEAD = "a" * 40
OLD = "b" * 40
MODULES = parse_modules("""
modules:
  - {name: pipeline, owner: Alice, paths: ["app/main.py", ".github/"]}
  - {name: card, owner: Bob, paths: ["app/card.py"]}
  - {name: practice, owner: Carol, paths: ["practice/"]}
""")


class FakeAPI:
    def __init__(self, reviews=(), card_head=None, asked=()):
        self.reviews = list(reviews)
        self.card = {"id": 1, "head": card_head} if card_head else None
        self.asked = list(asked)
        self.cards, self.requested, self.statuses = [], [], []

    def list_reviews(self, number):
        return self.reviews

    def requested_logins(self, number):
        return self.asked

    def find_card(self, number):
        return self.card

    def get_diff(self, number):
        return ""

    def upsert_card(self, number, head_sha, markdown, existing=None):
        self.cards.append(markdown)

    def request_reviewers(self, number, owners):
        self.requested.append(list(owners))
        return []

    def set_status(self, sha, state, description):
        self.statuses.append((sha, state, description))


def pr(author="Alice", body="Because the API changed.", changed_files=1):
    return {"number": 1, "title": "t", "body": body, "author": author, "head_sha": HEAD,
            "base_ref": "main", "base_sha": "c" * 40, "changed_files": changed_files}


def review(login, state, sha=HEAD):
    return {"user": {"login": login}, "state": state, "commit_id": sha}


# --- modules ------------------------------------------------------------------
def test_repository_module_map_parses():
    path = Path(__file__).resolve().parents[1] / ".changesignal" / "modules.yml"
    modules = load_modules(path)
    assert modules and all({"name", "owner", "paths"} <= m.keys() for m in modules)


def test_author_own_module_is_not_affected():
    assert find_affected(["app/main.py"], MODULES, "alice") == []


def test_other_module_is_affected_with_owner():
    assert find_affected(["app/card.py", "README.md"], MODULES, "Alice") == [
        {"module": "card", "owner": "Bob", "kind": "owned_path", "files": ["app/card.py"]}]


@pytest.mark.parametrize("text", [
    "",                                              # empty file
    "module:\n  - {name: a, owner: b, paths: [x]}",   # typo in the key
    "modules: []",                                   # no modules
    "modules:\n  - {name: a, paths: [x]}",            # no owner
    "modules:\n  - {name: a, owner: b, paths: []}",   # no paths
    "modules: [unclosed",                            # not valid YAML
])
def test_broken_module_map_is_rejected_not_treated_as_no_owners(text):
    with pytest.raises(ModuleMapError):
        parse_modules(text)


def test_module_map_comes_from_base_commit_with_head_fallback_only_if_missing():
    class Files:
        def __init__(self, by_ref):
            self.by_ref, self.asked = by_ref, []

        def get_file(self, path, ref):
            self.asked.append(ref)
            return self.by_ref.get(ref)

    good = "modules:\n  - {name: a, owner: b, paths: [x]}"
    api = Files({"c" * 40: good, HEAD: "modules: []"})
    assert load_modules_for(api, pr())[0]["owner"] == "b" and api.asked == ["c" * 40]
    api = Files({HEAD: good})
    assert load_modules_for(api, pr())[0]["owner"] == "b"
    with pytest.raises(ModuleMapError):
        load_modules_for(Files({}), pr())


def test_folder_prefix_matches():
    assert [a["owner"] for a in find_affected(["practice/score.py"], MODULES, "Bob")] == ["Carol"]


# --- reviews ------------------------------------------------------------------
def test_approval_on_old_commit_does_not_count():
    assert approved_owners([review("bob", "APPROVED", sha=OLD)], HEAD) == set()


def test_latest_decisive_review_wins():
    reviews = [review("a", "APPROVED"), review("a", "COMMENTED"),
               review("b", "APPROVED"), review("b", "CHANGES_REQUESTED"), review("c", "DISMISSED")]
    assert approved_owners(reviews, HEAD) == {"a"}


# --- reconcile ----------------------------------------------------------------
def test_new_pr_posts_card_requests_owner_and_sets_pending():
    api = FakeAPI()
    assert reconcile(api, pr(), ["app/card.py"], "pull_request", MODULES)["state"] == "pending"
    assert api.requested == [["Bob"]]
    assert "@Bob" in api.cards[0]
    assert api.statuses[-1][1] == "pending"


def test_approval_turns_green_without_touching_a_current_card():
    api = FakeAPI([review("bob", "APPROVED")], card_head=HEAD)  # case-insensitive login
    assert reconcile(api, pr(), ["app/card.py"], "pull_request_review", MODULES)["state"] == "success"
    assert api.cards == [] and api.requested == []


def test_review_run_redoes_stale_card_and_requests():
    # The review run replaced a queued push run, so the card still describes an old commit.
    api = FakeAPI(card_head=OLD)
    reconcile(api, pr(), ["app/card.py"], "pull_request_review", MODULES)
    assert len(api.cards) == 1 and api.requested == [["Bob"]]


def test_editing_pr_text_refreshes_card_but_does_not_re_request():
    api = FakeAPI([review("bob", "CHANGES_REQUESTED")], card_head=HEAD)
    reconcile(api, pr(), ["app/card.py"], "pull_request", MODULES)
    assert len(api.cards) == 1 and api.requested == []


def test_owner_already_asked_is_not_asked_again():
    api = FakeAPI(asked=["bob"])
    reconcile(api, pr(), ["app/card.py"], "pull_request", MODULES)
    assert api.requested == []


def test_failed_request_is_retried_even_if_card_is_current():
    api = FakeAPI(card_head=HEAD)  # card done, but Bob was never successfully asked
    reconcile(api, pr(), ["app/card.py"], "pull_request_review", MODULES)
    assert api.requested == [["Bob"]]


def test_head_that_keeps_moving_ends_pending_not_green():
    class Moving(FakeAPI):
        n = 0

        def get_pr(self, number):
            Moving.n += 1
            return dict(pr(), head_sha=f"{Moving.n:040d}")

        def list_pr_changes(self, number):
            return ["app/card.py"], {}

    api = Moving()
    assert run(api, 1, "pull_request")["state"] == "pending"
    assert api.statuses[-1][1] == "pending"


def test_invalid_base_map_sets_failure():
    class BadMap(FakeAPI):
        def get_pr(self, number):
            return pr()

        def list_pr_changes(self, number):
            return ["app/card.py"], {}

        def get_file(self, path, ref):
            return "module: oops"

    api = BadMap()
    with pytest.raises(ModuleMapError):
        run(api, 1, "pull_request")
    assert api.statuses[-1][1] == "failure"


def test_no_affected_owner_is_success():
    assert reconcile(FakeAPI(), pr(), ["README.md"], "pull_request", MODULES)["state"] == "success"


def test_too_many_files_fails_closed():
    api = FakeAPI()
    assert reconcile(api, pr(changed_files=3001), ["app/card.py"], "pull_request", MODULES)["state"] == "failure"


def test_missing_reason_is_flagged_in_card():
    api = FakeAPI()
    reconcile(api, pr(body=""), ["app/card.py"], "pull_request", MODULES)
    assert "No reason given" in api.cards[0]


# --- GitHub adapter -------------------------------------------------------------
def test_rename_reports_old_and_new_path():
    api = GitHubAPI("o/r", "t")
    api._get_all = lambda path: [{"filename": "misc/card.py", "previous_filename": "app/card.py"}]
    assert find_affected(api.list_pr_files(1), MODULES, "Alice")[0]["owner"] == "Bob"


class _Resp:
    def __init__(self, status):
        self.status_code, self.text = status, ""


def test_one_bad_reviewer_does_not_block_the_others():
    api = GitHubAPI("o/r", "t")
    calls = []

    def post(url, json):
        calls.append(json["reviewers"])
        return _Resp(422 if "ghost" in json["reviewers"] else 201)

    api.session.post = post
    assert api.request_reviewers(1, ["Bob", "ghost"]) == ["ghost"]
    assert ["Bob"] in calls
