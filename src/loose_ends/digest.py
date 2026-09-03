"""The digest: one email, at most three decisions, the counts, nothing else."""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from loose_ends.ledger import JsonLedger
from loose_ends.mail import Mailer, OutgoingMail
from loose_ends.schema import AccountStatus, Decision, Estate

MAX_DECISIONS = 3


class Digest(BaseModel):
    subject: str
    body: str
    decisions: list[Decision]
    counts: dict[str, int]


def compose_digest(ledger: JsonLedger, estate_id: str) -> Digest:
    estate = ledger.get_estate(estate_id)
    accounts = ledger.list_accounts(estate_id)
    counts = {status.value: 0 for status in AccountStatus}
    counts.update(Counter(a.status.value for a in accounts))
    open_decisions = sorted(ledger.open_decisions(estate_id), key=lambda d: d.created_at)
    top = open_decisions[:MAX_DECISIONS]
    more = len(open_decisions) - len(top)

    lines = [f"Hi {estate.executor_name.split()[0]},", ""]
    if top:
        lines.append("Things only you can decide:")
        for i, decision in enumerate(top, 1):
            lines.append(f"{i}. {decision.question}")
            lines.append(f"   Options: {' / '.join(decision.options)}")
        if more:
            lines.append(f"({more} more waiting; they will come in the next digests.)")
    else:
        lines.append("Nothing needs you today.")
    lines += ["", _progress_line(counts), "", "Reply with the number and your choice, or answer in the dashboard.",
              "", "Loose Ends"]
    subject = (f"Loose Ends: {len(top)} decision{'s' if len(top) != 1 else ''} for {estate.deceased}'s estate"
               if top else f"Loose Ends: update on {estate.deceased}'s estate")
    return Digest(subject=subject, body="\n".join(lines), decisions=top, counts=counts)


def send_digest(mailer: Mailer, estate: Estate, digest: Digest) -> OutgoingMail:
    return mailer.send(to=estate.executor_email, subject=digest.subject, body=digest.body)


def _progress_line(counts: dict[str, int]) -> str:
    done = counts["done"]
    waiting = counts["awaiting_reply"] + counts["follow_up"]
    working = counts["planned"] + counts["in_progress"] + counts["sent"] + counts["discovered"]
    needs_you = counts["awaiting_decision"]
    return f"Progress: {done} done, {working} in progress, {waiting} waiting on replies, {needs_you} need you."
