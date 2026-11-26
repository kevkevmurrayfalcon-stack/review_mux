"""The muxer against a fake GitHub, with bot answers shaped like the real ones
seen on Clavigers/review_mux."""
from datetime import datetime, timedelta, timezone

import pytest

from review_mux.github import GitHubError
from review_mux.ledger import Ledger, iso
from review_mux.mux import MARKER, Mux
from review_mux.providers import load
from review_mux.route import Settings

REPO = "Clavigers/review_mux"


class Clock:
    def __init__(self):
        self.t = datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.t

    def tick(self, minutes=1):
        self.t += timedelta(minutes=minutes)
        return iso(self.t)


class FakeGitHub:
    def __init__(self, clock):
        self.repo = REPO
        self.clock = clock
        self.pulls = {}
        self.icomments = {}   # pr -> list
        self.rcomments = {}
        self.revs = {}
        self.runs = {}        # sha -> list
        self.statuses = []    # (sha, state, desc)
        self.posted = []      # (pr, body, as_)
        self.bodies = []      # (pr, body, as_)
        self.fail_as = set()
        self.next_id = 100

    def pr(self, n, sha="a1", lines=20, labels=(), body=""):
        self.pulls[n] = {"number": n, "state": "open", "head": {"sha": sha},
                         "additions": lines, "deletions": 0, "body": body,
                         "labels": [{"name": l} for l in labels], "user": {"login": "x"}}
        for d in (self.icomments, self.rcomments, self.revs):
            d.setdefault(n, [])

    def say(self, pr, login, body, at=None):
        self.next_id += 1
        t = at or iso(self.clock())
        self.icomments[pr].append({"id": self.next_id, "user": {"login": login}, "body": body,
                                   "created_at": t, "updated_at": t,
                                   "html_url": f"https://x/{pr}#c{self.next_id}"})

    def inline(self, pr, login, path, line, body="finding", reply=False, at=None):
        self.next_id += 1
        self.rcomments[pr].append({
            "id": self.next_id, "user": {"login": login}, "path": path, "line": line,
            "start_line": None, "side": "RIGHT", "body": body, "commit_id": "",
            "created_at": at or iso(self.clock()), "html_url": f"https://x/r{self.next_id}",
            "in_reply_to_id": 1 if reply else None})

    def run(self, sha, name, conclusion="success", summary="Review completed", at=None):
        self.runs.setdefault(sha, []).append({
            "name": name, "status": "completed", "conclusion": conclusion,
            "started_at": at or iso(self.clock()), "html_url": f"https://x/run/{name}",
            "output": {"title": "", "summary": summary}})

    # the interface
    def pull(self, n):
        return self.pulls[n]

    def open_pulls(self):
        return [p for p in self.pulls.values() if p["state"] == "open"]

    def issue_comments(self, n):
        return self.icomments[n]

    def review_comments(self, n):
        return self.rcomments[n]

    def reviews(self, n):
        return self.revs[n]

    def check_runs(self, sha):
        return self.runs.get(sha, [])

    def comment(self, n, body, as_=None):
        if as_ in self.fail_as:
            raise GitHubError(f"no token for {as_}")
        self.posted.append((n, body, as_))
        self.say(n, as_ or "me", body)
        return self.next_id

    def edit_comment(self, cid, body, as_=None):
        for cs in self.icomments.values():
            for c in cs:
                if c["id"] == cid:
                    c["body"] = body
        self.posted.append(("edit", body, as_))

    def set_body(self, n, body, as_=None):
        self.pulls[n]["body"] = body
        self.bodies.append((n, body, as_))

    def status(self, sha, state, desc, context, url=None, as_=None):
        self.statuses.append((sha, state, desc))


@pytest.fixture
def rig(tmp_path):
    clock = Clock()
    gh = FakeGitHub(clock)
    said = []
    mux = Mux(gh, Ledger(str(tmp_path / "l.jsonl")), load("providers.yml"), Settings(),
              report_as="me", clock=clock, say=said.append)
    return clock, gh, mux


