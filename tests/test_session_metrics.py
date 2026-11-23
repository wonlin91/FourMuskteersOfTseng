"""Tests for evals/session_metrics.py with stored JSON. No network."""
import csv
import json
from pathlib import Path

import pytest

from evals import session_metrics as sm

FIXTURES = Path(__file__).parent / "fixtures" / "session_metrics"


def load(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def test_full_flow_card_changes_requested_approved_merged():
    r = sm.compute_metrics(load("full_flow"))
    assert r["open_to_card"] == 33  # only the bot comment that starts with the marker counts
    assert r["owners"] == ["bob"]  # carol reviewed but was never asked
    assert r["first_reviews"]["bob"][1] == "COMMENTED"
    assert r["open_to_decision"] == 5 * 60  # first APPROVED / CHANGES_REQUESTED, not COMMENTED
    assert r["open_to_approval"] == 20 * 60
    assert r["owner_ack"] == ["pending", "success"]  # across both commits, other contexts ignored
    assert r["outcome"] == "merged"
    assert r["reviewed_before_merge"] == "yes"


def test_closed_without_review():
    r = sm.compute_metrics(load("closed_without_review"))
    assert r["open_to_card"] == 40
    assert r["owners"] == ["bob"]
    assert r["first_reviews"] == {}
    assert r["decision_at"] is None and r["open_to_decision"] is None
    assert r["owner_ack"] == ["pending"]
    assert r["outcome"] == "closed"
    assert r["reviewed_before_merge"] == "n/a"  # never merged


def test_pr_without_card():
    r = sm.compute_metrics(load("no_card"))
    assert r["card_at"] is None and r["open_to_card"] is None
    assert r["owner_ack"] == []
    assert r["outcome"] == "merged"
    assert r["reviewed_before_merge"] == "no"  # the approval came after the merge


def test_partial_when_one_of_two_owners_reviewed_before_merge():
    raw = load("full_flow")
    raw["timeline"].append({"event": "review_requested", "created_at": "2026-11-23T12:00:34Z",
                            "requested_reviewer": {"login": "dave"}})
    assert sm.compute_metrics(raw)["reviewed_before_merge"] == "partial"


def test_author_and_pending_reviews_are_not_owner_reviews():
    raw = load("closed_without_review")
    raw["timeline"].append({"event": "review_requested", "created_at": "2026-11-23T13:01:00Z",
                            "requested_reviewer": {"login": "alice"}})  # the author
    raw["reviews"].append({"user": {"login": "bob"}, "state": "PENDING", "submitted_at": None})
    r = sm.compute_metrics(raw)
    assert r["owners"] == ["bob"] and r["first_reviews"] == {}


def test_summary_medians_and_ratio():
    rows = [sm.compute_metrics(load(n)) for n in ("full_flow", "closed_without_review", "no_card")]
    s = sm.summarize(rows)
    assert s["median_open_to_card"] == (36.5, 2)  # 33 s and 40 s; the PR without a card is left out
    assert s["median_open_to_decision"] == (3750, 2)  # 5 min and 2 h (approved after the merge)
    assert s["reviewed_before_merge"] == (1, 2)  # only merged PRs with owners count
    assert "1/2 (50%)" in sm.summary_text(s)


def test_summary_with_no_data():
    s = sm.summarize([sm.compute_metrics(load("closed_without_review"))])
    assert "n/a (no merged PR with owners)" in sm.summary_text(s)


@pytest.mark.parametrize("seconds, text", [
    (None, ""), (33, "33s"), (518, "8m 38s"), (3 * 3600 + 120, "3h 2m"), (90000, "1d 1h"), (-5, "-5s")])
def test_fmt_duration(seconds, text):
    assert sm.fmt_duration(seconds) == text


def test_outputs(tmp_path):
    rows = [sm.compute_metrics(load(n)) for n in ("full_flow", "no_card")]
    s = sm.summarize(rows)
    table = sm.markdown_table(rows, s)
    assert table.splitlines()[0].startswith("| pr | author |")
    assert "| #3 | alice |" in table and "no card" in table and "**Summary**" in table
    path = tmp_path / "m.csv"
    sm.write_csv(path, rows, s)
    with open(path, encoding="utf-8-sig") as f:
        got = list(csv.DictReader(f))
    assert got[0]["open_to_card"] == "33" and got[1]["open_to_card"] == ""
    assert got[-1]["pr"] == "summary"


# ---------- pagination (fake session, no network) ----------

class FakeResponse:
    def __init__(self, data, next_url=None, status=200):
        self._data, self.status_code, self.headers = data, status, {}
        self.links = {"next": {"url": next_url}} if next_url else {}

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, pages):
        self.pages, self.calls, self.headers = pages, [], {}

    def get(self, url, params=None):
        self.calls.append((url, params))
        return self.pages[url]


