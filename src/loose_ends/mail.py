"""Mail transport. OutboxMailer is the local stand-in for SES: sent mail lands in a folder
and replies are read from a folder. A tracking token in every subject links replies back
to the account they concern."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from loose_ends.schema import new_id, now

_TOKEN = re.compile(r"\[LE-([0-9a-f]+)\]")


def tracking_token(account_id: str) -> str:
    return f"[LE-{account_id}]"


def extract_token(subject: str) -> str | None:
    match = _TOKEN.search(subject)
    return match.group(1) if match else None


class OutgoingMail(BaseModel):
    id: str = Field(default_factory=new_id)
    to: str
    subject: str
    body: str
    attachments: list[str] = Field(default_factory=list)
    sent_at: datetime = Field(default_factory=now)


class IncomingMail(BaseModel):
    id: str
    sender: str
    date: date
    subject: str
    body: str = ""

    @property
    def token(self) -> str | None:
        return extract_token(self.subject)


class Mailer(Protocol):
    def send(self, to: str, subject: str, body: str, attachments: list[str] | None = None) -> OutgoingMail: ...
    def read_replies(self) -> list[IncomingMail]: ...


class OutboxMailer:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        for sub in ("sent", "inbox", "processed"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def send(self, to: str, subject: str, body: str, attachments: list[str] | None = None) -> OutgoingMail:
        mail = OutgoingMail(to=to, subject=subject, body=body, attachments=list(attachments or []))
        (self.root / "sent" / f"{mail.id}.json").write_text(mail.model_dump_json(indent=2), encoding="utf-8")
        return mail

    def sent(self) -> list[OutgoingMail]:
        mails = [OutgoingMail.model_validate_json(p.read_text(encoding="utf-8"))
                 for p in (self.root / "sent").glob("*.json")]
        return sorted(mails, key=lambda m: m.sent_at)

    def drop_reply(self, mail: IncomingMail) -> None:
        (self.root / "inbox" / f"{mail.id}.json").write_text(mail.model_dump_json(indent=2), encoding="utf-8")

    def read_replies(self) -> list[IncomingMail]:
        replies = []
        for path in sorted((self.root / "inbox").glob("*.json")):
            replies.append(IncomingMail.model_validate(json.loads(path.read_text(encoding="utf-8"))))
            path.replace(self.root / "processed" / path.name)
        return replies
