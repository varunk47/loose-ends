"""Vendor directory: known senders with their category and billing pattern.

Used two ways: to generate the demo inbox, and as the offline classifier and drafter so the
whole loop runs with no model credentials.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from loose_ends.correspondence import Notice
from loose_ends.discovery import Classifier, Message, MessageSignal
from loose_ends.followup import ReplyOutcome
from loose_ends.mail import IncomingMail
from loose_ends.playbooks import Playbook
from loose_ends.schema import Account, Estate

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "vendors.yaml"
ACCOUNT_KINDS = {"billing", "statement", "appointment", "membership", "government"}


class VendorEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    domain: str
    vendor: str
    category: str
    kind: str
    cadence: str
    amount: float | None = None
    senders: list[str] = []
    subjects: list[str] = []
    body: str = ""
    contact_email: str | None = None


class VendorDirectory:
    def __init__(self, entries: list[VendorEntry]) -> None:
        self._by_domain = {e.domain.lower(): e for e in entries}

    @classmethod
    @lru_cache(maxsize=4)
    def load(cls, path: Path | None = None) -> VendorDirectory:
        source = path or Path(os.environ.get("LOOSE_ENDS_VENDORS", DEFAULT_PATH))
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
        return cls([VendorEntry.model_validate(e) for e in raw])

    def lookup(self, domain: str) -> VendorEntry | None:
        return self._by_domain.get(domain.lower())

    def lookup_name(self, text: str) -> VendorEntry | None:
        """Match a statement description like "NETFLIX.COM 866-579" to an entry by its domain stem."""
        haystack = "".join(c for c in text.upper() if c.isalnum())
        for entry in self._by_domain.values():
            stem = entry.domain.split(".")[0].upper()
            if len(stem) >= 4 and stem in haystack:
                return entry
        return None


def rule_classifier(directory: VendorDirectory) -> Classifier:
    def classify(messages: list[Message]) -> list[MessageSignal]:
        return [_signal(m, directory.lookup(m.sender_domain)) for m in messages]

    return classify


_AMOUNT = re.compile(r"\$([\d,]+\.\d{2})")


def _signal(message: Message, entry: VendorEntry | None) -> MessageSignal:
    if entry is None and message.sender_domain.endswith(".statement"):
        found = _AMOUNT.search(message.body)
        return MessageSignal(message_id=message.id, vendor=message.sender_name or message.sender_domain,
                             domain=message.sender_domain, category="subscription", signal="billing",
                             is_account=True, confidence=0.6, cadence="monthly",
                             amount=float(found.group(1).replace(",", "")) if found else None)
    if entry is None:
        return MessageSignal(message_id=message.id, vendor=message.sender_name or message.sender_domain,
                             domain=message.sender_domain, category="other", signal="other",
                             is_account=False, confidence=0.3)
    billing = entry.kind == "billing"
    return MessageSignal(
        message_id=message.id, vendor=entry.vendor, domain=entry.domain, category=entry.category,
        signal=entry.kind if entry.kind != "government" else "government",
        is_account=entry.kind in ACCOUNT_KINDS, confidence=0.9,
        amount=entry.amount if billing else None, cadence=entry.cadence if billing else None,
    )


_ACTION_SENTENCE = {
    "cancel": "Please cancel the account effective {dod}, stop all billing, and refund any unused prepaid time to the original payment method.",
    "memorialize": "Please memorialize the account so it is preserved but no longer active.",
    "register": "Please register this notice so no further contact is sent.",
}
_DEFAULT_SENTENCE = "Please note the death on the account, stop all mailings and billing, and send me your procedure and any forms required to settle the account."


def template_notice(estate: Estate, account: Account, playbook: Playbook, instruction: str | None = None) -> Notice:
    action = _ACTION_SENTENCE.get(playbook.action, _DEFAULT_SENTENCE).format(dod=estate.date_of_death.strftime("%B %d, %Y"))
    lines = [
        f"To {account.vendor},",
        "",
        f"I am writing on behalf of {estate.executor_name}, {estate.executor_relationship} of {estate.deceased}, "
        f"who died on {estate.date_of_death.strftime('%B %d, %Y')}.",
        "",
        action,
    ]
    if instruction:
        lines += ["", instruction]
    if "certificate" in playbook.required_packet:
        lines += ["", "The death certificate is attached."]
    lines += ["", "Please confirm in writing when this is complete.", "",
              f"{estate.executor_name}", f"{estate.executor_email}"]
    return Notice(subject=f"Notice of death: {estate.deceased}", body="\n".join(lines))


def rule_reply_classifier(reply: IncomingMail, account: Account) -> ReplyOutcome:
    text = f"{reply.subject} {reply.body}".lower()
    if any(k in text for k in ("closed", "cancelled", "canceled", "memorialized", "has been processed", "refund")):
        return ReplyOutcome(kind="closed", summary="confirmed complete")
    if any(k in text for k in ("letters testamentary", "death certificate", "please provide", "we need", "require")):
        return ReplyOutcome(kind="needs_documents", summary=reply.body[:80])
    if any(k in text for k in ("call us", "phone", "by mail", "fax", "visit")):
        return ReplyOutcome(kind="wrong_channel", summary=reply.body[:80])
    if any(k in text for k in ("unable", "cannot", "decline", "not able")):
        return ReplyOutcome(kind="denied", summary=reply.body[:80])
    return ReplyOutcome(kind="other", summary=reply.body[:80])
