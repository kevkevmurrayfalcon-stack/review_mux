"""The little of GitHub review_mux uses, through the gh CLI, acting as any
account it holds a token for. Tests use a fake with the same methods."""
from __future__ import annotations

import json
import os
import subprocess


class GitHubError(Exception):
    pass


def token_for(account: str) -> str | None:
    """GH_TOKEN_<ACCOUNT> if set, else gh's stored token for that account."""
    env = os.environ.get("GH_TOKEN_" + account.upper().replace("-", "_"))
    if env:
        return env
    r = subprocess.run(["gh", "auth", "token", "--user", account],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


class GitHub:
    def __init__(self, repo: str):
        self.repo = repo

    def _gh(self, *args: str, as_: str | None = None, input: str | None = None) -> str:
        env = dict(os.environ)
        if as_:
            tok = token_for(as_)
            if not tok:
                raise GitHubError(f"no token for {as_}: set GH_TOKEN_{as_.upper().replace('-', '_')}")
            env["GH_TOKEN"] = tok
        r = subprocess.run(["gh", *args], capture_output=True, text=True, input=input, env=env)
        if r.returncode != 0:
            raise GitHubError(f"gh {' '.join(args[:3])}: {r.stderr.strip()[:400]}")
        return r.stdout

    def _get(self, path: str, paginate: bool = False):
        out = self._gh("api", *(["--paginate", "--slurp"] if paginate else []),
                       f"repos/{self.repo}/{path}")
        data = json.loads(out)
        return [x for page in data for x in page] if paginate else data

    # reading
    def pull(self, pr: int) -> dict:
        return self._get(f"pulls/{pr}")

    def open_pulls(self) -> list[dict]:
        return self._get("pulls?state=open&per_page=100", paginate=True)

    def issue_comments(self, pr: int) -> list[dict]:
        return self._get(f"issues/{pr}/comments?per_page=100", paginate=True)

    def review_comments(self, pr: int) -> list[dict]:
        return self._get(f"pulls/{pr}/comments?per_page=100", paginate=True)

    def reviews(self, pr: int) -> list[dict]:
        return self._get(f"pulls/{pr}/reviews?per_page=100", paginate=True)

    def check_runs(self, sha: str) -> list[dict]:
        return self._get(f"commits/{sha}/check-runs?per_page=100")["check_runs"]

    # writing
    def comment(self, pr: int, body: str, as_: str | None = None) -> int:
        out = self._gh("api", f"repos/{self.repo}/issues/{pr}/comments", "-X", "POST",
                       "-F", "body=@-", as_=as_, input=body)
        return json.loads(out)["id"]

    def edit_comment(self, comment_id: int, body: str, as_: str | None = None) -> None:
        self._gh("api", f"repos/{self.repo}/issues/comments/{comment_id}", "-X", "PATCH",
                 "-F", "body=@-", as_=as_, input=body)

    def set_body(self, pr: int, body: str, as_: str | None = None) -> None:
        self._gh("api", f"repos/{self.repo}/pulls/{pr}", "-X", "PATCH",
                 "-F", "body=@-", as_=as_, input=body)

    def status(self, sha: str, state: str, description: str, context: str,
               url: str | None = None, as_: str | None = None) -> None:
        args = ["api", f"repos/{self.repo}/statuses/{sha}", "-X", "POST",
                "-f", f"state={state}", "-f", f"context={context}",
                "-f", f"description={description[:140]}"]
        if url:
            args += ["-f", f"target_url={url}"]
        self._gh(*args, as_=as_)