def triggers(gh):
    return [(b, a) for _, b, a in gh.posted if not b.startswith(MARKER)]


def test_a_small_change_asks_free_bots_and_reports_merged_findings(rig):
    clock, gh, mux = rig
    gh.pr(1)
    gh.inline(1, "coderabbitai[bot]", "old.py", 3)  # before the trigger: not this review
    clock.tick()
    assert mux.step(1) == "waiting"
    assert triggers(gh) == [("@coderabbitai review", "sadosystems"), ("@greptileai", "sadosystems")]
    assert gh.statuses[-1][1] == "pending"
    clock.tick()
    gh.say(1, "coderabbitai[bot]", "<!-- auto-generated reply by CodeRabbit --> Review triggered.")
    gh.inline(1, "coderabbitai[bot]", "a.py", 10, "Off by one in the loop bound")
    gh.inline(1, "greptile-apps[bot]", "a.py", 11, "Loop bound skips the last item")
    gh.inline(1, "greptile-apps[bot]", "a.py", 11, "agreed", reply=True)
    assert mux.step(1) == "waiting"  # CodeRabbit's check run has not finished
    gh.run("a1", "CodeRabbit", summary="Result: Success\n9 remain after this review")
    gh.say(1, "greptile-apps[bot]", "<!-- greptile_summary --><!-- greptile_confidence_score:4 --> ok")
    assert mux.step(1) == "failure"
    sha, state, desc = gh.statuses[-1]
    assert (sha, state) == ("a1", "failure") and "1 finding " in desc
    report = gh.posted[-1][1]
    assert report.startswith(MARKER) and "(coderabbit, greptile)" in report and "a.py:10-11" in report
    # Asking again changes nothing and spends nothing.
    n = len(gh.posted)
    assert mux.step(1) == "failure" and len(gh.posted) == n
    rec = [r for r in mux.ledger.read() if r["event"] == "done" and r["bot"] == "coderabbit"]
    assert rec[0]["remaining"] == 9


def test_no_findings_is_success_and_a_bot_approval_counts_for_nothing(rig):
    clock, gh, mux = rig
    gh.pr(1)
    mux.step(1)
    clock.tick()
    gh.run("a1", "CodeRabbit")
    gh.say(1, "greptile-apps[bot]", "<!-- greptile_summary --><!-- greptile_confidence_score:5 -->")
    gh.revs[1].append({"user": {"login": "greptile-apps[bot]"}, "state": "APPROVED",
                       "submitted_at": iso(clock()), "html_url": "u", "body": ""})
    assert mux.step(1) == "success"


def test_a_low_confidence_summary_is_a_finding(rig):
    clock, gh, mux = rig
    gh.pr(1)
    mux.step(1)
    clock.tick()
    gh.run("a1", "CodeRabbit")
    gh.say(1, "greptile-apps[bot]", "<!-- greptile_summary --><!-- greptile_confidence_score:2 --> risky")
    assert mux.step(1) == "failure"
    assert "Summaries that count" in gh.posted[-1][1]


def test_a_new_push_is_a_new_review_and_the_report_is_edited_in_place(rig):
    clock, gh, mux = rig
    gh.pr(1)
    mux.step(1)
    clock.tick()
    gh.inline(1, "coderabbitai[bot]", "a.py", 10)
    gh.run("a1", "CodeRabbit")
    gh.say(1, "greptile-apps[bot]", "<!-- greptile_summary --><!-- greptile_confidence_score:5 -->")
    assert mux.step(1) == "failure"
    clock.tick()
    gh.pr(1, sha="b2")  # the fix
    gh.icomments[1] = [c for c in gh.icomments[1]]  # keep history
    assert mux.step(1) == "waiting"
    clock.tick()
    gh.run("b2", "CodeRabbit")
    gh.say(1, "greptile-apps[bot]", "<!-- greptile_summary --><!-- greptile_confidence_score:5 -->")
    assert mux.step(1) == "success"  # the old finding was for a1
    assert gh.posted[-1][0] == "edit"
    assert [s[:2] for s in gh.statuses if s[1] != "pending"] == [("a1", "failure"), ("b2", "success")]


