"""Thin GitHub REST adapter (requests).  Owner: LiLOUIS0803 (pipeline).

Only this file talks to GitHub; everything else works on plain Python data.
"""
import os
import re

import requests

API = "https://api.github.com"
STATUS_CONTEXT = "changesignal/owner-ack"
# The card comment starts with this marker; it records which head commit the card describes.
CARD_MARKER_RE = re.compile(r"\A<!-- changesignal head=([0-9a-f]{40}) -->")
# Comments posted with GITHUB_TOKEN are authored by this bot. Override when testing with a personal token.
BOT_LOGIN = os.environ.get("CHANGESIGNAL_BOT_LOGIN", "github-actions[bot]")
MAX_PR_FILES = 3000  # GitHub's "list PR files" endpoint returns at most this many


class GitHubError(RuntimeError):
    pass


def card_marker(head_sha):
    return f"<!-- changesignal head={head_sha} -->"


class GitHubAPI:
    def __init__(self, repo, token):
        self.repo = repo
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    # --- helpers -------------------------------------------------------------
    def _url(self, path):
        return f"{API}/repos/{self.repo}{path}"

    @staticmethod
    def _check(resp):
        if resp.status_code >= 400:
            raise GitHubError(f"{resp.request.method} {resp.url} -> {resp.status_code}: {resp.text[:500]}")
        return resp

    def _get_all(self, path):
        """GET every page of a list endpoint."""
        url, params, items = self._url(path), {"per_page": 100}, []
        while url:
            resp = self._check(self.session.get(url, params=params))
            items.extend(resp.json())
            url, params = resp.links.get("next", {}).get("url"), None
        return items

    # --- reads ---------------------------------------------------------------
    def get_pr(self, number):
        d = self._check(self.session.get(self._url(f"/pulls/{number}"))).json()
        return {
            "number": d["number"],
            "title": d["title"],
            "body": d.get("body") or "",
            "author": d["user"]["login"],
            "head_sha": d["head"]["sha"],
            "base_ref": d["base"]["ref"],
            "base_sha": d["base"]["sha"],
            "changed_files": d.get("changed_files", 0),
        }

    def get_diff(self, number):
        resp = self.session.get(self._url(f"/pulls/{number}"),
                                headers={"Accept": "application/vnd.github.diff"})
        if resp.status_code >= 400:  # e.g. diff too large; the card can live without it
            print(f"::warning::Could not fetch diff ({resp.status_code}); continuing without it.")
            return ""
        return resp.text

    def get_file(self, path, ref):
        """Text of `path` at `ref` (branch or commit SHA), or None if it does not exist there."""
        resp = self.session.get(self._url(f"/contents/{path}"), params={"ref": ref},
                                headers={"Accept": "application/vnd.github.raw+json"})
        if resp.status_code == 404:
            return None
        return self._check(resp).text

    def list_pr_files(self, number):
        """Every path the PR touches. For renames, both the old and the new path."""
        return self.list_pr_changes(number)[0]

    def list_pr_changes(self, number):
        """(paths, patches): paths as in list_pr_files; patches maps each current path to its
        unified-diff patch (None when GitHub omits it, e.g. binary or very large files)."""
        paths, patches = [], {}
        for f in self._get_all(f"/pulls/{number}/files"):
            paths.append(f["filename"])
            if f.get("previous_filename"):
                paths.append(f["previous_filename"])
            if f.get("status") != "removed":
                patches[f["filename"]] = f.get("patch")
        return paths, patches

    def list_reviews(self, number):
        return self._get_all(f"/pulls/{number}/reviews")

    def requested_logins(self, number):
        d = self._check(self.session.get(self._url(f"/pulls/{number}/requested_reviewers"))).json()
        return [u["login"] for u in d.get("users", [])]

    def find_card(self, pr_number):
        """Our card comment as {"id", "head"}, or None."""
        for c in self._get_all(f"/issues/{pr_number}/comments"):
            m = CARD_MARKER_RE.match(c.get("body") or "")
            if m and c["user"]["login"] == BOT_LOGIN:
                return {"id": c["id"], "head": m.group(1)}
        return None

    # --- writes --------------------------------------------------------------
    def upsert_card(self, pr_number, head_sha, markdown, existing=None):
        """Edit our existing card comment if there is one, otherwise create it."""
        body = f"{card_marker(head_sha)}\n{markdown}"
        if existing:
            self._check(self.session.patch(self._url(f"/issues/comments/{existing['id']}"), json={"body": body}))
        else:
            self._check(self.session.post(self._url(f"/issues/{pr_number}/comments"), json={"body": body}))

    def request_reviewers(self, pr_number, owners):
        """Ask owners to review. Returns the owners GitHub refused (e.g. not a collaborator)."""
        if not owners:
            return []
        url = self._url(f"/pulls/{pr_number}/requested_reviewers")
        resp = self.session.post(url, json={"reviewers": list(owners)})
        if resp.status_code != 422:
            self._check(resp)
            return []
        # One bad login makes GitHub reject the whole batch, so retry one by one.
        failed = []
        for owner in owners:
            r = self.session.post(url, json={"reviewers": [owner]})
            if r.status_code == 422:
                print(f"::warning::Could not request @{owner} as reviewer: {r.text[:300]} "
                      "-- check that every owner in .changesignal/modules.yml is a collaborator.")
                failed.append(owner)
            else:
                self._check(r)
        return failed

    def set_status(self, sha, state, description):
        payload = {"state": state, "context": STATUS_CONTEXT, "description": description[:140]}
        if os.environ.get("GITHUB_RUN_ID"):
            payload["target_url"] = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
                                     f"{self.repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}")
        self._check(self.session.post(self._url(f"/statuses/{sha}"), json=payload))
