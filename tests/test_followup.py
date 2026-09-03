"""Follow-up reads vendor replies and chases silence. Closed means done; a request for
documents or a denial becomes a decision; no reply gets one more notice, then escalation."""

from datetime import date

import pytest

from loose_ends.correspondence import Notice
from loose_ends.dispatch import dispatch
from loose_ends.followup import ReplyOutcome, follow_up
from loose_ends.ledger import JsonLedger
from loose_ends.mail import IncomingMail, OutboxMailer
from loose_ends.models.fake import FakeModel
from loose_ends.playbooks import load_playbooks, plan_account
from loose_ends.schema import Account, AccountStatus, Estate

SENT_ON = date(2026, 8, 10)


@pytest.fixture
def world(tmp_path):
    ledger = JsonLedger(tmp_path / "ledger")
    estate = ledger.create_estate(Estate(
        deceased="Raymond Okafor", date_of_death=date(2026, 8, 3), executor_name="Priya Okafor",
        executor_email="priya@example.com", state="IL"))
    books = load_playbooks()
    ledger.upsert_account(estate.id, plan_account(
        Account(vendor="Netflix", domain="netflix.com", category="subscription"), books))
    mailer = OutboxMailer(tmp_path / "mail")
    notice_model = FakeModel(structured=Notice(subject="Notice of death", body="Please cancel."))
    dispatch(ledger, mailer, notice_model, estate.id, books, today=SENT_ON)
    account = ledger.list_accounts(estate.id)[0]
    return ledger, estate, account, mailer, books


def reply(account, body):
    return IncomingMail(id=f"r-{account.id}", sender="support@netflix.com", date=date(2026, 8, 12),
                        subject=f"Re: Notice of death [LE-{account.id}]", body=body)


def test_closed_reply_marks_the_account_done(world):
    ledger, estate, account, mailer, books = world
    mailer.drop_reply(reply(account, "We have closed the account and refunded $7.75."))
    model = FakeModel(structured=ReplyOutcome(kind="closed", summary="closed, refund 7.75"))

    report = follow_up(ledger, mailer, model, estate.id, books, today=date(2026, 8, 12))

    assert report.closed == 1
    assert ledger.get_account(estate.id, account.id).status == AccountStatus.DONE
    assert ledger.list_actions(estate.id, account_id=account.id)[-1].result == "reply:closed"


def test_request_for_documents_becomes_a_decision(world):
    ledger, estate, account, mailer, books = world
    mailer.drop_reply(reply(account, "Please send Letters Testamentary."))
    model = FakeModel(structured=ReplyOutcome(kind="needs_documents", summary="Letters Testamentary"))

    follow_up(ledger, mailer, model, estate.id, books, today=date(2026, 8, 12))

    decision = ledger.open_decisions(estate.id)[0]
    assert decision.account_id == account.id
    assert "Letters Testamentary" in decision.question
    assert ledger.get_account(estate.id, account.id).status == AccountStatus.AWAITING_DECISION


def test_silence_gets_a_second_notice_then_escalates(world):
    ledger, estate, account, mailer, books = world
    model = FakeModel(structured=Notice(subject="Second notice", body="Following up."))

    first = follow_up(ledger, mailer, model, estate.id, books, today=date(2026, 8, 18))
    assert first.chased == 1
    assert len(mailer.sent()) == 2
    assert ledger.get_account(estate.id, account.id).status == AccountStatus.AWAITING_REPLY

    second = follow_up(ledger, mailer, model, estate.id, books, today=date(2026, 8, 26))
    assert second.escalated == 1
    assert ledger.get_account(estate.id, account.id).status == AccountStatus.AWAITING_DECISION
    assert "two notices" in ledger.open_decisions(estate.id)[0].question


def test_nothing_happens_before_the_follow_up_date(world):
    ledger, estate, account, mailer, books = world

    report = follow_up(ledger, mailer, FakeModel(), estate.id, books, today=date(2026, 8, 12))

    assert report.chased == 0 and report.escalated == 0 and len(mailer.sent()) == 1
