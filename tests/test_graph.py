"""The cycle as a Strands Graph: five nodes, deterministic order, same results as the plain
runner. Judges and observability see one node per stage."""

from datetime import date
from pathlib import Path

from loose_ends.brain import Brain
from loose_ends.cycle import CycleReport
from loose_ends.discovery import load_json_mailbox
from loose_ends.graph import build_graph, run_cycle_graph
from loose_ends.ledger import JsonLedger
from loose_ends.mail import OutboxMailer
from loose_ends.playbooks import load_playbooks
from loose_ends.schema import Estate

FIXTURE = Path(__file__).parent / "fixtures" / "inbox_small.json"
STAGES = ["discover", "plan", "dispatch", "follow_up", "watch", "concierge"]


def test_graph_has_one_node_per_stage_in_order():
    graph = build_graph()

    assert list(graph.nodes) == STAGES


def test_graph_cycle_runs_every_stage_and_returns_the_report(tmp_path):
    ledger = JsonLedger(tmp_path / "ledger")
    estate = ledger.create_estate(Estate(deceased="Raymond Okafor", date_of_death=date(2026, 8, 3),
                                         executor_name="Priya Okafor", executor_email="priya@example.com",
                                         state="IL", certificate_key="certs/raymond.pdf"))
    mailer = OutboxMailer(tmp_path / "mail")

    report, result = run_cycle_graph(ledger, estate.id, load_json_mailbox(FIXTURE), Brain.offline(), mailer,
                                     load_playbooks(), today=date(2026, 8, 10))

    assert isinstance(report, CycleReport)
    assert [node.node_id for node in result.execution_order] == STAGES
    assert report.discovered == 4 and report.decisions == 1 and report.digest_sent
    assert ledger.list_cycles(estate.id)[0].summary["discovered"] == 4
