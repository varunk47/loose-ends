"""Playbooks: one YAML per account category, encoding what actually works with each kind
of organization. The planner maps an account to a playbook deterministically."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from loose_ends.schema import Account, AccountStatus

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "playbooks"
FALLBACK_ID = "generic"


class Playbook(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    category: str
    action: str
    channel: str
    irreversible: bool
    priority: int
    follow_up_days: int
    required_packet: list[str]
    time_weight_hours: float
    escalation: str
    contact_hint: str = ""
    notes: str = ""


def playbook_dir() -> Path:
    return Path(os.environ.get("LOOSE_ENDS_PLAYBOOKS", DEFAULT_DIR))


@lru_cache(maxsize=4)
def _load(path: Path) -> dict[str, Playbook]:
    books = [Playbook.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))
             for p in sorted(path.glob("*.yaml"))]
    return {book.id: book for book in books}


def load_playbooks(path: Path | None = None) -> dict[str, Playbook]:
    return _load(path or playbook_dir())


def playbook_for(category: str, playbooks: dict[str, Playbook]) -> Playbook:
    by_category = {book.category: book for book in playbooks.values()}
    return by_category.get(category) or playbooks[FALLBACK_ID]


def plan_account(account: Account, playbooks: dict[str, Playbook]) -> Account:
    book = playbook_for(account.category, playbooks)
    return account.model_copy(update={
        "playbook": book.id,
        "priority": book.priority,
        "packet_needs": list(book.required_packet),
        "status": AccountStatus.PLANNED,
    })
