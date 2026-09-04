"""The vendor-action agent: a Strands agent with tools for the channels email cannot reach,
gated by a HumanInTheLoop intervention whose approval is deferred into the ledger.

A background cycle must never block on a human. So when the agent reaches for an
irreversible tool, the intervention writes a Decision and denies the call. The next cycle
runs the agent again; if the executor approved, the tool runs and is logged.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from strands import Agent, tool
from strands.hooks.events import BeforeToolCallEvent
from strands.interventions.actions import Deny, InterventionAction, Proceed
from strands.models import Model
from strands.vended_interventions.hitl import HumanInTheLoop

from loose_ends.ledger import JsonLedger
from loose_ends.playbooks import Playbook
from loose_ends.schema import Account, AccountStatus, Decision, Estate

ALLOWED_TOOLS = ["record_note"]
IRREVERSIBLE_LABELS = {"submit_form": "submitting the web form", "place_call": "placing a phone call"}


class ActionReport(BaseModel):
    executed: int = 0
    deferred: int = 0
    notes: int = 0


class DeferredApproval(HumanInTheLoop):
    """HumanInTheLoop whose 'ask' is the ledger: deny now, approve on a later cycle."""

    name = "loose-ends:deferred-approval"

    def __init__(self, ledger: JsonLedger, estate: Estate, account: Account, report: ActionReport) -> None:
        super().__init__(allowed_tools=ALLOWED_TOOLS)
        self._ledger, self._estate, self._account, self._report = ledger, estate, account, report

    async def before_tool_call(self, event: BeforeToolCallEvent, **kwargs: Any) -> InterventionAction:
        tool_name = event.tool_use["name"]
        if tool_name in self._allowed_tools:
            return Proceed()
        decisions = [d for d in self._ledger.answered_decisions(self._estate.id) + self._ledger.open_decisions(self._estate.id)
                     if d.account_id == self._account.id and d.resumes_action == "approve_tool" and d.context == tool_name]
        if any(d.answer == "approve" for d in decisions):
            return Proceed()
        if not any(d.answer is None for d in decisions):
            label = IRREVERSIBLE_LABELS.get(tool_name, tool_name)
            detail = event.tool_use["input"].get("url") or event.tool_use["input"].get("phone") or ""
            self._ledger.add_decision(self._estate.id, Decision(
                account_id=self._account.id, resumes_action="approve_tool", context=tool_name,
                options=["approve", "park"],
                question=f"Approve {label} for {self._account.vendor}? {detail}".strip()))
            self._ledger.set_status(self._estate.id, self._account.id, AccountStatus.AWAITING_DECISION)
        self._report.deferred += 1
        return Deny(reason=f"The executor has not approved {tool_name} yet. Stop and report that you are waiting.")


SYSTEM_PROMPT = """You act for the executor of a deceased person's estate on exactly one account,
following the playbook. Use submit_form for organizations that only accept a web form, with the
playbook's contact URL and the fields the form needs. Use place_call only if the playbook or notes
say email and forms are ignored. Use record_note for anything worth remembering. If a tool is
denied because the executor has not approved it, stop and say you are waiting. Never invent
account numbers or personal identifiers.
"""


def act_on_account(ledger: JsonLedger, model: Model, estate: Estate, account: Account,
                   playbook: Playbook, today: date) -> ActionReport:
    report = ActionReport()

    @tool
    def submit_form(url: str, fields: dict[str, str]) -> str:
        """Submit a vendor web form (memorialization, cancellation, deceased notification)."""
        ledger.log_action(estate.id, account.id, type="form", payload={"url": url, "fields": fields}, result="submitted")
        due = datetime.combine(today + timedelta(days=playbook.follow_up_days), datetime.min.time(), tzinfo=UTC)
        ledger.update_account(estate.id, ledger.get_account(estate.id, account.id).model_copy(
            update={"status": AccountStatus.AWAITING_REPLY, "next_action_at": due}))
        report.executed += 1
        return f"Submitted the form at {url}."

    @tool
    def place_call(phone: str, script: str) -> str:
        """Schedule a phone call to the organization; the voice agent places it."""
        ledger.log_action(estate.id, account.id, type="call", payload={"phone": phone, "script": script}, result="scheduled")
        ledger.set_status(estate.id, account.id, AccountStatus.IN_PROGRESS)
        report.executed += 1
        return f"Call to {phone} scheduled."

    @tool
    def record_note(note: str) -> str:
        """Remember something about this account for later cycles."""
        current = ledger.get_account(estate.id, account.id)
        ledger.update_account(estate.id, current.model_copy(update={"notes": f"{current.notes} {note}".strip()}))
        report.notes += 1
        return "Noted."

    agent = Agent(model=model, tools=[submit_form, place_call, record_note], system_prompt=SYSTEM_PROMPT,
                  interventions=[DeferredApproval(ledger, estate, account, report)], callback_handler=None)
    agent(_prompt(estate, account, playbook))
    return report


def _prompt(estate: Estate, account: Account, playbook: Playbook) -> str:
    return "\n".join([
        f"Deceased: {estate.deceased}, died {estate.date_of_death.isoformat()}. Executor: {estate.executor_name}.",
        f"Organization: {account.vendor} ({account.domain}), category {account.category}.",
        f"Playbook: action {playbook.action}, channel {playbook.channel}, contact {playbook.contact_hint}.",
        f"Playbook notes: {playbook.notes.strip()}",
        f"Account notes: {account.notes or 'none'}",
        "Take the next step for this account.",
    ])
