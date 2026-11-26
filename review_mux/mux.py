"""One review of one pull request head, as a resumable state machine.

    routed -> triggered -> (done | quota | timeout | failed, per bot) -> reported

Each call to `step` reads GitHub afresh, moves as far as it can, records what
it did in the ledger, and returns. Calling it again is always safe: what the
ledger says was done is not done twice. A new push is a new head and a new
review; findings from earlier heads do not count against it.

The answer is one commit status, `review_mux`, on the head:
  success  at least one bot reviewed and none found anything
  failure  a bot left an inline finding, or a finished summary its rules
           count as one (see providers.yml: blocks, clean)
  error    no routed bot gave a review (all out of quota, timed out or failed)
and one PR comment, edited in place, with every finding merged across bots.
Bot approvals are recorded nowhere as approval: they never count.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from review_mux.findings import Finding, from_review_comment, headline, merge
from review_mux.github import GitHubError
from review_mux.ledger import Ledger, iso
from review_mux.providers import Bot
from review_mux.route import Settings, route

CONTEXT = "review_mux"
MARKER = "<!-- review_mux -->"
SETTLED = {"done", "quota", "timeout", "failed"}


@dataclass
class Answer:
    bot: str
    outcome: str  # done | quota
    url: str = ""
    raw: str = ""  # the answer as posted, hidden markers and all

    @property
    def summary(self) -> str:
        return plain(self.raw)


@dataclass
class Head:
    """What the ledger says about one review."""
    routed: list[str] | None = None
    triggered: dict[str, str] = field(default_factory=dict)  # bot -> time
    settled: dict[str, str] = field(default_factory=dict)    # bot -> outcome
    reported: bool = False

    @classmethod
    def fold(cls, recs: list[dict]) -> "Head":
        h = cls()
        for r in recs:
            e = r["event"]
            if e == "routed":
                h.routed = r["bots"]
            elif e == "triggered":
                h.triggered[r["bot"]] = r["t"]
            elif e in SETTLED:
                h.settled[r["bot"]] = e
            elif e == "reported":
                h.reported = True
        return h


def plain(body: str) -> str:
    body = re.sub(r"<!--.*?-->", "", body or "", flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"[ \t]+", " ", body).strip()


class Mux:
    def __init__(self, gh, ledger: Ledger, bots: dict[str, Bot], settings: Settings | None = None,
                 report_as: str | None = None, clock: Callable[[], datetime] | None = None,
                 say: Callable[[str], None] = print):
        self.gh, self.ledger, self.bots = gh, ledger, bots
        self.s = settings or Settings()
        self.report_as = report_as
        self.clock = clock or (lambda: datetime.now().astimezone())
        self.say = say

    def _rec(self, pr: int, sha: str, event: str, **f) -> None:
        self.ledger.append(self.clock(), repo=self.gh.repo, pr=pr, sha=sha, event=event, **f)

    # ------------------------------------------------------------ the step

    def step(self, pr: int) -> str:
        """Advance the review of the PR's current head. Returns its state:
        routed, waiting, success, failure, error, or none (nothing to do)."""
        p = self.gh.pull(pr)
        if p["state"] != "open":
            return "none"
        sha = p["head"]["sha"]
        h = Head.fold(self.ledger.for_head(self.gh.repo, pr, sha))
        if h.reported:
            return self._last_conclusion(pr, sha)
        if h.routed is None:
            lines = int(p.get("additions", 0)) + int(p.get("deletions", 0))
            labels = {l["name"] for l in p.get("labels", [])}
            bots = route(self.bots, self.gh.repo, lines, labels, self.ledger.read(),
                         self.clock(), self.s)
            self._rec(pr, sha, "routed", bots=bots, lines=lines)
            h.routed = bots
            if not bots:
                return self._report(pr, sha, p, h, [])
            self._status(sha, "pending", f"asking {', '.join(bots)}")
        for name in h.routed:
            if name not in h.triggered and name not in h.settled:
                self._trigger(pr, sha, p, self.bots[name], h)
        answers = self._watch(pr, sha, h)
        if all(b in h.settled for b in h.routed):
            return self._report(pr, sha, p, h, answers)
        return "waiting"

    # ------------------------------------------------------------ triggering

    def _trigger(self, pr: int, sha: str, p: dict, b: Bot, h: Head) -> None:
        try:
            if b.trigger_kind == "comment":
                self.gh.comment(pr, b.trigger_text, as_=b.trigger_as)
            else:
                body = p.get("body") or ""
                if b.trigger_text not in body:
                    self.gh.set_body(pr, (body + "\n\n" + b.trigger_text).strip(), as_=b.trigger_as)
        except GitHubError as err:
            self.say(f"{self.gh.repo}#{pr} {b.name}: trigger failed: {err}")
            self._rec(pr, sha, "failed", bot=b.name, why=str(err)[:300])
            h.settled[b.name] = "failed"
            return
        now = self.clock()
        self._rec(pr, sha, "triggered", bot=b.name)
        h.triggered[b.name] = iso(now)

    # ------------------------------------------------------------ watching

    def _watch(self, pr: int, sha: str, h: Head) -> list[Answer]:
        """Settle every triggered bot that answered, ran out or timed out.
        Returns the answers of all bots that are done, for the report."""
        comments = self.gh.issue_comments(pr)
        reviews = self.gh.reviews(pr)
        runs = self.gh.check_runs(sha)
        answers = []
        now = self.clock()
        for name, since in h.triggered.items():
            b = self.bots[name]
            a = self._answer(b, since, comments, reviews, runs)
            if a and a.outcome == "done":
                answers.append(a)
            if name in h.settled:
                continue
            if a:
                extra = {"url": a.url}
                cost = re.search(r"\$(\d+\.\d+)", a.summary)
                if cost:
                    extra["usd"] = float(cost.group(1))
                left = re.search(r"(\d+) remain", a.summary)
                if left:
                    extra["remaining"] = int(left.group(1))
                self._rec(pr, sha, a.outcome, bot=name, **extra)
                h.settled[name] = a.outcome
                if a.outcome == "done" and extra.get("remaining") == 0:
                    self._rec(pr, sha, "quota", bot=name, why="0 remain")
            elif iso(now - timedelta(minutes=b.timeout_min)) > since:
                self._rec(pr, sha, "timeout", bot=name)
                h.settled[name] = "timeout"
        return answers

    def _answer(self, b: Bot, since: str, comments, reviews, runs) -> Answer | None:
        mine = [c for c in comments if c["user"]["login"] == b.login
                and (c.get("updated_at") or c["created_at"]) >= since]
        for c in mine:
            if b.is_quota(c["body"]):
                return Answer(b.name, "quota", c["html_url"], c["body"])
        kind, want = next(iter(b.done.items()))
        if kind == "comment":
            for c in mine:
                if not b.is_ignored(c["body"]) and re.search(want, c["body"]):
                    return Answer(b.name, "done", c["html_url"], c["body"])
        elif kind == "review":
            for r in reviews:
                if r["user"]["login"] == b.login and (r.get("submitted_at") or "") >= since:
                    return Answer(b.name, "done", r["html_url"], r.get("body") or "")
        elif kind == "check_run":
            for r in runs:
                if (r["name"] == want and r["status"] == "completed"
                        and (r.get("started_at") or "") >= since
                        and r.get("conclusion") != "skipped"):
                    out = r.get("output") or {}
                    text = f"{out.get('title') or ''}\n{out.get('summary') or ''}"
                    if b.is_quota(text) or "rate limit" in text.lower():
                        return Answer(b.name, "quota", r["html_url"], text)
                    return Answer(b.name, "done", r["html_url"], text)
        return None

    # ------------------------------------------------------------ reporting

    def _findings(self, pr: int, h: Head) -> list[Finding]:
        by_login = {self.bots[n].login: n for n in h.triggered}
        out = []
        for c in self.gh.review_comments(pr):
            name = by_login.get(c["user"]["login"])
            if (name and not c.get("in_reply_to_id") and h.settled.get(name) == "done"
                    and c["created_at"] >= h.triggered[name] and c.get("line") is not None):
                out.append(from_review_comment(name, c))
        return merge(out)

    def _report(self, pr: int, sha: str, p: dict, h: Head, answers: list[Answer]) -> str:
        found = self._findings(pr, h)
        blocking = [a for a in answers if self.bots[a.bot].summary_blocks(a.raw)]
        done = [a.bot for a in answers]
        if not done:
            state, desc = "error", "no bot gave a review: " + (
                ", ".join(f"{b} {h.settled.get(b, '?')}" for b in h.routed) or "none available")
        elif found or blocking:
            n = len(found) + len(blocking)
            state, desc = "failure", f"{n} finding{'s' * (n != 1)} from {', '.join(done)}"
        else:
            state, desc = "success", f"no findings from {', '.join(done)}"
        body = self._body(sha, state, h, answers, found, blocking)
        url = self._post(pr, body)
        self._status(sha, state, desc, url)
        self._rec(pr, sha, "reported", conclusion=state, findings=len(found),
                  blocking=[a.bot for a in blocking], url=url)
        self.say(f"{self.gh.repo}#{pr} {sha[:9]}: {state}: {desc}")
        # A description trigger stays in the body; take it out so the next
        # push is not reviewed unasked.
        self._untrigger(pr, h)
        return state

    def _untrigger(self, pr: int, h: Head) -> None:
        for name in h.triggered:
            b = self.bots[name]
            if b.trigger_kind != "description":
                continue
            body = self.gh.pull(pr).get("body") or ""
            if b.trigger_text in body:
                try:
                    self.gh.set_body(pr, body.replace(b.trigger_text, "").strip(), as_=b.trigger_as)
                except GitHubError as err:
                    self.say(f"{self.gh.repo}#{pr} {name}: could not remove trigger: {err}")

    def _body(self, sha, state, h, answers, found, blocking) -> str:
        icon = {"success": "✅", "failure": "❌", "error": "⚠️"}[state]
        lines = [MARKER, f"## {icon} review_mux: {state} on `{sha[:9]}`", ""]
        got = {a.bot: a for a in answers}
        lines.append("| Bot | Result |")
        lines.append("|---|---|")
        for b in h.routed:
            a = got.get(b)
            r = f"[{h.settled.get(b, '?')}]({a.url})" if a and a.url else h.settled.get(b, "?")
            lines.append(f"| {b} | {r} |")
        if found:
            lines += ["", "### Findings", ""]
            for i, f in enumerate(found, 1):
                where = f.path + (f":{f.start_line}" if f.start_line else "")
                if f.end_line and f.end_line != f.start_line:
                    where += f"-{f.end_line}"
                first = headline(f.body)[:200]
                links = " ".join(f"[{j}]({u})" for j, u in enumerate(f.sources, 1))
                lines.append(f"{i}. `{where}` ({', '.join(f.sources_bots)}): {first} {links}")
        if blocking:
            lines += ["", "### Summaries that count as findings", ""]
            for a in blocking:
                lines.append(f"- {a.bot}: [{plain(a.summary)[:200]}]({a.url})")
        return "\n".join(lines) + "\n"

    def _post(self, pr: int, body: str) -> str:
        for c in self.gh.issue_comments(pr):
            if MARKER in c["body"] and (not self.report_as or c["user"]["login"] == self.report_as):
                self.gh.edit_comment(c["id"], body, as_=self.report_as)
                return c["html_url"]
        cid = self.gh.comment(pr, body, as_=self.report_as)
        return f"https://github.com/{self.gh.repo}/pull/{pr}#issuecomment-{cid}"

    def _status(self, sha: str, state: str, desc: str, url: str | None = None) -> None:
        try:
            self.gh.status(sha, state, desc, CONTEXT, url, as_=self.report_as)
        except GitHubError as err:
            self.say(f"{self.gh.repo} {sha[:9]}: status: {err}")

    def _last_conclusion(self, pr: int, sha: str) -> str:
        recs = [r for r in self.ledger.for_head(self.gh.repo, pr, sha) if r["event"] == "reported"]
        return recs[-1]["conclusion"]