def test_get_all_follows_next_links():
    first = sm.API + "/repos/o/r/pulls/1/reviews"
    session = FakeSession({
        first: FakeResponse([{"id": 1}, {"id": 2}], next_url="https://api.github.com/page2"),
        "https://api.github.com/page2": FakeResponse([{"id": 3}], next_url="https://api.github.com/page3"),
        "https://api.github.com/page3": FakeResponse([{"id": 4}]),
    })
    gh = sm.GitHub(token="t", session=session)
    assert [x["id"] for x in gh.get_all("/repos/o/r/pulls/1/reviews")] == [1, 2, 3, 4]
    assert session.calls[0][1] == {"per_page": 100}
    assert session.calls[1][1] is None  # the next URL already carries the query
    assert session.headers["Authorization"] == "Bearer t"


def test_http_error_names_rate_limit():
    resp = FakeResponse({}, status=403)
    resp.headers["X-RateLimit-Remaining"] = "0"
    gh = sm.GitHub(session=FakeSession({sm.API + "/x": resp}))
    with pytest.raises(sm.GitHubError, match="rate limit"):
        gh.get("/x")


def test_fetch_pr_collects_statuses_for_every_commit():
    base = sm.API + "/repos/o/r"
    pages = {
        f"{base}/pulls/5": FakeResponse({"number": 5, "head": {"sha": "b"}}),
        f"{base}/pulls/5/commits": FakeResponse([{"sha": "a"}, {"sha": "b"}]),
        f"{base}/issues/5/comments": FakeResponse([]),
        f"{base}/issues/5/timeline": FakeResponse([]),
        f"{base}/pulls/5/reviews": FakeResponse([]),
        f"{base}/commits/a/statuses": FakeResponse([{"state": "pending"}]),
        f"{base}/commits/b/statuses": FakeResponse([{"state": "success"}]),
    }
    raw = sm.fetch_pr(sm.GitHub(session=FakeSession(pages)), "o/r", 5)
    assert raw["statuses"] == {"a": [{"state": "pending"}], "b": [{"state": "success"}]}


def test_removed_review_request_is_not_an_owner():
    raw = load("full_flow")
    raw["timeline"] += [
        {"event": "review_requested", "created_at": "2026-11-23T12:00:34Z", "requested_reviewer": {"login": "dave"}},
        {"event": "review_request_removed", "created_at": "2026-11-23T12:06:00Z", "requested_reviewer": {"login": "dave"}},
    ]
    r = sm.compute_metrics(raw)
    assert r["owners"] == ["bob"] and r["owners_removed"] == ["dave"]
    assert r["reviewed_before_merge"] == "yes"
    assert "request removed: dave" in sm.row_cells(r)["owners"]


def test_asked_again_after_removal_is_an_owner():
    raw = load("full_flow")
    raw["timeline"] += [
        {"event": "review_request_removed", "created_at": "2026-11-23T12:01:00Z", "requested_reviewer": {"login": "bob"}},
        {"event": "review_requested", "created_at": "2026-11-23T12:02:00Z", "requested_reviewer": {"login": "bob"}},
    ]
    assert sm.compute_metrics(raw)["owners"] == ["bob"]
