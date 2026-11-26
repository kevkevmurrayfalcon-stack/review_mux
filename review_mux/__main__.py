"""review_mux: route PRs across review bots and merge their findings.

    python -m review_mux review REPO PR [--wait]
    python -m review_mux watch REPO (--author LOGIN... | --label NAME | --all)
    python -m review_mux route REPO PR        # which bots it would ask, and why

Options: --providers providers.yml  --ledger review_mux.jsonl  --count 2
         --deep-lines 300  --report-as ACCOUNT (posts the comment and status)
"""
from __future__ import annotations

import argparse
import sys
import time

from review_mux.github import GitHub, GitHubError
from review_mux.ledger import Ledger
from review_mux.mux import Mux
from review_mux.providers import load
from review_mux.route import Settings, route, score

DONE = {"success", "failure", "error", "none"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="review_mux", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["review", "watch", "route"])
    ap.add_argument("repo")
    ap.add_argument("pr", nargs="?", type=int)
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--author", action="append", default=[])
    ap.add_argument("--label")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--providers", default="providers.yml")
    ap.add_argument("--ledger", default="review_mux.jsonl")
    ap.add_argument("--count", type=int, default=2)
    ap.add_argument("--deep-lines", type=int, default=300)
    ap.add_argument("--report-as")
    ap.add_argument("--every", type=int, default=60, help="seconds between passes")
    a = ap.parse_args(argv)
    gh = GitHub(a.repo)
    bots = load(a.providers)
    s = Settings(count=a.count, deep_lines=a.deep_lines)
    mux = Mux(gh, Ledger(a.ledger), bots, s, report_as=a.report_as)

    if a.cmd == "route":
        p = gh.pull(a.pr)
        lines = p["additions"] + p["deletions"]
        labels = {l["name"] for l in p["labels"]}
        chosen = route(bots, a.repo, lines, labels, mux.ledger.read(), mux.clock(), s)
        print(f"{lines} lines changed; asks: {', '.join(chosen) or 'nobody'}")
        for b in sorted(bots.values(), key=lambda b: -score(b, mux.clock().date())):
            why = ("not on this repo" if not b.serves(a.repo) else
                   "paid, change too small" if not b.free and lines < s.deep_lines else "")
            print(f"  {b.name:11} score {score(b, mux.clock().date()):+.2f}  {why}")
        return 0

    if a.cmd == "review":
        if a.pr is None:
            ap.error("review needs a PR number")
        while True:
            state = mux.step(a.pr)
            if state in DONE or not a.wait:
                print(state)
                return 0 if state in ("success", "none", "waiting", "routed") else 1
            time.sleep(a.every)

    if not (a.author or a.label or a.all):
        ap.error("watch needs --author, --label or --all: it spends credit on every PR it reviews")
    while True:
        try:
            for p in gh.open_pulls():
                if a.author and p["user"]["login"] not in a.author:
                    continue
                if a.label and a.label not in {l["name"] for l in p["labels"]}:
                    continue
                if p.get("draft"):
                    continue
                try:
                    mux.step(p["number"])
                except GitHubError as err:
                    print(f"#{p['number']}: {err}", file=sys.stderr)
        except GitHubError as err:
            print(f"listing pulls: {err}", file=sys.stderr)
        time.sleep(a.every)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
