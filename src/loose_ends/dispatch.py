"""Dispatch: walk planned accounts in priority order and act. Email playbooks are sent,
form playbooks are queued for the browser agent, and anything that is a decision or needs
paper or a phone call becomes a question for the executor. Answered decisions resume."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel
from strands.models import Model

from loose_ends.correspondence import draft_notice, send_notice
from loose_ends.ledger import JsonLedger
from loose_ends.mail import Mailer
from loose_ends.playbooks import Playbook
from loose_ends.schema import Account, AccountStatus, Decision, Estate


class DispatchReport(BaseModel):
    sent: int = 0
    decisions: int = 0
    queued: int = 0
    resumed: int = 0


_DECISIONS: dict[str, tuple[str, list[str], str]] = {
    "utility": ("{vendor} is in {deceased}'s name. Transfer it to someone in the household or close it?",
                ["transfer", "close"], "transfer_or_close"),
    "google": ("{deceased}'s Google account may hold photos and mail. Keep paying for now, request an export, or close it?",
               ["keep paying", "export", "close"], "choose"),
    "government": ("{vendor} needs the executor in person or on the phone. I will prepare the packet. Ready to file?",
                   ["prepare packet", "park"], "choose"),
}
_DEFAULT_DECISION = ("{vendor} needs a decision before I proceed. {notes}", ["proceed", "park"], "choose")


def dispatch(ledger: JsonLedger, mailer: Mailer, model: Model, estate_id: str,
             playbooks: dict[str, Playbook], today: date) -> DispatchReport:
    estate = ledger.get_estate(estate_id)
    report = DispatchReport()

    for decision in ledger.answered_decisions(estate_id):
        account = ledger.get_account(estate_id, decision.account_id)
        if account.status != AccountStatus.AWAITING_DECISION:
            continue
        if decision.answer == "park":
            ledger.set_status(estate_id, account.id, AccountStatus.PARKED)
            continue
        book = playbooks[account.playbook or "generic"]
        instruction = f"The executor decided: {decision.answer}. Write the notice accordingly."
        send_notice(ledger, mailer, estate, account, book, draft_notice(model, estate, account, book, instruction), today)
        report.resumed += 1

    planned = sorted(ledger.list_accounts(estate_id, AccountStatus.PLANNED), key=lambda a: a.priority)
    for account in planned:
        book = playbooks[account.playbook or "generic"]
        if book.action == "decision" or book.channel in ("mail", "phone"):
            _raise_decision(ledger, estate, account, book)
            report.decisions += 1
        elif book.channel == "email":
            send_notice(ledger, mailer, estate, account, book, draft_notice(model, estate, account, book), today)
            report.sent += 1
        else:
            ledger.log_action(estate_id, account.id, type="form", payload={"url": book.contact_hint}, result="queued")
            ledger.set_status(estate_id, account.id, AccountStatus.IN_PROGRESS)
            report.queued += 1
    return report


def _raise_decision(ledger: JsonLedger, estate: Estate, account: Account, book: Playbook) -> Decision:
    template, options, resumes = _DECISIONS.get(book.id, _DEFAULT_DECISION)
    question = template.format(vendor=account.vendor, deceased=estate.deceased, notes=book.notes.strip())
    decision = ledger.add_decision(estate.id, Decision(
        account_id=account.id, question=question, options=options, resumes_action=resumes,
        context=f"{account.category}; evidence {', '.join(account.evidence) or 'none'}"))
    ledger.set_status(estate.id, account.id, AccountStatus.AWAITING_DECISION)
    return decision
