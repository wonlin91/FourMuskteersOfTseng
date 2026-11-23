"""Walking-skeleton tests: the whole flow with a fake GitHub API.  Run: python -m pytest"""
from changesignal.main import approved_owners, reconcile
from changesignal.modules import find_affected, load_modules

MODULES = load_modules(".changesignal/modules.yml")


class FakeAPI:
    def __init__(self, reviews=()):
        self.reviews = list(reviews)
        self.comments, self.requested, self.statuses = [], [], []

    def list_reviews(self, number):
        return self.reviews

    def upsert_comment(self, number, markdown):
        self.comments.append(markdown)

    def request_reviewers(self, number, owners):
        self.requested.append(list(owners))

    def set_status(self, sha, state, description):
        self.statuses.append((sha, state, description))


def pr(author="LiLOUIS0803", body="Because the API changed."):
    return {"number": 1, "title": "t", "body": body, "author": author, "head_sha": "abc", "diff": ""}


def review(login, state, sha="abc"):
    return {"user": {"login": login}, "state": state, "commit_id": sha}


def test_author_own_module_is_not_affected():
    assert find_affected(["changesignal/main.py"], MODULES, "LiLOUIS0803") == []


def test_other_module_is_affected_with_owner():
    affected = find_affected(["changesignal/card.py", "README.md"], MODULES, "LiLOUIS0803")
    assert affected == [{"module": "card", "owner": "yixiang0706",
                         "kind": "owned_path", "files": ["changesignal/card.py"]}]


def test_folder_prefix_matches():
    affected = find_affected(["practice/score.py"], MODULES, "wonlin91")
    assert [a["owner"] for a in affected] == ["FatFang"]


def test_pr_event_posts_card_requests_owner_and_sets_pending():
    api = FakeAPI()
    result = reconcile(api, pr(), ["changesignal/card.py"], "pull_request")
    assert result["state"] == "pending"
    assert api.requested == [["yixiang0706"]]
    assert "@yixiang0706" in api.comments[0]
    assert api.statuses[-1][1] == "pending"


def test_approval_on_head_turns_status_green_without_new_card():
    api = FakeAPI([review("YiXiang0706", "APPROVED")])  # case-insensitive
    result = reconcile(api, pr(), ["changesignal/card.py"], "pull_request_review")
    assert result["state"] == "success"
    assert api.comments == [] and api.requested == []


def test_approval_on_old_commit_does_not_count():
    assert approved_owners([review("yixiang0706", "APPROVED", sha="old")], "abc") == set()


def test_latest_decisive_review_wins():
    reviews = [review("a", "APPROVED"), review("a", "COMMENTED"), review("b", "APPROVED"),
               review("b", "CHANGES_REQUESTED")]
    assert approved_owners(reviews, "abc") == {"a"}


def test_no_affected_owner_is_success():
    api = FakeAPI()
    assert reconcile(api, pr(), ["README.md"], "pull_request")["state"] == "success"


def test_missing_reason_is_flagged_in_card():
    api = FakeAPI()
    reconcile(api, pr(body=""), ["changesignal/card.py"], "pull_request")
    assert "No reason given" in api.comments[0]
