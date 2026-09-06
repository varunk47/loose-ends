"""Ledger records. Every agent writes these; the dashboard reads them."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now() -> datetime:
    return datetime.now(UTC)


FULL_PACKET = ("certificate", "executor_id", "authority_proof")
PACKET_LABELS = {
    "certificate": "death certificate",
    "executor_id": "executor ID",
    "authority_proof": "proof of authority (Letters Testamentary)",
}


class AccountStatus(StrEnum):
    DISCOVERED = "discovered"
    PLANNED = "planned"
    AWAITING_DECISION = "awaiting_decision"
    IN_PROGRESS = "in_progress"
    SENT = "sent"
    AWAITING_REPLY = "awaiting_reply"
    FOLLOW_UP = "follow_up"
    DONE = "done"
    FAILED = "failed"
    PARKED = "parked"
    WATCHING = "watching"


class Estate(BaseModel):
    id: str = Field(default_factory=new_id)
    deceased: str
    date_of_death: date
    executor_name: str
    executor_email: str
    executor_relationship: str = "executor"
    state: str
    certificate_key: str | None = None
    packet: list[str] = Field(default_factory=lambda: list(FULL_PACKET))
    status: str = "active"
    paused_until: date | None = None
    last_digest: list[str] = Field(default_factory=list)  # decision ids in the order the last digest listed them


class Account(BaseModel):
    id: str = Field(default_factory=new_id)
    vendor: str
    domain: str
    category: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    playbook: str | None = None
    priority: int = 100
    status: AccountStatus = AccountStatus.DISCOVERED
    packet_needs: list[str] = Field(default_factory=list)
    next_action_at: datetime | None = None
    artifacts: list[str] = Field(default_factory=list)
    notes: str = ""
    monthly_amount: float | None = None
    contact_email: str | None = None


class Decision(BaseModel):
    id: str = Field(default_factory=new_id)
    account_id: str
    question: str
    options: list[str]
    context: str = ""
    resumes_action: str
    created_at: datetime = Field(default_factory=now)
    answered_at: datetime | None = None
    answer: str | None = None
    applied_at: datetime | None = None  # set once dispatch has acted on the answer


class Action(BaseModel):
    id: str = Field(default_factory=new_id)
    account_id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    result: str = ""
    artifacts: list[str] = Field(default_factory=list)
    at: datetime = Field(default_factory=now)


class Cycle(BaseModel):
    id: str = Field(default_factory=new_id)
    at: datetime = Field(default_factory=now)
    summary: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class Watch(BaseModel):
    """A Ghost Watch hit: something happened after death that should not have."""

    id: str = Field(default_factory=new_id)
    signal: str  # zombie_charge | new_account | credit_inquiry
    account_id: str
    evidence: list[str] = Field(default_factory=list)
    summary: str = ""
    draft: str = ""
    status: str = "open"  # open | sent | ignored
    at: datetime = Field(default_factory=now)
