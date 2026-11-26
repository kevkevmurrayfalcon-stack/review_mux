import json
from pathlib import Path

from review_mux.findings import Finding, from_review_comment, overlaps

FIXTURES = Path(__file__).parent / "fixtures"


def f(start, end, side="RIGHT", path="a.py"):
    return Finding(bot="x", path=path, start_line=start, end_line=end, body="", side=side)


def test_overlap_nearby_lines():
    assert overlaps(f(10, 12), f(14, 14))
    assert not overlaps(f(10, 12), f(20, 20))


def test_opposite_sides_do_not_overlap():
    assert not overlaps(f(10, 10, "LEFT"), f(10, 10, "RIGHT"))


def test_lineless_findings():
    assert overlaps(f(None, None), f(None, None))
    assert not overlaps(f(None, None), f(10, 10))


def test_outdated_comment_has_no_lines():
    c = {"path": "a.py", "line": None, "original_line": 7, "body": "b", "html_url": "u"}
    assert from_review_comment("x", c).start_line is None


def test_devlo_real_comments_parse_and_dedupe():
    comments = json.loads((FIXTURES / "devlo_pr1_comments.json").read_text())
    found = [from_review_comment("devlo", c) for c in comments if "devlo" in c["user"]["login"]]
    assert len(found) >= 2
    # devlo reviewed twice and repeated itself; at least one pair must collapse.
    assert any(overlaps(a, b) for i, a in enumerate(found) for b in found[i + 1:])


def test_collect_keeps_known_bots_and_skips_replies():
    from review_mux.collect import collect

    comments = json.loads((FIXTURES / "devlo_pr1_comments.json").read_text())
    human = dict(comments[0], user={"login": "someone"})
    reply = dict(comments[0], in_reply_to_id=1)
    found = collect(comments + [human, reply], {"devloai[bot]": "devlo"})
    assert len(found) == len(comments)
    assert {f.bot for f in found} == {"devlo"}
