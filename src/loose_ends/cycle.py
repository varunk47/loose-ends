"""One background cycle as five stages: discover, plan, dispatch, follow up, concierge.

`run_cycle` composes them directly. `loose_ends.graph` wraps the same stages as Strands Graph
nodes, so there is exactly one implementation of each stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel

from loose_ends.brain import Brain
from loose_ends.digest import compose_digest, send_digest
from loose_ends.discovery import Message, aggregate_signals
from loose_ends.dispatch import DispatchReport, dispatch
from loose_ends.followup import FollowUpReport, follow_up
from loose_ends.ghostwatch import WatchReport, watch
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
    watched: int = 0
    ghost_hits: int = 0
    digest_sent: bool = False

    @property
    def had_activity(self) -> bool:
        return any(v for k, v in self.model_dump().items() if k not in ("digest_sent", "watched"))


@dataclass(frozen=True)
class CycleContext:
    ledger: JsonLedger
    estate_id: str
    messages: list[Message]
    brain: Brain
    mailer: Mailer
    playbooks: dict[str, Playbook]
    today: date


def stage_discover(ctx: CycleContext) -> int:
    seen = set(ctx.ledger.seen_messages(ctx.estate_id))
    new = [m for m in ctx.messages if m.id not in seen]
    if not new:
        return 0
    known = {a.domain for a in ctx.ledger.list_accounts(ctx.estate_id)}
    discovered = 0
    for account in aggregate_signals(ctx.brain.classify_messages(new)):
        ctx.ledger.upsert_account(ctx.estate_id, account)
        discovered += account.domain not in known
    ctx.ledger.mark_seen(ctx.estate_id, [m.id for m in new])
    return discovered


def stage_plan(ctx: CycleContext) -> int:
    planned = 0
    for account in ctx.ledger.list_accounts(ctx.estate_id, AccountStatus.DISCOVERED):
        ctx.ledger.update_account(ctx.estate_id, plan_account(account, ctx.playbooks))
        planned += 1
    return planned


def paused(ctx: CycleContext) -> bool:
    until = ctx.ledger.get_estate(ctx.estate_id).paused_until
    return until is not None and ctx.today < until


def stage_dispatch(ctx: CycleContext) -> DispatchReport:
    if paused(ctx):
        return DispatchReport()
    return dispatch(ctx.ledger, ctx.mailer, ctx.brain, ctx.estate_id, ctx.playbooks, ctx.today)


def stage_follow_up(ctx: CycleContext) -> FollowUpReport:
    if paused(ctx):
        return FollowUpReport()
    return follow_up(ctx.ledger, ctx.mailer, ctx.brain, ctx.estate_id, ctx.playbooks, ctx.today)


def stage_watch(ctx: CycleContext) -> WatchReport:
    return watch(ctx.ledger, ctx.estate_id, ctx.messages, ctx.brain, ctx.today)


def stage_concierge(ctx: CycleContext, report: CycleReport) -> CycleReport:
    if report.had_activity and not paused(ctx):
        send_digest(ctx.mailer, ctx.ledger.get_estate(ctx.estate_id),
                    compose_digest(ctx.ledger, ctx.estate_id, ctx.playbooks))
        report = report.model_copy(update={"digest_sent": True})
    ctx.ledger.record_cycle(ctx.estate_id, Cycle(summary=report.model_dump()))
    return report


def assemble_report(discovered: int, planned: int, d: DispatchReport, f: FollowUpReport,
                    w: WatchReport | None = None) -> CycleReport:
    w = w or WatchReport()
    return CycleReport(discovered=discovered, planned=planned, **d.model_dump(), **f.model_dump(),
                       watched=w.checked, ghost_hits=w.zombie_charges + w.new_accounts + w.credit_inquiries)


def run_cycle(ledger: JsonLedger, estate_id: str, messages: list[Message], brain: Brain,
              mailer: Mailer, playbooks: dict[str, Playbook], today: date) -> CycleReport:
    ctx = CycleContext(ledger, estate_id, messages, brain, mailer, playbooks, today)
    discovered = stage_discover(ctx)
    planned = stage_plan(ctx)
    report = assemble_report(discovered, planned, stage_dispatch(ctx), stage_follow_up(ctx), stage_watch(ctx))
    return stage_concierge(ctx, report)
