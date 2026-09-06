"""Follow-up: read vendor replies and chase silence.

Closed means done. A request for documents, a denial, or a wrong channel without a better
address becomes a decision. Silence gets one more notice, then escalates to a decision.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from email.utils import parseaddr
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel
from strands import Agent
from strands.models import Model

from loose_ends.correspondence import send_notice
from loose_ends.ledger import JsonLedger
from loose_ends.mail import IncomingMail, Mailer
from loose_ends.playbooks import Playbook
from loose_ends.schema import Account, AccountStatus, Decision, Estate

if TYPE_CHECKING:
    from loose_ends.brain import Brain


class ReplyOutcome(BaseModel):
    kind: Literal["closed", "needs_documents", "wrong_channel", "denied", "other"]
    summary: str
    contact_email: str | None = None


class FollowUpReport(BaseModel):
    replies: int = 0
    closed: int = 0
    escalated: int = 0
    chased: int = 0
    answers: int = 0


_NUMBERED = re.compile(r"^\s*(\d+)\s*[.):\-]?\s*(.*)$")


def answer_from_reply(ledger: JsonLedger, estate: Estate, reply: IncomingMail) -> bool:
    """A digest reply like "2 transfer" answers the second open decision. Returns True if it did."""
    if parseaddr(reply.sender)[1].lower() != estate.executor_email.lower():
        return False
    first_line = next((line for line in reply.body.splitlines() if line.strip()), "")
    match = _NUMBERED.match(first_line)
    if not match:
        return False
    number, text = int(match.group(1)), match.group(2).strip().lower()
    if estate.last_digest:
        listed = [ledger.get_decision(estate.id, i) for i in estate.last_digest]
    else:
        listed = sorted(ledger.open_decisions(estate.id), key=lambda d: d.created_at)
    if not 1 <= number <= len(listed) or not text:
        return False
    decision = listed[number - 1]
    if decision is None or decision.answer is not None:
        return False
    first_word = text.split()[0]
    choice = next((o for o in decision.options if text.startswith(o.lower()) or o.lower().startswith(first_word)), None)
    if choice is None:
        return False
    ledger.answer_decision(estate.id, decision.id, choice)
    ledger.log_action(estate.id, decision.account_id, type="answer",
                      payload={"decision_id": decision.id, "choice": choice, "via": "email", "reply_id": reply.id},
                      result=choice)
    return True


SYSTEM_PROMPT = """You read a reply from an organization to a death notification sent on behalf
of an executor, and classify it:
- closed: the account is closed, cancelled, memorialized, or the request is complete.
- needs_documents: they ask for documents or information before acting. Summarize what.
- wrong_channel: they say to use a different address, form, or phone number. Put any email
  address they give in contact_email.
- denied: they refuse or say they cannot help.
- other: anything else, including acknowledgements with no outcome.
Keep the summary under 25 words.
"""


def classify_reply(model: Model, reply: IncomingMail, account: Account) -> ReplyOutcome:
    agent = Agent(model=model, system_prompt=SYSTEM_PROMPT, callback_handler=None)
    prompt = (f"Organization: {account.vendor} ({account.category}).\n"
              f"From: {reply.sender}\nSubject: {reply.subject}\n\n{reply.body[:2000]}")
    return agent(prompt, structured_output_model=ReplyOutcome).structured_output


def follow_up(ledger: JsonLedger, mailer: Mailer, brain: Brain, estate_id: str,
              playbooks: dict[str, Playbook], today: date) -> FollowUpReport:
    estate = ledger.get_estate(estate_id)
    report = FollowUpReport()
    accounts = {a.id: a for a in ledger.list_accounts(estate_id)}

    for reply in mailer.read_replies():
        account = accounts.get(reply.token or "")
        if account is None:
            report.answers += answer_from_reply(ledger, estate, reply)
            continue
        report.replies += 1
        outcome = brain.classify_reply(reply, account)
        ledger.log_action(estate_id, account.id, type="reply",
                          payload={"from": reply.sender, "subject": reply.subject, "summary": outcome.summary},
                          result=f"reply:{outcome.kind}")
        _apply(ledger, estate, account, outcome, playbooks[account.playbook or "generic"], today, report)

    for account in ledger.list_accounts(estate_id, AccountStatus.AWAITING_REPLY):
        if account.next_action_at is None or account.next_action_at.date() > today:
            continue
        book = playbooks[account.playbook or "generic"]
        notices = [a for a in ledger.list_actions(estate_id, account.id) if a.type == "email"]
        if len(notices) < 2:
            notice = brain.draft(estate, account, book, "This is a second notice. The first received no reply.")
            send_notice(ledger, mailer, estate, account, book, notice, today)
            report.chased += 1
        else:
            _decide(ledger, estate, account,
                    f"{account.vendor} has not replied after two notices. Should I call them, or park this?",
                    ["call", "park"])
            report.escalated += 1
    return report


def _apply(ledger: JsonLedger, estate: Estate, account: Account, outcome: ReplyOutcome,
           book: Playbook, today: date, report: FollowUpReport) -> None:
    match outcome.kind:
        case "closed":
            ledger.set_status(estate.id, account.id, AccountStatus.DONE)
            report.closed += 1
        case "needs_documents":
            _decide(ledger, estate, account, f"{account.vendor} asks for: {outcome.summary}. Do you have it?",
                    ["provide", "park"])
            report.escalated += 1
        case "wrong_channel" if outcome.contact_email:
            ledger.update_account(estate.id, account.model_copy(update={
                "contact_email": outcome.contact_email, "status": AccountStatus.PLANNED}))
        case "wrong_channel":
            _decide(ledger, estate, account, f"{account.vendor} says email is the wrong channel: {outcome.summary}",
                    ["call", "park"])
            report.escalated += 1
        case "denied":
            _decide(ledger, estate, account, f"{account.vendor} declined: {outcome.summary}. Escalate or park?",
                    ["escalate", "park"])
            report.escalated += 1
        case _:
            due = datetime.combine(today + timedelta(days=book.follow_up_days), datetime.min.time(), tzinfo=UTC)
            ledger.update_account(estate.id, account.model_copy(update={"next_action_at": due}))


def _decide(ledger: JsonLedger, estate: Estate, account: Account, question: str, options: list[str]) -> Decision:
    decision = ledger.add_decision(estate.id, Decision(
        account_id=account.id, question=question, options=options, resumes_action="choose"))
    ledger.set_status(estate.id, account.id, AccountStatus.AWAITING_DECISION)
    return decision
