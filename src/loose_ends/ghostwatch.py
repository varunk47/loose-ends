"""Ghost Watch: after the notices go out, keep reading new mail for three things that should
not happen after a death: a charge from an account that was closed, a new account opened in
the deceased's name, and a credit inquiry. Each hit gets a drafted dispute and a decision.
"""

from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel

from loose_ends.brain import Brain
from loose_ends.discovery import Message, MessageSignal
from loose_ends.ledger import JsonLedger
from loose_ends.schema import Account, AccountStatus, Decision, Estate, Watch

_CREDIT = re.compile(r"hard inquiry|new inquiry|credit inquiry|inquiry on your credit|credit application", re.IGNORECASE)
_NEW_ACCOUNT = re.compile(r"welcome to|your new (line|account|card)|account (is|has been) (activated|opened|active)|"
                          r"new line is active|activate your", re.IGNORECASE)


class WatchReport(BaseModel):
    checked: int = 0
    zombie_charges: int = 0
    new_accounts: int = 0
    credit_inquiries: int = 0


def watch(ledger: JsonLedger, estate_id: str, messages: list[Message], brain: Brain, today: date) -> WatchReport:
    estate = ledger.get_estate(estate_id)
    watched = set(ledger.watched_messages(estate_id))
    candidates = [m for m in messages if m.date > estate.date_of_death and m.id not in watched]
    report = WatchReport(checked=len(candidates))
    if not candidates:
        return report

    signals = {s.message_id: s for s in brain.classify_messages(candidates)}
    accounts = {a.domain.lower(): a for a in ledger.list_accounts(estate_id)}

    for message in candidates:
        signal = signals.get(message.id)
        text = f"{message.subject} {message.body}"
        account = accounts.get(message.sender_domain)
        if _CREDIT.search(text):
            _record(ledger, estate, "credit_inquiry", account or _watching(ledger, estate, message, signal), message,
                    summary=message.subject, draft=_credit_draft(estate, message))
            report.credit_inquiries += 1
        elif _NEW_ACCOUNT.search(text):
            target = _watching(ledger, estate, message, signal) if account is None else account
            _record(ledger, estate, "new_account", target, message, summary=message.subject,
                    draft=_new_account_draft(estate, target, message))
            report.new_accounts += 1
        elif account is not None and account.status == AccountStatus.DONE and signal and signal.amount:
            _record(ledger, estate, "zombie_charge", account, message,
                    summary=f"${signal.amount:.2f} on {message.date.isoformat()}, after the account was closed",
                    draft=_zombie_draft(estate, account, message, signal))
            report.zombie_charges += 1

    ledger.mark_watched(estate_id, [m.id for m in candidates])
    return report


def _watching(ledger: JsonLedger, estate: Estate, message: Message, signal: MessageSignal | None) -> Account:
    vendor = signal.vendor if signal else message.sender_name or message.sender_domain
    category = signal.category if signal and signal.is_account else "other"
    account = ledger.upsert_account(estate.id, Account(vendor=vendor, domain=message.sender_domain, category=category,
                                                       evidence=[message.id], confidence=signal.confidence if signal else 0.5,
                                                       status=AccountStatus.WATCHING))
    return account


_QUESTIONS = {
    "zombie_charge": "{vendor} charged {summary}. Send the dispute?",
    "new_account": "Someone may have opened a {vendor} account in {deceased}'s name after the death. Send the fraud report?",
    "credit_inquiry": "A credit inquiry appeared on {deceased}'s report after the death. Send the fraud alert to the bureau?",
}


def _record(ledger: JsonLedger, estate: Estate, signal: str, account: Account, message: Message,
            summary: str, draft: str) -> Watch:
    hit = ledger.add_watch(estate.id, Watch(signal=signal, account_id=account.id, evidence=[message.id],
                                            summary=summary, draft=draft))
    ledger.add_decision(estate.id, Decision(
        account_id=account.id, resumes_action="send_dispute", options=["send", "ignore"], context=hit.id,
        question=_QUESTIONS[signal].format(vendor=account.vendor, deceased=estate.deceased, summary=summary)))
    return hit


def _zombie_draft(estate: Estate, account: Account, message: Message, signal: MessageSignal) -> str:
    return (f"To {account.vendor},\n\nThis account belonged to {estate.deceased}, who died on "
            f"{estate.date_of_death.strftime('%B %d, %Y')}. You confirmed the account was closed, yet a charge of "
            f"${signal.amount:.2f} was made on {message.date.strftime('%B %d, %Y')}. Please reverse it and confirm "
            f"in writing that no further charges will be made.\n\n{estate.executor_name}, executor\n{estate.executor_email}")


def _new_account_draft(estate: Estate, account: Account, message: Message) -> str:
    return (f"To {account.vendor} fraud department,\n\n{estate.deceased} died on {estate.date_of_death.strftime('%B %d, %Y')}. "
            f"A message dated {message.date.strftime('%B %d, %Y')} indicates a new account or service was opened in "
            f"their name after that date (\"{message.subject}\"). This was not authorized. Please close it, flag it as "
            f"fraudulent, and confirm in writing.\n\n{estate.executor_name}, executor\n{estate.executor_email}")


def _credit_draft(estate: Estate, message: Message) -> str:
    return (f"To the fraud department,\n\n{estate.deceased} died on {estate.date_of_death.strftime('%B %d, %Y')}. "
            f"A credit inquiry dated {message.date.strftime('%B %d, %Y')} appeared afterwards (\"{message.subject}\"). "
            f"Please place a deceased alert on the file, block the application, and confirm in writing.\n\n"
            f"{estate.executor_name}, executor\n{estate.executor_email}")
