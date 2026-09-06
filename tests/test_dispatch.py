"""Dispatch walks planned accounts in priority order: sends what can be sent, raises a
decision for what only the executor can decide, and resumes answered decisions."""

from datetime import date

import pytest

from loose_ends.brain import Brain
from loose_ends.correspondence import Notice
from loose_ends.dispatch import dispatch
from loose_ends.ledger import JsonLedger
from loose_ends.mail import OutboxMailer
from loose_ends.models.fake import FakeModel
from loose_ends.playbooks import load_playbooks, plan_account
from loose_ends.schema import Account, AccountStatus, Estate

TODAY = date(2026, 8, 10)


@pytest.fixture
def world(tmp_path):
    ledger = JsonLedger(tmp_path / "ledger")
    estate = ledger.create_estate(Estate(
        deceased="Raymond Okafor", date_of_death=date(2026, 8, 3), executor_name="Priya Okafor",
        executor_email="priya@example.com", state="IL", certificate_key="certs/raymond.pdf"))
    books = load_playbooks()
    for account in [
        Account(vendor="Netflix", domain="netflix.com", category="subscription"),
        Account(vendor="ComEd", domain="comed.com", category="utility"),
        Account(vendor="Facebook", domain="facebook.com", category="social_facebook"),
    ]:
        ledger.upsert_account(estate.id, plan_account(account, books))
    model = FakeModel(structured=lambda prompt: Notice(
        subject="Notice of death: Raymond Okafor",
        body="transfer" if "transfer" in prompt else "Please cancel."))
    return ledger, estate, OutboxMailer(tmp_path / "mail"), model, books


def test_dispatch_sends_email_playbooks_and_raises_decisions_for_the_rest(world):
    ledger, estate, mailer, model, books = world

    report = dispatch(ledger, mailer, Brain.from_model(model), estate.id, books, today=TODAY)

    statuses = {a.vendor: a.status for a in ledger.list_accounts(estate.id)}
    assert statuses["Netflix"] == AccountStatus.AWAITING_REPLY
    assert statuses["ComEd"] == AccountStatus.AWAITING_DECISION
    assert statuses["Facebook"] == AccountStatus.IN_PROGRESS
    assert report.sent == 1 and report.decisions == 1
    decision = ledger.open_decisions(estate.id)[0]
    assert "ComEd" in decision.question and decision.options == ["transfer", "close"]


def test_dispatch_is_idempotent_across_cycles(world):
    ledger, estate, mailer, model, books = world
    dispatch(ledger, mailer, Brain.from_model(model), estate.id, books, today=TODAY)

    report = dispatch(ledger, mailer, Brain.from_model(model), estate.id, books, today=TODAY)

    assert report.sent == 0 and report.decisions == 0
    assert len(mailer.sent()) == 1
    assert len(ledger.open_decisions(estate.id)) == 1


def test_a_second_decision_on_the_same_account_does_not_replay_the_first_answer(world):
    ledger, estate, mailer, model, books = world
    brain = Brain.from_model(model)
    dispatch(ledger, mailer, brain, estate.id, books, today=TODAY)
    first = ledger.open_decisions(estate.id)[0]
    ledger.answer_decision(estate.id, first.id, "transfer")
    dispatch(ledger, mailer, brain, estate.id, books, today=TODAY)
    comed = next(a for a in ledger.list_accounts(estate.id) if a.vendor == "ComEd")
    sent_after_first = len(mailer.sent())
    # later, follow-up escalates the same account with a new question
    from loose_ends.schema import Decision
    second = ledger.add_decision(estate.id, Decision(account_id=comed.id, question="ComEd has not replied. Call or park?",
                                                     options=["call", "park"], resumes_action="choose"))
    ledger.set_status(estate.id, comed.id, AccountStatus.AWAITING_DECISION)
    ledger.answer_decision(estate.id, second.id, "park")

    report = dispatch(ledger, mailer, brain, estate.id, books, today=TODAY)

    assert len(mailer.sent()) == sent_after_first, "the old 'transfer' answer must not be replayed"
    assert ledger.get_account(estate.id, comed.id).status == AccountStatus.PARKED
    assert report.parked == 1


def test_answered_decision_is_resumed_as_a_notice_carrying_the_answer(world):
    ledger, estate, mailer, model, books = world
    dispatch(ledger, mailer, Brain.from_model(model), estate.id, books, today=TODAY)
    decision = ledger.open_decisions(estate.id)[0]
    ledger.answer_decision(estate.id, decision.id, "transfer")

    report = dispatch(ledger, mailer, Brain.from_model(model), estate.id, books, today=TODAY)

    assert report.resumed == 1
    comed = next(a for a in ledger.list_accounts(estate.id) if a.vendor == "ComEd")
    assert comed.status == AccountStatus.AWAITING_REPLY
    assert "transfer" in model.last_user_text
    assert mailer.sent()[-1].to == "support@comed.com"
