"""Discovery: messages in, ledger accounts out.

The model classifies messages in batches into MessageSignal records. Aggregation by sender
domain is pure code so it can be tested and reasoned about without a model.
"""

from __future__ import annotations

import hashlib
import html
import json
import mailbox
import re
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import date
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from strands import Agent
from strands.models import Model

from loose_ends.schema import Account

Signal = Literal["billing", "statement", "appointment", "membership", "marketing", "newsletter",
                 "personal", "spam", "government", "other"]


class Message(BaseModel):
    id: str
    sender: str
    sender_name: str = ""
    date: date
    subject: str
    body: str = ""

    @property
    def sender_domain(self) -> str:
        host = self.sender.rsplit("@", 1)[-1].lower().strip(">")
        labels = host.split(".")
        return ".".join(labels[-2:]) if len(labels) >= 2 else host


class MessageSignal(BaseModel):
    message_id: str
    vendor: str
    domain: str
    category: str
    signal: Signal
    is_account: bool
    confidence: float = Field(ge=0, le=1)
    amount: float | None = None
    cadence: str | None = None


class BatchSignals(BaseModel):
    signals: list[MessageSignal]


Classifier = Callable[[list[Message]], list[MessageSignal]]


def load_json_mailbox(path: Path | str) -> list[Message]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return sorted((Message.model_validate(m) for m in raw), key=lambda m: (m.date, m.id))


def load_mbox(path: Path | str) -> list[Message]:
    """Google Takeout and most mail clients export .mbox. Bodies come back as plain text."""
    messages = []
    for raw in mailbox.mbox(str(path)):
        try:
            day = parsedate_to_datetime(raw.get("Date", "")).date()
        except (TypeError, ValueError):
            continue
        name, addr = parseaddr(_header(raw, "From"))
        subject = _header(raw, "Subject")
        message_id = (raw.get("Message-ID") or "").strip("<> ")
        if not message_id:
            message_id = hashlib.sha1(f"{addr}|{subject}|{raw.get('Date')}".encode()).hexdigest()[:16]
        messages.append(Message(id=message_id, sender=addr, sender_name=name, date=day, subject=subject,
                                body=_plain_body(raw)))
    return sorted(messages, key=lambda m: (m.date, m.id))


def load_mailbox(path: Path | str) -> list[Message]:
    return load_mbox(path) if Path(path).suffix.lower() == ".mbox" else load_json_mailbox(path)


def _header(raw: mailbox.mboxMessage, name: str) -> str:
    value = raw.get(name, "")
    return str(make_header(decode_header(value))) if value else ""


def _plain_body(raw: mailbox.mboxMessage) -> str:
    plain: str | None = None
    html_text: str | None = None
    for part in raw.walk():
        if part.get_content_maintype() == "multipart":
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if part.get_content_type() == "text/plain" and plain is None:
            plain = text
        elif part.get_content_type() == "text/html" and html_text is None:
            html_text = text
    if plain:
        return plain.strip()
    if html_text:
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", html_text))).strip()
    return ""


def aggregate_signals(signals: Iterable[MessageSignal]) -> list[Account]:
    groups: dict[str, list[MessageSignal]] = {}
    for signal in signals:
        if signal.is_account:
            groups.setdefault(signal.domain.lower(), []).append(signal)

    accounts = []
    for domain, group in groups.items():
        best = max(group, key=lambda s: s.confidence)
        category = Counter(s.category for s in group).most_common(1)[0][0]
        monthly = [s.amount for s in group if s.cadence == "monthly" and s.amount]
        accounts.append(Account(
            vendor=best.vendor,
            domain=domain,
            category=category,
            evidence=[s.message_id for s in group],
            confidence=best.confidence,
            monthly_amount=max(monthly) if monthly else None,
        ))
    return accounts


SYSTEM_PROMPT = """You classify emails from a deceased person's inbox to find every account,
subscription, utility, provider, membership and institution that will need to be notified.

For each message return one MessageSignal:
- vendor: the organization's plain name (e.g. "Netflix", "ComEd", "Chase").
- domain: the organization's primary domain (e.g. "netflix.com").
- category: one of credit_bureau, bank, insurance, subscription, utility, social_facebook, google,
  apple, amazon, medical, membership, employer, government, marketing, personal, other.
- signal: what kind of message this is.
- is_account: true only if this sender represents an account or relationship the estate must
  deal with. Personal mail, newsletters and spam are false.
- confidence: 0 to 1.
- amount and cadence when a recurring charge is visible.
"""


def build_classifier(model: Model, batch_size: int = 50) -> Classifier:
    def classify(messages: list[Message]) -> list[MessageSignal]:
        signals: list[MessageSignal] = []
        for start in range(0, len(messages), batch_size):
            batch = messages[start:start + batch_size]
            agent = Agent(model=model, system_prompt=SYSTEM_PROMPT, callback_handler=None)
            result = agent(_format_batch(batch), structured_output_model=BatchSignals)
            signals.extend(result.structured_output.signals)
        return signals

    return classify


def _format_batch(batch: list[Message]) -> str:
    lines = ["Classify each of these messages. Return one signal per message id.", ""]
    for m in batch:
        lines.append(f"[{m.id}] {m.date} from {m.sender_name} <{m.sender}>")
        lines.append(f"  subject: {m.subject}")
        lines.append(f"  body: {m.body[:400]}")
    return "\n".join(lines)
