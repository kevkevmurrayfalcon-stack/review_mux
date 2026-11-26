"""Fetch every review bot's inline comments on a PR as Findings."""
from __future__ import annotations

import json
import subprocess
import sys

import yaml

from review_mux.findings import Finding, from_review_comment


def load_providers(path: str = "providers.yml") -> dict[str, dict]:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def bot_by_login(providers: dict[str, dict]) -> dict[str, str]:
    """Map a GitHub login like 'devloai[bot]' to our provider name."""
    return {p["login"]: name for name, p in providers.items()}


def fetch_review_comments(repo: str, pr: int) -> list[dict]:
    out = subprocess.run(
        ["gh", "api", "--paginate", f"repos/{repo}/pulls/{pr}/comments"],
        check=True, capture_output=True, text=True,
    ).stdout
    # --paginate concatenates one JSON array per page.
    comments: list[dict] = []
    for page in out.replace("][", "]\n[").splitlines():
        if page.strip():
            comments.extend(json.loads(page))
    return comments


def collect(comments: list[dict], logins: dict[str, str]) -> list[Finding]:
    """Keep top-level comments from known bots; replies are discussion, not findings."""
    return [
        from_review_comment(logins[c["user"]["login"]], c)
        for c in comments
        if c["user"]["login"] in logins and not c.get("in_reply_to_id")
    ]


if __name__ == "__main__":
    repo, pr = sys.argv[1], int(sys.argv[2])
    logins = bot_by_login(load_providers())
    for f in collect(fetch_review_comments(repo, pr), logins):
        print(f"{f.bot:12} {f.path}:{f.start_line}-{f.end_line} {f.body.splitlines()[0][:80]}")
