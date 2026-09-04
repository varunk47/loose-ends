"""The cycle as a Strands Graph.

Each stage is a custom MultiAgentBase node wrapping the same stage function `run_cycle`
uses. The graph is deterministic and linear; edges exist so observability, hooks and
interrupts have one node per stage to attach to.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from strands.multiagent import GraphBuilder
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, Status
from strands.multiagent.graph import Graph, GraphResult

from loose_ends.brain import Brain
from loose_ends.cycle import (
    CycleContext,
    CycleReport,
    assemble_report,
    stage_concierge,
    stage_discover,
    stage_dispatch,
    stage_follow_up,
    stage_plan,
    stage_watch,
)
from loose_ends.discovery import Message
from loose_ends.ledger import JsonLedger
from loose_ends.mail import Mailer
from loose_ends.playbooks import Playbook

STAGES = ["discover", "plan", "dispatch", "follow_up", "watch", "concierge"]


class StageNode(MultiAgentBase):
    """Runs one deterministic stage against the shared invocation state."""

    def __init__(self, stage: str, fn: Callable[[dict[str, Any]], Any]) -> None:
        super().__init__()
        self.id = stage
        self.name = stage
        self._fn = fn

    async def invoke_async(self, task: Any, invocation_state: dict[str, Any] | None = None,
                           **kwargs: Any) -> MultiAgentResult:
        state = invocation_state if invocation_state is not None else {}
        state.setdefault("reports", {})[self.id] = self._fn(state)
        return MultiAgentResult(status=Status.COMPLETED, execution_count=1)


def _concierge(state: dict[str, Any]) -> CycleReport:
    reports = state["reports"]
    report = assemble_report(reports["discover"], reports["plan"], reports["dispatch"], reports["follow_up"],
                             reports["watch"])
    return stage_concierge(state["ctx"], report)


_STAGE_FNS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "discover": lambda s: stage_discover(s["ctx"]),
    "plan": lambda s: stage_plan(s["ctx"]),
    "dispatch": lambda s: stage_dispatch(s["ctx"]),
    "follow_up": lambda s: stage_follow_up(s["ctx"]),
    "watch": lambda s: stage_watch(s["ctx"]),
    "concierge": _concierge,
}


def build_graph() -> Graph:
    builder = GraphBuilder()
    for stage in STAGES:
        builder.add_node(StageNode(stage, _STAGE_FNS[stage]), stage)
    for upstream, downstream in zip(STAGES, STAGES[1:], strict=False):
        builder.add_edge(upstream, downstream)
    builder.set_entry_point(STAGES[0])
    builder.set_max_node_executions(len(STAGES))
    return builder.build()


def run_cycle_graph(ledger: JsonLedger, estate_id: str, messages: list[Message], brain: Brain,
                    mailer: Mailer, playbooks: dict[str, Playbook], today: date) -> tuple[CycleReport, GraphResult]:
    ctx = CycleContext(ledger, estate_id, messages, brain, mailer, playbooks, today)
    state: dict[str, Any] = {"ctx": ctx, "reports": {}}
    result = build_graph()("run one Loose Ends cycle", invocation_state=state)
    return state["reports"]["concierge"], result
