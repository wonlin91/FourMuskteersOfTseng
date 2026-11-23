"""Evaluation metrics from GitHub records.  Owner: FatFang (practice-and-tests).  Issue #14.

For each pull request: when it opened, when the ChangeSignal card first appeared, which owners
were asked to review, when each owner first reviewed and how, how `changesignal/owner-ack`
changed, how the PR ended, and whether every owner reviewed before the merge.

    python evals/session_metrics.py --repo LiLOUIS0803/changesignal-demo
    python evals/session_metrics.py --repo wonlin91/FourMuskteersOfTseng --pr 8

Token: GH_TOKEN, else `gh auth token`, else no token (public repos only, 60 requests per hour).
Fetching (GitHub) and computing (compute_metrics, summarize) are separate, so the computing
part is tested with stored JSON in tests/fixtures/session_metrics/ and no network.
"""
import argparse
import csv
import os
import shutil
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path

API = "https://api.github.com"
BOT = "github-actions[bot]"
CARD_PREFIX = "<!-- changesignal head="
STATUS_CONTEXT = "changesignal/owner-ack"
DECISIONS = {"APPROVED", "CHANGES_REQUESTED"}
RESULTS_DIR = Path(__file__).resolve().parent / "results"

COLUMNS = [
    "pr", "author", "opened_at", "card_at", "open_to_card", "owners", "first_reviews",
    "decision_at", "open_to_decision", "approved_at", "open_to_approval", "owner_ack", "outcome", "ended_at", "reviewed_before_merge",
]


# ---------- fetching ----------

class GitHubError(RuntimeError):
    pass


def get_token():
    token = (os.environ.get("GH_TOKEN") or "").strip()
    if token or not shutil.which("gh"):
        return token or None
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


class GitHub:
    def __init__(self, token=None, session=None):
        if session is None:
            import requests
            session = requests.Session()
        self.session = session
        self.session.headers.update({"Accept": "application/vnd.github+json",
                                     "X-GitHub-Api-Version": "2022-11-28"})
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _get(self, url, params=None):
        resp = self.session.get(url, params=params)
        if resp.status_code >= 400:
            hint = ""
            if resp.status_code in (403, 429) and resp.headers.get("X-RateLimit-Remaining") == "0":
                hint = " (rate limit reached: set GH_TOKEN)"
            raise GitHubError(f"GET {url} -> {resp.status_code}{hint}")
        return resp

    def get(self, path):
        return self._get(API + path).json()

    def get_all(self, path):
        """GET every page of a list endpoint, following the Link: rel="next" header."""
        url, params, items = API + path, {"per_page": 100}, []
        while url:
            resp = self._get(url, params)
            items.extend(resp.json())
            url, params = resp.links.get("next", {}).get("url"), None
        return items


def fetch_pr(gh, repo, number):
    """All raw records one PR needs, as plain JSON-able data."""
    base = f"/repos/{repo}"
    pr = gh.get(f"{base}/pulls/{number}")
    commits = gh.get_all(f"{base}/pulls/{number}/commits")
    shas = [c["sha"] for c in commits] or [pr["head"]["sha"]]
    return {
        "pr": pr,
        "comments": gh.get_all(f"{base}/issues/{number}/comments"),
        "timeline": gh.get_all(f"{base}/issues/{number}/timeline"),
        "reviews": gh.get_all(f"{base}/pulls/{number}/reviews"),
        "statuses": {sha: gh.get_all(f"{base}/commits/{sha}/statuses") for sha in shas},
    }


def list_pr_numbers(gh, repo):
    return sorted(p["number"] for p in gh.get_all(f"/repos/{repo}/pulls?state=all"))


# ---------- computing ----------

def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def seconds_between(start, end):
    return None if start is None or end is None else (end - start).total_seconds()


def fmt_duration(seconds):
    if seconds is None:
        return ""
    s = int(round(seconds))
    sign, s = ("-", -s) if s < 0 else ("", s)
    d, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m, sec = divmod(rem, 60)
    if d:
        return f"{sign}{d}d {h}h"
    if h:
        return f"{sign}{h}h {m}m"
    if m:
        return f"{sign}{m}m {sec}s"
    return f"{sign}{sec}s"


