"""Pause: the executor can stop everything for a while, except Ghost Watch."""

from datetime import date
from pathlib import Path

from loose_ends.brain import Brain
from loose_ends.cycle import run_cycle
from loose_ends.discovery import load_json_mailbox
from loose_ends.ledger import JsonLedger
from loose_ends.mail import OutboxMailer
from loose_ends.playbooks import load_playbooks
from loose_ends.schema import Estate

FIXTURE = Path(__file__).parent / "fixtures" / "inbox_small.json"


def test_paused_estate_sends_nothing_until_the_date_passes(tmp_path):
    ledger = JsonLedger(tmp_path / "ledger")
    estate = ledger.create_estate(Estate(deceased="Raymond Okafor", date_of_death=date(2026, 8, 3),
                                         executor_name="Priya Okafor", executor_email="priya@example.com",
                                         state="IL", paused_until=date(2026, 8, 15)))
    mailer = OutboxMailer(tmp_path / "mail")

    paused = run_cycle(ledger, estate.id, load_json_mailbox(FIXTURE), Brain.offline(), mailer, load_playbooks(),
                       today=date(2026, 8, 10))
    assert paused.discovered == 4 and paused.sent == 0 and paused.decisions == 0 and mailer.sent() == []

    resumed = run_cycle(ledger, estate.id, load_json_mailbox(FIXTURE), Brain.offline(), mailer, load_playbooks(),
                        today=date(2026, 8, 16))
    assert resumed.sent >= 2 and resumed.decisions == 1
