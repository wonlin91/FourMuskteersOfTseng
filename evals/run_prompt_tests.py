"""Prompt test suite for the AI impact card.  Owner: FatFang (practice-and-tests).

Runs every case in evals/prompt_cases/*.json through changesignal.card.ai_draft and checks
the draft against the case's "expect" block. Prints a pass/fail table and writes a report to
evals/results/<date-time>.md (model, prompt version, every AI output), so results from before
and after a prompt change can be compared.

    python evals/run_prompt_tests.py           # real API: needs ANTHROPIC_API_KEY, ~12 calls
    python evals/run_prompt_tests.py --fake    # canned replies, no API key, no cost
    python evals/run_prompt_tests.py --only demo-silent-break

Not run in CI: CI has no API key and every run costs money.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `import changesignal` works when run as a script

CASES_DIR = ROOT / "evals" / "prompt_cases"
RESULTS_DIR = ROOT / "evals" / "results"
PROMPT_FILE = ROOT / "changesignal" / "prompts" / "impact_card.md"
CATEGORIES = {"typical", "edge"}
EXPECT_KEYS = {"reason_given", "impacts_include", "impacts_exclude",
               "impacts_subset_of_affected", "must_not_contain"}
CJK = re.compile(r"[一-鿿]")


# ---------- loading ----------

def load_case(path):
    """Read one case file and fill in defaults. Raises ValueError on a malformed case."""
    case = json.loads(Path(path).read_text(encoding="utf-8"))
    name = Path(path).name
    for key in ("id", "category", "description", "pr", "expect"):
        if key not in case:
            raise ValueError(f"{name}: missing '{key}'")
    if case["category"] not in CATEGORIES:
        raise ValueError(f"{name}: category must be one of {sorted(CATEGORIES)}")
    unknown = set(case["expect"]) - EXPECT_KEYS
    if unknown:
        raise ValueError(f"{name}: unknown expect key(s) {sorted(unknown)}")
    case.setdefault("affected", [])
    case.setdefault("language", "en")
    pr = case["pr"]
    pr.setdefault("title", "")
    pr.setdefault("body", "")
    pr.setdefault("author", "")
    pr.setdefault("diff", "")
    # Huge diffs are generated instead of stored: "diff_repeat": n repeats "diff" n times.
    repeat = pr.pop("diff_repeat", 1)
    pr["diff"] = pr["diff"] * int(repeat)
    return case


def load_cases(directory=CASES_DIR, only=None):
    cases = [load_case(p) for p in sorted(Path(directory).glob("*.json"))]
    ids = [c["id"] for c in cases]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate case id(s): {sorted(dupes)}")
    if only:
        cases = [c for c in cases if c["id"] in only]
    return cases


# ---------- checking ----------

def draft_text(draft):
    """All text the card would show from the draft, for must_not_contain."""
    parts = [draft.get("what_changed", "")]
    for i in draft.get("impacts", []):
        parts += [i.get("module", ""), i.get("risk", ""), i.get("evidence", "")]
    parts += draft.get("questions_for_owner", [])
    return "\n".join(str(p) for p in parts)


def _impact_modules(draft):
    return [str(i.get("module", "")).lower() for i in draft.get("impacts", [])]


def check_case(case, draft, why_not=None):
    """Return a list of failure messages; an empty list means the case passed."""
    if draft is None:
        return [f"no draft ({why_not or 'unknown reason'})"]
    expect = case["expect"]
    failures = []

    if "reason_given" in expect and draft.get("reason_given") != expect["reason_given"]:
        failures.append(f"reason_given is {draft.get('reason_given')}, expected {expect['reason_given']}")

    modules = _impact_modules(draft)
    for want in expect.get("impacts_include", []):
        if not any(want.lower() in m for m in modules):
            failures.append(f"impacts miss module '{want}'")
    for unwanted in expect.get("impacts_exclude", []):
        if any(unwanted.lower() in m for m in modules):
            failures.append(f"impacts include excluded module '{unwanted}'")

    if expect.get("impacts_subset_of_affected"):
        known = {a["module"].lower() for a in case["affected"]}
        invented = [m for m in modules if not any(k in m for k in known)]
        if invented:
            failures.append(f"impacts name module(s) not in affected: {invented}")

    text = draft_text(draft)
    for phrase in expect.get("must_not_contain", []):
        # Whole words, any case: "safe" fails on "Safe" but not on "unsafe".
        if re.search(rf"\b{re.escape(phrase)}\b", text, re.IGNORECASE):
            failures.append(f"output contains forbidden phrase '{phrase}'")

    if case.get("language") == "zh-TW" and not CJK.search(draft.get("what_changed", "")):
        failures.append("what_changed has no Chinese characters (language zh-TW)")

    return failures


# ---------- drafting ----------

def fake_ai_draft(pr, affected, language="en"):
    """A canned reply built from the inputs, for testing the runner without an API key.

    It is deliberately naive (any non-template description counts as a reason), so some
    cases fail in --fake mode. That shows the checks work; it says nothing about the prompt.
    """
    body = (pr.get("body") or "").strip()
    seen, impacts = set(), []
    for a in affected:
        if a["module"] in seen:
            continue
        seen.add(a["module"])
        where = a.get("location") or ", ".join(a.get("files", []))
        impacts.append({"module": a["module"], "risk": "fake risk", "evidence": where})
    what = "（假回覆）此 PR 修改了程式碼。" if language == "zh-TW" else "(fake) This PR changes code."
    return {
        "what_changed": what,
        "reason_given": bool(body) and "<!--" not in body,
        "impacts": impacts,
        "questions_for_owner": [],
        "_model": "fake",
    }, None


def run_case(case, draft_fn):
    """Call draft_fn for one case with CHANGESIGNAL_LANG set. Never raises."""
    old = os.environ.get("CHANGESIGNAL_LANG")
    os.environ["CHANGESIGNAL_LANG"] = case["language"]
    start = time.monotonic()
    try:
        draft, why_not = draft_fn(case["pr"], case["affected"])
        failures = check_case(case, draft, why_not)
    except Exception as e:  # a crash is a failed case, not a crashed run
        draft, why_not = None, None
        failures = [f"crashed: {type(e).__name__}: {e}"]
    finally:
        if old is None:
            os.environ.pop("CHANGESIGNAL_LANG", None)
        else:
            os.environ["CHANGESIGNAL_LANG"] = old
    return {"case": case, "draft": draft, "why_not": why_not, "failures": failures,
            "seconds": round(time.monotonic() - start, 1)}


# ---------- reporting ----------

def prompt_version():
    """Last commit that touched the prompt file, its sha256, and whether it has local edits."""
    data = PROMPT_FILE.read_bytes() if PROMPT_FILE.exists() else b""
    info = {"sha256": hashlib.sha256(data).hexdigest()[:12], "commit": "unknown", "dirty": False}
    try:
        rel = PROMPT_FILE.relative_to(ROOT).as_posix()
        info["commit"] = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--", rel], cwd=ROOT,
            capture_output=True, text=True, check=True).stdout.strip() or "uncommitted"
        info["dirty"] = bool(subprocess.run(
            ["git", "status", "--porcelain", "--", rel], cwd=ROOT,
            capture_output=True, text=True, check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        pass
    return info


def summary_table(results):
    rows = ["| # | Case | Category | Result | Why |", "|---|---|---|---|---|"]
    for n, r in enumerate(results, 1):
        c = r["case"]
        status = "PASS" if not r["failures"] else "FAIL"
        why = "; ".join(r["failures"]).replace("|", "\\|")
        rows.append(f"| {n} | {c['id']} | {c['category']} | {status} | {why} |")
    return "\n".join(rows)


def build_report(results, model, prompt, started):
    passed = sum(not r["failures"] for r in results)
    dirty = " (with uncommitted edits)" if prompt["dirty"] else ""
    lines = [
        f"# Prompt test run {started:%Y-%m-%d %H:%M:%S}",
        "",
        f"- Model: `{model}`",
        f"- Prompt: `changesignal/prompts/impact_card.md` at commit `{prompt['commit']}`{dirty}, "
        f"sha256 `{prompt['sha256']}`",
        f"- Result: **{passed}/{len(results)} passed**",
        "",
        summary_table(results),
        "",
        "## Outputs",
    ]
    for r in results:
        c = r["case"]
        lines += ["", f"### {c['id']} ({'PASS' if not r['failures'] else 'FAIL'})", "",
                  f"{c['description']}", "",
                  f"Expected: `{json.dumps(c['expect'], ensure_ascii=False)}`  ",
                  f"Time: {r['seconds']} s"]
        if r["failures"]:
            lines += [""] + [f"- {f}" for f in r["failures"]]
        out = r["draft"] if r["draft"] is not None else {"why_not": r["why_not"]}
        lines += ["", "```json", json.dumps(out, ensure_ascii=False, indent=2), "```"]
    return "\n".join(lines) + "\n"


def real_drafter():
    """Return (draft_fn, model name) for the real API, or exit with a clear message."""
    try:
        from changesignal.card import MODEL, ai_draft
    except ImportError:
        sys.exit("changesignal.card.ai_draft is not available yet (it arrives with the AI card PR). "
                 "Use --fake until then.")
    if not (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        sys.exit("ANTHROPIC_API_KEY is not set. Set it in your shell (never commit it), or use --fake.")
    return ai_draft, MODEL


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--fake", action="store_true", help="use canned replies instead of the API")
    ap.add_argument("--only", nargs="+", metavar="ID", help="run only these case ids")
    ap.add_argument("--cases", default=str(CASES_DIR), help="folder with case JSON files")
    ap.add_argument("--out", default=str(RESULTS_DIR), help="folder for the markdown report")
    args = ap.parse_args(argv)

    cases = load_cases(args.cases, args.only)
    if not cases:
        sys.exit("no cases found")
    if args.fake:
        model = "fake"
        draft_fn = lambda pr, affected: fake_ai_draft(pr, affected, os.environ.get("CHANGESIGNAL_LANG", "en"))
    else:
        draft_fn, model = real_drafter()

    started = datetime.now()
    results = []
    for c in cases:
        print(f"running {c['id']} ...", flush=True)
        results.append(run_case(c, draft_fn))
    # The model that actually answered (it can differ if the API used a fallback model).
    answered = {r["draft"].get("_model") for r in results if r["draft"]} - {None}
    if answered and answered != {model}:
        model = f"{model} (answered by: {', '.join(sorted(answered))})"

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "-fake" if args.fake else ""
    report = out_dir / f"{started:%Y%m%d-%H%M%S}{suffix}.md"
    report.write_text(build_report(results, model, prompt_version(), started), encoding="utf-8")

    print()
    print(summary_table(results))
    passed = sum(not r["failures"] for r in results)
    print(f"\n{passed}/{len(results)} passed. Report: {report}")
    if args.fake:
        print("(--fake: replies are canned, so failures here only show that the checks work.)")
        return 0
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
