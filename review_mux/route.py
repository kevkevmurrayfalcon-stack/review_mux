"""Which bots review a pull request head: the most useful review for what it
costs. Free bots and credits about to expire are spent first; paid bots only
when the stakes are high."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from review_mux.providers import Bot


@dataclass
class Settings:
    count: int = 2            # bots per review
    deep_lines: int = 300     # a change this big justifies paid bots
    deep_label: str = "review:deep"
    rest_hours: float = 6     # how long a bot out of quota is left alone


def score(b: Bot, today: date) -> float:
    s = b.quality - 2.0 * b.usd - 0.02 * b.credits
    if b.expires and b.expires - today <= timedelta(days=7):
        s += 0.3  # use it or lose it
    return s


def out_of_quota(ledger: list[dict], now: datetime, rest: timedelta) -> set[str]:
    out = {}
    for r in ledger:
        if r.get("event") == "quota":
            out[r["bot"]] = r["t"]
    cutoff = (now - rest).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {b for b, t in out.items() if t > cutoff}


def route(bots: dict[str, Bot], repo: str, lines: int, labels: set[str],
          ledger: list[dict], now: datetime, s: Settings) -> list[str]:
    deep = lines >= s.deep_lines or s.deep_label in labels
    out = out_of_quota(ledger, now, timedelta(hours=s.rest_hours))
    able = [b for b in bots.values()
            if b.serves(repo) and b.name not in out
            and (b.free or deep or (b.expires and b.expires - now.date() <= timedelta(days=7)))
            and not (b.expires and b.expires < now.date())]
    able.sort(key=lambda b: (-score(b, now.date()), b.name))
    chosen = []
    if deep:  # the stakes buy the best paid review, whatever it costs
        paid = [b for b in able if not b.free]
        paid.sort(key=lambda b: (-b.quality, b.name))
        chosen = paid[:1]
    for b in able:
        if len(chosen) >= s.count:
            break
        if b not in chosen:
            chosen.append(b)
    return [b.name for b in chosen]
