"""One cycle: discover, plan, dispatch, follow up, digest. The second cycle with nothing new
does nothing loud. The offline brain runs the same loop with no model at all."""

from dataclasses import replace
from datetime import date
from pathlib import Path

from loose_ends.brain import Brain
from loose_ends.correspondence import Notice
from loose_ends.cycle import run_cycle
from loose_ends.discovery import MessageSignal, load_json_mailbox
from loose_ends.ledger import JsonLedger
from loose_ends.mail import OutboxMailer
from loose_ends.models.fake import FakeModel
from loose_ends.playbooks import load_playbooks
from loose_ends.schema import AccountStatus, Estate

FIXTURE = Path(__file__).parent / "fixtures" / "inbox_small.json"

SIGNALS = {
    "m1": ("Netflix", "netflix.com", "subscription", "billing", True),
    "m2": ("Netflix", "netflix.com", "subscription", "billing", True),
    "m3": ("ComEd", "comed.com", "utility", "statement", True),
    "m4": ("Ada", "gmail.com", "personal", "personal", False),
    "m5": ("Tribune", "chicagotribune.com", "marketing", "newsletter", False),
    "m6": ("Chase", "chase.com", "bank", "statement", True),
}


def stub_classifier(calls):
    def classify(messages):
        calls.append([m.id for m in messages])
        return [MessageSignal(message_id=m.id, vendor=SIGNALS[m.id][0], domain=SIGNALS[m.id][1],
                              category=SIGNALS[m.id][2], signal=SIGNALS[m.id][3],
                              is_account=SIGNALS[m.id][4], confidence=0.9) for m in messages]
    return classify


def make_world(tmp_path):
    ledger = JsonLedger(tmp_path / "ledger")
    estate = ledger.create_estate(Estate(deceased="Raymond Okafor", date_of_death=date(2026, 8, 3),
                                         executor_name="Priya Okafor", executor_email="priya@example.com",
                                         state="IL", certificate_key="certs/raymond.pdf"))
    calls = []
    brain = replace(Brain.from_model(FakeModel(structured=Notice(subject="Notice of death", body="Please act."))),
                    classify_messages=stub_classifier(calls))
    return ledger, estate, OutboxMailer(tmp_path / "mail"), brain, calls


def test_first_cycle_discovers_plans_sends_and_digests(tmp_path):
    ledger, estate, mailer, brain, _ = make_world(tmp_path)

    report = run_cycle(ledger, estate.id, load_json_mailbox(FIXTURE), brain, mailer, load_playbooks(),
                       today=date(2026, 8, 10))

    statuses = {a.vendor: a.status for a in ledger.list_accounts(estate.id)}
    assert statuses == {"Netflix": AccountStatus.AWAITING_REPLY, "ComEd": AccountStatus.AWAITING_DECISION,
                        "Chase": AccountStatus.AWAITING_REPLY}
    assert report.discovered == 3 and report.sent == 2 and report.decisions == 1
    digest = mailer.sent()[-1]
    assert digest.to == "priya@example.com" and "ComEd" in digest.body
    assert ledger.list_cycles(estate.id)[0].summary["sent"] == 2


def test_second_cycle_with_no_new_mail_is_quiet(tmp_path):
    ledger, estate, mailer, brain, calls = make_world(tmp_path)
    messages = load_json_mailbox(FIXTURE)
    run_cycle(ledger, estate.id, messages, brain, mailer, load_playbooks(), today=date(2026, 8, 10))
    sent_before = len(mailer.sent())

    report = run_cycle(ledger, estate.id, messages, brain, mailer, load_playbooks(), today=date(2026, 8, 11))

    assert len(calls) == 1, "classifier must not re-read messages it has already seen"
    assert report.discovered == 0 and report.sent == 0 and report.decisions == 0
    assert len(mailer.sent()) == sent_before, "no digest when nothing changed"


def test_offline_brain_runs_the_full_demo_inbox_without_a_model(tmp_path):
    ledger = JsonLedger(tmp_path / "ledger")
    estate = ledger.create_estate(Estate(deceased="Raymond Okafor", date_of_death=date(2026, 8, 3),
                                         executor_name="Priya Okafor", executor_email="priya@example.com",
                                         state="IL", certificate_key="certs/raymond.pdf"))
    mailer = OutboxMailer(tmp_path / "mail")
    inbox = Path(__file__).parents[1] / "data" / "synthetic" / "raymond_okafor.json"

    report = run_cycle(ledger, estate.id, load_json_mailbox(inbox), Brain.offline(), mailer, load_playbooks(),
                       today=date(2026, 8, 10))

    accounts = ledger.list_accounts(estate.id)
    assert report.discovered >= 25
    assert {a.category for a in accounts} >= {"subscription", "utility", "bank", "medical", "google"}
    assert "gmail.com" not in {a.domain for a in accounts}
    assert report.sent >= 15 and report.decisions >= 3
    assert mailer.sent()[-1].to == "priya@example.com"
