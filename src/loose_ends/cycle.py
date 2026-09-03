"""One background cycle: discover new mail, plan, dispatch, follow up, digest, record."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from loose_ends.brain import Brain
from loose_ends.digest import compose_digest, send_digest
from loose_ends.discovery import Message, aggregate_signals
from loose_ends.dispatch import dispatch
from loose_ends.followup import follow_up
from loose_ends.ledger import JsonLedger
from loose_ends.mail import Mailer
from loose_ends.playbooks import Playbook, plan_account
from loose_ends.schema import AccountStatus, Cycle


class CycleReport(BaseModel):
    discovered: int = 0
    planned: int = 0
    sent: int = 0
    decisions: int = 0
    queued: int = 0
    resumed: int = 0
    replies: int = 0
    closed: int = 0
    chased: int = 0
    escalated: int = 0
    digest_sent: bool = False

    @property
    def had_activity(self) -> bool:
        return any(v for k, v in self.model_dump().items() if k != "digest_sent")


def run_cycle(ledger: JsonLedger, estate_id: str, messages: list[Message], brain: Brain,
              mailer: Mailer, playbooks: dict[str, Playbook], today: date) -> CycleReport:
    report = CycleReport()

    seen = set(ledger.seen_messages(estate_id))
    new = [m for m in messages if m.id not in seen]
    if new:
        known = {a.domain for a in ledger.list_accounts(estate_id)}
        for account in aggregate_signals(brain.classify_messages(new)):
            ledger.upsert_account(estate_id, account)
            report.discovered += account.domain not in known
        ledger.mark_seen(estate_id, [m.id for m in new])

    for account in ledger.list_accounts(estate_id, AccountStatus.DISCOVERED):
        ledger.update_account(estate_id, plan_account(account, playbooks))
        report.planned += 1

    d = dispatch(ledger, mailer, brain, estate_id, playbooks, today)
    f = follow_up(ledger, mailer, brain, estate_id, playbooks, today)
    report = report.model_copy(update={**d.model_dump(), **f.model_dump()})

    if report.had_activity:
        send_digest(mailer, ledger.get_estate(estate_id), compose_digest(ledger, estate_id))
        report.digest_sent = True

    ledger.record_cycle(estate_id, Cycle(summary=report.model_dump()))
    return report
