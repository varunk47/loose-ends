"""Correspondence: draft a vendor-specific notice with the model, send it with the
certificate attached, and record the action in the ledger."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from pydantic import BaseModel
from strands import Agent
from strands.models import Model

from loose_ends.ledger import JsonLedger
from loose_ends.mail import Mailer, tracking_token
from loose_ends.playbooks import Playbook
from loose_ends.schema import Account, AccountStatus, Estate


class Notice(BaseModel):
    subject: str
    body: str


SYSTEM_PROMPT = """You write short, plain, humane notices to organizations on behalf of the
executor of a person who has died. Rules:
- Identify yourself as an assistant writing on behalf of the named executor. Never write as the
  deceased.
- Ask for exactly what the playbook says: notify, cancel, memorialize, or request the procedure.
- Never ask to move money, close a financial account, or change beneficiaries.
- Mention that the death certificate is attached when the playbook requires it.
- No exclamation marks. Under 180 words. Sign with the executor's name and email.
"""


def draft_notice(model: Model, estate: Estate, account: Account, playbook: Playbook,
                 instruction: str | None = None) -> Notice:
    agent = Agent(model=model, system_prompt=SYSTEM_PROMPT, callback_handler=None)
    result = agent(_prompt(estate, account, playbook, instruction), structured_output_model=Notice)
    return result.structured_output


def recipient(account: Account) -> str:
    return account.contact_email or f"support@{account.domain}"


def send_notice(ledger: JsonLedger, mailer: Mailer, estate: Estate, account: Account,
                playbook: Playbook, notice: Notice, today: date) -> Account:
    attachments = [estate.certificate_key] if estate.certificate_key and "certificate" in playbook.required_packet else []
    mail = mailer.send(
        to=recipient(account),
        subject=f"{notice.subject} {tracking_token(account.id)}",
        body=notice.body,
        attachments=attachments,
    )
    ledger.log_action(estate.id, account.id, type="email",
                      payload={"to": mail.to, "subject": mail.subject}, result="sent",
                      artifacts=[f"mail:{mail.id}"])
    due = datetime.combine(today + timedelta(days=playbook.follow_up_days), datetime.min.time(), tzinfo=UTC)
    return ledger.update_account(estate.id, account.model_copy(update={
        "status": AccountStatus.AWAITING_REPLY,
        "next_action_at": due,
        "artifacts": [*account.artifacts, f"mail:{mail.id}"],
    }))


def _prompt(estate: Estate, account: Account, playbook: Playbook, instruction: str | None) -> str:
    lines = [
        f"Deceased: {estate.deceased}, died {estate.date_of_death.isoformat()}.",
        f"Executor: {estate.executor_name} ({estate.executor_relationship}), {estate.executor_email}.",
        f"Organization: {account.vendor} ({account.domain}), category {account.category}.",
        f"Playbook action: {playbook.action}. Documents attached: {', '.join(playbook.required_packet) or 'none'}.",
        f"Playbook notes: {playbook.notes.strip()}",
    ]
    if account.notes:
        lines.append(f"Account notes: {account.notes}")
    if instruction:
        lines.append(f"Instruction: {instruction}")
    lines.append("Write the notice.")
    return "\n".join(lines)
