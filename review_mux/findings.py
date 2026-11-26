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
    sources_bots: list[str] = field(default_factory=list)  # every bot that found it


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


def merge(findings: list[Finding]) -> list[Finding]:
    """Collapse findings from different bots that point at the same code into
    one, keeping every bot and link. One bot's separate comments stay separate
    findings, however close. The first finding's text stands for the group."""
    groups: list[Finding] = []
    for f in findings:
        for g in groups:
            if f.bot not in g.sources_bots and overlaps(g, f):
                if f.bot not in g.sources_bots:
                    g.sources_bots.append(f.bot)
                g.sources.extend(f.sources)
                if f.start_line is not None and g.start_line is not None:
                    g.start_line = min(g.start_line, f.start_line)
                    g.end_line = max(g.end_line or g.start_line, f.end_line or f.start_line)
                break
        else:
            groups.append(Finding(bot=f.bot, path=f.path, start_line=f.start_line,
                                  end_line=f.end_line, body=f.body, side=f.side,
                                  commit=f.commit, severity=f.severity,
                                  sources=list(f.sources), sources_bots=[f.bot]))
    return groups


def headline(body: str) -> str:
    """The first line that says something: not a badge or a label row like
    CodeRabbit's "Major · Functional Correctness · Quick win"."""
    import re
    text = re.sub(r"<!--.*?-->", "", body or "", flags=re.S)
    for line in text.splitlines():
        line = re.sub(r"<[^>]+>", "", line).replace("**", "").strip(" #>*-`")
        if len(line.split()) >= 3 and " · " not in line and not line.startswith("```"):
            return line
    return ""