def _iso(t):
    return t.strftime("%Y-%m-%d %H:%M:%S") if t else ""


def compute_metrics(raw):
    """Turn one PR's raw records into one row of metrics (times as datetime, durations in seconds)."""
    pr = raw["pr"]
    author = pr["user"]["login"]
    opened = parse_time(pr["created_at"])

    cards = [parse_time(c["created_at"]) for c in raw["comments"]
             if c["user"]["login"] == BOT and (c.get("body") or "").startswith(CARD_PREFIX)]
    card_at = min(cards) if cards else None

    # Owners = people asked to review, minus those whose request was later removed (e.g. after
    # the PR's base changed and their module was no longer touched) and not asked again.
    asked, removed = {}, set()  # login -> first time asked
    events = [e for e in raw["timeline"] if e.get("event") in ("review_requested", "review_request_removed")
              and e.get("requested_reviewer") and e["requested_reviewer"]["login"] != author]
    for e in sorted(events, key=lambda e: e["created_at"]):
        login = e["requested_reviewer"]["login"]
        if e["event"] == "review_requested":
            asked.setdefault(login, parse_time(e["created_at"]))
            removed.discard(login)
        else:
            removed.add(login)
    owners = {o: t for o, t in asked.items() if o not in removed}

    first_review = {}  # login -> (time, state), only for owners
    for r in raw["reviews"]:
        login = (r.get("user") or {}).get("login")
        if login not in owners or not r.get("submitted_at") or r.get("state") == "PENDING":
            continue
        t = parse_time(r["submitted_at"])
        if login not in first_review or t < first_review[login][0]:
            first_review[login] = (t, r["state"])

    decisions = [parse_time(r["submitted_at"]) for r in raw["reviews"]
                 if (r.get("user") or {}).get("login") in owners and r.get("state") in DECISIONS
                 and r.get("submitted_at")]
    decision_at = min(decisions) if decisions else None
    approvals = [parse_time(r["submitted_at"]) for r in raw["reviews"]
                 if (r.get("user") or {}).get("login") in owners and r.get("state") == "APPROVED"
                 and r.get("submitted_at")]
    approved_at = min(approvals) if approvals else None

    statuses = sorted((s for lst in raw["statuses"].values() for s in lst
                       if s.get("context") == STATUS_CONTEXT), key=lambda s: s["created_at"])
    ack = []
    for s in statuses:  # collapse repeats: pending, pending, success -> pending > success
        if not ack or ack[-1] != s["state"]:
            ack.append(s["state"])

    merged_at, closed_at = parse_time(pr.get("merged_at")), parse_time(pr.get("closed_at"))
    outcome = "merged" if merged_at else ("closed" if closed_at else "open")

    if outcome != "merged" or not owners:
        before_merge = "n/a"
    else:
        early = [o for o in owners if o in first_review and first_review[o][0] <= merged_at]
        before_merge = "yes" if len(early) == len(owners) else ("partial" if early else "no")

    return {
        "pr": pr["number"],
        "author": author,
        "opened_at": opened,
        "card_at": card_at,
        "open_to_card": seconds_between(opened, card_at),
        "owners": sorted(owners),
        "owners_removed": sorted(removed & set(asked)),
        "first_reviews": {o: first_review[o] for o in sorted(first_review)},
        "decision_at": decision_at,
        "open_to_decision": seconds_between(opened, decision_at),
        "approved_at": approved_at,
        "open_to_approval": seconds_between(opened, approved_at),
        "owner_ack": ack,
        "outcome": outcome,
        "ended_at": merged_at or closed_at,
        "reviewed_before_merge": before_merge,
    }


def summarize(rows):
    def median(key):
        vals = [r[key] for r in rows if r[key] is not None]
        return (statistics.median(vals), len(vals)) if vals else (None, 0)

    judged = [r for r in rows if r["reviewed_before_merge"] in ("yes", "partial", "no")]
    yes = sum(r["reviewed_before_merge"] == "yes" for r in judged)
    return {
        "prs": len(rows),
        "median_open_to_card": median("open_to_card"),
        "median_open_to_decision": median("open_to_decision"),
        "median_open_to_approval": median("open_to_approval"),
        "reviewed_before_merge": (yes, len(judged)),
    }


