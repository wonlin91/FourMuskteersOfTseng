"""Tests for the prompt test runner (evals/run_prompt_tests.py). No real API calls."""
import json

import pytest

from evals import run_prompt_tests as runner

AFFECTED = [
    {"module": "preprocess", "owner": "bob", "kind": "owned_path", "files": ["pipeline/preprocess.py"]},
    {"module": "scoring", "owner": "bob", "kind": "possible_caller", "symbol": "crop_regions",
     "location": "pipeline/scoring.py:18"},
]


def make_case(expect, affected=AFFECTED, language="en"):
    return {"id": "t", "category": "edge", "description": "", "language": language,
            "pr": {"title": "", "body": "", "author": "a", "diff": ""},
            "affected": affected, "expect": expect}


def make_draft(impacts=("scoring",), reason_given=False, what="Changes crop_regions.", questions=()):
    return {"what_changed": what, "reason_given": reason_given,
            "impacts": [{"module": m, "risk": "r", "evidence": "e"} for m in impacts],
            "questions_for_owner": list(questions)}


def test_passing_draft_has_no_failures():
    case = make_case({"reason_given": False, "impacts_include": ["scoring"],
                      "must_not_contain": ["approved"]})
    assert runner.check_case(case, make_draft()) == []


def test_missing_included_module_fails():
    failures = runner.check_case(make_case({"impacts_include": ["scoring"]}), make_draft(impacts=["preprocess"]))
    assert failures == ["impacts miss module 'scoring'"]


def test_included_module_matches_case_insensitive_and_partial():
    case = make_case({"impacts_include": ["scoring"]})
    assert runner.check_case(case, make_draft(impacts=["Scoring (bob)"])) == []


def test_excluded_module_fails():
    failures = runner.check_case(make_case({"impacts_exclude": ["preprocess"]}), make_draft(impacts=["preprocess"]))
    assert failures == ["impacts include excluded module 'preprocess'"]


def test_wrong_reason_given_fails():
    failures = runner.check_case(make_case({"reason_given": False}), make_draft(reason_given=True))
    assert failures == ["reason_given is True, expected False"]


def test_invented_module_fails_subset_check():
    case = make_case({"impacts_subset_of_affected": True})
    assert runner.check_case(case, make_draft(impacts=["scoring"])) == []
    assert runner.check_case(case, make_draft(impacts=["billing"])) == [
        "impacts name module(s) not in affected: ['billing']"]


def test_subset_check_with_no_affected_means_no_impacts():
    case = make_case({"impacts_subset_of_affected": True}, affected=[])
    assert runner.check_case(case, make_draft(impacts=[])) == []
    assert len(runner.check_case(case, make_draft(impacts=["scoring"]))) == 1


@pytest.mark.parametrize("where", ["what", "questions", "risk"])
def test_forbidden_phrase_found_anywhere_in_output(where):
    draft = make_draft()
    if where == "what":
        draft["what_changed"] = "This change is Approved."
    elif where == "questions":
        draft["questions_for_owner"] = ["It was approved already?"]
    else:
        draft["impacts"][0]["risk"] = "approved by owner"
    assert runner.check_case(make_case({"must_not_contain": ["approved"]}), draft) == [
        "output contains forbidden phrase 'approved'"]


def test_forbidden_phrase_matches_whole_words_only():
    case = make_case({"must_not_contain": ["safe"]})
    assert runner.check_case(case, make_draft(what="This may be unsafe for scoring.")) == []
    assert len(runner.check_case(case, make_draft(what="This is safe."))) == 1


def test_zh_tw_needs_chinese_text():
    case = make_case({}, language="zh-TW")
    assert runner.check_case(case, make_draft(what="修改了 crop_regions")) == []
    assert runner.check_case(case, make_draft(what="Changes crop_regions")) == [
        "what_changed has no Chinese characters (language zh-TW)"]


def test_no_draft_is_a_failure_with_reason():
    assert runner.check_case(make_case({}), None, "API error: RateLimitError") == [
        "no draft (API error: RateLimitError)"]


def test_crash_in_drafter_is_a_failed_case_not_a_crash():
    def boom(pr, affected):
        raise RuntimeError("bad")
    result = runner.run_case(make_case({}), boom)
    assert result["failures"] == ["crashed: RuntimeError: bad"]


def test_run_case_sets_and_restores_language(monkeypatch):
    monkeypatch.setenv("CHANGESIGNAL_LANG", "en")
    seen = []

    def drafter(pr, affected):
        seen.append(runner.os.environ["CHANGESIGNAL_LANG"])
        return make_draft(what="中文"), None
    runner.run_case(make_case({}, language="zh-TW"), drafter)
    assert seen == ["zh-TW"]
    assert runner.os.environ["CHANGESIGNAL_LANG"] == "en"


def test_load_case_rejects_unknown_expect_key(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps(make_case({"impact_include": ["scoring"]})), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown expect key"):
        runner.load_case(p)


def test_load_case_expands_diff_repeat(tmp_path):
    case = make_case({})
    case["pr"].update(diff="ab", diff_repeat=3)
    p = tmp_path / "x.json"
    p.write_text(json.dumps(case), encoding="utf-8")
    assert runner.load_case(p)["pr"]["diff"] == "ababab"


def test_repo_cases_are_valid_and_cover_both_categories():
    cases = runner.load_cases()
    assert len(cases) >= 10
    assert {c["category"] for c in cases} == {"typical", "edge"}
    assert len(max(cases, key=lambda c: len(c["pr"]["diff"]))["pr"]["diff"]) >= 200_000


def test_fake_run_writes_report(tmp_path, capsys):
    assert runner.main(["--fake", "--out", str(tmp_path)]) == 0
    reports = list(tmp_path.glob("*-fake.md"))
    assert len(reports) == 1
    text = reports[0].read_text(encoding="utf-8")
    assert "Model: `fake`" in text and "sha256" in text
    assert "01-demo-silent-break" in text
