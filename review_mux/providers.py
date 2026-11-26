"""providers.yml as typed Bots."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

import yaml


@dataclass(frozen=True)
class Bot:
    name: str
    login: str
    trigger_kind: str  # comment | description
    trigger_text: str
    trigger_as: str
    done: dict
    repos: tuple[str, ...] = ()
    quota: tuple[str, ...] = ()
    ignore: tuple[str, ...] = ()
    blocks: str | None = None
    clean: str | None = None
    usd: float = 0.0
    credits: float = 0.0
    quality: float = 0.5
    expires: date | None = None
    timeout_min: int = 15

    @property
    def free(self) -> bool:
        return not self.usd and not self.credits

    def serves(self, repo: str) -> bool:
        return not self.repos or repo in self.repos

    def is_quota(self, body: str) -> bool:
        return any(re.search(p, body) for p in self.quota)

    def is_ignored(self, body: str) -> bool:
        return any(re.search(p, body) for p in self.ignore)

    def summary_blocks(self, body: str) -> bool:
        if self.blocks and re.search(self.blocks, body):
            return True
        return bool(self.clean) and not re.search(self.clean, body)


KEYS = {"login", "trigger", "trigger_as", "done", "repos", "quota", "ignore", "blocks",
        "clean", "cost", "quality", "expires", "timeout_min"}


def load(path: str = "providers.yml") -> dict[str, Bot]:
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    bots = {}
    for name, p in raw.items():
        extra = set(p) - KEYS
        if extra:
            raise ValueError(f"{name}: unknown keys {sorted(extra)}")
        (kind, text), = p["trigger"].items()
        if kind not in ("comment", "description"):
            raise ValueError(f"{name}: trigger must be comment or description")
        (dk, _), = p["done"].items()
        if dk not in ("review", "comment", "check_run"):
            raise ValueError(f"{name}: done must be review, comment or check_run")
        cost = p.get("cost") or {}
        exp = p.get("expires")
        bots[name] = Bot(
            name=name, login=p["login"], trigger_kind=kind, trigger_text=text,
            trigger_as=p["trigger_as"], done=p["done"], repos=tuple(p.get("repos") or ()),
            quota=tuple(p.get("quota") or ()), ignore=tuple(p.get("ignore") or ()),
            blocks=p.get("blocks"), clean=p.get("clean"),
            usd=float(cost.get("usd", 0)), credits=float(cost.get("credits", 0)),
            quality=float(p.get("quality", 0.5)),
            expires=exp if isinstance(exp, date) else (date.fromisoformat(exp) if exp else None),
            timeout_min=int(p.get("timeout_min", 15)))
    return bots