def test_out_of_quota_is_left_alone_for_a_while(rig):
    clock, gh, mux = rig
    gh.pr(1)
    mux.step(1)
    clock.tick()
    gh.say(1, "greptile-apps[bot]", "<!-- greptile-credit-pause:x --> Your organization has run out of review credits.")
    gh.run("a1", "CodeRabbit")
    assert mux.step(1) == "success"  # CodeRabbit reviewed and found nothing
    gh.pr(2, sha="c3")
    clock.tick()
    mux.step(2)
    assert "@greptileai" not in [b for b, _ in triggers(gh)[2:]]
    clock.tick(60 * 7)
    gh.pr(3, sha="d4")
    mux.step(3)
    assert "@greptileai" in [b for b, _ in triggers(gh)[4:]]


def test_nobody_answering_is_an_error(rig):
    clock, gh, mux = rig
    gh.pr(1)
    mux.step(1)
    clock.tick(16)
    assert mux.step(1) == "waiting"  # Greptile timed out; CodeRabbit has 20 minutes
    clock.tick(5)
    assert mux.step(1) == "error"
    assert gh.statuses[-1][1] == "error" and "timeout" in gh.statuses[-1][2]


def test_paid_bots_only_when_the_stakes_are_high(rig):
    clock, gh, mux = rig
    gh.pr(1, lines=20)
    gh.pr(2, sha="b", lines=500)
    gh.pr(3, sha="c", labels=["review:deep"])
    for n in (1, 2, 3):
        mux.step(n)
    asked = [r["bots"] for r in mux.ledger.read() if r["event"] == "routed"]
    assert "ellipsis" not in asked[0] and asked[1][0] == "ellipsis" and asked[2][0] == "ellipsis"


def test_a_trigger_that_cannot_be_posted_settles_the_bot(rig):
    clock, gh, mux = rig
    gh.fail_as.add("sadosystems")
    gh.pr(1)
    assert mux.step(1) == "error"
    assert [r["event"] for r in mux.ledger.read()].count("failed") == 2


def test_a_description_trigger_is_added_then_taken_out(rig):
    clock, gh, mux = rig
    mux.bots = {k: v for k, v in mux.bots.items() if k == "graphite"}
    gh.pr(1, body="Fixes things.")
    mux.step(1)
    assert gh.pulls[1]["body"] == "Fixes things.\n\n/graphite-review"
    clock.tick()
    gh.run("a1", "Graphite / AI Reviews", summary="AI review ran and left 0 comments")
    assert mux.step(1) == "success"
    assert gh.pulls[1]["body"] == "Fixes things."


def test_a_skipped_check_run_is_not_an_answer(rig):
    clock, gh, mux = rig
    mux.bots = {k: v for k, v in mux.bots.items() if k == "graphite"}
    gh.pr(1)
    mux.step(1)
    clock.tick()
    gh.run("a1", "Graphite / AI Reviews", conclusion="skipped", summary="does not match filters")
    assert mux.step(1) == "waiting"


def test_ellipsis_answers_in_prose(rig):
    clock, gh, mux = rig
    mux.bots = {k: v for k, v in mux.bots.items() if k == "ellipsis"}
    gh.pr(1, lines=400)
    gh.pr(2, sha="b", lines=400)
    mux.step(1)
    mux.step(2)
    clock.tick()
    gh.say(1, "ellipsis-dev[bot]", "I didn't find any bugs in this PR. 8 lines, $0.20")
    gh.say(2, "ellipsis-dev[bot]", "The loop in a.py skips its last item. $0.31")
    assert mux.step(1) == "success" and mux.step(2) == "failure"
    spent = [r["usd"] for r in mux.ledger.read() if r["event"] == "done"]
    assert spent == [0.2, 0.31]
