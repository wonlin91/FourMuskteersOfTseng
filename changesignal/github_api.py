"""Thin GitHub REST adapter (requests).  Owner: LiLOUIS0803 (pipeline).

Only this file talks to GitHub; everything else works on plain Python data.
"""
import os

import requests

API = "https://api.github.com"
MARKER = "<!-- changesignal -->"
STATUS_CONTEXT = "changesignal/owner-ack"
# Comments posted with GITHUB_TOKEN are authored by this bot. Override when testing with a personal token.
BOT_LOGIN = os.environ.get("CHANGESIGNAL_BOT_LOGIN", "github-actions[bot]")


class GitHubError(RuntimeError):
    pass


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
        }

    def get_diff(self, number):
        resp = self.session.get(self._url(f"/pulls/{number}"),
                                headers={"Accept": "application/vnd.github.diff"})
        if resp.status_code >= 400:  # e.g. diff too large; the card can live without it
            print(f"::warning::Could not fetch diff ({resp.status_code}); continuing without it.")
            return ""
        return resp.text

    def list_pr_files(self, number):
        return [f["filename"] for f in self._get_all(f"/pulls/{number}/files")]

    def list_reviews(self, number):
        return self._get_all(f"/pulls/{number}/reviews")

    # --- writes --------------------------------------------------------------
    def upsert_comment(self, pr_number, markdown):
        """Edit our existing card comment if there is one, otherwise create it."""
        body = f"{MARKER}\n{markdown}"
        for c in self._get_all(f"/issues/{pr_number}/comments"):
            if MARKER in (c.get("body") or "") and c["user"]["login"] == BOT_LOGIN:
                self._check(self.session.patch(self._url(f"/issues/comments/{c['id']}"), json={"body": body}))
                return
        self._check(self.session.post(self._url(f"/issues/{pr_number}/comments"), json={"body": body}))

    def request_reviewers(self, pr_number, owners):
        """Ask owners to review. A 422 (author, or not a collaborator) is reported, not fatal."""
        if not owners:
            return True
        resp = self.session.post(self._url(f"/pulls/{pr_number}/requested_reviewers"),
                                 json={"reviewers": list(owners)})
        if resp.status_code == 422:
            print(f"::warning::Could not request reviewers {owners}: {resp.text[:300]} "
                  "-- check that every owner in .changesignal/modules.yml is a collaborator.")
            return False
        self._check(resp)
        return True

    def set_status(self, sha, state, description):
        run_url = None
        if os.environ.get("GITHUB_RUN_ID"):
            run_url = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
                       f"{self.repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}")
        payload = {"state": state, "context": STATUS_CONTEXT, "description": description[:140]}
        if run_url:
            payload["target_url"] = run_url
        self._check(self.session.post(self._url(f"/statuses/{sha}"), json=payload))