# ---------- output ----------

def row_cells(r):
    return {
        "pr": f"#{r['pr']}",
        "author": r["author"],
        "opened_at": _iso(r["opened_at"]),
        "card_at": _iso(r["card_at"]) or "no card",
        "open_to_card": fmt_duration(r["open_to_card"]),
        "owners": (", ".join(r["owners"]) or "none")
                  + (f" (request removed: {', '.join(r['owners_removed'])})" if r["owners_removed"] else ""),
        "first_reviews": ", ".join(f"{o}: {st} {_iso(t)}" for o, (t, st) in r["first_reviews"].items()),
        "decision_at": _iso(r["decision_at"]),
        "open_to_decision": fmt_duration(r["open_to_decision"]),
        "approved_at": _iso(r["approved_at"]),
        "open_to_approval": fmt_duration(r["open_to_approval"]),
        "owner_ack": " > ".join(r["owner_ack"]),
        "outcome": r["outcome"],
        "ended_at": _iso(r["ended_at"]),
        "reviewed_before_merge": r["reviewed_before_merge"],
    }


def summary_text(s):
    def med(pair):
        value, n = pair
        return f"{fmt_duration(value)} (n={n})" if n else "n/a (n=0)"
    yes, n = s["reviewed_before_merge"]
    ratio = f"{yes}/{n} ({yes / n:.0%})" if n else "n/a (no merged PR with owners)"
    return (f"{s['prs']} PRs. Median open → card: {med(s['median_open_to_card'])}. "
            f"Median open → owner decision: {med(s['median_open_to_decision'])}. "
            f"Median open → first approval: {med(s['median_open_to_approval'])}. "
            f"All owners reviewed before merge: {ratio}.")


def markdown_table(rows, summary):
    def esc(v):
        return str(v).replace("|", "\\|")
    lines = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for r in rows:
        cells = row_cells(r)
        lines.append("| " + " | ".join(esc(cells[c]) for c in COLUMNS) + " |")
    lines.append(f"| **Summary** | {esc(summary_text(summary))} |" + " |" * (len(COLUMNS) - 2))
    return "\n".join(lines)


def write_csv(path, rows, summary):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel reads UTF-8
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            cells = row_cells(r)
            for key in ("open_to_card", "open_to_decision", "open_to_approval"):  # seconds, for Excel
                cells[key] = "" if r[key] is None else int(r[key])
            w.writerow(cells)
        w.writerow({"pr": "summary", "author": summary_text(summary)})


def main(argv=None):
    ap = argparse.ArgumentParser(description="Card and review timing per PR, from GitHub records.")
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--pr", type=int, nargs="+", help="only these PR numbers")
    ap.add_argument("--out", default=str(RESULTS_DIR), help="folder for the .md and .csv files")
    args = ap.parse_args(argv)

    token = get_token()
    if not token:
        print("No GH_TOKEN (and no `gh auth token`): public repos only, 60 requests per hour.",
              file=sys.stderr)
    gh = GitHub(token)
    try:
        numbers = args.pr or list_pr_numbers(gh, args.repo)
        rows = []
        for n in numbers:
            print(f"fetching #{n} ...", file=sys.stderr, flush=True)
            rows.append(compute_metrics(fetch_pr(gh, args.repo, n)))
    except GitHubError as e:
        sys.exit(str(e))

    summary = summarize(rows)
    table = markdown_table(rows, summary)
    started = datetime.now()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = str(out / f"metrics-{args.repo.replace('/', '-')}-{started:%Y%m%d-%H%M%S}")
    Path(stem + ".md").write_text(
        f"# ChangeSignal metrics for {args.repo}\n\nGenerated {started:%Y-%m-%d %H:%M:%S}. "
        f"Times are UTC. Columns: see evals/README.md.\n\n{table}\n", encoding="utf-8")
    write_csv(stem + ".csv", rows, summary)

    print(table)
    print(f"\nWrote {stem}.md and .csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
