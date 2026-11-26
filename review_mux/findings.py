"""One finding format for every review bot."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Finding:
    bot: str
    path: str
    start_line: int | None  # None for file-level or outdated comments
    end_line: int | None
    body: str
    side: str = "RIGHT"  # LEFT = old code, RIGHT = new code
    commit: str = ""
    severity: str = "unknown"
    sources: list[str] = field(default_factory=list)


def from_review_comment(bot: str, c: dict) -> Finding:
    """Build a Finding from a GitHub pull request review comment (REST API shape).

    Uses only `line`, which refers to the PR's current head. A comment with no
    `line` is file-level or outdated (its code changed after the review), so it
    keeps the file but no lines rather than pointing at a stale position.
    """
    end = c.get("line")
    start = c.get("start_line") or end
    return Finding(bot=bot, path=c["path"], start_line=start, end_line=end,
                   body=c["body"], side=c.get("side") or "RIGHT",
                   commit=c.get("commit_id", ""), sources=[c["html_url"]])


def overlaps(a: Finding, b: Finding, slack: int = 3) -> bool:
    """True when two findings point at the same code: same file and diff side,
    and nearby lines. Findings with no lines only match each other."""
    if a.path != b.path or a.side != b.side:
        return False
    if a.start_line is None or b.start_line is None:
        return a.start_line is None and b.start_line is None
    return a.start_line - slack <= b.end_line and b.start_line - slack <= a.end_line
