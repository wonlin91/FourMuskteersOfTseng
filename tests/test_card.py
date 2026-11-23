"""Impact card tests with a fake Claude client (no network, no cost)."""
import json
from types import SimpleNamespace

import anthropic
import httpx2

from changesignal.card import build_card

PR = {"number": 1, "title": "Skip tiny regions", "body": "Tiny crops make scores noisy.",
      "author": "alice", "head_sha": "a" * 40, "diff": "+    if w < 32: continue"}
AFFECTED = [
    {"module": "preprocess", "owner": "bob", "kind": "owned_path", "files": ["pipeline/preprocess.py"]},
    {"module": "scoring", "owner": "bob", "kind": "possible_caller", "symbol": "crop_regions",
     "location": "pipeline/scoring.py:7", "files": ["pipeline/scoring.py"], "snippet": "crops = crop_regions(...)"},
]
DRAFT = {"what_changed": "crop_regions now skips boxes under 32px, so it can return fewer crops.",
         "reason_given": True,
         "impacts": [{"module": "scoring", "risk": "scores no longer line up with boxes",
                      "evidence": "pipeline/scoring.py:7"}],
         "questions_for_owner": ["Does select_best pair scores with boxes by position?"]}


class FakeClient:
    def __init__(self, reply=None, stop_reason="end_turn", error=None):
        self.calls = []
        self._reply, self._stop, self._error = reply, stop_reason, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        text = json.dumps(self._reply) if isinstance(self._reply, dict) else self._reply
        return SimpleNamespace(stop_reason=self._stop, model="claude-opus-5-5",
                               content=[SimpleNamespace(type="text", text=text)])


def test_ai_draft_is_shown_and_labelled():
    client = FakeClient(DRAFT)
    md = build_card(PR, AFFECTED, client)["markdown"]
    assert "skips boxes under 32px" in md
    assert "scores no longer line up" in md
    assert "- [ ] Does select_best" in md
    assert "AI draft" in md and "claude-opus-5-5" in md
    assert "possible caller" in md and "`crop_regions`" in md


def test_request_uses_schema_and_sends_pr_text_as_data():
    client = FakeClient(DRAFT)
    build_card(PR, AFFECTED, client)
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    content = call["messages"][0]["content"]
    assert "<data>" in content and "Tiny crops make scores noisy." in content and "<diff>" in content


def test_ai_saying_no_reason_flags_missing_reason():
    md = build_card(PR, AFFECTED, FakeClient(dict(DRAFT, reason_given=False)))
    assert md["reason_missing"] and "No reason given" in md["markdown"]


def test_api_error_still_posts_rule_based_card():
    err = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com"))
    md = build_card(PR, AFFECTED, FakeClient(error=err))["markdown"]
    assert "AI summary unavailable" in md and "@bob" in md


def test_refusal_or_cutoff_still_posts_card():
    for stop in ("refusal", "max_tokens"):
        md = build_card(PR, AFFECTED, FakeClient(DRAFT, stop_reason=stop))["markdown"]
        assert "AI summary unavailable" in md and "scores no longer" not in md


def test_unreadable_json_still_posts_card():
    md = build_card(PR, AFFECTED, FakeClient("not json"))["markdown"]
    assert "unreadable AI response" in md


def test_no_api_key_skips_ai():
    md = build_card(PR, AFFECTED)["markdown"]  # conftest removes ANTHROPIC_API_KEY
    assert "no API key configured" in md and "@bob" in md


def test_huge_diff_is_cut_and_card_says_so():
    client = FakeClient(DRAFT)
    md = build_card(dict(PR, diff="x" * 200_000), AFFECTED, client)["markdown"]
    assert "first 150,000 characters" in md
    assert len(client.calls[0]["messages"][0]["content"]) < 160_000


def test_chinese_labels(monkeypatch):
    monkeypatch.setenv("CHANGESIGNAL_LANG", "zh-TW")
    client = FakeClient(DRAFT)
    md = build_card(PR, AFFECTED, client)["markdown"]
    assert "影響卡" in md
    assert "Traditional Chinese" in client.calls[0]["messages"][0]["content"]


def test_pipe_in_module_name_does_not_break_table():
    md = build_card(PR, [dict(AFFECTED[0], module="a|b")])["markdown"]
    assert "a\\|b" in md
