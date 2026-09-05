"""Amazon Bedrock AgentCore Runtime entrypoint.

Payloads:
  {"action": "run_cycle", "estate_id": "...", "brain": "bedrock", "today": "2026-08-10"}
  {"action": "status", "estate_id": "..."}
  {"action": "answer", "estate_id": "...", "decision_id": "...", "choice": "transfer"}

EventBridge Scheduler calls run_cycle on a schedule; the dashboard calls the rest on demand.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from loose_ends.brain import Brain
from loose_ends.graph import run_cycle_graph
from loose_ends.home import current_estate, home_dir, ledger_for, load_inbox, mailer_for
from loose_ends.models import get_model
from loose_ends.money import money_recovered
from loose_ends.playbooks import load_playbooks

app = BedrockAgentCoreApp()


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action")
    try:
        match action:
            case "run_cycle":
                return _run_cycle(payload)
            case "status":
                return _status(payload)
            case "answer":
                return _answer(payload)
            case "pause":
                return _pause(payload)
            case _:
                return {"ok": False, "error": f"unknown action {action!r}"}
    except Exception as exc:  # the runtime must always answer with JSON
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _run_cycle(payload: dict[str, Any]) -> dict[str, Any]:
    home = home_dir()
    estate = current_estate(home, payload.get("estate_id"))
    brain_name = payload.get("brain", "bedrock")
    brain = Brain.offline() if brain_name == "offline" else Brain.from_model(get_model(brain_name))
    today = date.fromisoformat(payload["today"]) if payload.get("today") else date.today()
    report, result = run_cycle_graph(ledger_for(home), estate.id, load_inbox(home, today), brain, mailer_for(home),
                                     load_playbooks(), today)
    return {"ok": True, "estate_id": estate.id, "report": report.model_dump(),
            "nodes": [node.node_id for node in result.execution_order]}


def _status(payload: dict[str, Any]) -> dict[str, Any]:
    home = home_dir()
    ledger = ledger_for(home)
    estate = current_estate(home, payload.get("estate_id"))
    accounts = ledger.list_accounts(estate.id)
    counts: dict[str, int] = {}
    for account in accounts:
        counts[account.status.value] = counts.get(account.status.value, 0) + 1
    return {
        "ok": True,
        "estate_id": estate.id,
        "estate": estate.model_dump(mode="json"),
        "counts": counts,
        "open_decisions": [d.model_dump(mode="json") for d in ledger.open_decisions(estate.id)],
        "accounts": [a.model_dump(mode="json") for a in sorted(accounts, key=lambda a: (a.priority, a.vendor))],
        "cycles": [c.model_dump(mode="json") for c in ledger.list_cycles(estate.id)],
        "watches": [w.model_dump(mode="json") for w in ledger.list_watches(estate.id)],
        "actions": [a.model_dump(mode="json") for a in ledger.list_actions(estate.id)],
        "money": money_recovered(ledger, estate.id, load_playbooks()).model_dump(),
    }


def _pause(payload: dict[str, Any]) -> dict[str, Any]:
    home = home_dir()
    ledger = ledger_for(home)
    estate = current_estate(home, payload.get("estate_id"))
    until = date.fromisoformat(payload["until"]) if payload.get("until") else None
    updated = ledger.update_estate(estate.model_copy(update={"paused_until": until}))
    return {"ok": True, "estate_id": estate.id, "paused_until": updated.paused_until.isoformat() if until else None}


def _answer(payload: dict[str, Any]) -> dict[str, Any]:
    home = home_dir()
    estate = current_estate(home, payload.get("estate_id"))
    decision = ledger_for(home).answer_decision(estate.id, payload["decision_id"], payload["choice"])
    return {"ok": True, "estate_id": estate.id, "decision": decision.model_dump(mode="json")}


@app.entrypoint
def invoke(payload: dict[str, Any], context: Any = None) -> dict[str, Any]:
    return handle(payload)


if __name__ == "__main__":
    app.run()
